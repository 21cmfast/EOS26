"""Checks of postprocess/box_movie.py: python -m pytest postprocess/test_box_movie.py"""

import math
from types import SimpleNamespace

import h5py
import numpy as np

import box_movie as bm


def test_reduce_box(tmp_path):
    rng = np.random.default_rng(0)
    box = rng.normal(size=(12, 12, 12)).astype(np.float32)
    with h5py.File(tmp_path / "b.h5", "w") as f:
        f["x"] = box
        coarse, fine = bm.reduce_box(f["x"], 3, (2, 5, 1), 6, slab=6)
    assert np.allclose(coarse, box.reshape(4, 3, 4, 3, 4, 3).mean(axis=(1, 3, 5)), atol=1e-6)
    assert np.array_equal(fine, box[2:8, 5:11, 1:7])
    assert bm.coarse_factor(1500, 500) == 3 and bm.coarse_factor(200, 500) == 1 and bm.coarse_factor(86, 43) == 2


def test_cast_uniform_cube():
    """Through a uniform cube, front to back with visio's opacity: colour * (1 - (1 - op)^n)."""
    lut, vmin, vmax = bm.colour_table([(-1, 255, 0, 0, 4), (1, 255, 0, 0, 4)])
    n, side = 8, 10.0
    box = np.zeros((n, n, n), np.float32)
    img = np.zeros((1, 1, 3), np.float32)
    step = 0.5 * side / n
    kappa = bm.OPACITY / side / 255.0
    eye = np.array([-30.0, 5.0, 5.0])  # on the axis through the cube centre
    bm.cast(img, box, box, box, box, 0.0, side / n, np.zeros(3), side / n, 0.0, np.zeros(3), np.full(3, side),
            step, eye, np.array([1.0, 0, 0]), np.array([0, -1.0, 0]), np.array([0, 0, 1.0]),
            0.1, 0.0, lut, vmin, vmax, kappa)
    op = 4 * kappa * step
    expected = 1 - (1 - op) ** round(side / step)
    assert math.isclose(img[0, 0, 0], expected, rel_tol=1e-5)
    assert img[0, 0, 1] == 0 and img[0, 0, 2] == 0


def test_clip_box_contains_sub_cube():
    boxes = SimpleNamespace(box_len=2250.0, fine_len=750.0, fine_lo=np.array([0.0, 750.0, 1500.0]))
    a = SimpleNamespace(z_start=35.0, z_end=5.0, dlnz=0.0025, hold=0.0, fps=25, zoom_z=[13.0, 11.0])
    tl = bm.Timeline(a, boxes)
    for p in np.linspace(0, 1, 21):
        s, c = tl.clip_box(p)
        assert np.all(c - s / 2 >= -1e-9) and np.all(c + s / 2 <= 2250 + 1e-9)
        assert np.all(c - s / 2 <= boxes.fine_lo + 1e-9) and np.all(c + s / 2 >= boxes.fine_lo + 750 - 1e-9)
    assert tl.zoom(14.0) == 0 and tl.zoom(10.0) == 1 and 0 < tl.zoom(12.0) < 1
    assert math.isclose(tl.z[0], 35.0) and math.isclose(tl.z[-1], 5.0)


def test_bracket(tmp_path):
    p = tmp_path / "x_box_movie_Tb.h5"
    with h5py.File(p, "w") as f:
        f["redshift"] = np.array([20.0, 15.0, 10.0])
        f["done"] = np.array([True, True, True])
        f["coarse"] = np.zeros((3, 2, 2, 2), np.float16)
        f["fine"] = np.zeros((3, 1, 1, 1), np.float16)
        f.attrs.update(box_len=4.0, n_cells=4, factor=2, fine_origin=np.array([1, 1, 1]), fine_cells=1)
    b = bm.Boxes(p)
    assert b.bracket(20.0) == (0, 1, 0.0)
    assert b.bracket(12.0) == (1, 2, 0.6)
    assert b.bracket(10.0) == (1, 2, 1.0)
