// ── Image view modal ──────────────────────────────────────────────────────────
const imageModal = document.getElementById("imageModal");
const modalImg = document.getElementById("fullImage");
const captionText = document.getElementById("caption");
const imageCloseBtn = document.getElementById("imageCloseBtn");

document.querySelectorAll(".gallery-item img").forEach(img => {
    img.onclick = function () {
        imageModal.style.display = "flex";
        modalImg.src = this.src;
        captionText.innerHTML = this.alt;
    };
});

imageCloseBtn.onclick = function () {
    imageModal.style.display = "none";
};

imageModal.onclick = function (event) {
    if (event.target === imageModal) {
        imageModal.style.display = "none";
    }
};

// ── Gallery switch (uploads ↔ results) ──────────────────────────────────────────
function switchGallery(target) {
    const isResults = target === "results";

    document.getElementById("uploadsGallery").style.display = isResults ? "none" : "block";
    document.getElementById("resultsGallery").style.display = isResults ? "block" : "none";

    document.getElementById("galleryTitle").textContent = isResults
        ? "Галерея результатів обробки"
        : "Галерея завантажених зображень";

    document.querySelectorAll(".gswitch-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.target === target);
    });
}

// ── Saved-result comparison modal ───────────────────────────────────────────────
const resultsModal = document.getElementById("resultsModal");
const resultsCloseBtn = document.getElementById("resultsCloseBtn");

function openResultsModal(card) {
    const d = card.dataset;

    document.getElementById("resultsFilename").textContent = d.source;
    document.getElementById("resultsAlpha").textContent = d.alpha;
    document.getElementById("resultsDate").textContent = d.date;

    document.getElementById("resFracImg").src = d.fracUrl;
    document.getElementById("resFracTime").textContent = d.fracTime;
    document.getElementById("resFracSNR").textContent = d.fracSnr;

    document.getElementById("resSobelImg").src = d.sobelUrl;
    document.getElementById("resSobelTime").textContent = d.sobelTime;
    document.getElementById("resSobelSNR").textContent = d.sobelSnr;

    resetZoom();
    resultsModal.style.display = "flex";
}

resultsCloseBtn.onclick = function () {
    resultsModal.style.display = "none";
    resetZoom();
};

resultsModal.onclick = function (event) {
    if (event.target === resultsModal) {
        resultsModal.style.display = "none";
        resetZoom();
    }
};

// ── Synchronized magnifier: hover one image → both zoom in at same point ──────────
const ZOOM_FACTOR = 2.4;
const zoomImgs = [
    document.getElementById("resFracImg"),
    document.getElementById("resSobelImg"),
];

function resetZoom() {
    zoomImgs.forEach(img => {
        img.style.transform = "scale(1)";
        img.style.transformOrigin = "center center";
    });
}

document.querySelectorAll("#resultsComparison .zoom-frame").forEach(frame => {
    frame.addEventListener("mousemove", function (e) {
        const rect = frame.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        zoomImgs.forEach(img => {
            img.style.transformOrigin = `${x}% ${y}%`;
            img.style.transform = `scale(${ZOOM_FACTOR})`;
        });
    });
    frame.addEventListener("mouseleave", resetZoom);
});

// ── Upload ────────────────────────────────────────────────────────────────────
function confirmDelete(filename) {
    if (confirm("Ви впевнені, що хочете видалити файл " + filename + "?")) {
        fetch("/delete/" + filename, { method: "DELETE" })
            .then(() => location.reload());
    }
}

document.getElementById("fileInput").addEventListener("change", function () {
    const file = this.files[0];
    if (!file) return;

    const dotIndex = file.name.lastIndexOf(".");
    const nameWithout = file.name.substring(0, dotIndex);
    const extension = file.name.substring(dotIndex);

    document.getElementById("customName").value = nameWithout;
    document.getElementById("fileExtension").textContent = extension;
    document.getElementById("renameSection").style.display = "block";
    document.getElementById("nameError").style.display = "none";
});

function validateFilename(name) {
    if (name.trim() === "")
        return "Файл не може бути без назви.";
    if (name.length > 100)
        return "Довжина назви файлу повинна не перевищувати 100 символів";
    if (!/^[a-zA-Z0-9_\-. ]+$/.test(name))
        return "Ім'я файлу може містити лише літери, цифри, пробіли, дефіси, символи підкреслення та крапки.";
    return null;
}

async function uploadImage() {
    const fileInput = document.getElementById("fileInput");
    if (!fileInput.files.length) {
        alert("Будь ласка, спочатку оберіть файл!");
        return;
    }
    const customName = document.getElementById("customName").value.trim();
    const extension = document.getElementById("fileExtension").textContent;
    const nameError = document.getElementById("nameError");

    const error = validateFilename(customName);
    if (error) {
        nameError.textContent = error;
        nameError.style.display = "block";
        return;
    }

    nameError.style.display = "none";

    const finalFilename = customName + extension;
    const formData = new FormData();
    formData.append("file", fileInput.files[0], finalFilename);

    const response = await fetch("/upload", {
        method: "POST",
        body: formData
    });

    if (response.status === 409) {
        const data = await response.json();
        nameError.textContent = data.error;
        nameError.style.display = "block";
    } else {
        location.reload();
    }
}

// ── Processing modal ──────────────────────────────────────────────────────────
const processModal = document.getElementById("processModal");
const processCloseBtn = document.getElementById("processCloseBtn");

let currentFilename = null;

function openProcessModal(filename) {
    currentFilename = filename;
    document.getElementById("processFilename").textContent = filename;

    // Скидаємо повзунок до α = 0.5
    alphaSlider.value = "0.5";
    alphaValue.textContent = "0.5";
    fracAlphaLabel.textContent = "0.5";

    // Ховаємо попередні результати й показуємо спінер (без миготіння старого фото)
    document.getElementById("processResults").style.display = "none";
    document.getElementById("classicalImg").src = "";
    document.getElementById("secondaryImg").src = "";
    document.getElementById("classicalTime").textContent = "—";
    document.getElementById("classicalSNR").textContent = "—";
    document.getElementById("secondaryTime").textContent = "—";
    document.getElementById("secondarySNR").textContent = "—";
    document.getElementById("processSpinner").style.display = "block";

    processModal.style.display = "flex";
    // Одразу обробляємо обидва методи (дробовий α=0.5 + Sobel)
    previewBoth();
}

processCloseBtn.onclick = function () {
    processModal.style.display = "none";
};

processModal.onclick = function (event) {
    if (event.target === processModal) {
        processModal.style.display = "none";
    }
};

// ── Повзунок α: real-time превʼю дробового методу ────────────────────────────────
const alphaSlider = document.getElementById("alphaSlider");
const alphaValue = document.getElementById("alphaValue");
const fracAlphaLabel = document.getElementById("fracAlphaLabel");

let previewTimer = null;
let previewSeq = 0;

function currentAlpha() {
    return parseFloat(alphaSlider.value).toFixed(1);
}

alphaSlider.addEventListener("input", function () {
    const a = currentAlpha();
    alphaValue.textContent = a;
    fracAlphaLabel.textContent = a;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(previewFractional, 180);
});

function _applyFractional(frac) {
    const img = document.getElementById("classicalImg");
    img.src = frac.data_url;
    img.style.opacity = "1";
    document.getElementById("classicalTime").textContent = frac.time_ms;
    document.getElementById("classicalSNR").textContent = frac.snr;
    fracAlphaLabel.textContent = parseFloat(frac.alpha).toFixed(1);
}

function _applySobel(sobel) {
    document.getElementById("secondaryImg").src = sobel.data_url;
    document.getElementById("secondaryTime").textContent = sobel.time_ms;
    document.getElementById("secondarySNR").textContent = sobel.snr;
}

// Початкове превʼю при відкритті вікна: обидва методи одразу (без запису в БД)
async function previewBoth() {
    if (!currentFilename) return;

    const seq = ++previewSeq;
    const alpha = currentAlpha();

    try {
        const response = await fetch(
            `/preview/${encodeURIComponent(currentFilename)}?alpha=${alpha}&with_sobel=true`,
            { method: "POST" }
        );
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const data = await response.json();
        if (seq !== previewSeq) return;

        _applyFractional(data.fractional);
        _applySobel(data.sobel);
        document.getElementById("processResults").style.display = "block";
    } catch (err) {
        alert("Помилка обробки: " + err.message);
    } finally {
        if (seq === previewSeq) {
            document.getElementById("processSpinner").style.display = "none";
        }
    }
}

// Превʼю лише дробового методу — для руху повзунка α
async function previewFractional() {
    if (!currentFilename) return;

    const seq = ++previewSeq;
    const alpha = currentAlpha();
    const img = document.getElementById("classicalImg");
    img.style.opacity = "0.4";

    try {
        const response = await fetch(
            `/preview/${encodeURIComponent(currentFilename)}?alpha=${alpha}`,
            { method: "POST" }
        );
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const data = await response.json();
        if (seq !== previewSeq) return;  // прийшла застаріла відповідь — ігноруємо

        _applyFractional(data.fractional);
    } catch (err) {
        if (seq === previewSeq) {
            document.getElementById("classicalTime").textContent = "—";
            document.getElementById("classicalSNR").textContent = "—";
        }
    } finally {
        if (seq === previewSeq) img.style.opacity = "1";
    }
}

async function runProcessing() {
    if (!currentFilename) return;

    const runBtn = document.getElementById("runBtn");
    const alpha = currentAlpha();

    document.getElementById("processSpinner").style.display = "block";
    runBtn.disabled = true;

    try {
        const response = await fetch(
            `/process/${encodeURIComponent(currentFilename)}?alpha=${alpha}`,
            { method: "POST" }
        );

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const data = await response.json();

        document.getElementById("classicalImg").src = data.classical.url;
        document.getElementById("classicalImg").style.opacity = "1";
        document.getElementById("classicalTime").textContent = data.classical.time_ms;
        document.getElementById("classicalSNR").textContent = data.classical.snr;
        fracAlphaLabel.textContent = parseFloat(data.classical.alpha).toFixed(1);

        document.getElementById("secondaryImg").src = data.secondary.url;
        document.getElementById("secondaryTime").textContent = data.secondary.time_ms;
        document.getElementById("secondarySNR").textContent = data.secondary.snr;

        document.getElementById("processResults").style.display = "block";
    } catch (err) {
        alert("Помилка обробки: " + err.message);
    } finally {
        document.getElementById("processSpinner").style.display = "none";
        runBtn.disabled = false;
    }
}
