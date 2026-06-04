import numpy as np


def edge_density(edge_map: np.ndarray) -> float:
    """Частка edge-пікселів у карті країв (значення в [0, 1]).

    Обчислюється однаково для обох методів (кількість edge-пікселів /
    загальна кількість пікселів), щоб порівняння було чесним.
    """
    binary = edge_map > 0
    return round(float(binary.sum()) / max(int(binary.size), 1), 4)


def compute_comparison_metrics(fractional_edges: np.ndarray,
                               sobel_edges: np.ndarray) -> dict:
    """
    Метрики порівняння двох карт країв між собою (Mishra et al., "Design of
    Fractional Calculus based differentiator for edge detection in color
    images").

    fractional_edges (I1) — карта країв GL-Canny (бінарна)
    sobel_edges (I2)      — карта країв Sobel (бінарна, референс)

    DER (Detection Error Rate)    = |є в I1, нема в I2| / N(I2)
    DCR (Detection Common Rate)   = |є і в I1, і в I2| / N(I2)
    DCS (Detect Correct Similarity) = DCR / DER
    """
    I1 = fractional_edges.astype(bool)
    I2 = sobel_edges.astype(bool)

    N_I2 = int(np.sum(I2))            # усі краї базового методу
    extra = int(np.sum(I1 & ~I2))     # є в I1, нема в I2
    common = int(np.sum(I1 & I2))     # є в обох

    DER = extra / N_I2 if N_I2 > 0 else 0.0
    DCR = common / N_I2 if N_I2 > 0 else 0.0
    DCS = DCR / DER if DER > 0 else 0.0

    return {
        'der': round(DER, 4),
        'dcr': round(DCR, 4),
        'dcs': round(DCS, 4),
    }
