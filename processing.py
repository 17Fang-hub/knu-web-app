import time
import base64
import numpy as np
import cv2
from pathlib import Path

from metrics import compute_all_metrics

DEFAULT_ALPHA = 0.5
DEFAULT_N = 2


# ── Grünwald–Letnikov fractional derivative ──────────────────────────────────

def gl_coefficients(alpha: float, n: int) -> np.ndarray:
    """GL coefficients w_0 … w_n (recurrence)."""
    w = np.zeros(n + 1)
    w[0] = 1.0
    for k in range(1, n + 1):
        w[k] = w[k - 1] * (-(alpha - k + 1) / k)
    return w


def build_fractional_kernel_x(alpha: float, n: int = DEFAULT_N) -> np.ndarray:
    """
    Antisymmetric 2D kernel (2n+1)×(2n+1) for the fractional derivative along X.
    Row weights are triangular [1,2,…,n+1,…,2,1] as in Sobel.
    At alpha=1 the kernel degenerates to the classical Sobel operator.
    """
    w = gl_coefficients(alpha, n)
    size = 2 * n + 1
    kernel = np.zeros((size, size))
    row_weights = np.array(list(range(1, n + 2)) + list(range(n, 0, -1)), dtype=float)
    for row_idx in range(size):
        rw = row_weights[row_idx]
        for k in range(1, n + 1):
            kernel[row_idx, n - k] += rw * w[k]
            kernel[row_idx, n + k] -= rw * w[k]
    norm = np.abs(kernel).sum()
    if norm > 0:
        kernel /= norm
    return kernel


def build_fractional_kernel_y(alpha: float, n: int = DEFAULT_N) -> np.ndarray:
    return build_fractional_kernel_x(alpha, n).T


def _channel_gradients(channel: np.ndarray, kx: np.ndarray, ky: np.ndarray):
    gx = cv2.filter2D(channel, cv2.CV_64F, kx, borderType=cv2.BORDER_REFLECT)
    gy = cv2.filter2D(channel, cv2.CV_64F, ky, borderType=cv2.BORDER_REFLECT)
    return gx, gy


def _non_max_suppression(g: np.ndarray, angle: np.ndarray) -> np.ndarray:
    gp = np.pad(g, 1, mode="constant")
    n_ = gp[0:-2, 1:-1]
    s_ = gp[2:, 1:-1]
    e_ = gp[1:-1, 2:]
    w_ = gp[1:-1, 0:-2]
    ne = gp[0:-2, 2:]
    nw = gp[0:-2, 0:-2]
    se = gp[2:, 2:]
    sw = gp[2:, 0:-2]

    a = angle % 180
    m0   = (a < 22.5)  | (a >= 157.5)
    m45  = (a >= 22.5) & (a < 67.5)
    m90  = (a >= 67.5) & (a < 112.5)
    m135 = (a >= 112.5) & (a < 157.5)

    q = np.zeros_like(g)
    r = np.zeros_like(g)
    q[m0],   r[m0]   = e_[m0],  w_[m0]
    q[m45],  r[m45]  = ne[m45], sw[m45]
    q[m90],  r[m90]  = n_[m90], s_[m90]
    q[m135], r[m135] = nw[m135], se[m135]

    keep = (g >= q) & (g >= r)
    return np.where(keep, g, 0.0)


def _hysteresis(nms: np.ndarray, low: float, high: float) -> np.ndarray:
    """
    Double-threshold + edge linking via connected components:
    a component is kept if it contains at least one strong pixel.
    """
    strong = nms >= high
    candidate = (nms >= low).astype(np.uint8)
    if not strong.any():
        return np.zeros_like(nms, dtype=np.uint8)
    _, labels = cv2.connectedComponents(candidate, connectivity=8)
    keep_labels = np.unique(labels[strong])
    keep_labels = keep_labels[keep_labels != 0]
    out = np.isin(labels, keep_labels)
    return (out.astype(np.uint8)) * 255


def fractional_edge_detection(
    image: np.ndarray,
    alpha: float = DEFAULT_ALPHA,
    n: int = DEFAULT_N,
    use_reconstruction_threshold: bool = False,
) -> tuple:
    """
    Full GL-Canny edge detection.
    Returns (edge_map uint8 {0,255}, gradient_magnitude float32 normalised [0,1]).
    """
    img = image.astype(np.float64)
    if img.max() > 1.0:
        img = img / 255.0

    kx = build_fractional_kernel_x(alpha, n)
    ky = build_fractional_kernel_y(alpha, n)

    if img.ndim == 3:
        gx_sq = np.zeros(img.shape[:2])
        gy_sq = np.zeros(img.shape[:2])
        for c in range(img.shape[2]):
            gx, gy = _channel_gradients(img[:, :, c], kx, ky)
            gx_sq += gx ** 2
            gy_sq += gy ** 2
        g_x = np.sqrt(gx_sq)
        g_y = np.sqrt(gy_sq)
    else:
        g_x, g_y = _channel_gradients(img, kx, ky)

    g = np.hypot(g_x, g_y)
    g_max = float(g.max())
    grad_mag = (g / g_max).astype(np.float32) if g_max > 0 else np.zeros(img.shape[:2], dtype=np.float32)

    theta = np.degrees(np.arctan2(g_y, g_x)) % 180

    nms = _non_max_suppression(g, theta)
    nms_max = float(nms.max())
    if nms_max <= 0:
        return np.zeros(img.shape[:2], dtype=np.uint8), grad_mag

    if use_reconstruction_threshold:
        n_max = float(image.astype(np.float64).max()) or 255.0
        low_frac = 1.0 / n_max
        low = low_frac * nms_max
        high = 3.0 * low
    else:
        mag8 = np.clip(nms / nms_max * 255.0, 0, 255).astype(np.uint8)
        otsu, _ = cv2.threshold(mag8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        high = otsu / 255.0 * nms_max
        low = 0.5 * high

    return _hysteresis(nms, low, high), grad_mag


def _read_image(image_path: Path) -> np.ndarray:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    assert img is not None, f"Cannot read image: {image_path}"
    return img


# ── Public methods for the web service ──────────────────────────────────────

def apply_fractional(image_path: Path, alpha: float = DEFAULT_ALPHA, n: int = DEFAULT_N) -> dict:
    img = _read_image(image_path)
    t0 = time.perf_counter()
    edges, grad_mag = fractional_edge_detection(img, alpha=alpha, n=n)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        'edges_bgr': cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR),
        'edge_map': edges,
        'gradient_magnitude': grad_mag,
        'elapsed_ms': elapsed_ms,
        'original': img,
    }


def apply_sobel(image_path: Path) -> dict:
    img = _read_image(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    t0 = time.perf_counter()
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(grad_x, grad_y)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    mag_max = float(magnitude.max())
    if mag_max > 0:
        norm_u8 = (magnitude / mag_max * 255).astype(np.uint8)
        grad_mag = (magnitude / mag_max).astype(np.float32)
    else:
        norm_u8 = magnitude.astype(np.uint8)
        grad_mag = np.zeros_like(magnitude, dtype=np.float32)
    _, edges = cv2.threshold(norm_u8, 20, 255, cv2.THRESH_BINARY)
    return {
        'edges_bgr': cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR),
        'edge_map': edges,
        'gradient_magnitude': grad_mag,
        'elapsed_ms': elapsed_ms,
        'original': img,
    }


def _encode_b64(img_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img_bgr)
    assert ok, "Cannot encode preview image"
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def fractional_preview(image_path: Path, alpha: float = DEFAULT_ALPHA, n: int = DEFAULT_N) -> dict:
    """Quick preview for the alpha slider — returns metrics without saving to disk/DB."""
    result = apply_fractional(image_path, alpha=alpha, n=n)
    m = compute_all_metrics(
        edge_map=result['edge_map'],
        gradient_magnitude=result['gradient_magnitude'],
        original_image=result['original'],
    )
    return {
        "data_url": _encode_b64(result['edges_bgr']),
        "time_ms": result['elapsed_ms'],
        "alpha": alpha,
        **m,
    }


def sobel_preview(image_path: Path) -> dict:
    """Sobel preview as base64 data-URL — no disk/DB write."""
    result = apply_sobel(image_path)
    m = compute_all_metrics(
        edge_map=result['edge_map'],
        gradient_magnitude=result['gradient_magnitude'],
        original_image=result['original'],
    )
    return {
        "data_url": _encode_b64(result['edges_bgr']),
        "time_ms": result['elapsed_ms'],
        **m,
    }


def process_both(source_path: Path, output_dir: Path, alpha: float = DEFAULT_ALPHA) -> dict:
    stem = source_path.stem
    frac = apply_fractional(source_path, alpha=alpha)
    sobel = apply_sobel(source_path)

    frac_m = compute_all_metrics(
        edge_map=frac['edge_map'],
        gradient_magnitude=frac['gradient_magnitude'],
        original_image=frac['original'],
    )
    sobel_m = compute_all_metrics(
        edge_map=sobel['edge_map'],
        gradient_magnitude=sobel['gradient_magnitude'],
        original_image=sobel['original'],
    )

    frac_filename = f"{stem}_fractional.jpg"
    sobel_filename = f"{stem}_sobel.jpg"
    cv2.imwrite(str(output_dir / frac_filename), frac['edges_bgr'])
    cv2.imwrite(str(output_dir / sobel_filename), sobel['edges_bgr'])

    return {
        "classical": {
            "filename": frac_filename,
            "time_ms": frac['elapsed_ms'],
            "alpha": alpha,
            **frac_m,
        },
        "secondary": {
            "filename": sobel_filename,
            "time_ms": sobel['elapsed_ms'],
            **sobel_m,
        },
    }
