import numpy as np


def add_gaussian_noise(image: np.ndarray, sigma: float, rng=None) -> np.ndarray:
    if rng is None:
        rng = np.random
    noise = rng.normal(0, sigma, image.shape)
    noisy = image.astype(np.float64) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)
