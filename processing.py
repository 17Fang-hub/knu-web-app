import time
import numpy as np
import cv2
from pathlib import Path


def _compute_snr(original_gray: np.ndarray, edge_mask: np.ndarray) -> float:
    edge_px = original_gray[edge_mask > 0].astype(float)
    bg_px = original_gray[edge_mask == 0].astype(float)
    if len(edge_px) == 0 or len(bg_px) == 0:
        return 0.0
    noise = float(np.std(bg_px))
    if noise == 0:
        return 0.0
    return round(float(np.mean(edge_px)) / noise, 3)


def apply_canny(image_path: Path) -> tuple:
    img = cv2.imread(str(image_path))
    assert img is not None, f"Cannot read image: {image_path}"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    t0 = time.perf_counter()
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    snr = _compute_snr(gray, edges)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), elapsed_ms, snr


def apply_sobel(image_path: Path) -> tuple:
    img = cv2.imread(str(image_path))
    assert img is not None, f"Cannot read image: {image_path}"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    t0 = time.perf_counter()
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(grad_x, grad_y)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    if magnitude.max() > 0:
        norm = (magnitude / magnitude.max() * 255).astype(np.uint8)
    else:
        norm = magnitude.astype(np.uint8)
    _, edges = cv2.threshold(norm, 20, 255, cv2.THRESH_BINARY)
    snr = _compute_snr(gray.astype(np.uint8), edges)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), elapsed_ms, snr


def process_both(source_path: Path, output_dir: Path) -> dict:
    stem = source_path.stem
    classical_img, classical_time, classical_snr = apply_canny(source_path)
    sobel_img, sobel_time, sobel_snr = apply_sobel(source_path)
    classical_filename = f"{stem}_canny.jpg"
    sobel_filename = f"{stem}_sobel.jpg"
    cv2.imwrite(str(output_dir / classical_filename), classical_img)
    cv2.imwrite(str(output_dir / sobel_filename), sobel_img)
    return {
        "classical": {
            "filename": classical_filename,
            "time_ms": classical_time,
            "snr": classical_snr,
        },
        "secondary": {
            "filename": sobel_filename,
            "time_ms": sobel_time,
            "snr": sobel_snr,
        },
    }
