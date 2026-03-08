const modal = document.getElementById("imageModal");
const modalImg = document.getElementById("fullImage");
const captionText = document.getElementById("caption");
const closeBtn = document.querySelector(".close-btn");

document.querySelectorAll(".gallery-item img").forEach(img => {
    img.onclick = function() {
        modal.style.display = "flex";
        modalImg.src = this.src;
        captionText.innerHTML = this.alt;
    }
});

closeBtn.onclick = function() {
    modal.style.display = "none";
}

modal.onclick = function(event) {
    if (event.target === modal) {
        modal.style.display = "none";
    }
}

function confirmDelete(filename) {
    if (confirm("Are you sure you want to delete " + filename + "?")) {
        fetch("/delete/" + filename, { method: "DELETE" })
            .then(() => location.reload());
    }
}

async function uploadImage() {
    const fileInput = document.getElementById("fileInput");
    if (!fileInput.files.length) {
        alert("Please select a file first.");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    const response = await fetch("/upload", {
        method: "POST",
        body: formData
    });

    if (response.status === 409) {
        const data = await response.json();
        alert(data.error);
    } else {
        location.reload();
    }
}