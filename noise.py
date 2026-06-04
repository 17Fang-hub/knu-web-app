import numpy as np


def add_gaussian_noise(image: np.ndarray, sigma: float, rng=None) -> np.ndarray:
    """Додає гаусівський шум зі стандартним відхиленням sigma (0..25).

    При sigma <= 0 повертається копія зображення (чистий випадок).
    """
    if sigma <= 0:
        return image.copy()
    if rng is None:
        rng = np.random
    noise = rng.normal(0, sigma, image.shape)
    noisy = image.astype(np.float64) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)
