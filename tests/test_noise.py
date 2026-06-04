import numpy as np

from metrics import edge_density, compute_comparison_metrics
from noise import add_gaussian_noise


# ── edge density ─────────────────────────────────────────────────────────────

def test_edge_density_full_and_empty():
    full = np.full((10, 10), 255, dtype=np.uint8)
    empty = np.zeros((10, 10), dtype=np.uint8)
    assert edge_density(full) == 1.0
    assert edge_density(empty) == 0.0


def test_edge_density_fraction():
    m = np.zeros((10, 10), dtype=np.uint8)
    m[0, :] = 255          # 10 з 100 пікселів
    assert edge_density(m) == 0.1


# ── comparison metrics (DER / DCR / DCS) ─────────────────────────────────────

def test_comparison_identical_maps():
    """I1 == I2: жодних зайвих пікселів (DER=0), повний збіг (DCR=1)."""
    m = np.zeros((10, 10), dtype=np.uint8)
    m[2:5, 2:5] = 255
    out = compute_comparison_metrics(m, m)
    assert out["der"] == 0.0
    assert out["dcr"] == 1.0
    # DER==0 → DCS визначено як 0.0
    assert out["dcs"] == 0.0


def test_comparison_partial_overlap():
    # I2 (Sobel, референс): 4 пікселі
    sobel = np.zeros((10, 10), dtype=np.uint8)
    sobel[0:4, 0] = 255
    # I1 (GL-Canny): 2 спільні + 2 зайві
    gl = np.zeros((10, 10), dtype=np.uint8)
    gl[0:2, 0] = 255       # спільні з sobel
    gl[0:2, 5] = 255       # зайві (нема в sobel)

    out = compute_comparison_metrics(gl, sobel)
    # N(I2)=4, extra=2, common=2
    assert out["der"] == 0.5      # 2/4
    assert out["dcr"] == 0.5      # 2/4
    assert out["dcs"] == 1.0      # 0.5/0.5


def test_comparison_empty_reference():
    """Порожній референс (N(I2)=0) → усі метрики 0."""
    gl = np.zeros((10, 10), dtype=np.uint8)
    gl[0, 0] = 255
    sobel = np.zeros((10, 10), dtype=np.uint8)
    out = compute_comparison_metrics(gl, sobel)
    assert out == {"der": 0.0, "dcr": 0.0, "dcs": 0.0}


# ── gaussian noise ───────────────────────────────────────────────────────────

def test_gaussian_noise_zero_sigma_returns_copy():
    img = np.full((20, 20, 3), 128, dtype=np.uint8)
    out = add_gaussian_noise(img, sigma=0)
    assert np.array_equal(out, img)
    assert out is not img       # копія, не той самий об'єкт


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
