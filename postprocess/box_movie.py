#!/usr/bin/env python
"""Volume-rendered movie of the brightness temperature of an EOS26 box, after visio.

visio (Marco Strambi, 2016; the `visio/` folder) made Andrei's EOS movie
(andreimesinger.github.io/images/frame_box_loop.gif). This is a port of its renderer, not of
its GUI. Every pixel casts a ray from a perspective camera through the cube. Each cell on the
ray has the colour and alpha of a piecewise-linear RGBA scale of its value, and the colours
are composited front to back with opacity alpha / 255 * 128 * (path length in units of the
cube side), at most 1, on a black background (RenderUniverse::integrate in
render_universe.cpp). Cells are sampled nearest-neighbour, as in visio, every half cell.

The movie runs from z = 35 to 5 at a constant step in ln(1 + z) per frame (that of the 2016
GIF), with T_b interpolated linearly in z between neighbouring node redshifts. It starts with
the whole box, block-averaged, and zooms into a sub-cube at the native resolution: the
rendered cube shrinks from the box to the sub-cube while the camera follows it, and inside
the sub-cube the native cells fade in over the averaged ones.

    python postprocess/box_movie.py prepare        # Gadi: reduce the coevals (~40 min of reading)
    python postprocess/box_movie.py render         # plots/movie/outputs/<run>_box_movie.mp4
    python postprocess/box_movie.py stills --z 20 12 8

`prepare` writes plots/movie/data/<run>_box_movie_Tb.h5: for every node redshift the box
block-averaged to about 500 cells per side ("coarse") and the sub-cube at the native cells
("fine"), as float16 (~0.5 GB per node at HII_DIM = 1500).
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import h5py
import numpy as np
from numba import njit, prange

REPO = Path(__file__).resolve().parents[1]
MOVIE = REPO / "plots" / "movie"

# The colour scale of the 2016 GIF (read off its colour bar): T_b [mK], R, G, B, alpha (0-255).
# The alphas are not on the colour bar; they are set so that the look is similar.
TB_SCALE = [
    (-200, 255, 255, 200, 60),
    (-175, 255, 255, 0, 50),
    (-30, 255, 0, 0, 16),
    (0, 0, 0, 0, 0),
    (9, 150, 150, 170, 14),
    (18, 0, 255, 255, 30),
    (30, 255, 255, 255, 50),
]
OPACITY = 128.0  # visio's opacity per unit alpha and cube side


# ============================================================== prepare (where the coevals are)
def reduce_box(ds, factor: int, origin, m: int, slab: int = 30):
    """Block mean of a cubic dataset over factor^3 cells, and its sub-cube of m cells per side
    at `origin` (cells), reading slabs of whole planes along the first axis."""
    n = ds.shape[0]
    nc = n // factor
    unit = math.lcm(factor, ds.chunks[0]) if ds.chunks else factor  # whole chunks if compressed
    slab = max(unit, slab // unit * unit)
    coarse = np.empty((nc, nc, nc), np.float32)
    fine = np.empty((m, m, m), np.float32)
    o = [int(x) for x in origin]
    for a in range(0, n, slab):
        s = np.asarray(ds[a:a + slab], np.float32)
        k = s.shape[0]
        coarse[a // factor:(a + k) // factor] = s.reshape(
            k // factor, factor, nc, factor, nc, factor).mean(axis=(1, 3, 5))
        lo, hi = max(a, o[0]), min(a + k, o[0] + m)
        if lo < hi:
            fine[lo - o[0]:hi - o[0]] = s[lo - a:hi - a, o[1]:o[1] + m, o[2]:o[2] + m]
    return coarse, fine


def coarse_factor(n: int, cells: int) -> int:
    """The smallest divisor of n that gives at most `cells` cells per side."""
    return next(f for f in range(max(1, math.ceil(n / cells)), n + 1) if n % f == 0)


def prepare(files: dict, out: Path, box_len: float, n: int, cells: int, zoom: float, origin=None):
    """Write the coarse box and the fine sub-cube of brightness_temp for every node redshift.
    `files` maps z to the cached BrightnessTemp file (None if missing). Resumes a partial file."""
    factor = coarse_factor(n, cells)
    m = int(round(n / zoom))
    origin = np.array(origin if origin is not None else [(n - m) // 2] * 3, int)
    zs = np.array(sorted(files, reverse=True))
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "a") as f:
        if "redshift" not in f:
            f["redshift"] = zs
            f["done"] = np.zeros(len(zs), bool)
            f.create_dataset("coarse", (len(zs), *(n // factor,) * 3), np.float16, chunks=(1, *(n // factor,) * 3))
            f.create_dataset("fine", (len(zs), m, m, m), np.float16, chunks=(1, m, m, m))
            f.attrs.update(box_len=box_len, n_cells=n, factor=factor, fine_origin=origin, fine_cells=m)
        elif not (np.allclose(f["redshift"][:], zs) and f.attrs["factor"] == factor
                  and f["fine"].shape[1] == m and np.array_equal(f.attrs["fine_origin"], origin)):
            sys.exit(f"{out} was written with other settings; remove it first")
        for i, z in enumerate(zs):
            if f["done"][i]:
                continue
            if files[z] is None:
                print(f"z = {z:.3f}: no BrightnessTemp yet, skipped", flush=True)
                continue
            t0 = time.time()
            with h5py.File(files[z], "r") as g:
                coarse, fine = reduce_box(g["BrightnessTemp/OutputFields/brightness_temp"], factor, origin, m)
            f["coarse"][i] = coarse
            f["fine"][i] = fine
            f["done"][i] = True
            f.flush()
            print(f"z = {z:.3f}: {time.time() - t0:.0f} s, T_b {coarse.min():.1f} .. {coarse.max():.1f} mK", flush=True)


# ============================================================================ the renderer
def colour_table(scale, n: int = 2048):
    """Look-up table of RGBA (RGB in 0-1, alpha in 0-255) on n values between the first and last
    stops of the scale (visio's ColorScale::getColor)."""
    s = np.array(scale, float)
    v = np.linspace(s[0, 0], s[-1, 0], n)
    lut = np.stack([np.interp(v, s[:, 0], s[:, k]) for k in range(1, 5)], axis=1)
    lut[:, :3] /= 255.0
    return lut.astype(np.float32), float(s[0, 0]), float(s[-1, 0])


@njit(parallel=True, fastmath=True, cache=True)
def cast(img, c0, c1, f0, f1, u, cell_c, fine_lo, cell_f, w_fine, lo, hi, step, eye, fwd, right, up,
         tan_half, shift, lut, vmin, vmax, kappa):
    """Ray-cast the box [lo, hi] (cMpc) into img (H, W, 3). Values are (1-u) c0 + u c1 on the
    coarse grid (cells of cell_c from 0), replaced inside the fine grid (cells of cell_f from
    fine_lo) by (1-w_fine) coarse + w_fine fine. kappa = opacity per unit alpha and length."""
    H, W = img.shape[0], img.shape[1]
    nc, nf, nl = c0.shape[0], f0.shape[0], lut.shape[0]
    scale = (nl - 1) / (vmax - vmin)
    for j in prange(H):
        d = np.empty(3)
        p = np.empty(3)
        for i in range(W):
            a = ((2.0 * (i + 0.5) / W - 1.0) + shift) * tan_half
            b = (1.0 - 2.0 * (j + 0.5) / H) * tan_half
            for k in range(3):
                d[k] = fwd[k] + a * right[k] + b * up[k]
            norm = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
            t0, t1 = 0.0, 1e30
            for k in range(3):
                d[k] /= norm
                if abs(d[k]) < 1e-12:
                    if eye[k] < lo[k] or eye[k] > hi[k]:
                        t1 = -1.0
                    continue
                ta, tb = (lo[k] - eye[k]) / d[k], (hi[k] - eye[k]) / d[k]
                if ta > tb:
                    ta, tb = tb, ta
                t0, t1 = max(t0, ta), min(t1, tb)
            r = g = bl = 0.0
            trans = 1.0
            t = t0 + 0.5 * step
            while t < t1 and trans > 1e-3:
                for k in range(3):
                    p[k] = eye[k] + t * d[k]
                x = min(max(int(p[0] / cell_c), 0), nc - 1)
                y = min(max(int(p[1] / cell_c), 0), nc - 1)
                z = min(max(int(p[2] / cell_c), 0), nc - 1)
                val = c0[x, y, z] + u * (c1[x, y, z] - c0[x, y, z]) if w_fine < 1.0 else 0.0
                if w_fine > 0.0:
                    x = int(math.floor((p[0] - fine_lo[0]) / cell_f))
                    y = int(math.floor((p[1] - fine_lo[1]) / cell_f))
                    z = int(math.floor((p[2] - fine_lo[2]) / cell_f))
                    if 0 <= x < nf and 0 <= y < nf and 0 <= z < nf:
                        vf = f0[x, y, z] + u * (f1[x, y, z] - f0[x, y, z])
                        val = vf if w_fine >= 1.0 else val + w_fine * (vf - val)
                li = min(max(int((val - vmin) * scale + 0.5), 0), nl - 1)
                op = min(lut[li, 3] * kappa * step, 1.0)
                r += trans * op * lut[li, 0]
                g += trans * op * lut[li, 1]
                bl += trans * op * lut[li, 2]
                trans -= trans * op
                t += step
            img[j, i, 0] = r
            img[j, i, 1] = g
            img[j, i, 2] = bl


class Boxes:
    """The prepared boxes, with the two nodes around the current redshift in memory (float32)."""

    def __init__(self, path: Path):
        self.f = h5py.File(path, "r")
        self.z = self.f["redshift"][:]
        done = self.f["done"][:]
        self.z_done = self.z[done]
        a = self.f.attrs
        self.box_len = float(a["box_len"])
        self.cell_c = self.box_len / self.f["coarse"].shape[1]
        self.cell_f = self.box_len / int(a["n_cells"])
        self.fine_lo = np.asarray(a["fine_origin"], float) * self.cell_f
        self.fine_len = self.f["fine"].shape[1] * self.cell_f
        self.cache = {}

    def node(self, kind: str, i: int):
        """One prepared box as float32, keeping the last two read of each kind."""
        c = self.cache.setdefault(kind, {})
        if i not in c:
            if len(c) >= 2:
                c.pop(next(iter(c)))
            c[i] = np.asarray(self.f[kind][i], np.float32)
        return c[i]

    def bracket(self, z: float):
        """Indices of the nodes above and below z and the weight u of the lower one."""
        zs = self.z_done
        if not zs.min() - 1e-6 <= z <= zs.max() + 1e-6:
            sys.exit(f"z = {z:.2f} is outside the prepared nodes ({zs.min():.2f} .. {zs.max():.2f})")
        k = min(max(int(np.searchsorted(-zs, -z)), 1), len(zs) - 1)
        za, zb = zs[k - 1], zs[k]
        ia, ib = (int(np.nonzero(self.z == zz)[0][0]) for zz in (za, zb))
        return ia, ib, float((za - z) / (za - zb))


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Timeline:
    """Redshift, zoom state and camera of every frame."""

    def __init__(self, a, boxes: Boxes):
        self.a = a
        ln0, ln1 = math.log1p(a.z_start), math.log1p(a.z_end)
        n = int(round((ln0 - ln1) / a.dlnz)) + 1
        self.z = list(np.expm1(np.linspace(ln0, ln1, n))) + [a.z_end] * int(round(a.hold * a.fps))
        self.b = boxes
        L, l = boxes.box_len, boxes.fine_len
        self.L, self.l = L, l
        self.centre_box = np.full(3, L / 2)
        self.centre_sub = boxes.fine_lo + l / 2
        self.lz = [math.log1p(z) for z in a.zoom_z]

    def zoom(self, z):
        """Zoom progress: 0 before the zoom, 1 after it (smooth in ln(1 + z))."""
        return smoothstep((self.lz[0] - math.log1p(z)) / (self.lz[0] - self.lz[1]))

    def clip_box(self, p):
        """Side and centre of the rendered cube: from the box (p = 0) to the sub-cube (p = 1),
        the side shrinking geometrically; the cube always contains the sub-cube."""
        s = self.L * (self.l / self.L) ** p
        c = self.centre_box + (self.centre_sub - self.centre_box) * (self.L - s) / (self.L - self.l)
        return s, c

    def camera(self, i, s, c):
        a = self.a
        t = i / a.fps
        phi = math.radians(a.azimuth + 360.0 * t / a.turn)
        th = math.radians(a.elevation + a.tilt * math.sin(2 * math.pi * t / a.tilt_period))
        eye = c + a.distance * s * np.array([math.cos(th) * math.cos(phi), math.cos(th) * math.sin(phi), math.sin(th)])
        fwd = (c - eye) / np.linalg.norm(c - eye)
        right = np.cross(fwd, [0.0, 0.0, 1.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        return eye, fwd, right, up


class Renderer:
    def __init__(self, a, boxes: Boxes, label: str):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        self.a, self.b = a, boxes
        self.lut, self.vmin, self.vmax = colour_table(TB_SCALE)
        self.tl = Timeline(a, boxes)
        W = H = a.size
        self.img = np.zeros((H, W, 3), np.float32)
        self.tan_half = math.tan(math.radians(a.fov) / 2)
        self.shift = 0.12  # cube a little left of centre, to leave room for the colour bar

        self.fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="black")
        ax = self.fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        self.im = ax.imshow(self.img, interpolation="nearest")
        ax.set_xlim(-0.5, W - 0.5)
        ax.set_ylim(H - 0.5, -0.5)
        self.ax = ax
        fs = 13 * a.size / 800
        kw = dict(color="0.85", fontsize=fs, va="top", ha="left")
        self.fig.text(0.04, 0.96, label, **kw)
        self.t_len = self.fig.text(0.04, 0.927, "", **kw)
        self.t_z = self.fig.text(0.04, 0.894, "", **kw)
        self.edges = [ax.plot([], [], color="white", lw=0.8 * a.size / 800, alpha=0)[0] for _ in range(12)]
        # colour bar (colours only, as in visio)
        cax = self.fig.add_axes([0.905, 0.29, 0.022, 0.42])
        v = np.linspace(self.vmin, self.vmax, 512)
        rgb = self.lut[np.linspace(0, len(self.lut) - 1, 512).astype(int), :3]
        cax.imshow(rgb[::-1, None, :], aspect="auto", extent=(0, 1, self.vmin, self.vmax))
        cax.set_xticks([])
        cax.yaxis.tick_right()
        cax.set_yticks(np.arange(-180, 31, 30))
        cax.tick_params(colors="0.85", labelsize=0.8 * fs, length=3)
        for sp in cax.spines.values():
            sp.set_color("0.5")
        cax.set_title(r"$\delta T_b$ [mK]", color="0.85", fontsize=0.85 * fs, pad=6)

    def render(self, i):
        tl, b, a = self.tl, self.b, self.a
        z = tl.z[i]
        p = tl.zoom(z)
        s, c = tl.clip_box(p)
        eye, fwd, right, up = tl.camera(i, s, c)
        ia, ib, u = b.bracket(z)
        need_c, need_f = p < 1.0, p > 0.0
        c0 = b.node("coarse", ia) if need_c else np.zeros((1, 1, 1), np.float32)
        c1 = b.node("coarse", ib) if need_c else c0
        f0 = b.node("fine", ia) if need_f else np.zeros((1, 1, 1), np.float32)
        f1 = b.node("fine", ib) if need_f else f0
        step = 0.5 * s / b.f["coarse"].shape[1]
        cast(self.img, c0, c1, f0, f1, u, b.cell_c, b.fine_lo, b.cell_f, p, c - s / 2, c + s / 2, step,
             eye, fwd, right, up, self.tan_half, self.shift, self.lut, self.vmin, self.vmax, OPACITY / s / 255.0)
        self.im.set_data(np.clip(self.img, 0, 1))
        self.t_len.set_text(f"box {s:.0f} cMpc")
        self.t_z.set_text(f"z = {z:.2f}")
        self.outline(i, eye, fwd, right, up, p)
        self.fig.canvas.draw()
        return np.asarray(self.fig.canvas.buffer_rgba())

    def outline(self, i, eye, fwd, right, up, p):
        """Edges of the sub-cube: fade in over a second before the zoom, out while it ends."""
        a, tl = self.a, self.tl
        z_in = math.expm1(tl.lz[0] + a.fps * a.dlnz)  # one second before the zoom starts
        fade = smoothstep((math.log1p(z_in) - math.log1p(tl.z[i])) / (a.fps * a.dlnz)) * (1 - smoothstep((p - 0.6) / 0.4))
        alpha = 0.7 * fade if a.outline else 0.0
        lo, l = self.b.fine_lo, self.b.fine_len
        corners = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)]) * l + lo
        rel = corners - eye
        zc = rel @ fwd
        W = a.size
        px = (W / 2) * (1 + rel @ right / zc / self.tan_half - self.shift)
        py = (W / 2) * (1 - rel @ up / zc / self.tan_half)
        pairs = [(m, m ^ bit) for m in range(8) for bit in (1, 2, 4) if m < m ^ bit]
        for line, (m, n) in zip(self.edges, pairs):
            line.set_data([px[m], px[n]], [py[m], py[n]])
            line.set_alpha(alpha)


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            sys.exit("no ffmpeg: module load ffmpeg, or pip install imageio-ffmpeg")
    return exe


def make_movie(R: Renderer, out: Path, gif: bool):
    a = R.a
    n = len(R.tl.z)
    out.parent.mkdir(parents=True, exist_ok=True)
    exe = ffmpeg_exe()
    ff = subprocess.Popen(
        [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{a.size}x{a.size}",
         "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(0, n, a.every):
        ff.stdin.write(R.render(i).tobytes())
        if i % 100 == 0:
            print(f"frame {i}/{n}, z = {R.tl.z[i]:.2f}, {time.time() - t0:.0f} s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"wrote {out} ({n // a.every} frames, {n / a.every / a.fps:.1f} s) in {time.time() - t0:.0f} s")
    if gif:
        g = out.with_suffix(".gif")
        subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(out), "-vf",
                        "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                        "-loop", "0", str(g)], check=True)
        print(f"wrote {g}")


# ==================================================================================== CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["prepare", "render", "stills"])
    ap.add_argument("--test", action="store_true", help="the HII_DIM=200 test cache (prepare)")
    ap.add_argument("--data", type=Path, help="prepared boxes (default plots/movie/data/<run>_box_movie_Tb.h5)")
    ap.add_argument("--out", type=Path, help="movie (default plots/movie/outputs/<run>_box_movie.mp4)")
    ap.add_argument("--label", help="run label on the frames (default: the run name)")
    g = ap.add_argument_group("prepare")
    g.add_argument("--cells", type=int, default=500, help="cells per side of the averaged box (at most)")
    g.add_argument("--zoom", type=float, default=3.0, help="box side / sub-cube side")
    g.add_argument("--sub-origin", type=int, nargs=3, help="first cell of the sub-cube (default: centred)")
    g = ap.add_argument_group("render")
    g.add_argument("--z-start", type=float, default=35.0)
    g.add_argument("--z-end", type=float, default=5.0)
    g.add_argument("--dlnz", type=float, default=0.0025, help="step in ln(1+z) per frame (2016 GIF: 0.0025)")
    g.add_argument("--zoom-z", type=float, nargs=2, default=[13.0, 11.0], help="zoom from z to z")
    g.add_argument("--hold", type=float, default=1.0, help="seconds at z-end")
    g.add_argument("--fps", type=int, default=25)
    g.add_argument("--size", type=int, default=800, help="frame side in pixels")
    g.add_argument("--fov", type=float, default=45.8, help="field of view in degrees (visio: 0.8 rad)")
    g.add_argument("--distance", type=float, default=3.0, help="camera distance in cube sides")
    g.add_argument("--azimuth", type=float, default=35.0, help="starting azimuth in degrees")
    g.add_argument("--turn", type=float, default=20.0, help="seconds per turn around the cube")
    g.add_argument("--elevation", type=float, default=22.0, help="mean elevation in degrees")
    g.add_argument("--tilt", type=float, default=12.0, help="elevation swing in degrees")
    g.add_argument("--tilt-period", type=float, default=29.0, help="seconds")
    g.add_argument("--no-outline", dest="outline", action="store_false", help="no sub-cube edges")
    g.add_argument("--every", type=int, default=1, help="render every n-th frame (quick previews)")
    g.add_argument("--crf", type=int, default=18)
    g.add_argument("--gif", action="store_true", help="also write a GIF")
    g.add_argument("--z", type=float, nargs="+", default=[30, 20, 15, 12, 10, 8, 6], help="stills at these z")
    a = ap.parse_args(argv)

    if a.data is None or a.what == "prepare":
        sys.path.insert(1, str(REPO / "run_scripts"))
        import settings
        run_name = settings.RUN_NAME + ("_test" if a.test else "")
    else:
        run_name = a.data.stem.removesuffix("_box_movie_Tb")
    data = a.data or MOVIE / "data" / f"{run_name}_box_movie_Tb.h5"

    if a.what == "prepare":
        sys.path.insert(1, str(REPO / "postprocess"))
        from eos_boxes import Run
        run = Run(test=a.test)
        files = {z: run.path("BrightnessTemp", z) for z in run.redshifts}
        prepare(files, data, run.n * run.cell, run.n, a.cells, a.zoom, a.sub_origin)
        return

    R = Renderer(a, Boxes(data), a.label or run_name)
    if a.what == "stills":
        import matplotlib.pyplot as plt
        zs = np.array(R.tl.z)
        for z in a.z:
            i = int(np.argmin(abs(zs - z)))
            p = (a.out or MOVIE / "outputs" / f"{run_name}_box_movie.png").with_name(
                f"{run_name}_box_movie_z{zs[i]:05.2f}.png")
            p.parent.mkdir(parents=True, exist_ok=True)
            plt.imsave(p, R.render(i)[..., :3])
            print(f"wrote {p}")
        return
    make_movie(R, a.out or MOVIE / "outputs" / f"{run_name}_box_movie.mp4", a.gif)


if __name__ == "__main__":
    main()
