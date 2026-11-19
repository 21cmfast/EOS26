"""Fields of view of 21-cm interferometers on a transverse slice of the EOS26 box: a figure (as
Greig et al. 2022, Fig. 1) and a movie that zooms from the whole box down to single galaxies.

    python postprocess/plot_fov_zoom.py figure                       # the HII_DIM=200 test run
    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/plot_fov_zoom.py figure --production
    python postprocess/plot_fov_zoom.py figure --quantity 6          # six quantities in sectors
    python postprocess/plot_fov_zoom.py figure --quantity all        # the figure for every quantity
    python postprocess/plot_fov_zoom.py figure --show-mwa            # frame wide enough for the MWA circle
    python postprocess/plot_fov_zoom.py stills --halos auto          # the movie's key frames as PNG
    python postprocess/plot_fov_zoom.py movie --halos auto           # z = 35 -> end of EoR, zooming in
    python postprocess/plot_fov_zoom.py movie --quantity neutral_fraction --size 960x540
    python postprocess/plot_fov_zoom.py movie --geometry healpix --halos auto   # the sky as a globe
    python postprocess/plot_fov_zoom.py movie --fixed-z --save-slice slice.npz   # one slice (150 MHz) ...
    python postprocess/plot_fov_zoom.py movie --fixed-z --slice-file slice.npz   # ... rendered elsewhere
    qsub -v EOS26_TEMPLATE=EOS26_earlyEoR postprocess/plot_fov_zoom_job.sh   # the movie on Gadi

Input: one slice (constant redshift, so constant frequency) of the rectilinear lightcones of
postprocess/lightcone/ (`<lightcone dir>/rect/<quantity>.h5`, tuesday LightconeStore, shape
(HII_DIM, HII_DIM, n_slices)): the slice nearest --freq (default 150 MHz, z = 8.47). It is a plane of
the periodic box, interpolated between the two bracketing node redshifts. Reading one slice touches
HII_DIM/4 chunks of 1 MiB per quantity (~0.4 GB at HII_DIM = 1500). --quantity takes any lightcone
quantity, or several (sectors; one figure each with --each; 'all': every released quantity that exists);
brightness_temp_with_rsds is the finalised T_b with dv/dr and RSDs. Each quantity has its label, colour
map and scale (SPEC, as plot_lightcone_square.py; others: viridis, linear), its colour-bar label (log10
when log-scaled), and circle colours that show on its colour map (--circle-colours to set them).

Fields of view: the angular sizes at 150 MHz of Greig et al. (2022, Table 1), scaled as 1/nu to the
frequency of the slice and converted to comoving size with the run's cosmology. Circles show the FoV
as a diameter, as in Greig et al. At 150 MHz in the EOS26 cosmology: SKA-Low 3.0 deg = 0.49 cGpc,
LOFAR 3.7 deg = 0.60 cGpc, HERA 8.2 deg = 1.33 cGpc, MWA 24.7 deg = 4.0 cGpc (larger than the 2.25 cGpc
box: drawn only with --show-mwa or --start mwa).

Galaxies (--halos FILE or auto): the PerturbedHaloCatalog of postprocess/galaxies at the node nearest
the slice, within --halo-slab of the slice's box plane, drawn as open red rings sized by M_UV (as
Davies et al. 2025), M_UV = 51.63 - 2.5 log10(SFR / 1.15e-28) as in tuesday.

Movie (default): it opens on a turning 3D view of the box (--intro cube; the initial density, or the
shown quantity's coeval at the first node with --intro-quantity same), whose front face is the box plane
of the first lightcone slice. The cube's face then becomes that slice and the movie moves through the
rect lightcone, slice after slice (fractional slices interpolated; averaged over the slices a frame
passes when it passes several), from --z-start (35) to --z-end (where the mean x_HI falls below
--xhi-end, 0.1), so in time and along the line of sight, while zooming from the box to --end (100 cMpc)
on a spot of the last slice with neutral and ionised gas and the most star formation. --seconds DARK
DAWN EOR (3 6 36) set the time to the onset of the absorption (--z-slow, from the mean T_b), to the
first stop and to the end. The zoom halts on the field of view of each instrument at the redshifts of
--stops (HERA 12.5, LOFAR 10.5, SKA-Low 9), drawn at the frame's frequency, within the instrument's band
and from 1.5 s before its stop (--all-circles: whenever in band). Each caption stays --caption-seconds
(3.5 s) on screen, also after the zoom has moved on from its stop. A line under the title gives z,
frequency, cosmic time and the epoch (from the mean T_b and x_HI). Galaxies come from the catalogue of
the node nearest each frame, within one cell of the frame's slice plane (read once per node and kept).
With several quantities (--quantity 4, 6, 8 or a list) the frames show sectors, as in the figure; their
colour scales follow the redshift (--sector-scale), and without --end the zoom ends on the last field
of view and keeps it to the end. After the last 21-cm stop, the footprints of other surveys appear while
one of their lines is in band (--footprints; FOOTPRINTS: COSMOS-3D, SPHEREx, FYST, COMAP, CONCERTO, TIME,
TIFUUN). At the end (--outro turn), after the pause on the last frame, the image there shifts into the
finished simulation under the circles, galaxies and text (--outro-shift: a cross-fade or a front sweeping out
from the centre, 3 s): the matter density of the last node (z = 5) on the box plane of the last slice. It then
zooms out to the whole box while the overlays fade, and turns as the intro in reverse (HEALPix: the globe of
the lowest shell).
--geometry healpix: the same on the HEALPix maps: each frame shows the shell's sky as a globe
(orthographic projection), the full-sky map degraded to the frame's sampling while zoomed out, the
patch where the frame lies in it and is finer than the full-sky pixels. It opens on the turning globe
of the density at z_start and zooms into the patch, to an end point chosen as above (--end defaults to
120 cMpc there: the patch pixels are 0.86 arcmin, 2.2 cMpc at z = 7.2). Galaxies are drawn once the
shell region in the frame is narrower than half the box, at their periodic image nearest the shell.
--fixed-z gives the earlier movie on the one slice at --freq: an optional intro, then a log-zoom with
stops ([MWA,] the box, HERA, LOFAR, SKA-Low, [extra footprints,] an ionised bubble near the box centre of
size near --bubble-size, last, in a frame of --end; with an --end below ~4 bubble radii, the bubble and
then the brightest galaxy in it at --end; with several quantities and no --end, the last field of view
is the end). Where sectors meet, the movies show a black disc (--black-centre). The 21-cm signal uses
tuesday's eor_colormap (as its angular lightcone tutorial) with a colour bar. Frames are piped to ffmpeg
(H.264).

Output: plots/fov_<run>_z<z>_<quantities>[_mwa].{pdf,png}; plots/movie/outputs/fov_evolve_<run>_<quantities>.mp4
or plots/movie/outputs/fov_sky_<run>_<quantities>.mp4, with the stills next to it, and the galaxies read in
plots/movie/data/<movie>_galaxies/; with --fixed-z plots/movie/outputs/fov_zoom_<run>_z<z>_<quantities>.mp4
(or --out). plots/movie/ is not in git.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

NU21 = 1420.40575  # MHz

# name, FoV at 150 MHz [deg] (Greig et al. 2022, Table 1), colour (as their Fig. 1)
# (colours: MWA, HERA and SKA as their Fig. 1; LOFAR amber instead of purple, which protan and deutan
# readers cannot tell from the HERA blue; the four pass the dataviz CVD check on all pairs)
INSTRUMENTS = [
    ("MWA", 24.7, "#ff5a36"),
    ("HERA", 8.2, "#3d8bff"),
    ("LOFAR", 3.7, "#f5c400"),
    ("SKA-Low", 3.0, "#19c2a8"),
]
# observing bands [MHz] (approximate; to confirm): HERA 50-250, LOFAR HBA 110-240, SKA-Low 50-350, MWA 70-300.
# In the evolving movie a circle shows only while the frame's frequency is in its band.
BANDS = {"MWA": (70.0, 300.0), "HERA": (50.0, 250.0), "LOFAR": (110.0, 240.0), "SKA-Low": (50.0, 350.0)}

# on the blue and black of the 21-cm colour map the HERA blue and SKA teal vanish: there HERA is white and
# SKA-Low pink (this set also passes the CVD check on all pairs)
ON_EOR = {"MWA": "#ff5a36", "HERA": "#ffffff", "LOFAR": "#f5c400", "SKA-Low": "#ff7ad9"}
# on blue and green colour maps (Blues_r, viridis, cividis) the HERA blue and SKA teal vanish too: there
# HERA is red-orange, SKA-Low pink and MWA white (CVD check on all pairs: worst deutan ΔE 15.6)
ON_BLUE = {"MWA": "#ffffff", "HERA": "#ff5a36", "LOFAR": "#f5c400", "SKA-Low": "#ff7ad9"}


def _oklab(rgb):
    """sRGB (..., 3) in 0..1 -> OKLab (..., 3)."""
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lms = c @ np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                        [0.2119034982, 0.6806995451, 0.1073969566],
                        [0.0883024619, 0.2817188376, 0.6299787005]]).T
    return np.cbrt(lms) @ np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                                    [1.9779984951, -2.4285922050, 0.4505937099],
                                    [0.0259040371, 0.7827717662, -0.8086757660]]).T


def low_contrast(colour, rgb_u8):
    """Fraction of the pixels (N, 3 uint8) close in colour to `colour` (hex): the mean of the fractions
    closer than ΔE_OK = 0.15 and 0.25 (a thin dashed line needs more than the usual 0.15)."""
    from matplotlib import colors
    c = _oklab(np.array(colors.to_rgb(colour)))
    d = np.linalg.norm(_oklab(rgb_u8.reshape(-1, 3) / 255.0) - c, axis=1)
    return float(0.5 * (np.mean(d < 0.15) + np.mean(d < 0.25)))


def instruments(quantities, colourers=None, override=None):
    """(name, FoV at 150 MHz [deg], colour), with colours that show on the first quantity's colour map.

    21-cm signal: ON_EOR. One other quantity: the set (default, ON_EOR, ON_BLUE) whose worst circle of
    HERA, LOFAR and SKA-Low is close in colour (low_contrast) to the fewest of the shown pixels; the
    default colours are kept unless that fraction is 3 points or more below theirs. Several quantities
    (sectors): the default colours. override: {name: colour} (--circle-colours) on top."""
    base = {n: c for n, _, c in INSTRUMENTS}
    one = len(quantities) == 1
    if one and SPEC.get(quantities[0], ("", "", ""))[2] == "eor":
        base = dict(ON_EOR)
    elif one and colourers and getattr(colourers.get(quantities[0]), "sample", None) is not None:
        px = colourers[quantities[0]].sample
        sets = {"default": base, "ON_EOR": ON_EOR, "ON_BLUE": ON_BLUE}
        worst = {k: max(low_contrast(s[n], px) for n in ("HERA", "LOFAR", "SKA-Low")) for k, s in sets.items()}
        best = min(worst, key=worst.get)
        pick = "default" if worst["default"] - worst[best] < 0.03 else best
        if pick != "default":
            log.info(f"circle colours for {quantities[0]}: {pick} (pixels close to a circle colour: "
                     + ", ".join(f"{k} {v:.0%}" for k, v in worst.items()) + ")")
        base = dict(sets[pick])
    for n, c in (override or {}).items():
        base[n] = c
    return [(n, d, base[n]) for n, d, _ in INSTRUMENTS]


# optional extra footprints for the movie (--extras): name, kind, size, unit, note
#   kind "square_deg2": a survey area (deg^2) drawn as a square; "box_cmpc": a simulation box side (cMpc)
EXTRAS = [
    ("COSMOS-Web (JWST)", "square_deg2", 0.54, "survey"),
    ("THESAN-1 box", "box_cmpc", 95.5, "simulation"),
    ("JADES (JWST)", "square_deg2", 0.0486, "survey"),
]

# other surveys (--footprints): a JWST galaxy survey and the line-intensity mapping (LIM) experiments of the paper
# draft that observe at z >~ 5, drawn at their angular size at the frame's redshift, only while one of their
# lines is in band. Entries: shape, size [deg] (square: side; rect: (width, height); circle: diameter),
# members (name, line, z_min, z_max), and for squares the corner of the name (tl, br); members of the same
# size share one outline.
FOOTPRINTS = [
    # SPHEREx deep fields, ~100 deg^2 each at the ecliptic poles (SPHEREx mission paper, arXiv:2511.02985);
    # H-alpha to z = 6.6, [O III] 5007 to z = 9.0 at 5 um
    ("circle", 2 * np.sqrt(100.0 / np.pi), [("SPHEREx deep field", "[O III]", 0.0, 9.0)]),
    # FYST/EoR-Spec Deep Spectroscopic Survey: two 4 deg^2 fields, 210-420 GHz (CCAT-Prime Collaboration 2023;
    # arXiv:2404.05352);
    # COMAP: three fields of 3.5-4.2 deg^2, CO(2-1) at z = 6-8 in 26-34 GHz (Cleary et al. 2022)
    ("square", 2.0, [("FYST EoR-Spec", "[C II]", 3.5, 8.05), ("COMAP", "CO(2-1)", 5.8, 7.9)], "tl"),
    # CONCERTO: nominal 1.4 deg^2 survey, 130-310 GHz (CONCERTO Collaboration 2020)
    ("square", np.sqrt(1.4), [("CONCERTO", "[C II]", 5.1, 13.6)], "tl"),
    # TIME: one-beam-wide 78' x 0.5' line scan, 183-326 GHz (Crites et al. 2014, as in arXiv:1812.08135; the 2017
    # LIM status report, arXiv:1709.09066, gives 1 deg x 0.3')
    ("rect", (78.0 / 60, 0.5 / 60), [("TIME", "[C II]", 5.3, 8.5)]),
    # TIFUUN on ASTE: 195-319 GHz, [C II] at z = 4.9-8.7 (Endo et al. 2026); survey ~1 deg^2 (provisional, LIM25)
    ("square", 1.0, [("TIFUUN", "[C II]", 4.9, 8.7)], "tl"),
    # COSMOS-3D (JWST NIRCam grism): 0.33 deg^2, [O III] emitters at z = 6.75-9.05 (Meyer et al. 2026)
    ("square", np.sqrt(0.33), [("COSMOS-3D", "[O III]", 6.75, 9.05)], "br"),
]
FP_COLOUR = "#f0f0f0"


def footprint_members(entry, z, dz=0.0):
    """Members of a FOOTPRINTS entry whose line range contains z (widened by dz)."""
    return [m for m in entry[2] if m[2] - dz <= z <= m[3] + dz]


def footprint_size(entry):
    """(width, height) [deg] of a FOOTPRINTS entry."""
    shape, size = entry[0], entry[1]
    return tuple(size) if shape == "rect" else (size, size)

# the quantities shared with plot_lightcone_square.py: label, colour map, scale
# (lin: percentiles; log: positive values; log1p: log10(1 + x); unit: 0..1; eor: -150..30 mK)
SPEC = {
    "density": ("Density", "magma", "log1p"),
    "sfrd_acg": ("Star formation", "afmhot", "log"),
    "sfrd_mcg": ("Star formation (MCGs)", "afmhot", "log"),
    "xray_emissivity": ("X-ray emissivity", "inferno", "log"),
    "n_ion": ("Ionising emissivity", "viridis", "log"),
    "kinetic_temp_neutral": ("Gas temperature", "inferno", "log"),
    "spin_temperature": ("Spin temperature", "plasma", "log"),
    "J_21_LW": ("Lyman–Werner", "Blues_r", "log"),
    "ionisation_rate_G12": ("Ionisation rate", "cividis", "log"),
    "cumulative_recombinations": ("Recombinations", "Reds_r", "log"),
    "neutral_fraction": ("Neutral fraction", "gray", "unit"),
    "brightness_temp": ("21-cm signal, real space", "EoR", "eor"),
    "brightness_temp_with_rsds": ("21-cm signal", "EoR", "eor"),
    "brightness_temp_dvdr_with_rsds": ("21-cm signal", "EoR", "eor"),
    "los_velocity": ("Line-of-sight velocity", "RdBu_r", "sym"),
    "ics": ("Initial conditions", "magma", "lin"),
    # the other quantities of plot_lightcone_square.py, with its colour maps and scales
    "velocity_z": ("Velocity", "RdBu_r", "lin"),
    "fesc_weighted_sfrd": ("Escaping star formation", "magma", "log"),
    "kinetic_temperature": ("Gas temperature", "inferno", "log"),
    "xray_ionised_fraction": ("X-ray ionisation", "cividis", "log"),
    "brightness_temp_dvdr": ("21-cm signal, velocity gradient", "EoR", "eor"),
    "brightness_temp_no_dvdr": ("21-cm signal, real space", "EoR", "eor"),
    "tau_21": ("21-cm optical depth", "YlGnBu", "log"),
    "mean_free_path": ("Mean free path", "viridis", "log"),
}
# colour-bar labels (units only where certain; the others show the SPEC name)
CBAR_LABEL = {
    "neutral_fraction": r"$x_{\rm HI}$",
    "brightness_temp": r"$\delta T_{\rm b}$ [mK]",
    "brightness_temp_dvdr_with_rsds": r"$\delta T_{\rm b}$ [mK]",
    "brightness_temp_with_rsds": r"$\delta T_{\rm b}$ [mK]",
    "brightness_temp_dvdr": r"$\delta T_{\rm b}$ [mK]",
    "brightness_temp_no_dvdr": r"$\delta T_{\rm b}$ [mK]",
    "density": r"$\log_{10}(1+\delta)$",
    "spin_temperature": r"$T_{\rm S}$ [K]",
    "kinetic_temp_neutral": r"$T_{\rm K}$ [K]",
    "kinetic_temperature": r"$T_{\rm K}$ [K]",
    "J_21_LW": r"$J_{21,\rm LW}$",  # J_LW in units of 1e-21 erg s^-1 cm^-2 Hz^-1 sr^-1
    "ionisation_rate_G12": r"$\Gamma_{12}$",  # in units of 1e-12 s^-1
}
# --quantity all (figure): the released lightcones (eos_lightcones.DEFAULT_QUANTITIES) and the 21-cm signal
# with dv/dr and RSDs, those that exist
ALL_QUANTITIES = ["brightness_temp_with_rsds", "density", "brightness_temp", "spin_temperature",
                  "neutral_fraction", "kinetic_temp_neutral", "J_21_LW", "sfrd_acg", "cumulative_recombinations",
                  "los_velocity", "ionisation_rate_G12", "sfrd_mcg", "n_ion", "xray_emissivity"]


def cbar_label(q, colourer=None):
    """Colour-bar label of q; log-scaled quantities say log10."""
    lab = CBAR_LABEL.get(q, SPEC.get(q, (q,))[0])
    if colourer is not None and colourer.scale == "log":
        lab = r"$\log_{10}$ " + lab if lab.startswith("$") else lab + r" ($\log_{10}$)"
    return lab
FALLBACK = {"brightness_temp_with_rsds": "brightness_temp"}  # before the finalise job
STORE = {"brightness_temp_with_rsds": "brightness_temp_dvdr_with_rsds"}  # store file names
PRESETS = {
    "4": ["density", "neutral_fraction", "brightness_temp", "sfrd_acg"],
    "6": ["density", "sfrd_acg", "J_21_LW", "neutral_fraction", "brightness_temp", "spin_temperature"],
    "8": ["density", "sfrd_acg", "kinetic_temp_neutral", "J_21_LW", "neutral_fraction",
          "brightness_temp", "spin_temperature", "cumulative_recombinations"],
}

log = logging.getLogger("fov_zoom")


# ====================================================================== command line
def parse(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("what", choices=("figure", "movie", "stills"),
                   help="figure: the paper figure; movie: the zoom movie; stills: a few movie frames as PNG")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--test", dest="production", action="store_false", help="the HII_DIM=200 test run (default)")
    src.add_argument("--production", dest="production", action="store_true", help="the production run")
    p.set_defaults(production=False)
    p.add_argument("--lightcone", default=None, help="rect lightcone directory (default: the run's)")
    p.add_argument("--slice-file", default=None,
                   help="npz with the 2D fields (from --save-slice, or synthetic test arrays) instead of the lightcones")
    p.add_argument("--save-slice", default=None,
                   help="also write the slice (fields, z, cell, halos) to this npz, e.g. on Gadi, to render elsewhere")
    p.add_argument("--freq", type=float, default=150.0, help="frequency of the slice [MHz] (default 150)")
    p.add_argument("--quantity", "--quantities", dest="quantities", nargs="+", default=None,
                   help="lightcone quantity, or several (sectors, clockwise from straight up), or a preset 4, 6, 8 "
                        "(default: neutral_fraction for the figure, brightness_temp_with_rsds for the movie; "
                        "brightness_temp_with_rsds is T_b with dv/dr and RSDs, brightness_temp the real-space T_b); "
                        "figure: 'all' makes the figure once for each released quantity that exists")
    p.add_argument("--each", action="store_true",
                   help="figure with several quantities: one figure per quantity instead of sectors")
    p.add_argument("--circle-colours", nargs="+", default=None, metavar="NAME=COLOUR",
                   help="circle colours, e.g. HERA=white LOFAR=#f5c400 (default: chosen to show on the colour map)")
    p.add_argument("--vmin", type=float, default=None, help="lower end of the colour scale (one quantity)")
    p.add_argument("--vmax", type=float, default=None, help="upper end of the colour scale (one quantity)")
    p.add_argument("--halos", default=None,
                   help="PerturbedHaloCatalog.h5 for the galaxies (postprocess/galaxies job), or 'auto': the run's "
                        "file at the node redshift nearest the slice")
    p.add_argument("--halo-slab", type=float, default=1.5, help="thickness of the halo slab [cMpc] (default 1.5)")
    p.add_argument("--centre", type=float, nargs=2, default=None,
                   help="centre of the circles [cMpc] (default: the chosen bubble for the movie, the box centre for the figure)")
    p.add_argument("--bubble-size", type=float, default=15.0, help="wanted bubble diameter [cMpc] (default 15)")
    p.add_argument("--bubble-search", type=float, default=150.0,
                   help="look for the bubble within this distance of the box centre [cMpc] (default 150)")
    # figure
    p.add_argument("--show-mwa", action="store_true", help="figure: widen the frame to show the MWA circle")
    p.add_argument("--periodic", action="store_true",
                   help="figure with --show-mwa: show the periodic copies of the box, dimmed, around it")
    p.add_argument("--deg-axis", action="store_true", help="figure: angle axes (degrees from the centre) on top and right")
    p.add_argument("--no-cbar", action="store_true", help="figure: no colour bar")
    p.add_argument("--figure-galaxies", type=int, default=0,
                   help="figure: draw the N brightest galaxies of the slice as rings sized by M_UV (needs --halos)")
    p.add_argument("--fig-width", type=float, default=7.0, help="figure width [in] (default 7)")
    # movie
    p.add_argument("--size", default="1920x1080", help="movie frame WxH (default 1920x1080)")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--intro", choices=("cube", "none"), default="cube",
                   help="movie: open on a rotating 3D view of the coeval box at the nearest node redshift, whose "
                        "front face is the slice, then zoom into the slice (default cube; needs the cached coeval)")
    p.add_argument("--intro-seconds", type=float, default=5.0, help="length of the cube intro (default 5 s)")
    p.add_argument("--outro", choices=("turn", "none"), default="turn",
                   help="evolving movie: after the end, zoom out to the whole box (globe) and turn the finished "
                        "simulation, the matter density at the last node (z = 5), as the intro in reverse "
                        "(default turn; needs that density coeval, or the HEALPix density at the lowest shell)")
    p.add_argument("--outro-shift", choices=("fade", "sweep"), default="fade",
                   help="the ending: how the last frame turns into the finished density, with the circles, galaxies "
                        "and text kept: a cross-fade (default) or a soft front sweeping out from the centre")
    p.add_argument("--outro-shift-seconds", type=float, default=3.0, help="length of that shift (default 3 s)")
    p.add_argument("--outro-seconds", type=float, default=5.0,
                   help="length of the turning box at the end (default 5 s; plus 2.5 s of zoom-out)")
    p.add_argument("--mwa", action="store_true", help="movie: draw the MWA circle too (wider than the box)")
    p.add_argument("--fixed-z", action="store_true",
                   help="movie: stay on the slice at --freq (no evolution); default: move through the lightcone")
    p.add_argument("--z-start", type=float, default=35.0, help="evolving movie: first redshift (default 35)")
    p.add_argument("--z-end", type=float, default=None,
                   help="evolving movie: last redshift (default: where the mean x_HI falls below --xhi-end)")
    p.add_argument("--xhi-end", type=float, default=0.1, help="mean neutral fraction at the end (default 0.1)")
    p.add_argument("--z-slow", type=float, default=None,
                   help="evolving movie: the end of the fast start (default: the onset of the absorption, where the "
                        "mean T_b first reaches 15%% of its minimum)")
    p.add_argument("--seconds", type=float, nargs=3, default=[3.0, 6.0, 36.0], metavar=("DARK", "DAWN", "EOR"),
                   help="evolving movie: seconds from --z-start to --z-slow, from there to the first stop, and from "
                        "the first stop to --z-end (default 3 6 36)")
    p.add_argument("--all-circles", action="store_true",
                   help="evolving movie: show the circles whenever in band (default: from 1.5 s before their stop)")
    p.add_argument("--geometry", choices=("rect", "healpix"), default="rect",
                   help="evolving movie: the rectilinear lightcone (default) or the HEALPix maps (the sky as a globe, "
                        "full sky then the patch)")
    p.add_argument("--stops", nargs="*", default=["HERA=12.5", "LOFAR=10.5", "SKA-Low=9", "surveys=7.8"],
                   help="evolving movie: NAME=z, the redshifts where the zoom halts on each field of view "
                        "(default HERA=12.5 LOFAR=10.5 SKA-Low=9 surveys=7.8); circles show only in their bands; "
                        "'surveys' frames the largest footprint of the other surveys in band (--footprints)")
    p.add_argument("--intro-quantity", default="ics",
                   help="evolving movie: the cube intro shows 'ics' (the initial density, default) or the shown "
                        "quantity's coeval at the first node ('same')")
    p.add_argument("--galaxies-zmax", type=float, default=16.0,
                   help="evolving movie: galaxies only below this redshift (default 16; one catalogue read per node)")
    p.add_argument("--target-search", type=float, default=300.0,
                   help="evolving movie: look for the end point within this distance of the box centre [cMpc]")
    p.add_argument("--start", choices=("box", "mwa"), default="box",
                   help="first stop: the whole box (default) or zoomed out to the MWA circle")
    p.add_argument("--extras", nargs="*", default=None,
                   help="extra footprints as stops between SKA-Low and the bubble (names from EXTRAS; no value: all)")
    p.add_argument("--end", type=float, default=None,
                   help="frame height at the end [cMpc] (default 100; 120 with --geometry healpix; with several "
                        "quantities: no default, the zoom ends on the last field of view)")
    p.add_argument("--sector-scale", choices=("follow", "fixed"), default="follow",
                   help="evolving movie with several quantities: the colour scales of the log-scaled quantities "
                        "(star formation, emissivities, temperatures, J_LW, ...) follow the redshift (default; "
                        "from slices at 6 redshifts) or stay fixed; density, x_HI and T_b always stay fixed")
    p.add_argument("--footprints", choices=("auto", "on", "none"), default="auto",
                   help="other surveys (FOOTPRINTS: COSMOS-3D, SPHEREx, FYST, COMAP, CONCERTO, TIME, TIFUUN) while "
                        "one of their lines is at the frame's (figure: the slice's) redshift; auto: on in the "
                        "evolving movie (after the last 21-cm stop), off in the figure and --fixed-z")
    p.add_argument("--black-centre", type=float, default=0.07,
                   help="movie with several quantities: a black disc where the sectors meet, of this radius "
                        "(fraction of the frame height; default 0.07; 0: none)")
    p.add_argument("--interp", choices=("nearest", "linear", "cubic"), default="linear",
                   help="sampling of the cells when zoomed in (default linear)")
    p.add_argument("--cell-grid", action="store_true",
                   help="movie: draw the cell edges once a cell is more than 25 pixels wide")
    p.add_argument("--hold", type=float, default=1.8, help="seconds at each stop (default 1.8)")
    p.add_argument("--caption-seconds", type=float, default=3.5,
                   help="seconds each caption stays on screen, also while the zoom moves on (default 3.5)")
    p.add_argument("--speed", type=float, default=0.8, help="zoom speed, factors of 2 per second (default 0.8)")
    p.add_argument("--spin", type=float, default=0.0, help="movie: rotate the sectors by this many degrees in total")
    p.add_argument("--crf", type=int, default=18, help="H.264 quality (default 18; lower = better)")
    p.add_argument("--no-text", action="store_true", help="no captions, title or scale bar")
    p.add_argument("--watermark", default=None, help="a line of text at the bottom of every frame (e.g. PRELIMINARY)")
    p.add_argument("--galaxies", choices=("rings", "virial", "none"), default="rings",
                   help="galaxies of --halos: open red rings sized by UV magnitude (default; as Davies et al. "
                        "2025), discs at the halo's comoving virial size, or none")
    p.add_argument("--max-galaxies", type=int, default=500,
                   help="movie: about this many rings in a 1920x1080 frame; the brightest are kept, so fainter "
                        "galaxies appear while zooming in (default 500)")
    p.add_argument("--out", default=None, help="output file (default: see above)")
    p.add_argument("--log-file", default=None)
    a = p.parse_args(argv)
    if a.quantities is None:
        a.quantities = ["neutral_fraction"] if a.what == "figure" else ["brightness_temp_with_rsds"]
    if len(a.quantities) == 1 and a.quantities[0] in PRESETS:
        a.quantities = PRESETS[a.quantities[0]]
    a.W, a.H = (int(v) for v in a.size.lower().split("x"))
    a.end_given = a.end is not None
    if a.end is None:
        a.end = 120.0 if (a.geometry == "healpix" and not a.fixed_z) else 100.0
    a.circle_colours = dict(v.split("=", 1) for v in a.circle_colours) if a.circle_colours else None
    if a.start == "mwa":
        a.mwa = True
    return a


# ====================================================================== data
class Slice:
    """One transverse slice: 2D fields indexed [y, x] (cell centres at (i + 0.5) * cell), periodic."""

    def __init__(self, fields, cell, z, tag, halos=None, cosmo=None):
        self.fields = fields
        self.cell = float(cell)
        self.N = next(iter(fields.values())).shape[0]
        self.L = self.N * self.cell
        self.z = float(z)
        self.tag = tag
        self.halos = halos  # (x, y, M, SFR) in cMpc, Msun, Msun/yr (SFR None if unknown), or None
        self.watermark = None
        self.cube = {}  # quantity -> faces of the coeval box: x0, x1 (j, k), y0, y1 (i, k), back (i, j); k back->front
        if cosmo is None:
            from astropy.cosmology import FlatLambdaCDM
            cosmo = FlatLambdaCDM(H0=67.66, Om0=0.30964144154550644, Ob0=0.04897468161869667, Tcmb0=2.7255)
        self.cosmo = cosmo
        self.Dc = float(cosmo.comoving_distance(self.z).to_value("Mpc"))
        self.nu = NU21 / (1 + self.z)

    def fov_cmpc(self, deg150):
        """Comoving size [cMpc] of a FoV given at 150 MHz [deg], at the frequency of the slice."""
        return np.radians(deg150 * 150.0 / self.nu) * self.Dc

    def fov_at(self, deg150, z):
        """Comoving size [cMpc] at redshift z of a FoV given at 150 MHz [deg]."""
        nu = NU21 / (1 + z)
        return np.radians(deg150 * 150.0 / nu) * float(self.cosmo.comoving_distance(z).to_value("Mpc"))

    def cmpc_per_deg(self):
        return np.radians(1.0) * self.Dc


def load_slice_file(path, quantities, slab, drop_missing=False):
    d = np.load(path)
    for i, q in enumerate(quantities):
        if q not in d and q in FALLBACK and FALLBACK[q] in d:
            log.warning(f"{q} not in {path}: showing {FALLBACK[q]}")
            quantities[i] = FALLBACK[q]
    quantities[:] = list(dict.fromkeys(quantities))
    missing = [q for q in quantities if q not in d]
    if missing and drop_missing:
        log.warning(f"not in {path}, skipped: {missing}")
        quantities[:] = [q for q in quantities if q in d]
    elif missing:
        sys.exit(f"{missing} not in {path}")
    fields = {q: np.asarray(d[q], dtype=np.float32) for q in quantities}
    for q in ("neutral_fraction", "sfrd_acg", "density"):  # for the bubble, the galaxy and the halo check
        if q not in fields and q in d:
            fields[q] = np.asarray(d[q], np.float32)
    halos = None
    if "all_halo_x" in d:  # real catalogue with offsets from the plane
        s = np.abs(d["all_halo_dz"]) < slab / 2
        halos = (d["all_halo_x"][s], d["all_halo_y"][s], d["all_halo_m"][s], None)
    elif "halo_x" in d:
        halos = (d["halo_x"], d["halo_y"], d["halo_m"], d["halo_sfr"] if "halo_sfr" in d else None)
    tag = str(d["tag"]) if "tag" in d else Path(path).stem
    sl = Slice(fields, float(d["cell"]), float(d["z"]), tag, halos)
    for q in quantities:
        base = FALLBACK.get(q, q) if f"cube_{q}_x0" not in d else q
        if f"cube_{base}_x0" in d:
            sl.cube[q] = {f: np.asarray(d[f"cube_{base}_{f}"], np.float32) for f in CUBE_FACES}
    if "source" not in d:  # synthetic or other test input
        sl.watermark = f"TEST INPUT ({Path(path).name}): not EOS26 data"
    return sl


def save_slice(sl, path, source):
    out = dict(sl.fields, z=sl.z, cell=sl.cell, tag=sl.tag, source=source)
    for q, faces in sl.cube.items():
        out.update({f"cube_{q}_{f}": v for f, v in faces.items()})
    if sl.halos is not None:
        out.update(halo_x=sl.halos[0], halo_y=sl.halos[1], halo_m=sl.halos[2])
        if sl.halos[3] is not None:
            out.update(halo_sfr=sl.halos[3])
    np.savez(path, **out)
    log.info(f"wrote {path}")


def load_rect_slice(a, quantities, drop_missing=False):
    """The slice nearest a.freq of the rect lightcone stores (see the module docstring); with
    drop_missing, the quantities without a store are removed from `quantities` instead of an exit."""
    import h5py
    sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
    sys.path.insert(1, str(Path(__file__).resolve().parent / "lightcone"))
    import eos_boxes as eb
    import eos_lightcones as el

    run = eb.Run(test=not a.production)
    lc_dir = Path(a.lightcone) if a.lightcone else el.default_out_dir(run.cache_dir) / "rect"
    if lc_dir.suffix == ".h5" and lc_dir.with_suffix("").is_dir():
        lc_dir = lc_dir.with_suffix("")
    store = {"brightness_temp_with_rsds": "brightness_temp_dvdr_with_rsds"}
    need = list(dict.fromkeys(quantities + ["neutral_fraction", "sfrd_acg", "density"]))
    z_want = NU21 / a.freq - 1
    fields, k, z, dist = {}, None, None, None
    for q in need:
        path = lc_dir / f"{store.get(q, q)}.h5"
        if not path.exists() and q in FALLBACK:
            log.warning(f"no {path.name} yet (finalise job): showing {FALLBACK[q]}")
            quantities[quantities.index(q)] = FALLBACK[q]
            q = FALLBACK[q]
            path = lc_dir / f"{q}.h5"
        if not path.exists():
            if q in quantities and drop_missing:
                log.warning(f"no {path}: skipped")
                quantities.remove(q)
            elif q in quantities:
                sys.exit(f"no {path}")
            continue
        with h5py.File(path, "r") as h:
            zs = h["lightcone_redshifts"][()]
            if k is None:
                k = int(np.argmin(np.abs(zs - z_want)))
                z = float(zs[k])
                dist = h["lightcone_distances"][()]
            elif not np.isclose(zs[k], z):
                sys.exit(f"{q}: other slices than {need[0]}")
            if not h.attrs.get("complete", False):
                log.warning(f"{q}: store not complete")
            t = time.time()
            fields[q] = np.ascontiguousarray(h["lightcone"][:, :, k].T, dtype=np.float32)  # [y, x]
            log.info(f"{q}: slice {k} (z = {z:.4f}) read in {time.time() - t:.1f} s")
            if np.isnan(fields[q]).any():
                log.warning(f"{q}: slice {k} has NaN (not filled yet)")
    cell = float(run.inputs.simulation_options.cell_size.to_value("Mpc"))
    halos = None
    if a.halos == "auto":
        sys.path.insert(1, str(Path(__file__).resolve().parent / "galaxies"))
        import galaxy_properties as gp
        zn = run.nearest_z(z)
        a.halos = gp.output_path(run.cache_dir, run.inputs, zn)
        log.info(f"galaxies of node z = {zn:.4f}: {a.halos}")
        if not Path(a.halos).exists():
            sys.exit(f"no {a.halos}: run postprocess/galaxies/galaxy_properties_job.sh for this node first")
    if a.halos:
        halos = read_halos(a.halos, dist, k, cell, next(iter(fields.values())).shape[0], a.halo_slab)
        if "density" in fields and len(halos[0]):
            # check of the plane: halos sit in overdense cells of this slice, not of a random plane
            d = fields["density"]
            n = d.shape[0]
            ix, iy = (halos[0] / cell).astype(int) % n, (halos[1] / cell).astype(int) % n
            here, rnd = 1 + d[iy, ix].mean(), 1 + np.roll(d, n // 3, axis=0)[iy, ix].mean()
            log.info(f"halo check: mean 1+delta at the halos {here:.2f} (a shifted plane: {rnd:.2f})")
            if here < rnd + 0.1:
                log.warning("the halos do not trace this slice: check the plane of read_halos")
    sl = Slice(fields, cell, z, f"{run.tag}", halos, run.inputs.cosmo_params.cosmo)
    if a.what != "figure" and a.intro == "cube":
        try:
            sl.cube[quantities[0]] = read_cube_faces(run, quantities[0], z, rect_plane(dist, k, cell, sl.N), sl.N)
        except Exception as e:  # noqa: BLE001
            log.warning(f"no cube intro: {e}")
    if a.save_slice:
        save_slice(sl, a.save_slice, f"{lc_dir} slice {k}")
    return sl


def rect_plane(dist, k, cell, n):
    """The box plane of rect slice k (21cmFAST RectilinearLightconer.coeval_subselect, index_offset = n_slices)."""
    pix = np.asarray(dist) / cell
    return (-int(pix.max() - pix[k] + 1) + len(dist)) % n


# the coeval structure and field of each lightcone quantity (for the cube intro)
COEVAL = {"density": ("PerturbedField", "density"), "neutral_fraction": ("IonizedBox", "neutral_fraction"),
          "cumulative_recombinations": ("IonizedBox", "cumulative_recombinations"),
          "ionisation_rate_G12": ("IonizedBox", "ionisation_rate_G12"),
          "brightness_temp": ("BrightnessTemp", "brightness_temp"),
          "brightness_temp_with_rsds": ("BrightnessTemp", "brightness_temp"),  # coevals have no RSDs
          "spin_temperature": ("TsBox", "spin_temperature"), "kinetic_temp_neutral": ("TsBox", "kinetic_temp_neutral"),
          "J_21_LW": ("TsBox", "J_21_LW"), "sfrd_acg": ("EmissivityFields", "sfrd_acg"),
          "sfrd_mcg": ("EmissivityFields", "sfrd_mcg"), "n_ion": ("EmissivityFields", "n_ion"),
          "xray_emissivity": ("EmissivityFields", "xray_emissivity")}
COEVAL["ics"] = ("InitialConditions", "lowres_density")
CUBE_FACES = ("x0", "x1", "y0", "y1", "back")


def read_cube_faces(run, q, z, plane, n, with_front=False):
    """Faces of the cached coeval box at the node nearest z, for a cube whose front face is box plane
    `plane` (the slice): x0 = box[0], x1 = box[-1] (j, k), y0 = box[:, 0], y1 = box[:, -1] (i, k), with k
    running from the back (plane - n + 1) to the front (plane); back = box[:, :, plane + 1]."""
    import h5py
    kind, field = COEVAL[q]
    zn = run.nearest_z(z)
    path = run.path(kind) if kind == "InitialConditions" else run.path(kind, zn)
    if path is None:
        raise FileNotFoundError(f"no cached {kind}" + ("" if kind == "InitialConditions" else f" at z = {zn:.4f}"))
    kk = (plane - n + 1 + np.arange(n)) % n
    t = time.time()
    with h5py.File(path, "r") as h:
        ds = h[kind]["OutputFields"][field]
        faces = {"x0": ds[0][:, kk], "x1": ds[n - 1][:, kk], "y0": ds[:, 0, :][:, kk], "y1": ds[:, n - 1, :][:, kk],
                 "back": ds[:, :, (plane + 1) % n]}
        if with_front:
            faces["front"] = ds[:, :, plane]
    log.info(f"cube faces of {kind}.{field} at z = {zn:.4f} read in {time.time() - t:.0f} s")
    return {f: np.asarray(v, np.float32) for f, v in faces.items()}


def read_halos(path, dist, k, cell, n, slab):
    """Galaxies of a PerturbedHaloCatalog within slab/2 of the box plane of rect slice k.

    The rect lightconer takes box plane -int(d_max/cell - d_k/cell + 1) + n_slices (mod HII_DIM) for
    slice k (21cmFAST RectilinearLightconer.coeval_subselect, index_offset = n_slices); halo_coords
    (x, y, z) are along box axes (i, j, k). The arrays are cut to the n_halos attribute (21cmFAST
    may write a longer buffer). SFR = sfr_acg + sfr_mcg (Msun/s in the file) in Msun/yr, if present.
    """
    import h5py
    plane = rect_plane(dist, k, cell, n)
    with h5py.File(path, "r") as h:
        g = h[next(iter(h))]["OutputFields"]
        nh = int(g.attrs.get("n_halos", g["halo_masses"].shape[0]))
        c = g["halo_coords"][:nh]
        m = g["halo_masses"][:nh]
        sfr = None
        if "sfr_acg" in g:
            sfr = g["sfr_acg"][:nh].astype(np.float64)
            if "sfr_mcg" in g:
                sfr = sfr + g["sfr_mcg"][:nh]
            sfr = sfr * 3.15576e7  # Msun/s -> Msun/yr
    L = n * cell
    dz = (c[:, 2] - (plane + 0.5) * cell + L / 2) % L - L / 2
    s = np.abs(dz) < slab / 2
    log.info(f"galaxies: {s.sum()} of {nh} within {slab / 2} cMpc of plane {plane}"
             + ("" if sfr is not None else " (no sfr_acg in the file: ring sizes from the halo mass)"))
    return c[s, 0], c[s, 1], m[s], (sfr[s].astype(np.float32) if sfr is not None else None)


def uv_magnitude(sl):
    """M_UV of the slice's galaxies: 51.63 - 2.5 log10(SFR / 1.15e-28) (Sun & Furlanetto 2016, as
    21cmFAST and tuesday). Without SFRs, a stand-in from the halo mass (SFR = 0.05 (M/1e10)^1.5)."""
    hx, hy, hm, sfr = sl.halos
    if sfr is None:
        sfr = 0.05 * (hm / 1e10) ** 1.5
    with np.errstate(divide="ignore"):
        return 51.63 - 2.5 * np.log10(np.maximum(sfr, 1e-30) / 1.15e-28)


# ====================================================================== colours
def eor_cmap(vmin, vmax):
    """tuesday's eor_colormap (tuesday.core.plotting.angular, as in its angular lightcone tutorial):
    zero black, absorption maroon -> orange -> yellow -> white at vmin, emission blue -> sky blue at vmax."""
    try:
        from tuesday.core import eor_colormap
        return eor_colormap(vmin, vmax)
    except ImportError:
        from matplotlib.colors import LinearSegmentedColormap
        zero = min(max(-vmin / (vmax - vmin), 0.0), 1.0)
        colours = [(zero * i / 4, c) for i, c in enumerate(["white", "yellow", "orange", "maroon"])] if zero > 0 else []
        colours.append((zero, "black"))
        if zero < 1:
            colours += [(zero + (1 - zero) * (i + 1) / 2, c) for i, c in enumerate(["#1f77b4", "skyblue"])]
        return LinearSegmentedColormap.from_list(f"EoR-{vmin:g}-{vmax:g}", colours)


class Colourer:
    """Fixed colour scale for one quantity (set once from the whole slice, so frames agree)."""

    def __init__(self, q, field, vmin=None, vmax=None):
        from matplotlib import colormaps, colors
        label, cmap, scale = SPEC.get(q, (q, "viridis", "lin"))
        self.q, self.label, self.scale = q, label, scale
        v = field[np.isfinite(field)]
        self.transform = lambda x: x
        if scale == "eor":
            # as tuesday: the range of the values, extended to zero (here the 0.05 and 99.95 percentiles)
            lo, hi = np.percentile(v, [0.05, 99.95])
            lo = min(lo, 0.0) if vmin is None else vmin
            hi = max(hi, 0.0) if vmax is None else vmax
            self.cmap = eor_cmap(lo, hi)
            self.norm = colors.Normalize(lo, hi)
        else:
            self.cmap = colormaps[cmap]
        if scale == "eor":
            pass
        elif scale == "unit":
            self.norm = colors.Normalize(0, 1)
        elif scale == "sym":
            s = np.percentile(np.abs(v), 99.5)
            self.norm = colors.Normalize(-s, s)
        elif scale == "log1p":
            self.transform = lambda x: np.log10(np.clip(1 + x, 1e-3, None))
            lo, hi = np.percentile(self.transform(v), [1, 99.5])
            self.norm = colors.Normalize(lo, hi)
        elif scale == "log":
            pos = v[v > 0]
            lo, hi = np.percentile(pos, [2, 99.8]) if pos.size else (1, 10)
            self.transform = lambda x, lo=lo: np.log10(np.clip(x, lo, None))
            self.norm = colors.Normalize(np.log10(lo), np.log10(max(hi, lo * 1.001)))
        else:
            lo, hi = np.percentile(v, [1, 99.5])
            self.norm = colors.Normalize(lo, hi)
        if scale != "eor" and (vmin is not None or vmax is not None):
            lo_, hi_ = self.norm.vmin, self.norm.vmax
            self.norm = colors.Normalize(lo_ if vmin is None else vmin, hi_ if vmax is None else vmax)
        self.lut = (self.cmap(np.linspace(0, 1, 4096))[:, :3] * 255).astype(np.uint8)
        # the colours of up to 20000 of the values (for the choice of the circle colours)
        step = max(1, v.size // 20000)
        self.sample = self(v[::step]) if v.size else None

    def set_range(self, lo, hi):
        """Colour range [lo, hi] in the scale's units (log10 for 'log'), for a scale that follows the
        redshift (--sector-scale follow)."""
        from matplotlib import colors
        self.norm = colors.Normalize(lo, max(hi, lo + 1e-6))
        if self.scale == "log":
            self.transform = lambda x, f=10.0 ** lo: np.log10(np.clip(x, f, None))

    def value(self, x):
        """Field values -> 0..1 (same as the colour bar)."""
        return np.clip(self.norm(self.transform(x)), 0, 1)

    def __call__(self, x):
        """Field values -> RGB uint8."""
        u = self.value(x)
        u = np.nan_to_num(u, nan=0.0)
        return self.lut[(u * 4095).astype(np.int32)]


def sector_weights(theta_deg, n, blend=1.5, offset=0.0):
    """Weights (n, ...) of n equal sectors, clockwise from straight up (theta: 0 = up, clockwise)."""
    edges = np.arange(n) * 360.0 / n + offset  # start of each sector
    half = 180.0 / n
    w = []
    for e in edges:
        mid = e + half
        d = (theta_deg - mid + 180) % 360 - 180
        w.append(1 / (1 + np.exp((np.abs(d) - half) / blend)))
    w = np.array(w)
    return w / w.sum(0)


def moving_scales(quantities, a, values_at, zs):
    """Colour ranges that follow the redshift (--sector-scale follow, several quantities): per quantity with a
    log scale (those that change by orders of magnitude), a function z -> (lo, hi) through the ranges of
    the slices at `zs` (monotone cubic in z; slices without positive values take the nearest range).
    values_at(q, z) -> values."""
    from scipy.interpolate import PchipInterpolator
    if len(quantities) < 2 or a.sector_scale != "follow" or a.vmin is not None or a.vmax is not None:
        return {}
    zs = np.sort(np.unique(np.asarray(zs, float)))
    out = {}
    for q in quantities:
        scale = SPEC.get(q, (q, "viridis", "lin"))[2]
        if scale != "log":
            continue
        lo, hi, ok = [], [], []
        for z in zs:
            v = values_at(q, z)
            v = v[np.isfinite(v)]
            c = Colourer(q, v) if v.size else None
            ok.append(c is not None and bool((v > 0).any()))
            lo.append(c.norm.vmin if c is not None else np.nan)
            hi.append(c.norm.vmax if c is not None else np.nan)
        ok = np.array(ok)
        if ok.sum() < 2:
            continue
        lo, hi = np.array(lo), np.array(hi)
        idx = np.flatnonzero(ok)
        for i in np.flatnonzero(~ok):
            j = idx[np.argmin(np.abs(idx - i))]
            lo[i], hi[i] = lo[j], hi[j]
        f_lo, f_hi = PchipInterpolator(zs, lo), PchipInterpolator(zs, hi)
        out[q] = lambda z, f_lo=f_lo, f_hi=f_hi, z0=zs[0], z1=zs[-1]: (
            float(f_lo(np.clip(z, z0, z1))), float(f_hi(np.clip(z, z0, z1))))
        log.info(f"{q}: colour range follows z, " + ", ".join(f"z={z:.1f}: {l_:.2f}..{h_:.2f}"
                                                              for z, l_, h_ in zip(zs, lo, hi)))
    return out


# ====================================================================== bubble and galaxy
def find_bubble(sl, centre, size, search):
    """An ionised region (x_HI < 0.5) of the slice near `centre`, of equivalent diameter close to `size`.

    Returns (centre of its largest inscribed circle [cMpc], inscribed radius, equivalent radius, mask).
    Score: |ln(d_eq / size)| + roundness penalty (1 - r_in / r_eq) + distance / search.
    """
    from scipy import ndimage as ndi
    x = sl.fields["neutral_fraction"]
    n, c = sl.N, sl.cell
    # roll the periodic slice so that `centre` is in the middle: the search is far from the edges
    sh = (int(n // 2 - centre[1] / c), int(n // 2 - centre[0] / c))
    ion = np.roll(x < 0.5, sh, axis=(0, 1))
    edt = ndi.distance_transform_edt(ion) * c
    lab, nlab = ndi.label(ion)
    yy, xx = np.indices(ion.shape)
    near = np.hypot((xx + 0.5) * c - n // 2 * c, (yy + 0.5) * c - n // 2 * c) < search
    cands = np.unique(lab[near & ion])
    cands = cands[cands > 0]
    if not len(cands):
        raise RuntimeError("no ionised region near the centre")
    areas = ndi.sum(np.ones_like(lab), lab, index=cands) * c * c
    rin = ndi.maximum(edt, lab, index=cands)
    pos = ndi.maximum_position(edt, lab, index=cands)
    best, score = None, np.inf
    for i, lb in enumerate(cands):
        req = np.sqrt(areas[i] / np.pi)
        py, px = pos[i]
        dist = np.hypot((px + 0.5) * c - n // 2 * c, (py + 0.5) * c - n // 2 * c)
        if dist > search or req < 1.5 * c:
            continue
        s = abs(np.log(2 * req / size)) + (1 - min(rin[i] / req, 1)) + dist / search
        if s < score:
            best, score = i, s
    if best is None:
        raise RuntimeError("no ionised region of a usable size near the centre")
    py, px = pos[best]
    cx = ((px + 0.5) * c - sh[1] * c) % sl.L
    cy = ((py + 0.5) * c - sh[0] * c) % sl.L
    mask = np.roll(lab == cands[best], (-sh[0], -sh[1]), axis=(0, 1))
    req = np.sqrt(areas[best] / np.pi)
    log.info(f"bubble at ({cx:.1f}, {cy:.1f}) cMpc: inscribed r = {rin[best]:.1f}, equivalent r = {req:.1f} cMpc")
    return (cx, cy), float(rin[best]), float(req), mask


def find_galaxy(sl, mask):
    """The most massive halo inside the bubble mask, else the cell of highest star formation."""
    c = sl.cell
    if sl.halos is not None and len(sl.halos[0]):
        hx, hy, hm, _ = sl.halos
        muv = uv_magnitude(sl)
        ix = (hx / c).astype(int) % sl.N
        iy = (hy / c).astype(int) % sl.N
        inside = mask[iy, ix]
        if inside.any():
            j = np.flatnonzero(inside)[np.argmin(muv[inside])]
            log.info(f"galaxy: M_UV = {muv[j]:.2f}, halo of {hm[j]:.3g} Msun at ({hx[j]:.2f}, {hy[j]:.2f})")
            return (float(hx[j]), float(hy[j])), float(hm[j]), float(muv[j])
    s = np.where(mask, sl.fields["sfrd_acg"], -np.inf)
    iy, ix = np.unravel_index(np.argmax(s), s.shape)
    return ((ix + 0.5) * c, (iy + 0.5) * c), None, None


def virial_radius_cmpc(sl, M):
    """Comoving virial radius of a halo of mass M [Msun] (Delta_c = 18 pi^2 of the critical density)."""
    rho = sl.cosmo.critical_density(sl.z).to_value("Msun / Mpc3")
    return (3 * M / (4 * np.pi * 18 * np.pi**2 * rho)) ** (1 / 3) * (1 + sl.z)


def lagrangian_radius_cmpc(sl, M):
    rho = sl.cosmo.critical_density0.to_value("Msun / Mpc3") * sl.cosmo.Om0
    return (3 * M / (4 * np.pi * rho)) ** (1 / 3)


# ====================================================================== sampling
class Sampler:
    """Samples the periodic fields on an axis-aligned pixel grid, anti-aliased when zoomed out."""

    SIGMAS = (0.0, 0.5, 1.0, 2.0, 4.0)  # Gaussian prefilters [cells]

    def __init__(self, sl, quantities, interp):
        from scipy import ndimage as ndi
        self.sl, self.order = sl, {"nearest": 0, "linear": 1, "cubic": 3}[interp]
        self.pyr = {}
        for q in quantities:
            f = np.nan_to_num(sl.fields[q], nan=0.0)
            levels = []
            for s in self.SIGMAS:
                g = ndi.gaussian_filter(f, s, mode="wrap") if s else f
                if s == 0 and self.order == 3:
                    g = ndi.spline_filter(g, 3, mode="grid-wrap")
                levels.append(g.astype(np.float32))
            self.pyr[q] = levels

    def sample(self, q, xs, ys):
        """Values at pixel centres xs (W,), ys (H,) [cMpc] -> (H, W)."""
        from scipy import ndimage as ndi
        c = self.sl.cell
        px = abs(xs[1] - xs[0]) / c  # cells per pixel
        lvl = int(np.argmin([abs(s - 0.5 * max(px - 1, 0)) for s in self.SIGMAS]))
        order = self.order if lvl == 0 else 1
        Y, X = np.meshgrid(ys / c - 0.5, xs / c - 0.5, indexing="ij")
        return ndi.map_coordinates(self.pyr[q][lvl], [Y, X], order=order, mode="grid-wrap",
                                   prefilter=False)


# ====================================================================== drawing helpers
RING = "#ff3b30"  # galaxy rings (red, as Davies et al. 2025)
RING_RGB = (1.0, 0.231, 0.188)


def ring_px(muv, fs=1.0):
    """Ring radius [pixels at 1080p x fs] for a UV magnitude: 3 px at M_UV = -15, +2.6 px per magnitude."""
    return fs * np.clip(3 + 2.6 * (-15 - np.asarray(muv, float)), 3, 26)


def outlined(lw=2.0, fg="black", alpha=0.85):
    from matplotlib import patheffects as pe
    return [pe.withStroke(linewidth=lw, foreground=fg, alpha=alpha)]


def nice_length(target):
    e = 10 ** np.floor(np.log10(target))
    for m in (1, 2, 5, 10):
        if m * e >= target * 0.999:
            return m * e
    return 10 * e


def fmt_len(x):
    """cMpc -> text."""
    if x >= 1000:
        return f"{x / 1000:g} cGpc"
    if x >= 1:
        return f"{x:g} cMpc"
    return f"{x * 1000:g} ckpc"


def fmt_angle(deg):
    if deg >= 1:
        return f"{deg:.1f}°" if deg < 100 else f"{deg:.0f}°"
    if deg * 60 >= 1:
        return f"{deg * 60:.0f}′" if deg * 60 >= 10 else f"{deg * 60:.1f}′"
    return f"{deg * 3600:.0f}″"


def render_rgb(sl, colourers, sampler, quantities, xs, ys, origin, spin=0.0, box_mask=True, hole=0.0):
    """RGB (H, W, 3) uint8 of the view; sectors around `origin` (cMpc) if several quantities, with a black
    disc of radius `hole` (fraction of the frame height, soft edge) where they meet."""
    H, W = len(ys), len(xs)
    if len(quantities) == 1:
        rgb = colourers[quantities[0]](sampler.sample(quantities[0], xs, ys)).astype(np.float32)
    else:
        X, Y = np.meshgrid(xs - origin[0], ys - origin[1])
        th = np.degrees(np.arctan2(X, Y)) % 360  # 0 = up, clockwise
        w = sector_weights(th, len(quantities), blend=0.8, offset=spin)
        rgb = np.zeros((H, W, 3), np.float32)
        for i, q in enumerate(quantities):
            rgb += colourers[q](sampler.sample(q, xs, ys)) * w[i][..., None]
        if hole > 0:
            r = np.hypot(X, Y) / (H * abs(ys[1] - ys[0]) if H > 1 else 1.0)  # fraction of the frame height
            rgb *= np.clip((r - hole) / 0.012 + 0.5, 0, 1)[..., None]
    if box_mask:
        outside = ((xs[None, :] < 0) | (xs[None, :] > sl.L)) | ((ys[:, None] < 0) | (ys[:, None] > sl.L))
        rgb[outside] = 0
    return np.clip(rgb, 0, 255).astype(np.uint8)


# ====================================================================== figure
def draw_figure_footprints(fig, ax, fps, sl, centre, img, Z, x0f, y0f, wf, hf, lim):
    """The other surveys of the figure (--footprints on): large ones (circles) on the box; the others in a zoom
    panel at figure fraction (x0f, y0f, wf, hf), whose region is marked on the box."""
    from matplotlib.patches import Circle, ConnectionPatch, Rectangle
    k = sl.cmpc_per_deg()

    def outline(axx, entry, lw=1.0):
        wd, hd = (v * k for v in footprint_size(entry))
        for lw_, colr, al in ((lw * 2.6, "black", 0.5), (lw, FP_COLOUR, 1.0)):
            if entry[0] == "circle":
                art = Circle(centre, wd / 2, fill=False, ec=colr, lw=lw_, alpha=al, zorder=3)
            else:
                art = Rectangle((centre[0] - wd / 2, centre[1] - hd / 2), wd, hd, fill=False, ec=colr, lw=lw_,
                                alpha=al, zorder=3)
            axx.add_patch(art)
        return wd, hd

    def label(axx, text, x, y, ha, va, fs_):
        axx.text(x, y, text, color="white", fontsize=fs_, ha=ha, va=va, zorder=4,
                 bbox=dict(boxstyle="round,pad=0.15", fc="black", ec=FP_COLOUR, lw=0.6, alpha=0.75))

    small = [f for f in fps if f[1][0] != "circle"]
    for i, entry, members in fps:
        names = " · ".join(m[0] for m in members)
        if entry[0] == "circle":
            wd, _ = outline(ax, entry)
            t = np.radians(125)
            label(ax, names, centre[0] + wd / 2 * np.cos(t), centre[1] + wd / 2 * np.sin(t), "right", "bottom", 7.5)
        log.info(f"  {names}: {footprint_size(entry)[0]:.3g} deg = {footprint_size(entry)[0] * k:.0f} cMpc")
    if not small:
        return
    R = 0.62 * max(max(footprint_size(e)) for _, e, _ in small) * k
    zx, zy = (centre[0] - R, centre[0] + R), (centre[1] - R, centre[1] + R)
    axz = fig.add_axes([x0f, y0f, wf, hf])
    axz.set_facecolor("black")
    L = sl.L
    axz.imshow(img, extent=(0, L, 0, L), origin="lower", interpolation="nearest", rasterized=True, zorder=0)
    axz.set_xlim(*zx)
    axz.set_ylim(*zy)
    axz.set_aspect("equal")
    axz.tick_params(direction="out", labelsize=8)
    axz.yaxis.tick_right()
    axz.set_xlabel(r"$x$ [cMpc]", fontsize=9)
    pad = 0.012 * 2 * R
    for i, entry, members in small:
        wd, hd = outline(axz, entry, lw=1.2)
        names = " · ".join(m[0] for m in members)
        if entry[0] == "rect":
            label(axz, names, centre[0] - wd / 2, centre[1] + hd / 2 + pad, "left", "bottom", 7.5)
        elif entry[-1] == "br":
            label(axz, names, centre[0] + wd / 2 - pad, centre[1] - hd / 2 + pad, "right", "bottom", 7.5)
        else:
            label(axz, names, centre[0] - wd / 2 + pad, centre[1] + hd / 2 - pad, "left", "top", 7.5)
    # the zoom region on the box, joined to the panel
    ax.add_patch(Rectangle((zx[0], zy[0]), 2 * R, 2 * R, fill=False, ec="white", lw=0.9, zorder=4))
    for yy in (zy[1], zy[0]):
        fig.add_artist(ConnectionPatch((zx[1], yy), (zx[0], yy), coordsA="data", coordsB="data", axesA=ax, axesB=axz,
                                       color="0.55", lw=0.7, zorder=1))


def make_figure(sl, a, quantities, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    # STIX: the Times-like font of A&A's text, with the glyphs the labels need (en dash, degree sign)
    plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 11})
    L, c = sl.L, sl.cell
    centre = a.centre if a.centre else (L / 2, L / 2)
    colourers = {q: Colourer(q, sl.fields[q], a.vmin, a.vmax) for q in quantities}
    insts = [(n, d, col, sl.fov_cmpc(d)) for n, d, col in instruments(quantities, colourers, a.circle_colours)]
    if a.show_mwa:
        half = max(L / 2, max(D for *_, D in insts) / 2 * 1.04)
        lim = (centre[0] - half, centre[0] + half), (centre[1] - half, centre[1] + half)
    else:
        lim = (0, L), (0, L)

    one = len(quantities) == 1
    cb = one and not a.no_cbar
    # a square axes S x S inches; margins in inches
    left, bottom, top = 0.75, 0.55, (0.55 if a.deg_axis else 0.15)
    right = (0.95 if cb else 0.15) + (0.45 if a.deg_axis else 0.0)
    S = a.fig_width - left - right
    FW, FH = a.fig_width, S + bottom + top
    # --footprints on: a zoom panel to the right with the other surveys' footprints (they are small on the box)
    fps = [(i, e, footprint_members(e, sl.z)) for i, e in enumerate(FOOTPRINTS)] if a.footprints == "on" else []
    fps = [f for f in fps if f[2]]
    Z = 0.62 * S if any(e[0] != "circle" for _, e, _ in fps) else 0.0
    FWt = FW + (0.35 + Z + 0.55 if Z else 0.0)
    fig = plt.figure(figsize=(FWt, FH))
    ax = fig.add_axes([left / FWt, bottom / FH, S / FWt, S / FH])
    # the image: native cells inside the box (nearest), black outside
    npx = sl.N
    xs = (np.arange(npx) + 0.5) * c
    if one:
        q = quantities[0]
        img = colourers[q](sl.fields[q])
    else:
        X, Y = np.meshgrid(xs - centre[0], xs - centre[1])
        th = np.degrees(np.arctan2(X, Y)) % 360
        w = sector_weights(th, len(quantities), blend=0.8)
        img = np.zeros((npx, npx, 3), np.float32)
        for i, q in enumerate(quantities):
            img += colourers[q](sl.fields[q]) * w[i][..., None]
        img = np.clip(img, 0, 255).astype(np.uint8)
    ax.set_facecolor("black")
    ax.imshow(img, extent=(0, L, 0, L), origin="lower", interpolation="nearest", rasterized=True, zorder=0)
    if a.show_mwa and a.periodic:
        dim = (img.astype(np.float32) * 0.35).astype(np.uint8)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                if i or j:
                    ax.imshow(dim, extent=(i * L, (i + 1) * L, j * L, (j + 1) * L), origin="lower",
                              interpolation="nearest", rasterized=True, zorder=0)
    if a.show_mwa:
        ax.add_patch(Rectangle((0, 0), L, L, fill=False, ec="0.85", lw=0.8, zorder=2))
    ax.set_xlim(*lim[0])
    ax.set_ylim(*lim[1])
    ax.set_aspect("equal")
    ax.set_xlabel(r"$x$ [cMpc]")
    ax.set_ylabel(r"$y$ [cMpc]")
    ax.tick_params(direction="out")
    # circles: dashed, coloured, with a dark casing; names inline on the circle, in a dark box
    angles = {"MWA": 225, "HERA": 90, "LOFAR": 50, "SKA-Low": 230}
    step = 500 if (lim[0][1] - lim[0][0]) < 3000 else 1000
    ax.xaxis.set_major_locator(plt.MultipleLocator(step))
    ax.yaxis.set_major_locator(plt.MultipleLocator(step))
    for name, deg, col, D in insts:
        r = D / 2
        for lw, colr, ls in ((3.2, "black", "-"), (1.8, col, (0, (3.0, 1.8)))):
            ax.add_patch(Circle(centre, r, fill=False, ec=colr, lw=lw, ls=ls, alpha=0.5 if colr == "black" else 1,
                                zorder=3))
        t = np.radians(angles.get(name, 45))
        lx, ly = centre[0] + r * np.cos(t), centre[1] + r * np.sin(t)
        if not (lim[0][0] < lx < lim[0][1] and lim[1][0] < ly < lim[1][1]):
            continue
        ax.text(lx, ly, name, color="white", fontsize=9, ha="center", va="center", zorder=4,
                bbox=dict(boxstyle="round,pad=0.18", fc="black", ec=col, lw=0.9, alpha=0.8))
    if a.figure_galaxies and sl.halos is not None and len(sl.halos[0]):
        muv = uv_magnitude(sl)
        j = np.argsort(muv)[: a.figure_galaxies]
        # ring radius in points: the movie's mapping at 1080p, scaled to the figure
        r_pt = ring_px(muv[j], 0.2)
        ax.scatter(sl.halos[0][j], sl.halos[1][j], s=(2 * r_pt) ** 2, facecolors="none", edgecolors=RING,
                   linewidths=0.7, zorder=3.5)
        log.info(f"figure: {len(j)} brightest galaxies, M_UV {muv[j].min():.1f} to {muv[j].max():.1f}")
    if not one:
        # sector names along the edge of the frame
        n = len(quantities)
        half = 180 / n
        for i, q in enumerate(quantities):
            mid = np.radians(i * 360 / n + half)
            dx, dy = np.sin(mid), np.cos(mid)
            k = 0.47 * (lim[0][1] - lim[0][0]) / max(abs(dx), abs(dy))
            ax.text(centre[0] + dx * k * 0.93, centre[1] + dy * k * 0.93, SPEC.get(q, (q,))[0],
                    color="white", fontsize=9, ha="center", va="center", path_effects=outlined(2.2), zorder=4)
    if a.deg_axis:
        dpd = sl.cmpc_per_deg()
        for which, cc in (("top", centre[0]), ("right", centre[1])):
            f = (lambda x, cc=cc: (x - cc) / dpd), (lambda t, cc=cc: t * dpd + cc)
            sec = ax.secondary_xaxis("top", functions=f) if which == "top" else ax.secondary_yaxis("right", functions=f)
            sec.set_xlabel(r"$\theta$ [deg]") if which == "top" else sec.set_ylabel(r"$\theta$ [deg]")
    if cb:
        from matplotlib.cm import ScalarMappable
        q = quantities[0]
        cl = colourers[q]
        cax = fig.add_axes([(left + S + 0.12 + (0.45 if a.deg_axis else 0)) / FWt, bottom / FH, 0.16 / FWt, S / FH])
        sm = ScalarMappable(norm=cl.norm, cmap=cl.cmap)
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label(cbar_label(q, cl), rotation=90, labelpad=8)
    if fps:
        draw_figure_footprints(fig, ax, fps, sl, centre, img, Z, (FW + 0.35) / FWt, (bottom + (S - Z) / 2) / FH,
                               Z / FWt, Z / FH, lim)
    if sl.watermark:
        fig.text(0.01, 0.005, sl.watermark, color="#d62728", fontsize=7, ha="left", va="bottom")
    base = str(out)
    base = base[:-4] if base.endswith((".pdf", ".png")) else base  # z8.47 must not read as a suffix
    fig.savefig(base + ".pdf", dpi=300)
    fig.savefig(base + ".png", dpi=200)
    log.info(f"wrote {base}.pdf and .png")
    for name, deg, col, D in insts:
        log.info(f"  {name}: {deg * 150 / sl.nu:.2f} deg at {sl.nu:.1f} MHz = {D:.0f} cMpc ({D / L:.2f} box)")


# ====================================================================== movie
class Stop:
    def __init__(self, name, h, centre, title, sub="", hold=None, mark=None):
        self.name, self.h, self.centre, self.title, self.sub = name, float(h), centre, title, sub
        self.hold, self.mark = hold, mark  # mark: ("circle", (x, y), r) / ("square", (x, y), side)


def sci(m):
    e = int(np.floor(np.log10(m)))
    return f"{m / 10**e:.1f}×10$^{{{e}}}$"


def plan_stops(sl, a, C, bubble, galaxy, sectors=False):
    """The stops from the outside in; C = centre of the circles. With several quantities (sectors) and no
    --end given, the movie ends on the last field of view (SKA-Low, or the last --extras footprint)."""
    L = sl.L
    aspect = a.W / a.H
    stops = []
    insts = {n: (d, col, sl.fov_cmpc(d)) for n, d, col in INSTRUMENTS}
    nu = f"{sl.nu:.0f} MHz"
    if a.start == "mwa":
        d, col, D = insts["MWA"]
        stops.append(Stop("MWA", D * 1.10, C, "MWA field of view",
                          f"{fmt_angle(d * 150 / sl.nu)} at {nu} ≈ {D / 1000:.1f} cGpc, wider than the box"))
    box_h = L * 1.06 if aspect >= 1 else L * 1.06 / aspect
    stops.append(Stop("box", box_h, (L / 2, L / 2), "EOS26 simulation box",
                      f"{L / 1000:g} cGpc across · {sl.N}³ cells of {sl.cell:g} cMpc"))
    for n in ("HERA", "LOFAR", "SKA-Low"):
        d, col, D = insts[n]
        size = f"{D / 1000:.2f} cGpc" if D >= 1000 else f"{D:.0f} cMpc"
        stops.append(Stop(n, D * 1.12, C, f"{n} field of view", f"{fmt_angle(d * 150 / sl.nu)} at {nu} ≈ {size}"))
    if a.extras is not None:
        want = a.extras or [e[0] for e in EXTRAS]
        for name, kind, size, what in EXTRAS:
            if name not in want:
                continue
            side = np.radians(np.sqrt(size)) * sl.Dc if kind == "square_deg2" else size
            sub = (f"{size:g} deg² ≈ {side:.0f} × {side:.0f} cMpc at z = {sl.z:.1f}" if kind == "square_deg2"
                   else f"{size:g} cMpc across: {(size / L) ** 3 * 100:.2g} % of the EOS26 volume")
            stops.append(Stop(name, side * 1.25, C, name, sub, mark=("square", C, side)))
    if sectors and not a.end_given:
        stops.sort(key=lambda s: -s.h)
        stops[-1].hold = a.hold * 1.8
        return stops
    (bc, rin, req) = bubble
    h_bub = max(4.2 * req, 6 * sl.cell)
    if a.end >= h_bub / 1.5:
        # the movie ends on the bubble, in a frame of --end (or wider): no deeper zoom to a galaxy
        stops.append(Stop("bubble", max(h_bub, a.end), bc, "An ionised bubble", f"≈ {2 * req:.0f} cMpc across",
                          hold=a.hold * 1.8, mark=("circle", bc, req)))
        last = stops.pop()
        stops.sort(key=lambda s: -s.h)
        return stops + [last]
    stops.append(Stop("bubble", h_bub, bc, "An ionised bubble",
                      f"≈ {2 * req:.0f} cMpc across", mark=("circle", bc, req)))
    gpos, gm, gmuv = galaxy
    if gm is not None:
        rl = lagrangian_radius_cmpc(sl, gm)
        mu = f"M$_{{\\rm UV}}$ = −{abs(gmuv):.1f} · " if sl.halos[3] is not None else ""
        sub = f"{mu}halo of {sci(gm)} M$_\\odot$ · its matter came from ≈ {2 * rl:.1f} cMpc"
        mark = ("circle", gpos, rl)
    else:
        sub = f"the cell with the most star formation · one cell = {sl.cell:g} cMpc"
        mark = ("circle", gpos, sl.cell)
    stops.append(Stop("galaxy", a.end, gpos, "A galaxy", sub, hold=a.hold * 1.8, mark=mark))
    last = stops.pop()
    stops.sort(key=lambda s: -s.h)  # extras fall in place by size
    return stops + [last]


def timeline(stops, a):
    """Per frame: (h, centre, caption index or None, caption alpha)."""
    fps = a.fps
    frames = []
    ease = lambda u: u * u * (3 - 2 * u)  # noqa: E731
    fade = 0.3
    cap_s = max(a.caption_seconds, 1.0)  # each caption stays this long, also while the zoom moves on
    for i, s in enumerate(stops):
        hold = s.hold if s.hold is not None else a.hold
        nh = int(round(hold * fps))
        n0 = len(frames)
        for f in range(nh):
            t = f / fps
            frames.append((s.h, s.centre, i, min(1.0, t / fade)))
        if i == len(stops) - 1:
            break
        nxt = stops[i + 1]
        ratio = s.h / nxt.h
        dur = max(0.8, np.log2(abs(ratio)) / a.speed) if not np.isclose(ratio, 1) else 0.8
        nz = max(2, int(round(dur * fps)))
        # zoom about the point that stays put on screen from (c0, h0) to (c1, h1)
        c0, c1 = np.array(s.centre, float), np.array(nxt.centre, float)
        same = np.isclose(s.h, nxt.h)
        P = c1 if same else (c0 * nxt.h - c1 * s.h) / (nxt.h - s.h)
        for f in range(1, nz + 1):
            u = ease(f / nz)
            h = np.exp(np.log(s.h) + u * (np.log(nxt.h) - np.log(s.h)))
            cen = c0 + u * (c1 - c0) if same else P + (c0 - P) * h / s.h
            frames.append((h, tuple(cen), None, 0.0))
        # the caption of stop i: from its stop for cap_s (at least the hold), fading out over 0.5 s
        last = min(n0 + int(round(max(cap_s, hold) * fps)), len(frames))
        for j in range(n0, last):
            t = (j - n0) / fps
            frames[j] = frames[j][:2] + (i, max(0.0, min(1.0, t / fade, (last - j) / fps / 0.5)))
    return frames


def cube_textures(sl, q, colourer, size=1100):
    """RGB textures (PIL images, row 0 at the top) of the six faces as seen from outside the cube."""
    from PIL import Image
    f = sl.cube[q]
    front = f["front"] if "front" in f else sl.fields[q].T  # (i, j)
    imgs = {
        "front": front.T[::-1],
        "back": f["back"].T[::-1, ::-1],
        "x1": f["x1"][::-1, ::-1],
        "x0": f["x0"][::-1, :],
        "y1": f["y1"].T,
        "y0": f["y0"].T[::-1],
    }
    out = {}
    for name, arr in imgs.items():
        im = Image.fromarray(colourer(arr))
        if max(im.size) > size:
            im = im.resize((size, size), Image.BOX)
        out[name] = im
    return out


# corner P0 and edge vectors E1 (texture columns) and E2 (rows) of each face, cube [-1/2, 1/2]^3,
# x right, y up, z towards the viewer; the front face (z = +1/2) is the slice
CUBE_GEOM = {
    "front": ((-.5, .5, .5), (1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "back": ((.5, .5, -.5), (-1, 0, 0), (0, -1, 0), (0, 0, -1)),
    "x1": ((.5, .5, .5), (0, 0, -1), (0, -1, 0), (1, 0, 0)),
    "x0": ((-.5, .5, -.5), (0, 0, 1), (0, -1, 0), (-1, 0, 0)),
    "y1": ((-.5, .5, -.5), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "y0": ((-.5, -.5, .5), (1, 0, 0), (0, 0, -1), (0, -1, 0)),
}


def rotation(azim, elev):
    a, e = np.radians(azim), np.radians(elev)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    return rx @ ry


def render_cube(tex, W, H, azim, elev, side, centre=None):
    """Orthographic view of the textured cube: RGB (H, W, 3) uint8 (row 0 at the top) and the screen
    segments of the visible edges. side: edge length in pixels."""
    from PIL import Image
    R = rotation(azim, elev)
    cx, cy = centre if centre else (W / 2, H / 2)
    canvas = np.zeros((H, W, 3), np.float32)
    proj = lambda p: np.array([cx + side * (R @ p)[0], cy - side * (R @ p)[1]])  # noqa: E731
    visible = {}
    for name, (p0, e1, e2, nrm) in CUBE_GEOM.items():
        nz = (R @ np.array(nrm, float))[2]
        visible[name] = nz > 1e-3
        if nz < 0.02:
            continue
        q0 = proj(np.array(p0, float))
        v1 = proj(np.array(p0, float) + e1) - q0
        v2 = proj(np.array(p0, float) + e2) - q0
        M = np.array([v1, v2]).T
        Minv = np.linalg.inv(M)
        im = tex[name]
        tw, th = im.size
        A, B = tw * Minv[0], th * Minv[1]
        coeffs = (A[0], A[1], -(A @ q0), B[0], B[1], -(B @ q0))
        face = np.asarray(im.transform((W, H), Image.AFFINE, coeffs, resample=Image.BILINEAR), np.float32)
        mask = np.asarray(Image.new("L", im.size, 255).transform((W, H), Image.AFFINE, coeffs,
                                                                  resample=Image.BILINEAR), np.float32) / 255
        shade = 0.55 + 0.45 * nz
        canvas = canvas * (1 - mask[..., None]) + face * shade * mask[..., None]
    # edges: those of a visible face
    segs = []
    for name, (p0, e1, e2, nrm) in CUBE_GEOM.items():
        if not visible[name]:
            continue
        p0 = np.array(p0, float)
        quad = [p0, p0 + e1, p0 + np.array(e1) + e2, p0 + e2]
        pts = [proj(p) for p in quad]
        for i in range(4):
            segs.append((tuple(pts[i]), tuple(pts[(i + 1) % 4])))
    return np.clip(canvas, 0, 255).astype(np.uint8), segs


class Renderer:
    """Draws frames: the sampled slice, FoV circles, marks, halos, captions, title and scale bar."""

    def __init__(self, sl, a, quantities, C, stops, colourers=None, sampler=None, dynamic_galaxies=False):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import Circle, Rectangle

        plt.rcParams.update({"font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans"})
        self.sl, self.a, self.q, self.C, self.stops = sl, a, quantities, C, stops
        self.plt = plt
        self.colourers = colourers or {q: Colourer(q, sl.fields[q], a.vmin, a.vmax) for q in quantities}
        self.sampler = sampler or Sampler(sl, quantities, a.interp)
        self.zcur = None  # redshift of the frame (evolving movie): FoV sizes and bands follow it
        self.circ_alpha = None  # per-instrument alpha of the frame (evolving movie)
        self.angular = False  # globe of HEALPix maps: data coordinates in sin units, circles around (0, 0)
        self.gal_local = dynamic_galaxies
        W, H = self.W, self.H = a.W, a.H
        fs = self.fs = H / 1080  # font and line scale
        self.fig = fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="black")
        self.ax = ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        self.im = ax.imshow(np.zeros((H, W, 3), np.uint8), origin="lower", interpolation="nearest",
                            extent=(0, 1, 0, 1), zorder=0)
        box = dict(boxstyle="round,pad=0.3", fc="black", ec="none", alpha=0.55)
        # FoV circles (dark casing under a coloured dashed line) and their names
        self.circ = {}
        for n, d, col in instruments(quantities, self.colourers, a.circle_colours):
            if n == "MWA" and not a.mwa:
                continue
            r = sl.fov_cmpc(d) / 2
            casing = Circle(C, r, fill=False, ec="black", lw=5 * fs, alpha=0.45, zorder=3)
            line = Circle(C, r, fill=False, ec=col, lw=2.8 * fs, ls=(0, (4, 2.5)), zorder=3)
            lab = ax.text(0, 0, n, color="white", fontsize=18 * fs, ha="left", va="bottom", zorder=5,
                          bbox=dict(boxstyle="round,pad=0.25", fc="black", ec=col, lw=1.2 * fs, alpha=0.7))
            ax.add_patch(casing)
            ax.add_patch(line)
            self.circ[n] = (casing, line, lab, r)
        self.deg150 = {n: d for n, d, _ in INSTRUMENTS}
        # other surveys: thin solid outlines (dark casing), shown while a line is in band (draw: circ_alpha["_fp"])
        self.fp = []
        for i, entry in enumerate(FOOTPRINTS):
            mk = (lambda **kw: Circle(C, 1.0, fill=False, **kw)) if entry[0] == "circle" else \
                (lambda **kw: Rectangle(C, 1.0, 1.0, fill=False, **kw))
            casing = mk(ec="black", lw=4.2 * fs, alpha=0.45, zorder=3, visible=False)
            line = mk(ec=FP_COLOUR, lw=1.8 * fs, zorder=3, visible=False)
            lab = ax.text(0, 0, "", color="white", fontsize=15 * fs, zorder=5, visible=False,
                          bbox=dict(boxstyle="round,pad=0.22", fc="black", ec=FP_COLOUR, lw=1.0 * fs, alpha=0.7))
            ax.add_patch(casing)
            ax.add_patch(line)
            self.fp.append((entry, casing, line, lab, i))
        self.marks = []
        for s in stops:
            if s.mark is None:
                continue
            kind, pos, size = s.mark
            if kind == "circle":
                art = Circle(pos, size, fill=False, ec="white", lw=2.2 * fs, ls=(0, (2, 2)), zorder=4)
            else:
                art = Rectangle((pos[0] - size / 2, pos[1] - size / 2), size, size, fill=False, ec="white",
                                lw=2.2 * fs, ls=(0, (2, 2)), zorder=4)
            ax.add_patch(art)
            self.marks.append((s, art, size))
        self.box_edge = Rectangle((0, 0), sl.L, sl.L, fill=False, ec="0.75", lw=1.2 * fs, zorder=2)
        ax.add_patch(self.box_edge)
        from matplotlib.collections import LineCollection
        self.grid = LineCollection([], colors="#8fd3ff", linewidths=0.8 * fs, zorder=2)
        ax.add_collection(self.grid)
        self.cube_edges = LineCollection([], colors="white", linewidths=1.3 * fs, alpha=0.75, zorder=3)
        ax.add_collection(self.cube_edges)
        self.cube_tex = None
        # galaxies: open red rings sized by M_UV (rings), or discs at the comoving virial size (virial)
        self.legend_artists = []
        self.gal = None
        have = sl.halos is not None and len(sl.halos[0])
        if (have or dynamic_galaxies) and a.galaxies != "none":
            if have:
                hx, hy, hm, _ = sl.halos
                muv = uv_magnitude(sl)
                order = np.argsort(muv)  # brightest first
                self.gal = dict(x=hx[order], y=hy[order], m=hm[order], muv=muv[order],
                                rv=virial_radius_cmpc(sl, 1.0) * hm[order] ** (1 / 3))
            else:
                self.gal = dict(x=np.zeros(0), y=np.zeros(0), m=np.zeros(0), muv=np.zeros(0), rv=np.zeros(0),
                                w=np.zeros(0))
            self.gal_n = a.max_galaxies * (W * H) / (1920 * 1080)
            if a.galaxies == "rings":
                self.g_art = ax.scatter([], [], s=[], facecolors="none", edgecolors=RING, linewidths=1.6 * fs,
                                        zorder=6)
            else:
                self.h_glow = ax.scatter([], [], s=[], c="#ffb347", alpha=0.35, linewidths=0, zorder=6)
                self.g_art = ax.scatter([], [], s=[], c="#fff4d6", edgecolors="#7a3d00", linewidths=0.6 * fs,
                                        zorder=7)
            if a.galaxies == "rings" and not a.no_text:
                # legend: three ring sizes in a dark box, top right (below the colour bar)
                from matplotlib.patches import FancyBboxPatch
                mags = (-16, -19, -22)
                bw, bh = 260 * fs / W, 118 * fs / H  # box size in axes fractions
                top = 0.975 - (150 * fs / H if len(quantities) == 1 else 0)
                bx, by = 0.985 - bw, top - bh
                self.legend_artists.append(ax.add_patch(FancyBboxPatch(
                    (bx, by), bw, bh, boxstyle="round,pad=0,rounding_size=0.006", transform=ax.transAxes,
                    fc="black", ec="none", alpha=0.7, zorder=8)))
                xs_ = [bx + bw * f for f in (0.2, 0.5, 0.8)]
                yr = by + bh * 0.45
                self.legend_artists.append(ax.scatter(
                    xs_, [yr] * 3, s=[(2 * ring_px(m, fs) * 0.72) ** 2 for m in mags], facecolors="none",
                    edgecolors=RING, linewidths=1.6 * fs, transform=ax.transAxes, zorder=9))
                for x, m in zip(xs_, mags):
                    self.legend_artists.append(ax.text(x, by + bh * 0.06, f"−{abs(m)}", transform=ax.transAxes,
                                                       ha="center", va="bottom", color="white", fontsize=13 * fs,
                                                       zorder=9))
                self.legend_artists.append(ax.text(bx + bw / 2, by + bh * 0.95, "galaxies: M$_{\\rm UV}$",
                                                   transform=ax.transAxes, ha="center", va="top", color="white",
                                                   fontsize=14 * fs, zorder=9))
        if not a.no_text and len(quantities) == 1:
            # colour bar, top right, in the style of tuesday's dark-mode plots
            from matplotlib.cm import ScalarMappable
            from matplotlib.patches import FancyBboxPatch
            cl = self.colourers[quantities[0]]
            cw, chh = 420 * fs / W, 18 * fs / H
            cx0, cy0 = 0.985 - cw - 20 * fs / W, 0.975 - 58 * fs / H - chh
            self.cbar_bg = ax.add_patch(FancyBboxPatch(
                (cx0 - 20 * fs / W, cy0 - 50 * fs / H), cw + 40 * fs / W, 138 * fs / H,
                boxstyle="round,pad=0,rounding_size=0.006", transform=ax.transAxes, fc="black", ec="none", alpha=0.7,
                zorder=8))
            cax = fig.add_axes([cx0, cy0, cw, chh])
            cax.set_zorder(10)
            cb = fig.colorbar(ScalarMappable(norm=cl.norm, cmap=cl.cmap), cax=cax, orientation="horizontal")
            cb.outline.set_edgecolor("white")
            cb.outline.set_linewidth(0.8 * fs)
            cax.tick_params(colors="white", labelsize=14 * fs, length=4 * fs, width=0.8 * fs)
            cax.set_title(cbar_label(quantities[0], cl), color="white", fontsize=16 * fs, pad=6 * fs)
            self.cax = cax
        if not a.no_text:
            self.cap1 = ax.text(0.025, 0.125, "", transform=ax.transAxes, ha="left", va="bottom", color="white",
                                fontsize=34 * fs, weight="bold", bbox=box, zorder=8)
            self.cap2 = ax.text(0.025, 0.105, "", transform=ax.transAxes, ha="left", va="top", color="0.92",
                                fontsize=20 * fs, bbox=box, zorder=8)
            ax.text(0.02, 0.97, "EOS26", transform=ax.transAxes, ha="left", va="top", color="white",
                    fontsize=34 * fs, weight="bold", family="serif", bbox=box, zorder=8)
            ql = (SPEC.get(quantities[0], (quantities[0],))[0] if len(quantities) == 1 else "")
            self.info = ax.text(0.02, 0.895, " · ".join(t for t in (ql, f"z = {sl.z:.2f} ({sl.nu:.0f} MHz)") if t),
                                transform=ax.transAxes, ha="left", va="top", color="0.9", fontsize=17 * fs, bbox=box,
                                zorder=8)
            self.epoch = ax.text(0.02, 0.84, "", transform=ax.transAxes, ha="left", va="top", color="#ffd27a",
                                 fontsize=17 * fs, bbox=box, zorder=8)
            self.epoch.set_visible(False)
            self.sb_line = Line2D([], [], color="white", lw=3.5 * fs, transform=ax.transAxes,
                                  solid_capstyle="butt", zorder=8)
            ax.add_line(self.sb_line)
            self.sb_text = ax.text(0, 0, "", transform=ax.transAxes, ha="center", va="bottom", color="white",
                                   fontsize=16 * fs, path_effects=outlined(2.5 * fs, alpha=0.6), zorder=8)
            if sl.watermark:
                ax.text(0.5, 0.012, sl.watermark, transform=ax.transAxes, ha="center", va="bottom",
                        color="#ff6b6b", fontsize=13 * fs, bbox=dict(box, alpha=0.5), zorder=8)
            self.qtexts = []
            if len(quantities) > 1:
                self.qtexts = [ax.text(0, 0, SPEC.get(q, (q,))[0], transform=ax.transAxes, ha="center",
                                       va="center", color="white", fontsize=17 * fs, bbox=box, zorder=8)
                               for q in quantities]

    def text_alpha(self, t, al):
        """Fade a text and its box together (1: as drawn)."""
        bp = t.get_bbox_patch()
        if not hasattr(self, "_box_alpha"):
            self._box_alpha = {}
        if bp is not None and id(t) not in self._box_alpha:
            self._box_alpha[id(t)] = bp.get_alpha()
        t.set_alpha(al)
        if bp is not None:
            base = self._box_alpha[id(t)]
            bp.set_alpha((1.0 if base is None else base) * al if al < 1 else base)

    def keys_alpha(self, al, legend=None):
        """Fade the colour bar (al) and the galaxy legend (legend, default al); 1: as drawn."""
        if not hasattr(self, "_key_arts"):  # the artists and their own alphas, once
            cbar = []
            if getattr(self, "cax", None) is not None:
                cax = self.cax
                cbar = [cax.patch, cax.title] + list(cax.get_children()) + cax.get_xticklabels()
            if getattr(self, "cbar_bg", None) is not None:
                cbar.append(self.cbar_bg)
            self._key_arts = [(art, art.get_alpha(), False) for art in cbar] + \
                [(art, art.get_alpha(), True) for art in self.legend_artists]
        for art, base, is_legend in self._key_arts:
            f = (al if legend is None else legend) if is_legend else al
            try:
                art.set_alpha((1.0 if base is None else base) * f if f < 1 else base)
            except Exception:  # noqa: BLE001  (artists without alpha)
                pass

    def show_keys(self, on):
        """Colour bar and galaxy legend (hidden while the cube shows another quantity)."""
        for art in self.legend_artists + [getattr(self, "cbar_bg", None), getattr(self, "cax", None)]:
            if art is not None:
                art.set_visible(on)

    def set_caption(self, cap, alpha):
        if self.a.no_text:
            return
        if cap is not None:
            t1, t2 = (self.stops[cap].title, self.stops[cap].sub) if isinstance(cap, int) else cap
            self.cap1.set_text(t1)
            self.cap2.set_text(t2)
        for t in (self.cap1, self.cap2):
            t.set_alpha(alpha)
            t.get_bbox_patch().set_alpha(0.55 * alpha)
            t.set_visible(alpha > 0.01)

    def draw_cube(self, azim, elev, side, cap=None, alpha=0.0, centre=None):
        """RGBA buffer of an intro frame: the textured cube (edge `side` pixels) seen from (azim, elev)."""
        sl, ax, W, H = self.sl, self.ax, self.W, self.H
        if self.cube_tex is None:
            q = getattr(self, "cube_q", self.q[0])
            col = getattr(self, "cube_colourer", None) or self.colourers[q]
            self.cube_tex = cube_textures(sl, q, col, size=int(1.1 * H))
        rgb, segs = render_cube(self.cube_tex, W, H, azim, elev, side, centre)
        self.im.set_data(rgb[::-1])
        self.im.set_extent((0, W, 0, H))
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        self.cube_edges.set_segments([[(x0, H - y0), (x1, H - y1)] for (x0, y0), (x1, y1) in segs])
        self.cube_edges.set_visible(True)
        for art in self._overlays():
            art.set_visible(False)
        for t in getattr(self, "qtexts", []):  # sector names: only once the sectors are on screen
            t.set_visible(False)
        self.set_caption(cap, alpha)
        self.fig.canvas.draw()
        return np.asarray(self.fig.canvas.buffer_rgba()).copy()

    def draw_footprints(self, x0, y0, w, h, ov):
        """The FOOTPRINTS outlines at the frame's redshift, with the gate circ_alpha["_fp"] (0..1)."""
        if self.a.footprints == "none":
            gate = 0.0
        elif self.circ_alpha is None:  # figure-like frames (--fixed-z): only with --footprints on
            gate = 1.0 if self.a.footprints == "on" else 0.0
        else:  # the evolving movie: set per frame by plan_evolve
            gate = self.circ_alpha.get("_fp", 0.0)
        z = self.zcur if self.zcur is not None else self.sl.z
        big = max(w, h)
        if self.angular:
            to_data = lambda deg: 2 * np.sin(np.radians(deg) / 2)  # noqa: E731
        else:
            k = np.radians(1.0) * float(self.sl.cosmo.comoving_distance(z).to_value("Mpc"))
            to_data = lambda deg: deg * k  # noqa: E731
        cx, cy = self.C
        for entry, casing, line, lab, i in self.fp:
            members = footprint_members(entry, z, 0.15)
            if not members or gate <= 0 or ov <= 0:
                for art in (casing, line, lab):
                    art.set_visible(False)
                continue
            zf = max(float(np.clip(min(z - m[2] + 0.15, m[3] + 0.15 - z) / 0.15, 0, 1)) for m in members)
            wd, hd = (to_data(v) for v in footprint_size(entry))
            side = max(wd, hd)
            # in while larger than ~10 % of the frame; out once it no longer fits (its name would be outside)
            fit = w if entry[0] == "rect" else h
            fade_in = float(np.clip((side / big - 0.06) / 0.06, 0, 1))
            fade_out = float(np.clip((1.05 * fit - side) / (0.25 * fit), 0, 1))
            al = gate * ov * zf * fade_in * fade_out
            if entry[0] == "circle":
                for art in (casing, line):
                    art.set_center((cx, cy))
                    art.set_radius(wd / 2)
                t = np.radians(125)
                lx, ly, ha, va = cx + wd / 2 * np.cos(t), cy + wd / 2 * np.sin(t), "right", "bottom"
            else:
                for art in (casing, line):
                    art.set_xy((cx - wd / 2, cy - hd / 2))
                    art.set_width(wd)
                    art.set_height(hd)
                pad = 0.012 * h
                if entry[0] == "rect":  # a line scan: name above its left end
                    lx, ly, ha, va = cx - wd / 2, cy + hd / 2 + pad, "left", "bottom"
                elif entry[-1] == "br":  # corners chosen so that nested names do not collide
                    lx, ly, ha, va = cx + wd / 2 - pad, cy - hd / 2 + pad, "right", "bottom"
                else:
                    lx, ly, ha, va = cx - wd / 2 + pad, cy + hd / 2 - pad, "left", "top"
            for art in (casing, line):
                art.set_visible(al > 0.02)
                art.set_alpha(al * (0.45 if art is casing else 1.0))
            lab.set_text(" · ".join(m[0] for m in members))
            lab.set_position((lx, ly))
            lab.set_ha(ha)
            lab.set_va(va)
            fx, fy = (lx - x0) / w, (ly - y0) / h
            # not off the frame, nor on the title, the info lines, the colour bar and legend, or the caption
            blocked = ((fx < 0.13 and fy > 0.88) or (fx < 0.3 and 0.78 < fy < 0.92) or (fx > 0.72 and fy > 0.62)
                       or (fx < 0.75 and fy < 0.2))
            inside = 0.01 < fx < 0.99 and 0.04 < fy < 0.98 and not blocked
            lab.set_visible(al > 0.3 and inside and not self.a.no_text)
            lab.set_alpha(min(1.0, al))

    def _overlays(self):
        arts = [self.box_edge, self.grid]
        for casing, line, lab, r in self.circ.values():
            arts += [casing, line, lab]
        for _, casing, line, lab, _ in self.fp:
            arts += [casing, line, lab]
        arts += [art for _, art, _ in self.marks]
        if self.gal is not None:
            arts.append(self.g_art)
            if self.a.galaxies == "virial":
                arts.append(self.h_glow)
        if not self.a.no_text:
            arts += [self.sb_line, self.sb_text]
        return arts

    def draw(self, h, cen, cap=None, alpha=0.0, spin=0.0, ov=1.0, mix=None):
        """RGBA buffer (H, W, 4) of one frame: height h [cMpc] centred on cen; ov fades the overlays. mix = (w, fn,
        mode): the background shifts to fn(xs, ys, cen) (RGB) by w (0..1), everywhere ('fade') or behind a soft
        front sweeping out from the centre ('sweep'); the overlays are drawn once on top."""
        sl, a, ax, W, H, fs = self.sl, self.a, self.ax, self.W, self.H, self.fs
        self.cube_edges.set_visible(False)
        w = h * W / H
        x0, y0 = cen[0] - w / 2, cen[1] - h / 2
        xs = x0 + (np.arange(W) + 0.5) * (w / W)
        ys = y0 + (np.arange(H) + 0.5) * (h / H)
        rgb = render_rgb(sl, self.colourers, self.sampler, self.q, xs, ys, cen, spin=spin, box_mask=not self.angular,
                         hole=a.black_centre if len(self.q) > 1 else 0.0)
        if self.angular:
            rgb[~self.sampler.mask] = 0
        if mix is not None and mix[0] > 0:
            w_, fn, mode = mix
            rgb2 = fn(xs, ys, cen).astype(np.float32)
            if mode == "sweep":
                e = 0.35  # width of the soft front, in units of the half-diagonal
                gx, gy = np.meshgrid(np.arange(W) + 0.5 - W / 2, np.arange(H) + 0.5 - H / 2)
                u = np.hypot(gx, gy) / np.hypot(W / 2, H / 2)
                wt = np.clip((w_ * (1 + e) - e / 2 - u) / e + 0.5, 0, 1)[..., None]
            else:
                wt = w_
            rgb = np.clip(rgb.astype(np.float32) * (1 - wt) + rgb2 * wt, 0, 255).astype(np.uint8)
        self.im.set_data(rgb)
        self.im.set_extent((x0, x0 + w, y0, y0 + h))
        ax.set_xlim(x0, x0 + w)
        ax.set_ylim(y0, y0 + h)
        pxs = h / H  # cMpc per pixel
        self.box_edge.set_visible(w > 0.5 * sl.L and ov > 0.01 and not self.angular)
        self.box_edge.set_alpha(ov)
        cpx = sl.cell / pxs  # pixels per cell
        if a.cell_grid and cpx > 25 and not self.angular:
            c = sl.cell
            gx = np.arange(np.floor(x0 / c), np.ceil((x0 + w) / c) + 1) * c
            gy = np.arange(np.floor(y0 / c), np.ceil((y0 + h) / c) + 1) * c
            segs = [[(x, y0), (x, y0 + h)] for x in gx] + [[(x0, y), (x0 + w, y)] for y in gy]
            self.grid.set_segments(segs)
            self.grid.set_alpha(0.45 * min(1.0, (cpx - 25) / 40))
            self.grid.set_visible(True)
        else:
            self.grid.set_visible(False)
        big = max(w, h)
        for n, (casing, line, lab, r) in self.circ.items():
            band = 1.0
            if self.zcur is not None:
                nu = NU21 / (1 + self.zcur)
                if self.angular:
                    r = np.sin(np.radians(self.deg150[n] * 150 / nu) / 2)
                else:
                    r = sl.fov_at(self.deg150[n], self.zcur) / 2
                casing.set_radius(r)
                line.set_radius(r)
                lo, hi = BANDS[n]  # MHz
                band = float(np.clip((nu - lo) / 4, 0, 1) * np.clip((hi - nu) / 4, 0, 1))
                if self.circ_alpha is not None:
                    band *= self.circ_alpha.get(n, 0.0)
            fade_out = 1.0 if r < 0.75 * big else max(0.0, 1 - (r - 0.75 * big) / (0.85 * big))
            fade_in = np.clip((r / pxs - 6) / 20, 0, 1)  # a few pixels: gone
            al = fade_out * fade_in * ov * band
            for art in (casing, line):
                art.set_visible(al > 0.02)
                art.set_alpha(al * (0.45 if art is casing else 1.0))
            t = np.radians(LABEL_ANGLE.get(n, 45))
            lx, ly = self.C[0] + r * np.cos(t), self.C[1] + r * np.sin(t)
            fx, fy = (lx - x0) / w, (ly - y0) / h
            inside = 0.03 < fx < 0.88 and 0.05 < fy < 0.85 and not (fy < 0.2 and fx < 0.5)  # not on the caption
            lab.set_position((lx + 8 * pxs * np.sign(np.cos(t)), ly + 8 * pxs * np.sign(np.sin(t))))
            lab.set_ha("left" if np.cos(t) >= 0 else "right")
            lab.set_va("bottom" if np.sin(t) >= 0 else "top")
            lab.set_visible(al > 0.3 and inside and not a.no_text and r > 40 * pxs)
        self.draw_footprints(x0, y0, w, h, ov)
        for s, art, size in self.marks:
            on = cap is not None and self.stops[cap] is s
            art.set_visible(s.h * 0.3 < h < s.h * 4 and size > 3 * pxs and ov > 0.01)
            art.set_alpha((1.0 if on else 0.5) * ov)
        if self.gal is not None:
            g = self.gal
            m = (g["x"] > x0 - 1) & (g["x"] < x0 + w + 1) & (g["y"] > y0 - 1) & (g["y"] < y0 + h + 1)
            idx = np.flatnonzero(m)  # sorted brightest first
            if a.galaxies == "rings":
                if self.gal_local:
                    # the brightest in the frame (galaxies near the slice plane of this frame only)
                    sel = idx[: int(self.gal_n)]
                    mlim = g["muv"][sel[-1]] if len(sel) == int(self.gal_n) and len(sel) else np.inf
                    fade = np.clip((mlim - g["muv"][sel]) / 0.25, 0, 1) if np.isfinite(mlim) else np.ones(len(sel))
                    fade = fade * g["w"][sel]
                else:
                    # keep the brightest: a magnitude limit set by the view's area, faded over 0.25 mag,
                    # so that fainter galaxies appear smoothly while zooming in
                    area = min(w, sl.L) * min(h, sl.L)
                    k = int(self.gal_n * sl.L**2 / max(area, 1e-9))
                    mlim = g["muv"][min(k, len(g["muv"]) - 1)] if k < len(g["muv"]) else np.inf
                    sel = idx[g["muv"][idx] < mlim]
                    fade = np.clip((mlim - g["muv"][sel]) / 0.25, 0, 1) if np.isfinite(mlim) else np.ones(len(sel))
                r = ring_px(g["muv"][sel], fs)
                self.g_art.set_offsets(np.c_[g["x"][sel], g["y"][sel]])
                self.g_art.set_sizes((2 * r * 0.72) ** 2)
                self.g_art.set_edgecolor(np.c_[np.tile(RING_RGB, (len(sel), 1)), fade * ov])
                self.g_art.set_visible(True)
            else:
                dpx = 2 * g["rv"][idx] / pxs  # diameter in pixels
                sel = idx[dpx > 0.8]
                dpx = 2 * g["rv"][sel] / pxs
                d = np.maximum(dpx, 1.5) * 0.72
                fade = np.clip((dpx - 0.8) / 2.5, 0, 1)
                pts = np.c_[g["x"][sel], g["y"][sel]]
                self.g_art.set_offsets(pts)
                self.g_art.set_sizes(d**2)
                self.g_art.set_facecolor(np.c_[np.tile([1.0, 0.957, 0.84], (len(d), 1)), fade * ov])
                self.g_art.set_edgecolor(np.c_[np.tile([0.48, 0.24, 0.0], (len(d), 1)), fade * 0.8 * ov])
                self.g_art.set_visible(True)
                self.h_glow.set_visible(True)
                self.h_glow.set_offsets(pts)
                self.h_glow.set_sizes((d * 2.6) ** 2)
                self.h_glow.set_facecolor(np.c_[np.tile([1.0, 0.70, 0.28], (len(d), 1)), fade * 0.3 * ov])
        if not a.no_text:
            self.set_caption(cap, alpha)
            self.sb_line.set_visible(ov > 0.01)
            self.sb_text.set_visible(ov > 0.01)
            self.sb_line.set_alpha(ov)
            self.sb_text.set_alpha(ov)
            if self.angular:
                a_deg = nice_length(np.degrees(0.15 * w))
                frac = np.radians(a_deg) / w
                d_ = float(sl.cosmo.comoving_distance(self.zcur).to_value("Mpc")) if self.zcur else sl.Dc
                sb_label = f"{fmt_angle(a_deg)} ≈ {fmt_len(round(np.radians(a_deg) * d_, -1) if np.radians(a_deg) * d_ > 30 else round(np.radians(a_deg) * d_, 1))}"
                on = w < 1.2
                self.sb_line.set_visible(on and ov > 0.01)
                self.sb_text.set_visible(on and ov > 0.01)
            else:
                lw_ = nice_length(0.15 * w)
                frac = lw_ / w
                d_ = float(sl.cosmo.comoving_distance(self.zcur).to_value("Mpc")) if self.zcur else sl.Dc
                sb_label = f"{fmt_len(lw_)} ≈ {fmt_angle(np.degrees(lw_ / d_))}"
            self.sb_line.set_data([0.975 - frac, 0.975], [0.05, 0.05])
            self.sb_text.set_position((0.975 - frac / 2, 0.064))
            self.sb_text.set_text(sb_label)
            n = len(self.qtexts)
            for i, tq in enumerate(self.qtexts):
                tq.set_visible(len(self.q) > 1)  # not while the intro shows one quantity
                mid = np.radians(i * 360 / n + 180 / n + spin)
                sx, sy = np.sin(mid), np.cos(mid)
                k = min(0.38 * W / max(abs(sx), 1e-9), 0.30 * H / max(abs(sy), 1e-9))  # pixels
                tq.set_position((0.5 + k * sx / W, 0.5 + k * sy / H))
        self.fig.canvas.draw()
        return np.asarray(self.fig.canvas.buffer_rgba())


# where the FoV names sit on their circles in the movie [deg, counter-clockwise from +x]
LABEL_ANGLE = {"MWA": 215, "HERA": 40, "LOFAR": 18, "SKA-Low": 158}


def setup_movie(sl, a, quantities):
    L = sl.L
    bc, rin, req, mask = find_bubble(sl, a.centre or (L / 2, L / 2), a.bubble_size, a.bubble_search)
    galaxy = find_galaxy(sl, mask)
    C = tuple(a.centre) if a.centre else bc
    stops = plan_stops(sl, a, C, (bc, rin, req), galaxy, sectors=len(quantities) > 1)
    intro = a.intro == "cube" and quantities[0] in sl.cube
    if a.intro == "cube" and not intro:
        log.warning(f"no coeval faces of {quantities[0]}: no cube intro")
    if intro and stops[0].name == "box":
        stops[0].title = f"A slice at {sl.nu:.0f} MHz"
        stops[0].sub = f"z = {sl.z:.2f} · circles: fields of view of 21-cm telescopes"
    frames = []
    if intro:
        frames = intro_frames(sl, a, stops[0])
    zoom = timeline(stops, a)
    if intro:
        # the overlays (circles, galaxies, scale bar) fade in once the cube has turned into the slice
        nx, nf = int(0.5 * a.fps), int(0.8 * a.fps)
        last = frames[-1]
        for i in range(nx):
            frames.append(("blend", (i + 1) / (nx + 1), last, ("zoom",) + zoom[0][:4] + (0.0,)))
        for i, f in enumerate(zoom):
            ov = 1.0 if i >= nf else i / nf
            frames.append(("zoom",) + f[:4] + (ov,))
    else:
        frames = [("zoom",) + f[:4] + (1.0,) for f in zoom]
    log.info(f"{len(stops)} stops, {len(frames)} frames ({len(frames) / a.fps:.1f} s)")
    return C, stops, frames


def intro_frames(sl, a, first):
    """The cube turns (azimuth -200 -> 0 deg, elevation 28 -> 0 deg) and grows until its front face is
    the box of the first stop."""
    n = max(2, int(a.intro_seconds * a.fps))
    W, H = a.W, a.H
    s1 = H * sl.L / first.h
    cx = W / 2 + (sl.L / 2 - first.centre[0]) * H / first.h
    cy = H / 2 - (sl.L / 2 - first.centre[1]) * H / first.h
    s0 = 0.42 * H
    ease = lambda u: u * u * (3 - 2 * u)  # noqa: E731
    cap = ("EOS26 simulation box", f"{sl.L / 1000:g} cGpc · {sl.N}³ cells of {sl.cell:.3g} cMpc · z = {sl.z:.2f}")
    out = []
    hold = int(0.4 * a.fps)  # a still front view at the end
    for i in range(n):
        t = min(i / (n - 1 - hold), 1.0)
        azim = -200 * (1 - t) ** 2.2
        elev = 28 * (1 - ease(np.clip((t - 0.3) / 0.7, 0, 1)))
        g = ease(np.clip((t - 0.4) / 0.6, 0, 1))
        side = s0 + (s1 - s0) * g
        centre = (W / 2 + (cx - W / 2) * g, H / 2 + (cy - H / 2) * g)
        tt = i / a.fps
        al = float(np.clip(min((tt - 0.3) / 0.4, (n / a.fps - 0.2 - tt) / 0.4), 0, 1))
        out.append(("cube", azim, elev, side, centre, cap, al))
    return out


def draw_frame(R, f, spin, cache):
    if f[0] == "cube":
        _, azim, elev, side, centre, cap, al = f
        key = (azim, elev, side, centre, al)
        if cache.get("key") != key:
            cache["key"], cache["buf"] = key, R.draw_cube(azim, elev, side, cap, al, centre=centre)
        return cache["buf"]
    if f[0] == "blend":
        _, w, cube, zoom = f
        b0 = draw_frame(R, cube, spin, cache)
        b1 = R.draw(*zoom[1:5], spin=spin, ov=zoom[5])
        return ((1 - w) * b0.astype(np.float32) + w * b1.astype(np.float32)).astype(np.uint8)
    _, h, cen, cap, al, ov = f
    return R.draw(h, cen, cap, al, spin=spin, ov=ov)


def make_movie(sl, a, quantities, out, stills=False):
    C, stops, frames = setup_movie(sl, a, quantities)
    R = Renderer(sl, a, quantities, C, stops)
    nfr = len(frames)
    cache = {}
    if stills:
        todo, seen = [], set()
        cube = [i for i, f in enumerate(frames) if f[0] == "cube"]
        if cube:
            todo += [cube[0], cube[len(cube) // 3], cube[2 * len(cube) // 3], cube[-1]]
        for i, f in enumerate(frames):  # the middle of each stop, and the last frame
            if f[0] == "zoom" and f[3] is not None and f[3] not in seen and f[4] >= 0.999:
                seen.add(f[3])
                todo.append(min(i + int(0.3 * a.fps), nfr - 1))
        todo.append(nfr - 1)
        for fi in todo:
            buf = draw_frame(R, frames[fi], a.spin * fi / max(nfr - 1, 1), cache)
            p = Path(out).with_name(f"{Path(out).stem}_f{fi:04d}.png")
            R.plt.imsave(p, buf[..., :3])
            log.info(f"wrote {p.name} ({frames[fi][0]})")
        return
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            sys.exit("no ffmpeg: module load ffmpeg, or pip install imageio-ffmpeg, or --save-slice and render elsewhere")
    ff = subprocess.Popen(
        [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{a.W}x{a.H}",
         "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    t0 = time.time()
    for fi, f in enumerate(frames):
        ff.stdin.write(draw_frame(R, f, a.spin * fi / max(nfr - 1, 1), cache).tobytes())
        if fi % 150 == 0:
            log.info(f"frame {fi}/{nfr}  {time.time() - t0:.0f} s")
    ff.stdin.close()
    ff.wait()
    log.info(f"wrote {out} ({nfr} frames, {nfr / a.fps:.1f} s) in {time.time() - t0:.0f} s")


# ====================================================================== the ending (--outro turn)
def outro_zoom(last, h1, c1, a):
    """Frames (as `last`, ["lc", s, h, centre, caption, caption alpha, overlay alpha, circle alphas]) that zoom
    out from the last frame to height h1 centred on c1 in 2.5 s, about the point that stays put on screen;
    the overlays fade out over the first 40 %, the caption over the first 0.5 s."""
    ease = lambda u: u * u * (3 - 2 * u)  # noqa: E731
    _, s, h0, c0, cap, al0, ov0, ca = last
    n = int(round(2.5 * a.fps))
    c0, c1 = np.array(c0, float), np.array(c1, float)
    P = c1 if np.isclose(h0, h1) else (c0 * h1 - c1 * h0) / (h1 - h0)
    out = []
    for i in range(1, n + 1):
        t = i / n
        h = float(np.exp(np.log(h0) + ease(t) * (np.log(h1) - np.log(h0))))
        cen = c0 + ease(t) * (c1 - c0) if np.isclose(h0, h1) else P + (c0 - P) * h / h0
        al = al0 * max(0.0, 1 - (i / a.fps) / 0.5)
        out.append(["lc", s, h, tuple(cen), cap if al > 0 else None, al, ov0 * (1 - ease(min(t / 0.4, 1.0))), ca])
    return out


def outro_turn(a, n_hold=None):
    """(t, azimuth [deg], elevation [deg], shrink 0..1, caption alpha) of the turning finished box: from
    face-on, turning on the way the intro turned, tilting up and shrinking, then at rest (last 0.8 s)."""
    ease = lambda u: u * u * (3 - 2 * u)  # noqa: E731
    n = max(2, int(round(a.outro_seconds * a.fps)))
    hold = int(round(0.8 * a.fps)) if n_hold is None else n_hold
    out = []
    for i in range(n):
        t = min(i / max(n - 1 - hold, 1), 1.0)
        tt = i / a.fps
        out.append((t, 200.0 * ease(t), 28.0 * ease(min(t / 0.7, 1.0)), ease(min(t / 0.6, 1.0)),
                    float(np.clip((tt - 0.4) / 0.4, 0, 1))))
    return out


# ====================================================================== the evolving movie
class Lightcone:
    """The rect lightcone stores of a run, read one block of slices (one chunk deep) at a time."""

    def __init__(self, lc_dir, quantities, extra=("brightness_temp", "neutral_fraction", "sfrd_acg")):
        import h5py
        self.dir = Path(lc_dir)
        self.f, self.q = {}, []
        for q in list(quantities) + [e for e in extra if e not in quantities]:
            path = self.dir / f"{STORE.get(q, q)}.h5"
            if not path.exists() and q in FALLBACK:
                log.warning(f"no {path.name}: using {FALLBACK[q]}")
                path = self.dir / f"{FALLBACK[q]}.h5"
            if not path.exists():
                if q in quantities:
                    sys.exit(f"no {path}")
                continue
            self.f[q] = h5py.File(path, "r")
            self.q.append(q)
        first = self.f[self.q[0]]
        ds = first["lightcone"]
        self.N, self.ns = ds.shape[0], ds.shape[2]
        self.blk = ds.chunks[2] if ds.chunks else 32
        self.z = first["lightcone_redshifts"][()]
        self.dist = first["lightcone_distances"][()]
        self.nodes = first["node_redshifts"][()] if "node_redshifts" in first else None
        self.cache = {}

    def has(self, q):
        return q in self.f

    def slice(self, q, k):
        """Slice k of quantity q as [y, x]."""
        k = int(min(max(k, 0), self.ns - 1))
        b = k // self.blk
        key = (q, b)
        if key not in self.cache:
            mine = [kk for kk in self.cache if kk[0] == q]
            for kk in mine[:-1]:  # keep the last block read (frames step through neighbouring blocks)
                del self.cache[kk]
            t = time.time()
            self.cache[key] = self.f[q]["lightcone"][:, :, b * self.blk:(b + 1) * self.blk]
            log.debug(f"{q}: block {b} read in {time.time() - t:.1f} s")
        return self.cache[key][:, :, k - b * self.blk].T

    def at(self, q, s):
        """Quantity q at fractional slice s (linear between the two slices)."""
        k0 = int(np.floor(s))
        f = s - k0
        a0 = self.slice(q, k0)
        if f < 1e-4 or k0 + 1 >= self.ns:
            return np.asarray(a0, np.float32)
        return ((1 - f) * a0 + f * self.slice(q, k0 + 1)).astype(np.float32)

    def over(self, q, s, ds):
        """Mean of q over the slices from s - ds/2 to s + ds/2 (motion blur where a frame passes many
        slices), else the slice at s."""
        if ds <= 1.5:
            return self.at(q, s)
        k0, k1 = int(np.ceil(s - ds / 2)), int(np.floor(s + ds / 2))
        ks = np.unique(np.clip(np.linspace(k0, k1, min(k1 - k0 + 1, 16)).round().astype(int), 0, self.ns - 1))
        acc = np.zeros_like(self.slice(q, ks[0]), dtype=np.float32)
        for k in ks:
            acc += self.slice(q, k)
        return acc / len(ks)

    def k_of_z(self, z):
        return float(np.interp(z, self.z, np.arange(self.ns)))

    def z_of_k(self, s):
        return float(np.interp(s, np.arange(self.ns), self.z))

    def plane_cmpc(self, s, cell):
        """Position [cMpc] along the box's third axis of the plane of fractional slice s."""
        k0 = int(np.floor(s))
        p = rect_plane(self.dist, k0, cell, self.N) + (s - k0)
        return ((p + 0.5) * cell) % (self.N * cell)

    def global_mean(self, q):
        """(node redshifts, mean of the quantity's box) where read, or None."""
        if q not in self.f or "global_mean" not in self.f[q] or self.nodes is None:
            return None
        g = self.f[q]["global_mean"][()]
        ok = np.isfinite(g)
        if ok.sum() < 3:
            return None
        o = np.argsort(self.nodes[ok])
        return self.nodes[ok][o], g[ok][o]


class FieldSampler:
    """Samples per-frame fields (set with set_fields) on the pixel grid, prefiltered when zoomed out."""

    def __init__(self, cell, order=1):
        self.cell, self.order, self.fields, self._f = cell, order, {}, {}

    def set_fields(self, fields):
        self.fields, self._f = fields, {}

    def sample(self, q, xs, ys):
        from scipy import ndimage as ndi
        px = abs(xs[1] - xs[0]) / self.cell
        sig = round(0.5 * max(px - 1, 0), 1)
        if (q, sig) not in self._f:
            f = self.fields[q]
            self._f[(q, sig)] = ndi.gaussian_filter(f, sig, mode="wrap") if sig > 0.25 else f
        f = self._f[(q, sig)]
        Y, X = np.meshgrid(ys / self.cell - 0.5, xs / self.cell - 0.5, indexing="ij")
        return ndi.map_coordinates(f, [Y, X], order=0 if self.order == 0 and sig <= 0.25 else 1,
                                   mode="grid-wrap", prefilter=False)


def epochs_of(lc, z_end):
    """Epoch boundaries from the mean T_b and x_HI histories (None where not available)."""
    out = {"z_slow": None, "z_trough": None, "z_x90": None, "z_end": z_end}
    tb = lc.global_mean("brightness_temp")
    if tb is not None:
        zz, tt = tb
        zf = np.linspace(zz.min(), zz.max(), 4000)
        tf = np.interp(zf, zz, tt)
        if tf.min() < 0:
            out["z_trough"] = float(zf[np.argmin(tf)])
            above = zf > out["z_trough"]
            reached = above & (tf < 0.15 * tf.min())
            out["z_slow"] = float(zf[reached].max()) if reached.any() else None
    xh = lc.global_mean("neutral_fraction")
    if xh is not None:
        zz, xx = xh
        zf = np.linspace(zz.min(), zz.max(), 4000)
        xf = np.interp(zf, zz, xx)
        below = xf < 0.9
        out["z_x90"] = float(zf[below].max()) if below.any() else None
    return out


def epoch_label(z, ep, xhi=None):
    if ep["z_slow"] is not None and z > ep["z_slow"]:
        return "dark ages"
    if ep["z_trough"] is not None and z > ep["z_trough"]:
        return "cosmic dawn: Lyman-α coupling"
    if ep["z_x90"] is not None and z > ep["z_x90"]:
        return "cosmic dawn: X-ray heating"
    return "reionisation" + (f" · mean x$_{{\\rm HI}}$ = {xhi:.2f}" if xhi is not None else "")


def choose_target(lc, k_end, h_end, W, H, cell, L, search):
    """End point: a window of the last slice with ionised and neutral gas (neutral fraction near 0.4)
    and the most star formation, within `search` of the box centre."""
    from scipy import ndimage as ndi
    x = lc.at("neutral_fraction", k_end) if lc.has("neutral_fraction") else None
    sf = lc.at("sfrd_acg", k_end) if lc.has("sfrd_acg") else None
    n = lc.N
    size = (max(1, int(h_end / cell)), max(1, int(h_end * W / H / cell)))
    score = np.zeros((n, n), np.float32)
    if sf is not None:
        s_ = ndi.uniform_filter(sf.astype(np.float32), size, mode="wrap")
        score += s_ / max(float(s_.max()), 1e-30)
    if x is not None:
        score -= 2 * np.abs(ndi.uniform_filter(x.astype(np.float32), size, mode="wrap") - 0.4)
    yy, xx = np.indices((n, n))
    far = np.hypot((xx + 0.5) * cell - L / 2, (yy + 0.5) * cell - L / 2) > search
    score[far] = -np.inf
    iy, ix = np.unravel_index(np.argmax(score), score.shape)
    return float((ix + 0.5) * cell), float((iy + 0.5) * cell)


def plan_evolve(lc, a, sl, C, ep, size_of=None, h_start=None, h_end=None, centre_of=None, angle_size=None):
    """Frames of the evolution: ["lc", s, h, centre, caption, caption alpha, overlay alpha, circle alphas].
    With several quantities and no --end, the zoom ends at the last stop and keeps its field of view.

    Time: --seconds DARK DAWN EOR for z_start -> z_slow (absorption onset) -> the first stop -> z_end,
    joined smoothly (monotone cubic of the slice index against time). Zoom: h (frame height; cMpc for
    rect, sin units for the globe) from h_start through 1.12 x size_of(name, z) at each stop to h_end.
    A circle shows from 1.5 s before its stop on."""
    from scipy.interpolate import PchipInterpolator
    fps, L = a.fps, sl.L
    aspect = a.W / a.H
    z_start = min(a.z_start, float(lc.z.max()) - 1e-3)
    z_end = ep["z_end"]
    k_start, k_end = lc.k_of_z(z_start), lc.k_of_z(z_end)
    z_slow = a.z_slow if a.z_slow is not None else (ep["z_slow"] or 20.0)
    deg = {n: d for n, d, _ in INSTRUMENTS}
    if size_of is None:
        size_of = lambda name, z: sl.fov_at(deg[name], z)  # noqa: E731
    if angle_size is None:  # an angle [deg] at z in the frame's units (cMpc)
        angle_size = lambda d, z: np.radians(d) * float(sl.cosmo.comoving_distance(z).to_value("Mpc"))  # noqa: E731
    fov_size = size_of

    def survey_deg(z):  # the largest footprint in band at z, other than the circles [deg]
        sides = [max(footprint_size(e)) for e in FOOTPRINTS if e[0] != "circle" and footprint_members(e, z)]
        return max(sides) if sides else None

    def size_of(name, z):  # noqa: F811  (the stop "surveys" frames the largest footprint in band)
        if name == "surveys":
            d = survey_deg(z)
            return angle_size(d, z) if d else fov_size("SKA-Low", z)
        return fov_size(name, z)
    if h_start is None:
        h_start = L * 1.06 if aspect >= 1 else L * 1.06 / aspect
    h_end = a.end if h_end is None else h_end
    stops_req = []
    for spec in a.stops:
        name, zs_ = spec.split("=")
        zs_ = float(zs_)
        if name == "surveys":
            if not (z_end < zs_ < z_start) or a.footprints == "none" or survey_deg(zs_) is None:
                log.warning(f"stop {spec} skipped (outside z = {z_end:.1f}-{z_start:.1f}, no footprint in band, "
                            f"or --footprints none)")
                continue
            stops_req.append((name, zs_))
            continue
        lo, hi = BANDS[name]
        if not (z_end < zs_ < z_start) or not (lo <= NU21 / (1 + zs_) <= hi) or (name == "MWA" and not a.mwa):
            log.warning(f"stop {spec} skipped (outside z = {z_end:.1f}-{z_start:.1f}, its band, or MWA off)")
            continue
        stops_req.append((name, zs_))
    stops_req.sort(key=lambda v: -v[1])
    z_first = stops_req[0][1] if stops_req else (ep["z_x90"] or 0.5 * (z_slow + z_end))
    z_slow = max(min(z_slow, z_start - 0.5), z_first + 0.5)
    t_dark, t_dawn, t_eor = a.seconds
    ne = max(4, int(round((t_dark + t_dawn + t_eor) * fps)))
    tk = np.array([0.0, t_dark, t_dark + t_dawn, t_dark + t_dawn + t_eor])
    kk = np.array([k_start, lc.k_of_z(z_slow), lc.k_of_z(z_first), k_end])
    s_f = PchipInterpolator(tk, kk)(np.arange(ne) / fps * tk[-1] / ((ne - 1) / fps))
    z_f = np.interp(s_f, np.arange(lc.ns), lc.z)
    stops, nh, last = [], int(round(a.hold * fps)), -1
    for name, zs_ in stops_req:
        f0 = max(int(np.argmax(z_f <= zs_)), last + int(0.4 * fps))
        if f0 + nh >= ne - int(1.5 * fps):
            log.warning(f"stop {name} skipped (too close to the end)")
            continue
        stops.append((name, f0))
        last = f0 + nh
    hold, keys = {}, [(0, h_start)]
    for name, f0 in stops:
        for f in range(f0, f0 + nh):
            hold[f] = name
        keys.append((f0, 1.12 * size_of(name, z_f[f0])))
        keys.append((f0 + nh - 1, 1.12 * size_of(name, z_f[f0 + nh - 1])))
    keys.append((ne - 1, h_end))
    h_f = np.empty(ne)
    ease = lambda v: v * v * (3 - 2 * v)  # noqa: E731
    for (fa, ha), (fb, hb) in zip(keys[:-1], keys[1:]):
        for f in range(fa, fb + 1):
            v = ease((f - fa) / max(fb - fa, 1))
            h_f[f] = np.exp(np.log(ha) + v * (np.log(hb) - np.log(ha)))
    for f, name in hold.items():
        h_f[f] = 1.12 * size_of(name, z_f[f])
    if len(a.quantities) > 1 and not a.end_given and stops:
        # several quantities (sectors) and no --end: after the last stop the frame keeps that field of view
        name, f0 = stops[-1]
        for f in range(f0, ne):
            h_f[f] = 1.12 * size_of(name, z_f[f])
    first_stop = {n: f0 for n, f0 in stops}
    f1 = stops[0][1] if stops else ne // 3
    c0, c1 = np.array([L / 2, L / 2]), np.array(C)
    frames = []
    # captions: each stays --caption-seconds on screen (fade in 0.3 s, out 0.5 s), from its stop on, also
    # while the zoom moves on; a later caption takes over from an earlier one
    cap_s = max(a.caption_seconds, 1.0)
    cap_len = int(round(cap_s * fps))
    caps = [(0, ("The lightcone", f"from z = {z_start:.0f} to {z_end:.1f}, moving towards us through cosmic time"))]
    for name, f0 in stops:
        zz = z_f[f0]
        if name == "surveys":  # the footprints that fit the frame of this stop, by line
            hh = 1.12 * size_of(name, zz)
            by_line = {}
            for entry in FOOTPRINTS:
                sz = angle_size(max(footprint_size(entry)), zz)
                if 0.06 * hh <= sz <= hh * max(aspect, 1.0):
                    for nm, ln, _, _ in footprint_members(entry, zz):
                        by_line.setdefault(ln, []).append(nm)
            caps.append((f0, ("Galaxy surveys and line-intensity mapping",
                              f"z = {zz:.1f} · " + " · ".join(f"{ln}: {', '.join(nm)}" for ln, nm in by_line.items()))))
            continue
        D = sl.fov_at(deg[name], zz)
        size = f"{D / 1000:.2f} cGpc" if D >= 1000 else f"{D:.0f} cMpc"
        caps.append((f0, (f"{name} field of view", f"{fmt_angle(deg[name] * 150 * (1 + zz) / NU21)} at "
                                                   f"{NU21 / (1 + zz):.0f} MHz (z = {zz:.1f}) ≈ {size}")))
    # other surveys: with the stop "surveys" (fading in over the 1.5 s before it); without it, from the end of
    # the last stop's caption, with a caption of their own
    f_fp = None
    if a.footprints != "none" and "surveys" in dict(stops):
        f_fp = dict(stops)["surveys"]
    elif a.footprints != "none" and stops:
        f_fp = stops[-1][1] + cap_len
        zz = z_f[min(f_fp, ne - 1)]
        by_line = {}
        for entry in FOOTPRINTS:
            for name, line, z0, z1 in footprint_members(entry, zz):
                by_line.setdefault(line, []).append(name)
        if f_fp < ne - cap_len and by_line:
            caps.append((f_fp, ("Galaxy surveys and line-intensity mapping",
                                " · ".join(f"{ln}: {', '.join(nm)}" for ln, nm in by_line.items()))))
            caps.sort(key=lambda c: c[0])
        elif not by_line:
            f_fp = None
    ramp = 1.5 * fps
    for f in range(ne):
        cen = tuple(centre_of(f)) if centre_of else tuple(c0 + (c1 - c0) * ease(min(f / max(f1, 1), 1.0)))
        cap, al = None, 0.0
        for i, (fc, text) in enumerate(caps):
            nxt = caps[i + 1][0] if i + 1 < len(caps) else ne
            if fc <= f < min(fc + cap_len, nxt):
                t, t_end = (f - fc) / fps, min(cap_len, nxt - fc) / fps
                cap, al = text, min(1.0, t / 0.3, (t_end - t) / 0.5)
        ca = {n: (float(np.clip((f - (f0 - ramp)) / ramp, 0, 1)) if not a.all_circles else 1.0)
              for n, f0 in first_stop.items()}
        ca["_fp"] = float(np.clip((f - f_fp) / ramp + 1.0, 0, 1)) if f_fp is not None else 0.0
        frames.append(["lc", float(s_f[f]), float(h_f[f]), cen, cap, max(al, 0.0), 1.0, ca])
    ne_end = int(round(max(2 * a.hold, cap_s + 1.5) * fps))
    xh = lc.global_mean("neutral_fraction")
    xe = float(np.interp(z_end, *xh)) if xh is not None else None
    sub = f"z = {z_end:.1f}" + (f" · mean x$_{{\\rm HI}}$ = {xe:.2f}" if xe is not None else "")
    for f in range(ne_end):
        t = f / fps
        frames.append(["lc", float(s_f[-1]), float(h_f[-1]), frames[-1][3], ("End of reionisation", sub),
                       min(1.0, t / 0.3), 1.0, frames[-1][7]])
    log.info(f"evolution z = {z_start:.2f} -> {z_slow:.2f} -> {z_first:.2f} -> {z_end:.2f} in "
             f"{t_dark:g} + {t_dawn:g} + {t_eor:g} s; stops " + ", ".join(f"{n} at z = {z_f[f]:.2f}" for n, f in stops))
    return frames, z_start, z_end


def wrap_interval(lo, hi, L):
    """[lo, hi) on a periodic axis of length L, as intervals within [0, L)."""
    if hi - lo >= L:
        return [(0.0, L)]
    lo_, hi_ = lo % L, hi % L
    return [(lo_, hi_)] if lo_ <= hi_ else [(lo_, L), (0.0, hi_)]


def merge_intervals(iv):
    out = []
    for lo, hi in sorted(iv):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def in_intervals(v, iv):
    m = np.zeros(len(v), bool)
    for lo, hi in iv:
        m |= (v >= lo) & (v < hi)
    return m


def plan_galaxies(lc, frames, sl, a, slab):
    """Per node: the slab intervals (cMpc along the third axis) and the window the frames need."""
    L = sl.L
    need = {}
    nodes = np.asarray(sorted(lc.nodes)) if lc.nodes is not None else None
    for fr in frames:
        if fr[0] != "lc":
            continue
        s, h, cen = fr[1], fr[2], fr[3]
        z = lc.z_of_k(s)
        if z > a.galaxies_zmax + 0.5 or nodes is None:
            continue
        zn = float(nodes[np.argmin(np.abs(nodes - z))])
        w = h * a.W / a.H
        zc = lc.plane_cmpc(s, sl.cell)
        d = need.setdefault(zn, {"z": [], "win": [np.inf, -np.inf, np.inf, -np.inf]})
        d["z"].append(zc)
        win = d["win"]
        win[0], win[1] = min(win[0], cen[0] - w / 2), max(win[1], cen[0] + w / 2)
        win[2], win[3] = min(win[2], cen[1] - h / 2), max(win[3], cen[1] + h / 2)
    for zn, d in need.items():
        iv = []
        for zc in sorted(set(np.round(d["z"], 3))):
            iv += wrap_interval(zc - slab / 2, zc + slab / 2, L)
        w = d.pop("win")
        d["ivz"] = merge_intervals(iv)
        d["ivx"] = [(max(w[0], 0.0), min(w[1], L))]
        d["ivy"] = [(max(w[2], 0.0), min(w[3], L))]
        d.pop("z")
    return need


MOVIE_DIR = Path(__file__).resolve().parents[1] / "plots" / "movie"  # outputs/ and data/, not in git


def galaxy_cache(out):
    """The galaxies read for the movie `out`, kept for later runs: plots/movie/data/<movie>_galaxies/."""
    return MOVIE_DIR / "data" / f"{Path(out).stem}_galaxies"


def load_galaxies(need, path_of, cache_dir, block=20_000_000):
    """Read, for each node, the galaxies within its intervals along x, y, z from its PerturbedHaloCatalog
    (in blocks of rows), with a cache of the selection per node. Returns {node z: dict x, y, zc, muv}."""
    import h5py
    out = {}
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for zn, d in sorted(need.items()):
        path = path_of(zn)
        if path is None or not Path(path).exists():
            log.warning(f"no galaxy catalogue at z = {zn:.4f}")
            continue
        sig = repr((str(path), [[tuple(np.round(i, 2)) for i in d[k]] for k in ("ivx", "ivy", "ivz")]))
        cf = cache_dir / f"galaxies_z{zn:.4f}.npz"
        if cf.exists():
            c = np.load(cf)
            if str(c["sig"]) == sig:
                out[zn] = {k: c[k] for k in ("x", "y", "zc", "muv")}
                continue
        t = time.time()
        xs, ys, zcs, sfrs = [], [], [], []
        with h5py.File(path, "r") as h:
            g = h[next(iter(h))]["OutputFields"]
            nh = int(g.attrs.get("n_halos", g["halo_masses"].shape[0]))
            for i0 in range(0, nh, block):
                i1 = min(nh, i0 + block)
                c = g["halo_coords"][i0:i1]
                m = in_intervals(c[:, 0], d["ivx"]) & in_intervals(c[:, 1], d["ivy"]) & in_intervals(c[:, 2], d["ivz"])
                idx = np.flatnonzero(m)
                if not idx.size:
                    continue
                if "sfr_acg" in g:
                    sfr = g["sfr_acg"][i0:i1][idx].astype(np.float64)
                    if "sfr_mcg" in g:
                        sfr = sfr + g["sfr_mcg"][i0:i1][idx]
                    sfr *= 3.15576e7
                else:
                    sfr = 0.05 * (g["halo_masses"][i0:i1][idx] / 1e10) ** 1.5
                xs.append(c[idx, 0])
                ys.append(c[idx, 1])
                zcs.append(c[idx, 2])
                sfrs.append(sfr)
        cat = lambda v: np.concatenate(v) if v else np.zeros(0)  # noqa: E731
        sfr = cat(sfrs)
        with np.errstate(divide="ignore"):
            muv = 51.63 - 2.5 * np.log10(np.maximum(sfr, 1e-30) / 1.15e-28)
        o = np.argsort(muv)
        res = {"x": cat(xs)[o].astype(np.float32), "y": cat(ys)[o].astype(np.float32),
               "zc": cat(zcs)[o].astype(np.float32), "muv": muv[o].astype(np.float32)}
        np.savez(cf, sig=sig, **res)
        out[zn] = res
        log.info(f"galaxies of z = {zn:.4f}: {len(o)} of {nh} in {time.time() - t:.0f} s")
    return out


def make_evolve_movie(a, quantities, out=None, stills=False, plots=Path("plots"), qtag=""):
    """Zoom while moving through the lightcone in time (see the module docstring)."""
    if a.slice_file:
        sys.exit("the evolving movie reads the lightcones themselves: run it where they are, or use --fixed-z")
    sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
    sys.path.insert(1, str(Path(__file__).resolve().parent / "lightcone"))
    import eos_boxes as eb
    import eos_lightcones as el

    run = eb.Run(test=not a.production)
    lc_dir = Path(a.lightcone) if a.lightcone else el.default_out_dir(run.cache_dir) / "rect"
    lc = Lightcone(lc_dir, quantities)
    out = out or Path(plots) / f"fov_evolve_{run.tag}_{qtag}.mp4"
    cell = float(run.inputs.simulation_options.cell_size.to_value("Mpc"))
    cosmo = run.inputs.cosmo_params.cosmo
    xh = lc.global_mean("neutral_fraction")
    if a.z_end is not None:
        z_end = a.z_end
    elif xh is not None and (xh[1] < a.xhi_end).any():
        zz, xx = xh
        zf = np.linspace(zz.min(), zz.max(), 4000)
        z_end = float(zf[np.interp(zf, zz, xx) < a.xhi_end].max())
    else:
        z_end = 6.0
    z_end = max(z_end, float(lc.z.min()) + 1e-3)
    ep = epochs_of(lc, z_end)
    k_end = lc.k_of_z(z_end)
    fields_end = {q: lc.at(q, k_end) for q in quantities}
    sl = Slice(fields_end, cell, z_end, run.tag, None, cosmo)
    sl.watermark = a.watermark
    W, H = a.W, a.H
    C = tuple(a.centre) if a.centre else choose_target(lc, k_end, a.end, W, H, cell, sl.L, a.target_search)
    log.info(f"end point ({C[0]:.0f}, {C[1]:.0f}) cMpc at z = {z_end:.2f}; epochs {ep}")
    frames, z_start, z_end = plan_evolve(lc, a, sl, C, ep)
    # colour scales from slices along the way (the start, the absorption trough, the middle of the slow part, the end)
    zs_ = [z_start, z_end, 0.5 * (z_start + z_end)] + ([ep["z_trough"]] if ep["z_trough"] else [])
    sub = {}

    def values_at(q, z):  # every third cell of the slice at z (kept: each block is read once here)
        k = int(round(lc.k_of_z(z)))
        if (q, k) not in sub:
            sub[(q, k)] = lc.at(q, k)[::3, ::3].ravel()
        return sub[(q, k)]
    colourers = {q: Colourer(q, np.concatenate([values_at(q, z) for z in zs_]), a.vmin, a.vmax) for q in quantities}
    # with several quantities: ranges that follow z, from slices at 6 redshifts evenly spaced in log(1 + z)
    z_t = (1 + z_end) * ((1 + z_start) / (1 + z_end)) ** np.linspace(0, 1, 6) - 1
    moving = moving_scales(quantities, a, values_at, z_t)
    sub.clear()
    # galaxies
    slab = max(a.halo_slab, 2 * cell)
    gals = {}
    if a.halos and a.galaxies != "none":
        need = plan_galaxies(lc, frames, sl, a, slab)
        sys.path.insert(1, str(Path(__file__).resolve().parent / "galaxies"))
        import galaxy_properties as gp
        path_of = (lambda zn: gp.output_path(run.cache_dir, run.inputs, zn)) if a.halos == "auto" else \
            (lambda zn: Path(a.halos.format(z=zn)))
        gals = load_galaxies(need, path_of, galaxy_cache(out))
    gnodes = np.array(sorted(gals)) if gals else None
    # intro cube
    k_start = lc.k_of_z(z_start)
    if a.intro == "cube":
        # the initial density, else (or with --intro-quantity same) the shown quantity's first coeval
        plane = rect_plane(lc.dist, int(np.floor(k_start)), cell, lc.N)
        for iq in (["ics"] if a.intro_quantity == "ics" else []) + [quantities[0]]:
            try:
                faces = read_cube_faces(run, iq, z_start, plane, lc.N, with_front=(iq == "ics"))
                if iq != "ics":
                    faces["front"] = lc.at(quantities[0], k_start).T
                sl.cube[iq] = faces
                break
            except Exception as e:  # noqa: BLE001
                log.warning(f"no cube of {iq}: {e}")
    R = Renderer(sl, a, quantities, C, [], colourers=colourers, sampler=FieldSampler(cell, 0 if a.interp == "nearest" else 1),
                 dynamic_galaxies=bool(gals))
    allf = []
    if sl.cube:
        iq = next(iter(sl.cube))
        R.cube_q = iq
        R.cube_colourer = Colourer(iq, sl.cube[iq]["front"]) if iq == "ics" else colourers[quantities[0]]
        first = Stop("start", frames[0][2], frames[0][3], "")
        intro = intro_frames(sl, a, first)
        if iq == "ics":
            cap = ("Initial conditions", f"{sl.L / 1000:g} cGpc · {sl.N}³ cells of {sl.cell:.3g} cMpc")
        else:
            cap = ("EOS26 simulation box", f"{sl.L / 1000:g} cGpc · {sl.N}³ cells of {sl.cell:.3g} cMpc · z = {z_start:.0f}")
        intro = [f[:5] + (cap, f[6]) for f in intro]
        allf += intro
        nx, nf = int(0.5 * a.fps), int(0.8 * a.fps)
        for i in range(nx):
            fr = list(frames[0])
            fr[5], fr[6] = 0.0, 0.0
            allf.append(("blend", (i + 1) / (nx + 1), intro[-1], fr))
        for i, fr in enumerate(frames):
            if i < nf:
                fr[6] = i / nf
            allf.append(fr)
    else:
        allf = frames
    # the ending: zoom out to the box, then the finished box (the density at the last node) turns
    cubes = {R.cube_q: R.cube_colourer} if sl.cube else {}
    intro_key = R.cube_q if sl.cube else None
    z_fin = None
    if a.outro == "turn":
        z_fin = float(min(run.redshifts))
        try:
            plane_end = rect_plane(lc.dist, int(round(frames[-1][1])), cell, lc.N)
            faces = read_cube_faces(run, "density", z_fin, plane_end, lc.N, with_front=True)
            sl.cube["outro"] = faces
            cubes["outro"] = Colourer("density", faces["front"])
        except Exception as e:  # noqa: BLE001
            log.warning(f"no turning box at the end: {e}")
            z_fin = None
    n_main, marks = len(allf), []
    dens_sampler = None
    if z_fin is not None:
        # after the pause on the last frame: there the slice shifts into the finished density (the density of the
        # last node on the plane of the last slice) under the circles, galaxies and text (--outro-shift); then the
        # density zooms out to the whole box while those fade, becomes the cube's front face (0.3 s) and turns
        box_h = sl.L * 1.06 if W >= H else sl.L * 1.06 * H / W
        last = frames[-1]
        cap_l = last[4]
        cap_o = (f"EOS26 at z = {z_fin:.1f}", f"the matter density at the end of the simulation · {sl.L / 1000:g} cGpc"
                 f" · {sl.N}³ cells of {sl.cell:.3g} cMpc")
        dens_sampler = FieldSampler(cell, 0 if a.interp == "nearest" else 1)
        dens_sampler.set_fields({"density": np.ascontiguousarray(sl.cube["outro"]["front"].T)})  # [y, x]
        nsh = max(2, int(round(a.outro_shift_seconds * a.fps)))
        ease = lambda u: u * u * (3 - 2 * u)  # noqa: E731
        for i in range(1, nsh + 1):
            allf.append(("mix", ease(i / nsh), last))
        marks += [len(allf) - nsh // 2, len(allf) - 1]
        zo = outro_zoom(list(last[:4]) + [None, 0.0] + list(last[6:]), box_h, (sl.L / 2, sl.L / 2), a)
        n04, n05 = int(round(0.4 * a.fps)), int(round(0.5 * a.fps))
        for j, fr in enumerate(zo):  # the end caption fades out (0.4 s), then the new one fades in
            cap, al = (cap_l, 1 - (j + 1) / n04) if j < n04 else (cap_o, min(1.0, (j - n05) / n05) if j >= n05 else 0.0)
            allf.append(("dens", fr[2], fr[3], cap, max(al, 0.0), fr[6], fr[7]))
        marks += [len(allf) - len(zo) // 2, len(allf) - 1]
        s1, s0_ = H * sl.L / box_h, 0.42 * H
        face = ("ocube", 0.0, 0.0, s1, (W / 2, H / 2), cap_o, 1.0)
        nb = int(round(0.3 * a.fps))
        for i in range(nb):
            allf.append(("oblend", 1 - (i + 1) / (nb + 1), face,
                         ("dens", box_h, (sl.L / 2, sl.L / 2), cap_o, 1.0, 0.0, last[7])))
        turn = outro_turn(a)
        for _, az, elev, g, _al in turn:
            allf.append(("ocube", az, elev, s1 + (s0_ - s1) * g, (W / 2, H / 2), cap_o, 1.0))
        marks.append(len(allf) - len(turn) // 2)
    label = SPEC.get(quantities[0], (quantities[0],))[0] if len(quantities) == 1 else ""

    lcs = [f[1] for f in frames]
    step = np.abs(np.gradient(lcs)) if len(lcs) > 1 else np.zeros(1)
    step_of = {id(f): float(st) for f, st in zip(frames, step)}

    def dens_rgb(xs, ys, cen):  # the finished density (the background the ending shifts to)
        return render_rgb(sl, {"density": cubes["outro"]}, dens_sampler, ["density"], xs, ys, cen)

    def draw_lc(fr, spin, mix=None):
        _, s, h, cen, cap, al, ov, ca = fr
        R.circ_alpha = ca
        z = lc.z_of_k(s)
        R.sampler.set_fields({q: lc.over(q, s, step_of.get(id(fr), 0.0)) for q in quantities})
        for q, rng_of in moving.items():
            R.colourers[q].set_range(*rng_of(z))
        R.show_keys(True)
        R.zcur = z
        if gnodes is not None:
            g = None
            if z <= a.galaxies_zmax + 0.5:
                zn = float(gnodes[np.argmin(np.abs(gnodes - z))])
                g = gals[zn]
            if g is not None and len(g["x"]):
                zc = lc.plane_cmpc(s, cell)
                dz = np.abs((g["zc"] - zc + sl.L / 2) % sl.L - sl.L / 2)
                m = dz < slab / 2
                fade_z = float(np.clip((a.galaxies_zmax + 0.5 - z) / 1.0, 0, 1))
                R.gal = {"x": g["x"][m], "y": g["y"][m], "muv": g["muv"][m], "rv": np.zeros(m.sum()),
                         "w": (1 - (dz[m] / (slab / 2)) ** 2) * fade_z}
            else:
                R.gal = {k: np.zeros(0) for k in ("x", "y", "muv", "rv", "w")}
        if not a.no_text:
            age = float(cosmo.age(z).to_value("Myr"))
            R.info.set_text(" · ".join(t for t in (label, f"z = {z:.2f}", f"{NU21 / (1 + z):.0f} MHz",
                                                   f"{age:.0f} Myr") if t))
            xhi = float(np.interp(z, *xh)) if xh is not None and (ep["z_x90"] is None or z <= ep["z_x90"]) else None
            R.epoch.set_text(epoch_label(z, ep, xhi))
            R.epoch.set_visible(True)
        if mix is None:
            return R.draw(h, cen, cap, al, spin=spin, ov=ov)
        # the shift of the ending: the colour bar fades; the info lines fade out and, from half-way, back in for
        # the density
        w = mix[0]
        R.keys_alpha(1 - w, legend=1.0)
        if not a.no_text:
            R.text_alpha(R.info, abs(1 - 2 * w))
            R.text_alpha(R.epoch, max(0.0, 1 - 2 * w))
            if w > 0.5:
                R.info.set_text(f"matter density · z = {z_fin:.2f}")
        return R.draw(h, cen, cap, al, spin=spin, ov=ov, mix=mix)

    cache = {}

    def draw_dens(fr, spin):  # the finished density, zooming out from the end view while the overlays fade
        _, h, cen, cap, al, ov, ca = fr
        save = R.colourers, R.q, R.sampler
        R.colourers, R.q, R.sampler, R.circ_alpha = {"density": cubes["outro"]}, ["density"], dens_sampler, ca
        R.zcur = z_end  # circles and footprints keep the sizes of the last frame while they fade
        if not a.no_text:
            R.epoch.set_visible(False)
            R.info.set_text(f"matter density · z = {z_fin:.2f}")
        R.show_keys(ov > 0.01)
        R.keys_alpha(0.0, legend=ov)  # the colour bar is gone; the galaxy legend fades with the galaxies
        buf = R.draw(h, cen, cap, al, spin=spin, ov=ov)
        R.colourers, R.q, R.sampler = save
        return buf

    def use_cube(key):  # the intro cube or the finished box at the end
        if key is not None and getattr(R, "cube_q", None) != key:
            R.cube_q, R.cube_colourer, R.cube_tex = key, cubes[key], None
            cache.clear()

    def frame(fr, fi):
        spin = a.spin * fi / max(len(allf) - 1, 1)
        if not a.no_text:
            R.text_alpha(R.info, 1.0)
            R.text_alpha(R.epoch, 1.0)
        R.keys_alpha(1.0)
        if fr[0] == "mix":
            return draw_lc(fr[2], spin, mix=(fr[1], dens_rgb, a.outro_shift))
        if fr[0] == "dens":
            return draw_dens(fr, spin)
        if fr[0] == "ocube":
            use_cube("outro")
            if not a.no_text:
                R.epoch.set_visible(False)
                R.info.set_text(f"matter density · z = {z_fin:.2f}")
                R.show_keys(False)
            return draw_frame(R, ("cube",) + tuple(fr[1:]), spin, cache)
        if fr[0] == "oblend":  # (1 - w) * the cube + w * the density
            b1 = frame(fr[3], fi)
            b0 = frame(fr[2], fi)
            return ((1 - fr[1]) * b0.astype(np.float32) + fr[1] * b1.astype(np.float32)).astype(np.uint8)
        if fr[0] in ("cube", "blend"):
            use_cube(intro_key)
        if fr[0] == "cube":
            if not a.no_text:
                R.epoch.set_visible(False)
                R.info.set_text("initial density" if R.cube_q == "ics" else f"{label} · z = {z_start:.1f}")
                R.show_keys(R.cube_q != "ics")
            return draw_frame(R, fr, spin, cache)
        if fr[0] == "blend":
            b0 = draw_frame(R, fr[2], spin, cache)
            b1 = draw_lc(fr[3], spin)
            return ((1 - fr[1]) * b0.astype(np.float32) + fr[1] * b1.astype(np.float32)).astype(np.uint8)
        return draw_lc(fr, spin)

    if stills:
        todo = [i for i, f in enumerate(allf) if f[0] == "cube"]
        todo = todo[::max(1, len(todo) // 3)][:3] + (todo[-1:] if todo else [])
        lcf = [i for i, f in enumerate(allf) if f[0] == "lc"]
        zl = np.array([lc.z_of_k(allf[i][1]) for i in lcf])
        for zt in [z_start - 0.3] + [v for v in (ep["z_slow"], ep["z_trough"], ep["z_x90"]) if v] + [z_end + 0.05]:
            todo.append(lcf[int(np.argmin(np.abs(zl - zt)))])
        for i in lcf:  # each caption, 0.9 s after it starts
            if allf[i][4] and (i - 1 not in lcf or allf[i - 1][4] != allf[i][4]):
                todo.append(min(i + int(0.9 * a.fps), len(allf) - 1))
        todo += [n_main - 1] + marks  # the ending: half-way shifted, shifted, half-way out, out, turning
        todo.append(len(allf) - 1)
        for fi in sorted(set(todo)):
            buf = frame(allf[fi], fi)
            p = Path(out).with_name(f"{Path(out).stem}_f{fi:04d}.png")
            R.plt.imsave(p, buf[..., :3])
            log.info(f"wrote {p.name} ({allf[fi][0]})")
        return
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            sys.exit("no ffmpeg: module load ffmpeg, or pip install imageio-ffmpeg")
    ff = subprocess.Popen(
        [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
         "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    t0 = time.time()
    for fi, fr in enumerate(allf):
        ff.stdin.write(frame(fr, fi).tobytes())
        if fi % 150 == 0:
            log.info(f"frame {fi}/{len(allf)}  {time.time() - t0:.0f} s")
    ff.stdin.close()
    ff.wait()
    log.info(f"wrote {out} ({len(allf)} frames, {len(allf) / a.fps:.1f} s) in {time.time() - t0:.0f} s")


# ====================================================================== the evolving movie on HEALPix maps
class HealpixStore:
    """One HEALPix lightcone store (rows = RING pixels: all, or the sorted `pixels` of a patch), read one
    chunk (rows x shells) at a time, or one whole block of shells when most rows are needed."""

    def __init__(self, path, nside, pixels=None, budget=3e9):
        import h5py
        from collections import OrderedDict
        self.f = h5py.File(path, "r")
        self.ds = self.f["lightcone"]
        self.nrow, self.ns = self.ds.shape
        self.cr, self.cs = self.ds.chunks if self.ds.chunks else (self.nrow, 1)
        self.nside, self.pix = nside, pixels
        self.tiles = OrderedDict()
        self.max_tiles = max(16, int(budget / (self.cr * self.cs * 4)))
        self.block = (None, None)

    def rows(self, pix):
        if self.pix is None:
            return pix, np.ones(len(pix), bool)
        r = np.clip(np.searchsorted(self.pix, pix), 0, len(self.pix) - 1)
        return r, self.pix[r] == pix

    def _tile(self, c, b):
        key = (c, b)
        if key in self.tiles:
            self.tiles.move_to_end(key)
        else:
            self.tiles[key] = self.ds[c * self.cr:(c + 1) * self.cr, b * self.cs:(b + 1) * self.cs]
            if len(self.tiles) > self.max_tiles:
                self.tiles.popitem(last=False)
        return self.tiles[key]

    def column(self, rows, k):
        k = int(min(max(k, 0), self.ns - 1))
        b = k // self.cs
        cs = rows // self.cr
        uc = np.unique(cs)
        if len(uc) > 0.3 * (self.nrow / self.cr) or self.block[0] == b:
            if self.block[0] != b:
                self.block = (b, self.ds[:, b * self.cs:(b + 1) * self.cs])
                self.tiles.clear()
            return self.block[1][rows, k - b * self.cs]
        out = np.empty(len(rows), np.float32)
        order = np.argsort(cs, kind="stable")
        bounds = np.searchsorted(cs[order], uc, side="left").tolist() + [len(rows)]
        for i, c in enumerate(uc):
            sel = order[bounds[i]:bounds[i + 1]]
            out[sel] = self._tile(int(c), b)[rows[sel] - c * self.cr, k - b * self.cs]
        return out

    def values(self, rows, s, ds=0.0):
        """Values at fractional shell s: linear between shells, or the mean over the shells a frame passes."""
        if ds > 1.5:
            k0, k1 = int(np.ceil(s - ds / 2)), int(np.floor(s + ds / 2))
            ks = np.unique(np.clip(np.linspace(k0, k1, min(k1 - k0 + 1, 12)).round().astype(int), 0, self.ns - 1))
            return np.mean([self.column(rows, k) for k in ks], axis=0)
        k0 = int(np.floor(s))
        f = s - k0
        v = self.column(rows, k0)
        if f > 1e-4 and k0 + 1 < self.ns:
            v = (1 - f) * v + f * self.column(rows, k0 + 1)
        return v


def pix_size(nside):
    return np.sqrt(4 * np.pi / (12 * nside**2))  # rad


class GlobeSampler:
    """The sky at one shell, seen as a globe (orthographic projection centred on the camera direction):
    x, y in sin units. Full-sky store (degraded to the sample spacing when zoomed out) and patch store
    (when the frame lies in the patch and is finer than the full-sky pixels), blended at the switch."""

    def __init__(self, full, patch=None, patch_centre=(0.0, 0.0), patch_radius=0.0, res=0.5):
        self.full, self.patch = full, patch  # {q: HealpixStore}
        self.pc = lonlat_vec(*np.radians(patch_centre))
        self.pr = np.radians(patch_radius)
        self.res = res
        self.t = np.array([1.0, 0, 0])
        self.s, self.ds = 0.0, 0.0
        self._nest = {}
        self.mask = None

    def set_view(self, t, s, ds):
        self.t, self.s, self.ds = t / np.linalg.norm(t), s, ds
        self._cache = {}

    def basis(self):
        t = self.t
        up = np.array([0.0, 0.0, 1.0]) - t[2] * t
        if np.linalg.norm(up) < 1e-6:
            up = np.array([0.0, 1.0, 0.0])
        up /= np.linalg.norm(up)
        return np.cross(up, t), up, t

    def directions(self, x, y):
        er, eu, et = self.basis()
        rho2 = x * x + y * y
        inside = rho2 <= 1.0
        zc = np.sqrt(np.clip(1 - rho2, 0, None))
        n = x[..., None] * er + y[..., None] * eu + zc[..., None] * et
        return n, inside

    def _degraded(self, q, nside_eff):
        """The full-sky shell at the frame's s, averaged to nside_eff (NESTED)."""
        from astropy_healpix.core import nested_to_ring
        st = self.full[q]
        key = (q, nside_eff)
        if key in self._cache:
            return self._cache[key]
        if st.nside not in self._nest:
            self._nest[st.nside] = nested_to_ring(np.arange(12 * st.nside**2), st.nside)
        ring_of_nest = self._nest[st.nside]
        m = st.values(ring_of_nest, self.s, self.ds)  # full map in NESTED order
        f = (st.nside // nside_eff) ** 2
        m = m.reshape(-1, f).mean(1) if f > 1 else m
        self._cache[key] = m
        return m

    def sample(self, q, xs, ys):
        from astropy_healpix import lonlat_to_healpix
        from scipy import ndimage as ndi
        import astropy.units as un
        W, H = len(xs), len(ys)
        r = self.res
        xs2 = np.linspace(xs[0], xs[-1], max(2, int(W * r)))
        ys2 = np.linspace(ys[0], ys[-1], max(2, int(H * r)))
        X, Y = np.meshgrid(xs2, ys2)
        n, inside = self.directions(X, Y)
        px = abs(xs2[1] - xs2[0])  # rad per sample at the centre
        lon = np.arctan2(n[..., 1], n[..., 0])[inside]
        lat = np.arcsin(np.clip(n[..., 2], -1, 1))[inside]
        val = np.full(X.shape, np.nan, np.float32)
        # full sky, degraded to about the sample spacing
        st = self.full[q]
        ns_eff = st.nside
        while ns_eff > 8 and pix_size(ns_eff) < 0.7 * px:
            ns_eff //= 2
        if ns_eff < st.nside:
            m = self._degraded(q, ns_eff)
            v_full = m[lonlat_to_healpix(lon * un.rad, lat * un.rad, ns_eff, order="nested")]
        else:
            p = lonlat_to_healpix(lon * un.rad, lat * un.rad, st.nside, order="ring")
            v_full = st.values(p, self.s, self.ds)
        theta_map = pix_size(ns_eff)
        v = v_full.astype(np.float32)
        # patch: where the frame lies within it and is finer than the full-sky pixels
        if self.patch and q in self.patch:
            pst = self.patch[q]
            cos_in = np.cos(self.pr - np.radians(1.0))
            frame_in = inside.all() and float((n[inside] @ self.pc).min()) > cos_in
            wp = float(np.clip((1.6 * pix_size(st.nside) - px) / (0.6 * pix_size(st.nside)), 0, 1)) if frame_in else 0
            if wp > 0:
                p = lonlat_to_healpix(lon * un.rad, lat * un.rad, pst.nside, order="ring")
                rows, ok = pst.rows(p)
                vp = np.full(len(p), np.nan, np.float32)
                vp[ok] = pst.values(rows[ok], self.s, self.ds)
                vp = np.where(np.isfinite(vp), vp, v)
                v = (1 - wp) * v + wp * vp
                theta_map = (1 - wp) * theta_map + wp * pix_size(pst.nside)
        val[inside] = v
        # map pixels larger than the samples: smooth (no diamond blocks)
        sig = 0.45 * theta_map / px
        if sig > 0.6:
            good = np.isfinite(val)
            num = ndi.gaussian_filter(np.where(good, val, 0), sig)
            den = ndi.gaussian_filter(good.astype(np.float32), sig)
            val = np.where(good, num / np.maximum(den, 1e-6), np.nan)
        # back to the frame's pixels
        out = ndi.zoom(np.nan_to_num(val, nan=0.0), (H / val.shape[0], W / val.shape[1]), order=1)[:H, :W]
        XX, YY = np.meshgrid(xs, ys)
        self.mask = XX**2 + YY**2 <= 1.0
        return out


def lonlat_vec(lon, lat):
    return np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def sky_target(stores, s, centre, radius, alpha):
    """End direction: a cap of radius alpha, within `radius` of `centre`, with a neutral fraction near 0.4
    (patch neutral_fraction store, else |T_b| > 0) and the most star formation (sfrd_acg) if available."""
    from astropy_healpix import lonlat_to_healpix
    import astropy.units as un
    c = lonlat_vec(*np.radians(centre))
    cands, score = [], []
    g = np.radians(np.linspace(-radius, radius, 25))
    ring = [(a * np.cos(b), a * np.sin(b)) for a in np.linspace(0, 1, 6)[1:] for b in np.linspace(0, 2 * np.pi, 12, endpoint=False)]
    up = np.array([0.0, 0.0, 1.0]) - c[2] * c
    up /= np.linalg.norm(up)
    er = np.cross(up, c)
    for gx in g:
        for gy in g:
            if np.hypot(gx, gy) > np.radians(radius):
                continue
            t = c + np.tan(gx) * er + np.tan(gy) * up
            t /= np.linalg.norm(t)
            upt = np.array([0.0, 0.0, 1.0]) - t[2] * t
            upt /= np.linalg.norm(upt)
            ert = np.cross(upt, t)
            pts = np.array([t + alpha * (u * ert + w * upt) for u, w in ring + [(0, 0)]])
            pts /= np.linalg.norm(pts, axis=1)[:, None]
            lon, lat = np.arctan2(pts[:, 1], pts[:, 0]), np.arcsin(pts[:, 2])
            sc = 0.0
            for q, f in (("neutral_fraction", None), ("brightness_temp", None)):
                if q in stores:
                    st = stores[q]
                    p = lonlat_to_healpix(lon * un.rad, lat * un.rad, st.nside, order="ring")
                    rows, ok = st.rows(p)
                    if not ok.all():
                        sc = -np.inf
                        break
                    v = st.values(rows, s)
                    frac = float(np.mean(v > 0.5)) if q == "neutral_fraction" else float(np.mean(np.abs(v) > 1e-3))
                    sc = -abs(frac - 0.4)
                    break
            if "sfrd_acg" in stores and np.isfinite(sc):
                st = stores["sfrd_acg"]
                p = lonlat_to_healpix(lon * un.rad, lat * un.rad, st.nside, order="ring")
                rows, ok = st.rows(p)
                if ok.all():
                    sc += 0.3 * float(np.log10(np.mean(st.values(rows, s)) + 1e-30))
            cands.append(t)
            score.append(sc)
    return cands[int(np.argmax(score))]


def make_sky_movie(a, quantities, out=None, stills=False, plots=Path("plots"), qtag=""):
    """The evolving movie on the HEALPix maps: the sky at each shell as a globe, zooming into the patch."""
    sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
    sys.path.insert(1, str(Path(__file__).resolve().parent / "lightcone"))
    import eos_boxes as eb
    import eos_lightcones as el

    run = eb.Run(test=not a.production)
    base = Path(a.lightcone).parent if a.lightcone else el.default_out_dir(run.cache_dir)
    out = out or Path(plots) / f"fov_sky_{run.tag}_{qtag}.mp4"
    opts = el.default_options()
    full_dirs = sorted(base.glob("healpix_nside*"))
    patch_dirs = sorted(base.glob("patch_nside*"))
    if not full_dirs:
        sys.exit(f"no healpix_nside*/ in {base}")
    full_dir = full_dirs[0]
    nside_full = int(full_dir.name.split("nside")[1])
    want = list(dict.fromkeys(quantities + ["brightness_temp", "neutral_fraction", "sfrd_acg", "density"]))

    def store_path(d, q):
        p = d / f"{STORE.get(q, q)}.h5"
        if not p.exists() and q in FALLBACK:
            p = d / f"{FALLBACK[q]}.h5"
        return p if p.exists() else None

    full = {q: HealpixStore(store_path(full_dir, q), nside_full) for q in want if store_path(full_dir, q)}
    patch = {}
    if patch_dirs:
        pd_ = patch_dirs[0]
        opts = dict(opts, patch_nside=int(pd_.name.split("nside")[1]))
        t = time.time()
        pix = np.sort(el.patch_pixels(opts))
        log.info(f"patch: {len(pix)} pixels of Nside {opts['patch_nside']} within {opts['patch_radius_deg']} deg "
                 f"({time.time() - t:.0f} s)")
        for q in want:
            p = store_path(pd_, q)
            if p:
                st = HealpixStore(p, opts["patch_nside"], pix)
                if st.nrow != len(pix):
                    sys.exit(f"{p}: {st.nrow} rows, but the patch has {len(pix)} pixels")
                patch[q] = st
    for q in quantities:
        if q not in full and FALLBACK.get(q) not in full:
            sys.exit(f"no {q} in {full_dir}")
    quantities = [q if q in full else FALLBACK[q] for q in quantities]
    lc = Lightcone(base / "rect", [quantities[0]]) if (base / "rect").exists() else None
    # the shells: those of the HEALPix stores
    f0 = full[quantities[0]].f
    shell = type("Shells", (), {})()
    shell.z = f0["lightcone_redshifts"][()]
    shell.ns = len(shell.z)
    shell.nodes = f0["node_redshifts"][()]
    shell.k_of_z = lambda z: float(np.interp(z, shell.z, np.arange(shell.ns)))
    shell.z_of_k = lambda s_: float(np.interp(s_, np.arange(shell.ns), shell.z))

    def gmean(q):
        st = full.get(q) or (lc.f.get(q) if lc else None)
        if st is None:
            return None
        g = (st.f if hasattr(st, "f") else st)["global_mean"][()]
        ok = np.isfinite(g)
        o = np.argsort(shell.nodes[ok])
        return shell.nodes[ok][o], g[ok][o]

    shell.global_mean = gmean
    xh = gmean("neutral_fraction")
    if a.z_end is not None:
        z_end = a.z_end
    elif xh is not None and (xh[1] < a.xhi_end).any():
        zf = np.linspace(xh[0].min(), xh[0].max(), 4000)
        z_end = float(zf[np.interp(zf, *xh) < a.xhi_end].max())
    else:
        z_end = 6.0
    ep = epochs_of(shell, z_end)
    cell = float(run.inputs.simulation_options.cell_size.to_value("Mpc"))
    cosmo = run.inputs.cosmo_params.cosmo
    k_end = shell.k_of_z(z_end)
    sl = Slice({q: np.zeros((2, 2), np.float32) for q in quantities}, cell, z_end, run.tag, None, cosmo)
    sl.N = int(run.inputs.simulation_options.HII_DIM)
    sl.L = sl.N * cell  # the box (the fields above are placeholders)
    sl.watermark = a.watermark
    Dend = float(cosmo.comoving_distance(z_end).to_value("Mpc"))
    alpha_end = (a.end / 2) / Dend
    pc, pr = opts["patch_center_deg"], opts["patch_radius_deg"]
    t_end = sky_target(patch or full, k_end, pc, min(15.0, 0.4 * pr), alpha_end) if (patch or full) else lonlat_vec(0, 0)
    lon_e, lat_e = np.degrees(np.arctan2(t_end[1], t_end[0])), np.degrees(np.arcsin(t_end[2]))
    log.info(f"end direction (lon, lat) = ({lon_e:.2f}, {lat_e:.2f}) deg at z = {z_end:.2f}; epochs {ep}")
    deg = {n: d for n, d, _ in INSTRUMENTS}
    frames, z_start, z_end = plan_evolve(
        shell, a, sl, (0.0, 0.0), ep,
        size_of=lambda name, z: 2 * np.sin(np.radians(deg[name] * 150 * (1 + z) / NU21) / 2),
        angle_size=lambda d, z: 2 * np.sin(np.radians(d) / 2),
        h_start=2.3, h_end=2 * np.sin(alpha_end), centre_of=lambda f: (0.0, 0.0))
    # spin: the globe turns while it is whole, and stops when the zoom starts in earnest
    nspin = int(round((a.intro_seconds + a.seconds[0] + 0.6 * a.seconds[1]) * a.fps))
    ease = lambda v: v * v * (3 - 2 * v)  # noqa: E731

    def cam(i):  # camera direction for global frame i (intro + evolution)
        phi = np.radians(140.0) * (1 - ease(min(i / max(nspin, 1), 1.0)))
        c, s_ = np.cos(phi), np.sin(phi)
        return np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]]) @ t_end
    # colours from shells along the way
    zs_ = [z_start, z_end, 0.5 * (z_start + z_end)] + ([ep["z_trough"]] if ep["z_trough"] else [])
    colourers = {}
    rng = np.random.default_rng(0)
    rows_of = {}
    for q in quantities:
        st = full[q]
        rows_of[q] = np.sort(rng.choice(st.nrow, min(st.nrow, 200000), replace=False))
        v = np.concatenate([st.values(rows_of[q], shell.k_of_z(z)) for z in zs_])
        colourers[q] = Colourer(q, v, a.vmin, a.vmax)
    z_t = (1 + z_end) * ((1 + z_start) / (1 + z_end)) ** np.linspace(0, 1, 6) - 1
    moving = moving_scales(quantities, a, lambda q, z: full[q].values(rows_of[q], shell.k_of_z(z)), z_t)
    sampler = GlobeSampler(full, patch, pc, pr)
    # galaxies near the end (frames narrow enough that the shell region is smaller than half the box)
    slab = max(a.halo_slab, 2 * cell)
    L = sl.L
    centre_box = np.array([L / 2, L / 2, L / 2])
    gals = {}
    nodes = np.asarray(sorted(shell.nodes))
    if a.halos and a.galaxies != "none":
        need = {}
        for i, fr in enumerate(frames):
            s_, h = fr[1], fr[2]
            z = shell.z_of_k(s_)
            d = float(cosmo.comoving_distance(z).to_value("Mpc"))
            half = np.arcsin(min(0.999, 0.5 * h * np.hypot(1, a.W / a.H)))
            ext = d * np.sin(half) + slab
            if z > a.galaxies_zmax + 0.5 or 2 * ext > L / 2:
                continue
            zn = float(nodes[np.argmin(np.abs(nodes - z))])
            p = centre_box + d * cam(len(frames) + 10 ** 6)  # (no spin by then)
            dd = need.setdefault(zn, {"ivx": [], "ivy": [], "ivz": []})
            for ax, key in enumerate(("ivx", "ivy", "ivz")):
                dd[key] += wrap_interval(p[ax] - ext, p[ax] + ext, L)
        for d_ in need.values():
            for key in ("ivx", "ivy", "ivz"):
                d_[key] = merge_intervals(d_[key])
        sys.path.insert(1, str(Path(__file__).resolve().parent / "galaxies"))
        import galaxy_properties as gp
        path_of = (lambda zn: gp.output_path(run.cache_dir, run.inputs, zn)) if a.halos == "auto" else \
            (lambda zn: Path(a.halos.format(z=zn)))
        gals = load_galaxies(need, path_of, galaxy_cache(out))
    gnodes = np.array(sorted(gals)) if gals else None
    R = Renderer(sl, a, quantities, (0.0, 0.0), [], colourers=colourers, sampler=sampler,
                 dynamic_galaxies=bool(gals))
    R.angular = True
    from matplotlib.patches import Circle
    limb = Circle((0, 0), 1.0, fill=False, ec="0.55", lw=1.0 * R.fs, zorder=2)
    R.ax.add_patch(limb)
    label = SPEC.get(quantities[0], (quantities[0],))[0] if len(quantities) == 1 else ""
    # intro: the globe of the density (else the shown quantity) at z_start, turning
    iq = "density" if "density" in full else quantities[0]
    icol = Colourer(iq, full[iq].values(np.sort(rng.choice(full[iq].nrow, 200000, replace=False)),
                                        shell.k_of_z(z_start))) if iq != quantities[0] else colourers[iq]
    nin = int(round(a.intro_seconds * a.fps))
    s0 = frames[0][1]
    allf = []
    for i in range(nin):
        t = i / a.fps
        al = float(np.clip(min((t - 0.3) / 0.4, (a.intro_seconds - 0.2 - t) / 0.4), 0, 1))
        cap = (f"The sky at z = {z_start:.0f}", f"{'matter density' if iq == 'density' else label} on a shell "
               f"{float(cosmo.comoving_distance(z_start).to_value('Gpc')):.1f} cGpc away, around the observer")
        allf.append(("intro", i, cap, al))
    nx = int(0.6 * a.fps)
    last_cap = allf[-1][2]
    for i in range(nx):
        allf.append(("blend", (i + 1) / (nx + 1), ("intro", nin - 1, last_cap, 0.0), nin + i))
    for j, fr in enumerate(frames):
        allf.append(("sky", fr, nin + nx + j))
    steps = np.abs(np.gradient([fr[1] for fr in frames]))
    # the ending: zoom out to the whole globe, then the sky of the lowest shell (z = 5), density, turns
    n_main, ocol, k_fin, z_fin, turn = len(allf), None, None, None, []
    if a.outro == "turn" and "density" in full:
        k_fin = float(np.argmin(shell.z))
        z_fin = shell.z_of_k(k_fin)
        st = full["density"]
        v = st.values(np.sort(rng.choice(st.nrow, min(st.nrow, 200000), replace=False)), k_fin)
        if np.isfinite(v).mean() > 0.5:
            ocol = Colourer("density", v[np.isfinite(v)])
        else:
            log.warning(f"no HEALPix density at z = {z_fin:.2f}: no turning globe at the end")
    elif a.outro == "turn":
        log.warning("no HEALPix density: no turning globe at the end")
    marks = []
    if ocol is not None:
        # after the pause on the last frame: there the shell shifts into the density of the lowest shell under
        # the circles, galaxies and text (--outro-shift); then the density zooms out to the whole globe while
        # those fade, and the globe turns
        ease = lambda u: u * u * (3 - 2 * u)  # noqa: E731
        last, gl = frames[-1], n_main - 1
        cap_l = last[4]
        cap_o = (f"The sky at z = {z_fin:.1f}", f"matter density on a shell "
                 f"{float(cosmo.comoving_distance(z_fin).to_value('Gpc')):.1f} cGpc away, at the end of the simulation")
        turn = outro_turn(a)
        nsh = max(2, int(round(a.outro_shift_seconds * a.fps)))
        for i in range(1, nsh + 1):
            allf.append(("smix", ease(i / nsh), ("sky", last, gl)))
        marks += [len(allf) - nsh // 2, len(allf) - 1]
        zo = outro_zoom(list(last[:4]) + [None, 0.0] + list(last[6:]), 2.3, (0.0, 0.0), a)
        n04, n05 = int(round(0.4 * a.fps)), int(round(0.5 * a.fps))
        for j, fr in enumerate(zo):  # the end caption fades out (0.4 s), then the new one fades in
            cap, al = (cap_l, 1 - (j + 1) / n04) if j < n04 else (cap_o, min(1.0, (j - n05) / n05) if j >= n05 else 0.0)
            allf.append(("odens", fr[2], fr[3], cap, max(al, 0.0), fr[6], fr[7]))
        marks += [len(allf) - len(zo) // 2, len(allf) - 1]
        for j in range(len(turn)):
            allf.append(("outro", j, cap_o, 1.0))
        marks.append(len(allf) - len(turn) // 2)

    def cam_out(j):  # the globe keeps turning the way it turned in the intro: 0 -> -140 deg
        phi = -np.radians(140.0) * turn[j][1] / 200.0
        c, s_ = np.cos(phi), np.sin(phi)
        return np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]]) @ t_end

    def dens_sky_rgb(xs, ys, cen):  # the density of the lowest shell, seen as the last frame (the ending's shift)
        sampler.set_view(cam_out(0), k_fin, 0.0)
        rgb = render_rgb(sl, {"density": ocol}, sampler, ["density"], xs, ys, cen, box_mask=False)
        rgb[~sampler.mask] = 0
        return rgb

    def draw_sky(fr, gi, spin=0.0, mix=None):
        _, s_, h, cen, cap, al, ov, ca = fr
        z = shell.z_of_k(s_)
        sampler.set_view(cam(gi), s_, float(steps[min(max(gi - nin - nx, 0), len(steps) - 1)]))
        for q, rng_of in moving.items():
            R.colourers[q].set_range(*rng_of(z))
        R.zcur = z
        R.circ_alpha = ca
        R.show_keys(True)
        limb.set_visible(h > 0.8)
        d = float(cosmo.comoving_distance(z).to_value("Mpc"))
        if gnodes is not None:
            R.gal = {k: np.zeros(0) for k in ("x", "y", "muv", "rv", "w")}
            if z <= a.galaxies_zmax + 0.5:
                zn = float(gnodes[np.argmin(np.abs(gnodes - z))])
                g = gals.get(zn)
                if g is not None and len(g["x"]):
                    er, eu, et = sampler.basis()
                    p_ref = centre_box + d * et
                    xyz = np.stack([g["x"], g["y"], g["zc"]], 1).astype(np.float64)
                    xyz += L * np.round((p_ref - xyz) / L)
                    v = xyz - centre_box
                    r = np.linalg.norm(v, axis=1)
                    nn = v / r[:, None]
                    dz = np.abs(r - d)
                    m = (dz < slab / 2) & (nn @ et > np.cos(np.arcsin(min(0.999, h))))
                    R.gal = {"x": nn[m] @ er, "y": nn[m] @ eu, "muv": g["muv"][m], "rv": np.zeros(m.sum()),
                             "w": 1 - (dz[m] / (slab / 2)) ** 2}
        if not a.no_text:
            age = float(cosmo.age(z).to_value("Myr"))
            R.info.set_text(" · ".join(t for t in (label, f"z = {z:.2f}", f"{NU21 / (1 + z):.0f} MHz",
                                                   f"{age:.0f} Myr") if t))
            xhi = float(np.interp(z, *xh)) if xh is not None and (ep["z_x90"] is None or z <= ep["z_x90"]) else None
            R.epoch.set_text(epoch_label(z, ep, xhi))
            R.epoch.set_visible(True)
        if mix is None:
            return R.draw(h, cen, cap, al, spin=spin, ov=ov)
        w = mix[0]  # the shift of the ending, as in the rect movie
        R.keys_alpha(1 - w, legend=1.0)
        if not a.no_text:
            R.text_alpha(R.info, abs(1 - 2 * w))
            R.text_alpha(R.epoch, max(0.0, 1 - 2 * w))
            if w > 0.5:
                R.info.set_text(f"matter density · z = {z_fin:.2f}")
        return R.draw(h, cen, cap, al, spin=spin, ov=ov, mix=mix)

    def draw_odens(item):  # the density of the lowest shell, zooming out while the overlays fade
        _, h, cen, cap, al, ov, ca = item
        sampler.set_view(cam_out(0), k_fin, 0.0)
        R.zcur, R.circ_alpha = z_end, ca  # circles and footprints keep their last sizes while they fade
        R.show_keys(ov > 0.01)
        R.keys_alpha(0.0, legend=ov)
        limb.set_visible(h > 0.8)
        save = R.colourers, R.q
        R.colourers, R.q = {"density": ocol}, ["density"]
        if not a.no_text:
            R.info.set_text(f"matter density · z = {z_fin:.2f}")
            R.epoch.set_visible(False)
        buf = R.draw(h, cen, cap, al, ov=ov)
        R.colourers, R.q = save
        return buf

    def draw_intro(i, cap, al):
        sampler.set_view(cam(i), shell.k_of_z(z_start), 0.0)
        R.zcur, R.circ_alpha = shell.z_of_k(s0), {}
        R.show_keys(iq == quantities[0])
        limb.set_visible(True)
        save = R.colourers, R.q, R.gal
        R.colourers, R.q = {iq: icol}, [iq]
        R.gal = {k: np.zeros(0) for k in ("x", "y", "muv", "rv", "w")} if gnodes is not None else R.gal
        if not a.no_text:
            R.info.set_text("matter density" if iq == "density" else label)
            R.epoch.set_visible(False)
        buf = R.draw(2.3, (0.0, 0.0), cap, al, ov=0.0)
        R.colourers, R.q, R.gal = save
        return buf

    def draw_outro(j, cap, al):
        sampler.set_view(cam_out(j), k_fin, 0.0)
        R.zcur, R.circ_alpha = z_fin, {}
        R.show_keys(False)
        limb.set_visible(True)
        save = R.colourers, R.q, R.gal
        R.colourers, R.q = {"density": ocol}, ["density"]
        R.gal = {k: np.zeros(0) for k in ("x", "y", "muv", "rv", "w")} if gnodes is not None else R.gal
        if not a.no_text:
            R.info.set_text(f"matter density · z = {z_fin:.2f}")
            R.epoch.set_visible(False)
        buf = R.draw(2.3, (0.0, 0.0), cap, al, ov=0.0)
        R.colourers, R.q, R.gal = save
        return buf

    def frame(item):
        if not a.no_text:
            R.text_alpha(R.info, 1.0)
            R.text_alpha(R.epoch, 1.0)
        R.keys_alpha(1.0)
        if item[0] == "intro":
            return draw_intro(item[1], item[2], item[3])
        if item[0] == "outro":
            return draw_outro(item[1], item[2], item[3])
        if item[0] == "smix":
            return draw_sky(item[2][1], item[2][2], mix=(item[1], dens_sky_rgb, a.outro_shift))
        if item[0] == "odens":
            return draw_odens(item)
        if item[0] == "blend":
            b0 = draw_intro(item[2][1], item[2][2], 0.0)
            fr = list(frames[0])
            fr[5], fr[6] = 0.0, 0.0
            b1 = draw_sky(fr, item[3])
            return ((1 - item[1]) * b0.astype(np.float32) + item[1] * b1.astype(np.float32)).astype(np.uint8)
        fr = item[1]
        j = item[2] - nin - nx
        if j < int(0.8 * a.fps):
            fr = list(fr)
            fr[6] = j / (0.8 * a.fps)
        return draw_sky(fr, item[2])

    if stills:
        idx = [0, nin // 2, nin - 1]
        sky = [i for i, it in enumerate(allf) if it[0] == "sky"]
        zl = np.array([shell.z_of_k(allf[i][1][1]) for i in sky])
        for zt in [z_start - 0.3] + [v for v in (ep["z_slow"], ep["z_trough"], ep["z_x90"]) if v] + [z_end + 0.05]:
            idx.append(sky[int(np.argmin(np.abs(zl - zt)))])
        for i in sky:
            c = allf[i][1][4]
            if c and allf[i - 1][0] == "sky" and allf[i - 1][1][4] != c:  # each caption, 0.9 s after it starts
                idx.append(min(i + int(0.9 * a.fps), len(allf) - 1))
        idx += [n_main - 1] + marks  # the ending: half-way shifted, shifted, half-way out, out, turning
        idx.append(len(allf) - 1)
        for fi in sorted(set(idx)):
            buf = frame(allf[fi])
            p = Path(out).with_name(f"{Path(out).stem}_f{fi:04d}.png")
            R.plt.imsave(p, buf[..., :3])
            log.info(f"wrote {p.name} ({allf[fi][0]})")
        return
    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            sys.exit("no ffmpeg: module load ffmpeg, or pip install imageio-ffmpeg")
    ff = subprocess.Popen(
        [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{a.W}x{a.H}",
         "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    t0 = time.time()
    for fi, item in enumerate(allf):
        ff.stdin.write(frame(item).tobytes())
        if fi % 150 == 0:
            log.info(f"frame {fi}/{len(allf)}  {time.time() - t0:.0f} s")
    ff.stdin.close()
    ff.wait()
    log.info(f"wrote {out} ({len(allf)} frames, {len(allf) / a.fps:.1f} s) in {time.time() - t0:.0f} s")


# ====================================================================== main
def main(argv=None):
    a = parse(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        filename=a.log_file if a.log_file else None)
    quantities = a.quantities
    every = quantities == ["all"]
    if every and a.what != "figure":
        sys.exit("--quantity all is for the figure")
    if every:
        quantities = list(ALL_QUANTITIES)
    if a.what != "figure" and not a.fixed_z:
        plots = MOVIE_DIR / "outputs"
        plots.mkdir(parents=True, exist_ok=True)
        qtag = quantities[0] if len(quantities) == 1 else f"{len(quantities)}q"
        movie = make_sky_movie if a.geometry == "healpix" else make_evolve_movie
        movie(a, quantities, a.out, stills=(a.what == "stills"), plots=plots, qtag=qtag)
        return
    sl = (load_slice_file(a.slice_file, quantities, a.halo_slab, drop_missing=every) if a.slice_file
          else load_rect_slice(a, quantities, drop_missing=every))
    log.info(f"slice: {sl.tag}, z = {sl.z:.4f} ({sl.nu:.1f} MHz), {sl.N}² cells of {sl.cell} cMpc, "
             f"D_c = {sl.Dc:.0f} cMpc, 1 deg = {sl.cmpc_per_deg():.1f} cMpc")
    qtag = quantities[0] if len(quantities) == 1 else f"{len(quantities)}q"
    plots = Path(__file__).resolve().parents[1] / "plots"
    if a.what == "figure" and (every or (a.each and len(quantities) > 1)):
        for q in dict.fromkeys(quantities):  # the same figure for each quantity
            out = (f"{str(a.out)[:-4] if str(a.out).endswith(('.pdf', '.png')) else a.out}_{q}" if a.out
                   else plots / f"fov_{sl.tag}_z{sl.z:.2f}_{q}{'_mwa' if a.show_mwa else ''}")
            make_figure(sl, a, [q], out)
    elif a.what == "figure":
        out = a.out or plots / f"fov_{sl.tag}_z{sl.z:.2f}_{qtag}{'_mwa' if a.show_mwa else ''}"
        make_figure(sl, a, quantities, out)
    else:
        (MOVIE_DIR / "outputs").mkdir(parents=True, exist_ok=True)
        out = a.out or MOVIE_DIR / "outputs" / f"fov_zoom_{sl.tag}_z{sl.z:.2f}_{qtag}.mp4"
        make_movie(sl, a, quantities, out, stills=(a.what == "stills"))


if __name__ == "__main__":
    main()
