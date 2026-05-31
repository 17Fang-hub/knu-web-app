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
    document.getElementById("processResults").style.display = "none";
    document.getElementById("processSpinner").style.display = "none";
    processModal.style.display = "flex";
}

processCloseBtn.onclick = function () {
    processModal.style.display = "none";
};

processModal.onclick = function (event) {
    if (event.target === processModal) {
        processModal.style.display = "none";
    }
};

async function runProcessing() {
    if (!currentFilename) return;

    const runBtn = document.getElementById("runBtn");

    document.getElementById("processResults").style.display = "none";
    document.getElementById("processSpinner").style.display = "block";
    runBtn.disabled = true;

    try {
        const response = await fetch(`/process/${encodeURIComponent(currentFilename)}`, {
            method: "POST",
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Помилка сервера (${response.status})`);
        }

        const data = await response.json();

        document.getElementById("classicalImg").src = data.classical.url;
        document.getElementById("classicalTime").textContent = data.classical.time_ms;
        document.getElementById("classicalSNR").textContent = data.classical.snr;

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
