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

// ── Metrics helpers ────────────────────────────────────────────────────────────

// [apiKey, pm-frac-id, pm-sobel-id, rm-frac-id, rm-sobel-id, dataset-frac-key, dataset-sobel-key, formatter]
const METRICS_DEF = [
    ["edge_density",          "pmFracDensity",  "pmSobelDensity",  "rmFracDensity",  "rmSobelDensity",  "fracEdgeDensity",    "sobelEdgeDensity",    v => v.toFixed(4)],
    ["mean_edge_strength",    "pmFracStrength", "pmSobelStrength", "rmFracStrength", "rmSobelStrength", "fracMeanStrength",   "sobelMeanStrength",   v => v.toFixed(4)],
    ["num_components",        "pmFracNumComp",  "pmSobelNumComp",  "rmFracNumComp",  "rmSobelNumComp",  "fracNumComp",        "sobelNumComp",        v => String(Math.round(v))],
    ["mean_component_length", "pmFracMeanLen",  "pmSobelMeanLen",  "rmFracMeanLen",  "rmSobelMeanLen",  "fracMeanLen",        "sobelMeanLen",        v => v.toFixed(1)],
    ["fragmentation",         "pmFracFrag",     "pmSobelFrag",     "rmFracFrag",     "rmSobelFrag",     "fracFrag",           "sobelFrag",           v => v.toFixed(6)],
    ["contrast_ratio",        "pmFracContrast", "pmSobelContrast", "rmFracContrast", "rmSobelContrast", "fracContrast",       "sobelContrast",       v => v.toFixed(4)],
];

function _fmtMetric(val, fmt) {
    if (val === null || val === undefined || val === "" || val === "—") return "—";
    const n = parseFloat(val);
    return isNaN(n) ? "—" : fmt(n);
}

/** Update the GL-Canny column of the processing-modal metrics table. */
function _updatePmFrac(m) {
    METRICS_DEF.forEach(([key, fracId, , , , , , fmt]) => {
        const el = document.getElementById(fracId);
        if (el) el.textContent = _fmtMetric(m[key], fmt);
    });
}

/** Update the Sobel column of the processing-modal metrics table. */
function _updatePmSobel(m) {
    METRICS_DEF.forEach(([key, , sobelId, , , , , fmt]) => {
        const el = document.getElementById(sobelId);
        if (el) el.textContent = _fmtMetric(m[key], fmt);
    });
}

/** Reset all processing-modal metric cells to "—". */
function _resetPmMetrics() {
    METRICS_DEF.forEach(([, fracId, sobelId]) => {
        const f = document.getElementById(fracId);
        const s = document.getElementById(sobelId);
        if (f) f.textContent = "—";
        if (s) s.textContent = "—";
    });
}

/** Populate the results-modal metrics table from a result card's dataset. */
function _populateRmMetrics(d) {
    METRICS_DEF.forEach(([, , , rmFracId, rmSobelId, dsFracKey, dsSobelKey, fmt]) => {
        const fEl = document.getElementById(rmFracId);
        const sEl = document.getElementById(rmSobelId);
        if (fEl) fEl.textContent = _fmtMetric(d[dsFracKey], fmt);
        if (sEl) sEl.textContent = _fmtMetric(d[dsSobelKey], fmt);
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

    document.getElementById("resSobelImg").src = d.sobelUrl;
    document.getElementById("resSobelTime").textContent = d.sobelTime;

    _populateRmMetrics(d);
    _renderResultsNoise(card);

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

    alphaSlider.value = "0.5";
    alphaValue.textContent = "0.5";
    fracAlphaLabel.textContent = "0.5";
    _updateSliderFill(alphaSlider);

    document.getElementById("processResults").style.display = "none";
    document.getElementById("classicalImg").src = "";
    document.getElementById("secondaryImg").src = "";
    document.getElementById("classicalTime").textContent = "—";
    document.getElementById("secondaryTime").textContent = "—";
    _resetPmMetrics();
    _resetNoiseTest();
    document.getElementById("processSpinner").style.display = "block";

    processModal.style.display = "flex";
    lockScroll();
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

// ── Alpha slider: real-time fractional preview ────────────────────────────────
const alphaSlider = document.getElementById("alphaSlider");
const alphaValue = document.getElementById("alphaValue");
const fracAlphaLabel = document.getElementById("fracAlphaLabel");

let previewTimer = null;
let previewSeq = 0;

function currentAlpha() {
    return parseFloat(alphaSlider.value).toFixed(1);
}

function _updateSliderFill(slider) {
    const pct = (slider.value - slider.min) / (slider.max - slider.min) * 100;
    slider.style.setProperty("--fill-pct", pct.toFixed(2) + "%");
}

_updateSliderFill(alphaSlider);

alphaSlider.addEventListener("input", function () {
    const a = currentAlpha();
    alphaValue.textContent = a;
    fracAlphaLabel.textContent = a;
    _updateSliderFill(this);
    clearTimeout(previewTimer);
    previewTimer = setTimeout(previewFractional, 180);
    // The noise chart was computed for a previous α — invalidate it.
    _resetNoiseTest();
});

function _applyFractional(frac) {
    const img = document.getElementById("classicalImg");
    img.src = frac.data_url;
    img.style.opacity = "1";
    document.getElementById("classicalTime").textContent = frac.time_ms;
    fracAlphaLabel.textContent = parseFloat(frac.alpha).toFixed(1);
    _updatePmFrac(frac);
}

function _applySobel(sobel) {
    document.getElementById("secondaryImg").src = sobel.data_url;
    document.getElementById("secondaryTime").textContent = sobel.time_ms;
    _updatePmSobel(sobel);
}

// Initial preview on modal open: both methods at once (no DB write)
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

// Preview only the fractional method — triggered by alpha slider movement
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
        if (seq !== previewSeq) return;

        _applyFractional(data.fractional);
    } catch (err) {
        if (seq === previewSeq) {
            document.getElementById("classicalTime").textContent = "—";
            _resetPmMetrics();
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

function _insertResultCard(filename, data, noiseData) {
    const alpha    = parseFloat(data.classical.alpha).toFixed(1);
    const fracUrl  = data.classical.url;
    const sobelUrl = data.secondary.url;
    const origUrl  = `/static/uploads/${encodeURIComponent(filename)}`;
    const fracTime  = parseFloat(data.classical.time_ms).toFixed(1);
    const sobelTime = parseFloat(data.secondary.time_ms).toFixed(1);
    const date = _formatNow();

    const card = document.createElement("div");
    card.className = "result-card";
    card.dataset.id        = data.id;
    card.dataset.source    = filename;
    card.dataset.origUrl   = origUrl;
    card.dataset.alpha     = alpha;
    card.dataset.fracUrl   = fracUrl;
    card.dataset.fracTime  = fracTime;
    card.dataset.sobelUrl  = sobelUrl;
    card.dataset.sobelTime = sobelTime;
    card.dataset.date      = date;
    card.dataset.noise     = noiseData ? JSON.stringify(noiseData) : "";

    // Store all new metrics in dataset
    METRICS_DEF.forEach(([key, , , , , dsFracKey, dsSobelKey]) => {
        const fracVal  = data.classical[key];
        const sobelVal = data.secondary[key];
        card.dataset[dsFracKey]  = (fracVal  !== undefined && fracVal  !== null) ? fracVal  : "";
        card.dataset[dsSobelKey] = (sobelVal !== undefined && sobelVal !== null) ? sobelVal : "";
    });

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

    const empty = gallery.querySelector(".empty-msg");
    if (empty) empty.remove();

    let grid = gallery.querySelector(".results-grid");
    if (!grid) {
        grid = document.createElement("div");
        grid.className = "gallery results-grid";
        gallery.appendChild(grid);
    }

    grid.prepend(card);

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
        fracAlphaLabel.textContent = parseFloat(data.classical.alpha).toFixed(1);

        document.getElementById("secondaryImg").src = data.secondary.url;
        document.getElementById("secondaryTime").textContent = data.secondary.time_ms;

        _updatePmFrac(data.classical);
        _updatePmSobel(data.secondary);

        document.getElementById("processResults").style.display = "block";

        // Persist the noise test together with the pair, but only if it was
        // computed for the same α that is now being saved.
        let noiseToSave = null;
        if (lastNoise && Math.abs(lastNoise.alpha - parseFloat(alpha)) < 1e-9) {
            noiseToSave = lastNoise.data;
            try {
                await fetch(`/result/${data.id}/noise`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(noiseToSave),
                });
            } catch (e) {
                noiseToSave = null;  // persistence failed → no chart on the card
            }
        }

        _insertResultCard(currentFilename, data, noiseToSave);

        runBtn.textContent = "Збережено ✓";
        setTimeout(() => { runBtn.textContent = originalText; }, 2000);
    } catch (err) {
        alert("Помилка обробки: " + err.message);
        runBtn.textContent = originalText;
    } finally {
        runBtn.disabled = false;
    }
}

// ── Noise-robustness test (IoU vs σ) ────────────────────────────────────────────
// Charts are keyed by canvas id: one for the processing modal (preview),
// one for the saved-result modal.
const noiseCharts = { noiseChart: null, resultsNoiseChart: null };

// Last computed (preview) noise test, awaiting persistence with the saved pair.
let lastNoise = null;

function _resetNoiseTest() {
    const wrap = document.getElementById("noiseChartWrap");
    const spinner = document.getElementById("noiseSpinner");
    if (wrap) wrap.style.display = "none";
    if (spinner) spinner.style.display = "none";
    if (noiseCharts.noiseChart) { noiseCharts.noiseChart.destroy(); noiseCharts.noiseChart = null; }
    lastNoise = null;
}

function _cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return v ? v.trim() : fallback;
}

function _renderNoiseChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return;

    const labels = data.noise_levels.map(v => "σ=" + v);

    const tick = _cssVar("--text-soft", "#7d8696");
    const grid = _cssVar("--border", "rgba(125,134,150,0.25)");

    if (noiseCharts[canvasId]) noiseCharts[canvasId].destroy();
    noiseCharts[canvasId] = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "GL-Canny",
                    data: data.gl_canny_iou,
                    borderColor: "#4f8cff",
                    backgroundColor: "rgba(79,140,255,0.15)",
                    borderWidth: 2,
                    tension: 0.25,
                    pointRadius: 4,
                },
                {
                    label: "Sobel",
                    data: data.sobel_iou,
                    borderColor: "#ff7d4f",
                    backgroundColor: "rgba(255,125,79,0.15)",
                    borderWidth: 2,
                    tension: 0.25,
                    pointRadius: 4,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: {
                y: {
                    min: 0, max: 1,
                    title: { display: true, text: "IoU з чистою картою", color: tick },
                    ticks: { color: tick },
                    grid: { color: grid },
                },
                x: {
                    title: { display: true, text: "Рівень гаусового шуму σ", color: tick },
                    ticks: { color: tick },
                    grid: { color: grid },
                },
            },
            plugins: {
                legend: { position: "top", labels: { color: tick } },
            },
        },
    });
}

async function runNoiseRobustness() {
    if (!currentFilename) return;

    const btn = document.getElementById("noiseTestBtn");
    const spinner = document.getElementById("noiseSpinner");
    const wrap = document.getElementById("noiseChartWrap");
    const alpha = currentAlpha();

    btn.disabled = true;
    wrap.style.display = "none";
    spinner.style.display = "block";

    try {
        const response = await fetch(
            `/analyze/noise-robustness/${encodeURIComponent(currentFilename)}?alpha=${alpha}`,
            { method: "POST" }
        );
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const data = await response.json();
        // Cache for persistence with the saved pair (tagged with the α it used).
        lastNoise = { alpha: parseFloat(alpha), data };
        _renderNoiseChart("noiseChart", data);
        wrap.style.display = "block";
    } catch (err) {
        alert("Помилка тесту робастності: " + err.message);
    } finally {
        spinner.style.display = "none";
        btn.disabled = false;
    }
}

// Render the saved-result modal chart from a card's data-noise attribute.
function _renderResultsNoise(card) {
    const wrap = document.getElementById("resultsNoiseWrap");
    const empty = document.getElementById("resultsNoiseEmpty");
    if (noiseCharts.resultsNoiseChart) {
        noiseCharts.resultsNoiseChart.destroy();
        noiseCharts.resultsNoiseChart = null;
    }

    let data = null;
    const raw = card.dataset.noise;
    if (raw && raw !== "") {
        try { data = JSON.parse(raw); } catch (e) { data = null; }
    }

    if (data && Array.isArray(data.noise_levels) && data.noise_levels.length) {
        wrap.style.display = "block";
        empty.style.display = "none";
        _renderNoiseChart("resultsNoiseChart", data);
    } else {
        wrap.style.display = "none";
        empty.style.display = "block";
    }
}
