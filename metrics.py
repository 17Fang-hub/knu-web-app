import numpy as np
import cv2


def edge_density(edge_map: np.ndarray) -> float:
    binary = edge_map > 0
    return round(float(binary.sum()) / max(int(binary.size), 1), 6)


def mean_edge_strength(edge_map: np.ndarray, gradient_magnitude: np.ndarray) -> float:
    binary = edge_map > 0
    if not binary.any():
        return 0.0
    return round(float(gradient_magnitude[binary].mean()), 6)


def edge_continuity(edge_map: np.ndarray) -> dict:
    binary = (edge_map > 0).astype(np.uint8)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    num_components = n_labels - 1  # label 0 is background
    total_edge_pixels = int(binary.sum())
    if num_components == 0 or total_edge_pixels == 0:
        return {
            'num_components': 0,
            'mean_length': 0.0,
            'max_length': 0.0,
            'fragmentation': 0.0,
        }
    sizes = stats[1:, cv2.CC_STAT_AREA]
    return {
        'num_components': int(num_components),
        'mean_length': round(float(sizes.mean()), 6),
        'max_length': round(float(sizes.max()), 6),
        'fragmentation': round(float(num_components) / total_edge_pixels, 6),
    }


def contrast_ratio(edge_map: np.ndarray, original_image: np.ndarray) -> float:
    """Mean local contrast at edge pixels (max diff with 4-connected neighbors), normalised to [0,1]."""
    if original_image.ndim == 3:
        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray = original_image.astype(np.float32)

    binary = edge_map > 0
    if not binary.any():
        return 0.0

    padded = np.pad(gray, 1, mode='edge')
    neighbors = np.stack([
        padded[0:-2, 1:-1],   # N
        padded[2:,   1:-1],   # S
        padded[1:-1, 2:],     # E
        padded[1:-1, 0:-2],   # W
    ])  # shape (4, H, W)
    local_contrast = np.abs(gray - neighbors).max(axis=0)
    return round(float(local_contrast[binary].mean()) / 255.0, 6)


def iou_score(edge_map_1: np.ndarray, edge_map_2: np.ndarray) -> float:
    """
    Intersection over Union between two binary edge maps.
    Returns float in [0, 1]: 1 = identical, 0 = no overlap.
    """
    m1 = edge_map_1 > 0
    m2 = edge_map_2 > 0
    intersection = int(np.logical_and(m1, m2).sum())
    union = int(np.logical_or(m1, m2).sum())
    return round(intersection / union, 6) if union > 0 else 0.0


def compute_all_metrics(
    edge_map: np.ndarray,
    gradient_magnitude: np.ndarray,
    original_image: np.ndarray,
) -> dict:
    cont = edge_continuity(edge_map)
    return {
        'edge_density': edge_density(edge_map),
        'mean_edge_strength': mean_edge_strength(edge_map, gradient_magnitude),
        'num_components': cont['num_components'],
        'mean_component_length': cont['mean_length'],
        'fragmentation': cont['fragmentation'],
        'contrast_ratio': contrast_ratio(edge_map, original_image),
    }
