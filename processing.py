import time
import base64
import numpy as np
import cv2
from pathlib import Path

# Порядок дробової похідної за замовчуванням (рекомендація статті: 0.5–0.7)
DEFAULT_ALPHA = 0.5
# Кількість членів ряду Грюнвальда–Летнікова (розмір маски = 2*n+1)
DEFAULT_N = 2


def _compute_snr(original_gray: np.ndarray, edge_mask: np.ndarray) -> float:
    edge_px = original_gray[edge_mask > 0].astype(float)
    bg_px = original_gray[edge_mask == 0].astype(float)
    if len(edge_px) == 0 or len(bg_px) == 0:
        return 0.0
    noise = float(np.std(bg_px))
    if noise == 0:
        return 0.0
    return round(float(np.mean(edge_px)) / noise, 3)


# ── Дробова похідна (Grünwald–Letnikov) ─────────────────────────────────────────

def gl_coefficients(alpha: float, n: int) -> np.ndarray:
    """Коефіцієнти Грюнвальда–Летнікова w_0 … w_n (рекурентна формула)."""
    w = np.zeros(n + 1)
    w[0] = 1.0
    for k in range(1, n + 1):
        w[k] = w[k - 1] * (-(alpha - k + 1) / k)
    return w


def build_fractional_kernel_x(alpha: float, n: int = DEFAULT_N) -> np.ndarray:
    """
    Будує антисиметричну 2D-маску (2n+1)×(2n+1) для дробової похідної по X.

    Центральний стовпець нульовий; ліва/права частини дзеркальні (left- мінус
    right-sided похідна). Рядки зважені трикутно [1,2,…,n+1,…,2,1] — так само,
    як у Sobel. При alpha=1 маска вироджується у класичний оператор Sobel.
    """
    w = gl_coefficients(alpha, n)
    size = 2 * n + 1
    kernel = np.zeros((size, size))

    # Трикутні ваги рядків: для n=2 → [1, 2, 3, 2, 1]
    row_weights = np.array(list(range(1, n + 2)) + list(range(n, 0, -1)), dtype=float)

    for row_idx in range(size):
        rw = row_weights[row_idx]
        for k in range(1, n + 1):
            kernel[row_idx, n - k] += rw * w[k]   # ліва частина
            kernel[row_idx, n + k] -= rw * w[k]   # права (дзеркальна)

    # Нормування для уникнення переповнення (розділ 13.3 статті)
    norm = np.abs(kernel).sum()
    if norm > 0:
        kernel /= norm
    return kernel


def build_fractional_kernel_y(alpha: float, n: int = DEFAULT_N) -> np.ndarray:
    """Похідна по Y — транспозиція X-маски."""
    return build_fractional_kernel_x(alpha, n).T


def _channel_gradients(channel: np.ndarray, kx: np.ndarray, ky: np.ndarray):
    """G_x, G_y одного каналу через згортку (mode='reflect' проти артефактів)."""
    gx = cv2.filter2D(channel, cv2.CV_64F, kx, borderType=cv2.BORDER_REFLECT)
    gy = cv2.filter2D(channel, cv2.CV_64F, ky, borderType=cv2.BORDER_REFLECT)
    return gx, gy


def _non_max_suppression(g: np.ndarray, angle: np.ndarray) -> np.ndarray:
    """Придушення немаксимумів уздовж напрямку градієнта (векторизовано)."""
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
    m0 = (a < 22.5) | (a >= 157.5)            # горизонталь → E, W
    m45 = (a >= 22.5) & (a < 67.5)            # 45°        → NE, SW
    m90 = (a >= 67.5) & (a < 112.5)           # вертикаль  → N, S
    m135 = (a >= 112.5) & (a < 157.5)         # 135°       → NW, SE

    q = np.zeros_like(g)
    r = np.zeros_like(g)
    q[m0], r[m0] = e_[m0], w_[m0]
    q[m45], r[m45] = ne[m45], sw[m45]
    q[m90], r[m90] = n_[m90], s_[m90]
    q[m135], r[m135] = nw[m135], se[m135]

    keep = (g >= q) & (g >= r)
    return np.where(keep, g, 0.0)


def _hysteresis(nms: np.ndarray, low: float, high: float) -> np.ndarray:
    """
    Гістерезисне порогування + edge linking через зв'язні компоненти:
    компонента зберігається повністю, якщо містить хоча б один «сильний» піксель.
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
) -> np.ndarray:
    """
    Повний алгоритм виявлення контурів на основі дробових похідних.

    image  : grayscale (H×W) або кольорове (H×W×3, BGR/RGB), uint8 чи float.
    alpha  : порядок дробової похідної.
    n      : кількість членів ряду GL (розмір маски 2n+1).
    use_reconstruction_threshold : True → пороги за помилкою реконструкції
                                    (low=1/N_max, high=3·low; дуже чутливо,
                                    більше текстури); False → авто-поріг Otsu.
    Повертає бінарну карту контурів uint8 {0, 255}.
    """
    img = image.astype(np.float64)
    if img.max() > 1.0:
        img = img / 255.0

    kx = build_fractional_kernel_x(alpha, n)
    ky = build_fractional_kernel_y(alpha, n)

    if img.ndim == 3:
        # Поканальна обробка з подальшою L2-нормою (векторний підхід статті)
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
    theta = np.degrees(np.arctan2(g_y, g_x)) % 180

    nms = _non_max_suppression(g, theta)
    nms_max = float(nms.max())
    if nms_max <= 0:
        return np.zeros(img.shape[:2], dtype=np.uint8)

    if use_reconstruction_threshold:
        # Поріг за помилкою реконструкції (розділ 7 статті): N_max у шкалі 0–255
        n_max = float(image.astype(np.float64).max()) or 255.0
        low_frac = 1.0 / n_max
        low = low_frac * nms_max
        high = 3.0 * low
    else:
        # Авто-поріг Otsu по магнітуді градієнта
        mag8 = np.clip(nms / nms_max * 255.0, 0, 255).astype(np.uint8)
        otsu, _ = cv2.threshold(mag8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        high = otsu / 255.0 * nms_max
        low = 0.5 * high

    return _hysteresis(nms, low, high)


def _read_image(image_path: Path) -> np.ndarray:
    """
    Безпечне читання зображення: IMREAD_COLOR завжди повертає 3-канальне BGR,
    тож чорно-білі (1-канальні) та зображення з alpha-каналом не спричиняють помилок.
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    assert img is not None, f"Cannot read image: {image_path}"
    return img


# ── Публічні методи для вебсервісу ──────────────────────────────────────────────

def apply_fractional(image_path: Path, alpha: float = DEFAULT_ALPHA, n: int = DEFAULT_N) -> tuple:
    img = _read_image(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    t0 = time.perf_counter()
    edges = fractional_edge_detection(img, alpha=alpha, n=n)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    snr = _compute_snr(gray, edges)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), elapsed_ms, snr


def apply_sobel(image_path: Path) -> tuple:
    img = _read_image(image_path)
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


def _encode_b64(img_bgr: np.ndarray) -> str:
    """Кодує BGR-зображення у base64 data-URL (JPEG)."""
    ok, buf = cv2.imencode(".jpg", img_bgr)
    assert ok, "Cannot encode preview image"
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def fractional_preview(image_path: Path, alpha: float = DEFAULT_ALPHA, n: int = DEFAULT_N) -> dict:
    """
    Швидке превʼю дробового методу для повзунка α: повертає зображення як
    base64 data-URL (без запису на диск і без збереження в БД).
    """
    edges_bgr, time_ms, snr = apply_fractional(image_path, alpha=alpha, n=n)
    return {
        "data_url": _encode_b64(edges_bgr),
        "time_ms": time_ms,
        "snr": snr,
        "alpha": alpha,
    }


def sobel_preview(image_path: Path) -> dict:
    """Превʼю методу Sobel як base64 data-URL (без запису на диск/в БД)."""
    edges_bgr, time_ms, snr = apply_sobel(image_path)
    return {
        "data_url": _encode_b64(edges_bgr),
        "time_ms": time_ms,
        "snr": snr,
    }


def process_both(source_path: Path, output_dir: Path, alpha: float = DEFAULT_ALPHA) -> dict:
    stem = source_path.stem
    classical_img, classical_time, classical_snr = apply_fractional(source_path, alpha=alpha)
    sobel_img, sobel_time, sobel_snr = apply_sobel(source_path)
    classical_filename = f"{stem}_fractional.jpg"
    sobel_filename = f"{stem}_sobel.jpg"
    cv2.imwrite(str(output_dir / classical_filename), classical_img)
    cv2.imwrite(str(output_dir / sobel_filename), sobel_img)
    return {
        "classical": {
            "filename": classical_filename,
            "time_ms": classical_time,
            "snr": classical_snr,
            "alpha": alpha,
        },
        "secondary": {
            "filename": sobel_filename,
            "time_ms": sobel_time,
            "snr": sobel_snr,
        },
    }
