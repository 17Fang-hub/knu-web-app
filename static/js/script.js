// ── Scroll lock ──────────────────────────────────────────────────────────────
function lockScroll()   { document.body.style.overflow = "hidden"; }
function unlockScroll() { document.body.style.overflow = ""; }

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
        lockScroll();
    };
});

imageCloseBtn.onclick = function () {
    imageModal.style.display = "none";
    unlockScroll();
};

imageModal.onclick = function (event) {
    if (event.target === imageModal) {
        imageModal.style.display = "none";
        unlockScroll();
    }
};

// ── Info / about modal ─────────────────────────────────────────────────────────
const infoModal = document.getElementById("infoModal");
const infoBtn = document.getElementById("infoBtn");
const infoCloseBtn = document.getElementById("infoCloseBtn");

infoBtn.onclick = function () {
    infoModal.style.display = "flex";
    lockScroll();
};

infoCloseBtn.onclick = function () {
    infoModal.style.display = "none";
    unlockScroll();
};

infoModal.onclick = function (event) {
    if (event.target === infoModal) {
        infoModal.style.display = "none";
        unlockScroll();
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
let currentResultCard = null;

function openResultsModal(card) {
    currentResultCard = card;
    const d = card.dataset;

    document.getElementById("resultsFilename").textContent = d.source;
    document.getElementById("resultsAlpha").textContent = d.alpha;
    document.getElementById("resultsDate").textContent = d.date;

    const origImg = document.getElementById("resOrigImg");
    origImg.onerror = function () { origImg.onerror = null; origImg.src = window.ORIG_FALLBACK; };
    origImg.src = d.origUrl;

    document.getElementById("resFracImg").src = d.fracUrl;
    document.getElementById("resFracTime").textContent = d.fracTime;
    document.getElementById("resFracSNR").textContent = d.fracSnr;

    document.getElementById("resSobelImg").src = d.sobelUrl;
    document.getElementById("resSobelTime").textContent = d.sobelTime;
    document.getElementById("resSobelSNR").textContent = d.sobelSnr;

    resetZoom();
    resultsModal.style.display = "flex";
    lockScroll();
}

function _closeResultsModal() {
    resultsModal.style.display = "none";
    resetZoom();
    unlockScroll();
}

resultsCloseBtn.onclick = _closeResultsModal;

resultsModal.onclick = function (event) {
    if (event.target === resultsModal) _closeResultsModal();
};

// ── Delete result ─────────────────────────────────────────────────────────────
async function _doDeleteResult(card) {
    const id = card.dataset.id;
    const response = await fetch(`/result/${id}`, { method: "DELETE" });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        alert("Помилка видалення: " + (err.error || response.status));
        return;
    }

    card.remove();

    const grid = document.querySelector("#resultsGallery .results-grid");
    if (grid && grid.children.length === 0) {
        grid.remove();
        const msg = document.createElement("p");
        msg.className = "empty-msg";
        msg.textContent = "Поки що немає збережених результатів обробки.";
        document.getElementById("resultsGallery").appendChild(msg);

        const csvBtn = document.querySelector(".btn-export");
        if (csvBtn) {
            const span = document.createElement("span");
            span.className = "btn-export btn-export-disabled";
            span.innerHTML = "&#x2193; Експортувати результати (CSV)";
            csvBtn.replaceWith(span);
        }
    }
}

function confirmDeleteResult(card) {
    if (!confirm(`Видалити результат обробки «${card.dataset.source}»?`)) return;
    _doDeleteResult(card);
}

function confirmDeleteResultFromModal() {
    if (!currentResultCard) return;
    if (!confirm(`Видалити результат обробки «${currentResultCard.dataset.source}»?`)) return;
    const card = currentResultCard;
    _closeResultsModal();
    currentResultCard = null;
    _doDeleteResult(card);
}

// ── Synchronized magnifier: hover one image → both zoom in at same point ──────────
const ZOOM_FACTOR = 2.4;
const zoomImgs = [
    document.getElementById("resOrigImg"),
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
    lockScroll();
    // Одразу обробляємо обидва методи (дробовий α=0.5 + Sobel)
    previewBoth();
}

processCloseBtn.onclick = function () {
    processModal.style.display = "none";
    unlockScroll();
};

processModal.onclick = function (event) {
    if (event.target === processModal) {
        processModal.style.display = "none";
        unlockScroll();
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

function _formatNow() {
    const d = new Date();
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function _fmtSnr(v) {
    return (v === null || v === undefined) ? "—" : parseFloat(v).toFixed(2);
}

function _insertResultCard(filename, data) {
    const alpha = parseFloat(data.classical.alpha).toFixed(1);
    const fracUrl  = data.classical.url;
    const sobelUrl = data.secondary.url;
    const origUrl  = `/static/uploads/${encodeURIComponent(filename)}`;
    const fracTime  = parseFloat(data.classical.time_ms).toFixed(1);
    const sobelTime = parseFloat(data.secondary.time_ms).toFixed(1);
    const fracSnr   = _fmtSnr(data.classical.snr);
    const sobelSnr  = _fmtSnr(data.secondary.snr);
    const date = _formatNow();

    const card = document.createElement("div");
    card.className = "result-card";
    card.dataset.id       = data.id;
    card.dataset.source   = filename;
    card.dataset.origUrl  = origUrl;
    card.dataset.alpha    = alpha;
    card.dataset.fracUrl  = fracUrl;
    card.dataset.fracTime = fracTime;
    card.dataset.fracSnr  = fracSnr;
    card.dataset.sobelUrl  = sobelUrl;
    card.dataset.sobelTime = sobelTime;
    card.dataset.sobelSnr  = sobelSnr;
    card.dataset.date = date;
    card.setAttribute("onclick", "openResultsModal(this)");

    const fallback = `this.onerror=null;this.src=window.ORIG_FALLBACK`;
    card.innerHTML = `
        <div class="result-thumbs">
            <img src="${origUrl}" alt="Оригінал" onerror="${fallback}">
            <img src="${fracUrl}" alt="Дробовий">
            <img src="${sobelUrl}" alt="Sobel">
        </div>
        <div class="result-info">
            <span class="result-name">${filename}</span>
            <span class="result-badge">α = ${alpha}</span>
        </div>
        <button class="result-delete-btn"
            onclick="event.stopPropagation(); confirmDeleteResult(this.closest('.result-card'))">
            Видалити
        </button>`;

    const gallery = document.getElementById("resultsGallery");

    // Remove empty-msg placeholder if present
    const empty = gallery.querySelector(".empty-msg");
    if (empty) empty.remove();

    // Create the grid if this is the very first result
    let grid = gallery.querySelector(".results-grid");
    if (!grid) {
        grid = document.createElement("div");
        grid.className = "gallery results-grid";
        gallery.appendChild(grid);
    }

    grid.prepend(card);

    // Enable the CSV export button if it was disabled
    const csvBtn = document.querySelector(".btn-export-disabled");
    if (csvBtn) {
        const link = document.createElement("a");
        link.href = "/export-csv";
        link.className = "btn-export";
        link.innerHTML = "&#x2193; Експортувати результати (CSV)";
        csvBtn.replaceWith(link);
    }
}

async function runProcessing() {
    if (!currentFilename) return;

    const runBtn = document.getElementById("runBtn");
    const alpha = currentAlpha();

    const originalText = runBtn.textContent;
    runBtn.disabled = true;
    runBtn.textContent = "Збереження…";

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

        _insertResultCard(currentFilename, data);

        runBtn.textContent = "Збережено ✓";
        setTimeout(() => { runBtn.textContent = originalText; }, 2000);
    } catch (err) {
        alert("Помилка обробки: " + err.message);
        runBtn.textContent = originalText;
    } finally {
        runBtn.disabled = false;
    }
}
