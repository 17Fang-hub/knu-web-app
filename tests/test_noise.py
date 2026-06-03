import numpy as np

from metrics import iou_score
from noise import add_gaussian_noise


def test_iou_identical_maps():
    m = np.zeros((10, 10), dtype=np.uint8)
    m[2:5, 2:5] = 255
    assert iou_score(m, m) == 1.0


def test_iou_disjoint_maps():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = np.zeros((10, 10), dtype=np.uint8)
    a[0:3, 0:3] = 255
    b[6:9, 6:9] = 255
    assert iou_score(a, b) == 0.0


def test_iou_partial_overlap():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = np.zeros((10, 10), dtype=np.uint8)
    a[0:4, 0:1] = 255      # 4 px
    b[0:2, 0:1] = 255      # 2 px, fully inside a
    # intersection = 2, union = 4 → 0.5
    assert iou_score(a, b) == 0.5


def test_iou_empty_maps():
    z = np.zeros((10, 10), dtype=np.uint8)
    assert iou_score(z, z) == 0.0


def test_gaussian_noise_shape_and_range():
    img = np.full((20, 20, 3), 128, dtype=np.uint8)
    noisy = add_gaussian_noise(img, sigma=15.0)
    assert noisy.shape == img.shape
    assert noisy.dtype == np.uint8
    assert noisy.min() >= 0 and noisy.max() <= 255


def test_gaussian_noise_reproducible_with_seed():
    img = np.full((20, 20), 100, dtype=np.uint8)
    a = add_gaussian_noise(img, 10.0, rng=np.random.RandomState(42))
    b = add_gaussian_noise(img, 10.0, rng=np.random.RandomState(42))
    assert np.array_equal(a, b)


def test_gaussian_noise_changes_image():
    img = np.full((40, 40), 128, dtype=np.uint8)
    noisy = add_gaussian_noise(img, 20.0, rng=np.random.RandomState(1))
    assert not np.array_equal(img, noisy)
