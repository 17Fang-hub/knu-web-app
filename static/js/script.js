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

// ── Metric formatting helpers ────────────────────────────────────────────────
function _fmtNum(val, digits) {
    if (val === null || val === undefined || val === "") return "—";
    const n = parseFloat(val);
    return isNaN(n) ? "—" : n.toFixed(digits);
}

function _alphaStr(a) {
    return parseFloat(a).toFixed(1);
}

/**
 * Render the per-α metrics table into a <tbody>. `alphas` is a list of
 * {alpha, gl_edge_density, der, dcr, dcs, gl_time_ms}. The row matching
 * `selectedAlpha` gets the .alpha-row-active class.
 */
function _renderAlphaTable(tbodyId, alphas, selectedAlpha) {
    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = "";
    alphas.forEach(a => {
        const tr = document.createElement("tr");
        const active = Math.abs(a.alpha - selectedAlpha) < 1e-9;
        if (active) tr.className = "alpha-row-active";
        tr.innerHTML =
            `<td>${_alphaStr(a.alpha)}</td>` +
            `<td>${_fmtNum(a.gl_edge_density, 4)}</td>` +
            `<td>${_fmtNum(a.der, 4)}</td>` +
            `<td>${_fmtNum(a.dcr, 4)}</td>` +
            `<td>${_fmtNum(a.dcs, 4)}</td>` +
            `<td>${_fmtNum(a.gl_time_ms, 1)}</td>`;
        tbody.appendChild(tr);
    });
}

function _sobelFootText(sobel) {
    return `Sobel: edge density = ${_fmtNum(sobel.edge_density, 4)}, час = ${_fmtNum(sobel.time_ms, 1)} мс`;
}

function _findAlpha(alphas, alpha) {
    let best = alphas[0];
    let bestDiff = Infinity;
    alphas.forEach(a => {
        const d = Math.abs(a.alpha - alpha);
        if (d < bestDiff) { bestDiff = d; best = a; }
    });
    return best;
}

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
const sigmaSelect = document.getElementById("sigmaSelect");
const alphaSelect = document.getElementById("alphaSelect");

let currentFilename = null;
let currentPreview = null;   // last preview payload {sigma, sobel, alphas}
let previewSeq = 0;

function _selectedSigma() { return parseFloat(sigmaSelect.value); }
function _selectedAlpha() { return parseFloat(alphaSelect.value); }

function openProcessModal(filename) {
    currentFilename = filename;
    currentPreview = null;
    document.getElementById("processFilename").textContent = filename;

    sigmaSelect.value = "0";
    alphaSelect.value = "0.5";

    document.getElementById("processResults").style.display = "none";
    document.getElementById("processSpinner").style.display = "block";

    processModal.style.display = "flex";
    lockScroll();
    loadPreview();
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

function _applyProcessView() {
    if (!currentPreview) return;
    const alpha = _selectedAlpha();
    const a = _findAlpha(currentPreview.alphas, alpha);
    const sobel = currentPreview.sobel;

    document.getElementById("fracAlphaLabel").textContent = _alphaStr(a.alpha);
    document.getElementById("fracSigmaLabel").textContent = String(currentPreview.sigma);
    document.getElementById("classicalImg").src = a.data_url;
    document.getElementById("classicalImg").style.opacity = "1";
    document.getElementById("classicalTime").textContent = a.gl_time_ms;
    document.getElementById("classicalDensity").textContent = _fmtNum(a.gl_edge_density, 4);

    document.getElementById("secondaryImg").src = sobel.data_url;
    document.getElementById("secondaryTime").textContent = sobel.time_ms;
    document.getElementById("secondaryDensity").textContent = _fmtNum(sobel.edge_density, 4);

    _renderAlphaTable("processAlphaTbody", currentPreview.alphas, a.alpha);
    document.getElementById("processSobelFoot").textContent = _sobelFootText(sobel);
}

async function loadPreview() {
    if (!currentFilename) return;

    const seq = ++previewSeq;
    const sigma = _selectedSigma();

    document.getElementById("processResults").style.display = "none";
    document.getElementById("processSpinner").style.display = "block";

    try {
        const response = await fetch(
            `/preview/${encodeURIComponent(currentFilename)}?sigma=${sigma}`,
            { method: "POST" }
        );
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const data = await response.json();
        if (seq !== previewSeq) return;

        currentPreview = data;
        _applyProcessView();
        document.getElementById("processResults").style.display = "block";
    } catch (err) {
        alert("Помилка обробки: " + err.message);
    } finally {
        if (seq === previewSeq) {
            document.getElementById("processSpinner").style.display = "none";
        }
    }
}

function onProcessSigmaChange() {
    loadPreview();
}

function onProcessAlphaChange() {
    _applyProcessView();
}

// ── Save a run (all α) ─────────────────────────────────────────────────────────
function _insertResultCard(run) {
    const origUrl = `/static/uploads/${encodeURIComponent(run.source_filename)}`;
    const firstGl = run.alphas.length ? run.alphas[0].url : "";

    const card = document.createElement("div");
    card.className = "result-card";
    card.dataset.id = run.id;
    card.dataset.run = JSON.stringify(run);
    card.setAttribute("onclick", "openResultsModal(this)");

    const fallback = `this.onerror=null;this.src=window.ORIG_FALLBACK`;
    card.innerHTML = `
        <div class="result-thumbs">
            <img src="${origUrl}" alt="Оригінал" onerror="${fallback}">
            <img src="${firstGl}" alt="GL-Canny">
            <img src="${run.sobel.url}" alt="Sobel">
        </div>
        <div class="result-info">
            <span class="result-name">${run.source_filename}</span>
            <span class="result-badge">σ = ${run.sigma}</span>
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
    const sigma = _selectedSigma();

    const originalText = runBtn.textContent;
    runBtn.disabled = true;
    runBtn.textContent = "Збереження…";

    try {
        const response = await fetch(
            `/process/${encodeURIComponent(currentFilename)}?sigma=${sigma}`,
            { method: "POST" }
        );

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const run = await response.json();
        _insertResultCard(run);

        runBtn.textContent = "Збережено ✓";
        setTimeout(() => { runBtn.textContent = originalText; }, 2000);
    } catch (err) {
        alert("Помилка обробки: " + err.message);
        runBtn.textContent = originalText;
    } finally {
        runBtn.disabled = false;
    }
}

// ── Saved-result comparison modal ───────────────────────────────────────────────
const resultsModal = document.getElementById("resultsModal");
const resultsCloseBtn = document.getElementById("resultsCloseBtn");
const resultsAlphaSelect = document.getElementById("resultsAlphaSelect");
let currentResultCard = null;
let currentRun = null;

function openResultsModal(card) {
    currentResultCard = card;
    let run;
    try { run = JSON.parse(card.dataset.run); } catch (e) { return; }
    currentRun = run;

    document.getElementById("resultsFilename").textContent = run.source_filename;
    document.getElementById("resultsSigma").textContent = run.sigma;

    const origImg = document.getElementById("resOrigImg");
    origImg.onerror = function () { origImg.onerror = null; origImg.src = window.ORIG_FALLBACK; };
    origImg.src = `/static/uploads/${encodeURIComponent(run.source_filename)}`;

    document.getElementById("resSobelImg").src = run.sobel.url;
    document.getElementById("resSobelTime").textContent = _fmtNum(run.sobel.time_ms, 1);
    document.getElementById("resSobelDensity").textContent = _fmtNum(run.sobel.edge_density, 4);
    document.getElementById("resultsSobelFoot").textContent = _sobelFootText(run.sobel);

    // Populate α selector (default to 0.5 if present, else first).
    resultsAlphaSelect.innerHTML = "";
    let defaultIdx = 0;
    run.alphas.forEach((a, i) => {
        const opt = document.createElement("option");
        opt.value = String(a.alpha);
        opt.textContent = _alphaStr(a.alpha);
        resultsAlphaSelect.appendChild(opt);
        if (Math.abs(a.alpha - 0.5) < 1e-9) defaultIdx = i;
    });
    resultsAlphaSelect.selectedIndex = defaultIdx;

    _applyResultsView();

    resetZoom();
    resultsModal.style.display = "flex";
    lockScroll();
}

function _applyResultsView() {
    if (!currentRun) return;
    const alpha = parseFloat(resultsAlphaSelect.value);
    const a = _findAlpha(currentRun.alphas, alpha);

    document.getElementById("resFracAlpha").textContent = _alphaStr(a.alpha);
    document.getElementById("resFracImg").src = a.url;
    document.getElementById("resFracTime").textContent = _fmtNum(a.gl_time_ms, 1);
    document.getElementById("resFracDensity").textContent = _fmtNum(a.gl_edge_density, 4);

    _renderAlphaTable("resultsAlphaTbody", currentRun.alphas, a.alpha);
    resetZoom();
}

function onResultsAlphaChange() {
    _applyResultsView();
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
    let name = card.dataset.id;
    try { name = JSON.parse(card.dataset.run).source_filename; } catch (e) {}
    if (!confirm(`Видалити результат обробки «${name}»?`)) return;
    _doDeleteResult(card);
}

function confirmDeleteResultFromModal() {
    if (!currentResultCard) return;
    const name = currentRun ? currentRun.source_filename : "";
    if (!confirm(`Видалити результат обробки «${name}»?`)) return;
    const card = currentResultCard;
    _closeResultsModal();
    currentResultCard = null;
    _doDeleteResult(card);
}

// ── Synchronized magnifier: hover one image → all zoom in at same point ──────────
const ZOOM_FACTOR = 2.4;
const zoomImgs = [
    document.getElementById("resOrigImg"),
    document.getElementById("resFracImg"),
    document.getElementById("resSobelImg"),
];

function resetZoom() {
    zoomImgs.forEach(img => {
        if (!img) return;
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
            if (!img) return;
            img.style.transformOrigin = `${x}% ${y}%`;
            img.style.transform = `scale(${ZOOM_FACTOR})`;
        });
    });
    frame.addEventListener("mouseleave", resetZoom);
});
