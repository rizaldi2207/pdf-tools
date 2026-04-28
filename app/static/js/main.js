const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const selectedFilename = document.getElementById("selected-filename");
const clearBtn = document.getElementById("clear-btn");
const convertBtn = document.getElementById("convert-btn");
const progressSection = document.getElementById("progress-section");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const resultSection = document.getElementById("result-section");
const resultTitle = document.getElementById("result-title");
const imageGrid = document.getElementById("image-grid");
const downloadAllBtn = document.getElementById("download-all-btn");
const docxResultSection = document.getElementById("docx-result-section");
const docxDownloadBtn = document.getElementById("docx-download-btn");
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const toast = document.getElementById("toast");
const fmtGroup = document.getElementById("fmt-group");
const dpiGroup = document.getElementById("dpi-group");
const pdfPasswordInput = document.getElementById("pdf-password");
const pwEyeBtn = document.getElementById("pw-eye-btn");
const pwEyeOpen = document.getElementById("pw-eye-open");
const pwEyeClosed = document.getElementById("pw-eye-closed");

let selectedOutput = "images";
let selectedFmt = "png";
let selectedDpi = "150";
let currentFile = null;
let toastTimer = null;

// Output type toggle
document.querySelectorAll("#output-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#output-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedOutput = btn.dataset.value;
    fmtGroup.classList.toggle("hidden", selectedOutput === "docx");
    dpiGroup.classList.toggle("hidden", selectedOutput === "docx");
  });
});

// Format toggle
document.querySelectorAll("#fmt-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#fmt-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedFmt = btn.dataset.value;
  });
});

// DPI toggle
document.querySelectorAll("#dpi-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#dpi-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedDpi = btn.dataset.value;
  });
});

// Password show/hide
pwEyeBtn.addEventListener("click", () => {
  const show = pdfPasswordInput.type === "password";
  pdfPasswordInput.type = show ? "text" : "password";
  pwEyeOpen.classList.toggle("hidden", show);
  pwEyeClosed.classList.toggle("hidden", !show);
});

// Drag & drop
dropzone.addEventListener("dragover", e => { e.preventDefault(); dropzone.classList.add("drag-over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
dropzone.addEventListener("drop", e => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
dropzone.addEventListener("click", e => {
  if (e.target === dropzone || e.target.closest(".dropzone-inner")) fileInput.click();
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showToast("Only PDF files are supported", "error"); return;
  }
  if (file.size > 52428800) {
    showToast("File exceeds 50 MB limit", "error"); return;
  }
  currentFile = file;
  selectedFilename.textContent = file.name;
  selectedFile.classList.remove("hidden");
  convertBtn.disabled = false;
  hideResults();
  progressSection.classList.add("hidden");
}

clearBtn.addEventListener("click", () => {
  currentFile = null;
  fileInput.value = "";
  pdfPasswordInput.value = "";
  selectedFile.classList.add("hidden");
  convertBtn.disabled = true;
  hideResults();
  progressSection.classList.add("hidden");
});

function hideResults() {
  resultSection.classList.add("hidden");
  docxResultSection.classList.add("hidden");
}

// Convert
convertBtn.addEventListener("click", async () => {
  if (!currentFile) return;
  convertBtn.disabled = true;
  progressSection.classList.remove("hidden");
  hideResults();
  animateProgress();
  try {
    if (selectedOutput === "docx") {
      await convertToDocx();
    } else {
      await convertToImages();
    }
  } finally {
    convertBtn.disabled = false;
  }
});

async function convertToImages() {
  const form = new FormData();
  form.append("file", currentFile);
  form.append("format", selectedFmt);
  form.append("dpi", selectedDpi);
  form.append("password", pdfPasswordInput.value.trim());

  try {
    const res = await fetch("/convert", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Conversion failed");
    finishProgress();
    setTimeout(() => {
      progressSection.classList.add("hidden");
      showImageResults(data);
    }, 400);
  } catch (err) {
    progressSection.classList.add("hidden");
    showToast(err.message, "error");
  }
}

async function convertToDocx() {
  const form = new FormData();
  form.append("file", currentFile);
  form.append("password", pdfPasswordInput.value.trim());

  try {
    const res = await fetch("/convert-docx", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Conversion failed");
    finishProgress();
    setTimeout(() => {
      progressSection.classList.add("hidden");
      showDocxResult(data);
    }, 400);
  } catch (err) {
    progressSection.classList.add("hidden");
    showToast(err.message, "error");
  }
}

function animateProgress() {
  progressBar.value = 0;
  progressLabel.textContent = "Converting...";
  let pct = 0;
  const interval = setInterval(() => {
    pct += Math.random() * 10;
    if (pct >= 90) { clearInterval(interval); pct = 90; }
    progressBar.value = pct;
  }, 300);
  progressBar._interval = interval;
}

function finishProgress() {
  if (progressBar._interval) clearInterval(progressBar._interval);
  progressBar.value = 100;
  progressLabel.textContent = "Done!";
}

function showImageResults(data) {
  resultTitle.textContent = `${data.total_pages} page${data.total_pages !== 1 ? "s" : ""} · ${data.format.toUpperCase()} · ${data.dpi} DPI`;
  downloadAllBtn.onclick = () => { window.location.href = data.zip_url; };

  imageGrid.innerHTML = "";
  data.images.forEach(img => {
    const card = document.createElement("div");
    card.className = "image-card";
    card.innerHTML = `
      <img src="${img.url}" alt="Page ${img.page}" loading="lazy" />
      <div class="image-card-footer">
        <span class="page-label">Page ${img.page}</span>
        <button class="dl-btn" aria-label="Download page ${img.page}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>
          </svg>
        </button>
      </div>`;
    card.querySelector("img").addEventListener("click", () => openLightbox(img.url, `Page ${img.page}`));
    card.querySelector(".dl-btn").addEventListener("click", e => {
      e.stopPropagation();
      downloadFile(img.url, img.filename);
    });
    imageGrid.appendChild(card);
  });

  resultSection.classList.remove("hidden");
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showDocxResult(data) {
  docxDownloadBtn.onclick = e => {
    e.preventDefault();
    downloadFile(data.download_url, "converted.docx");
  };
  docxResultSection.classList.remove("hidden");
  docxResultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  setTimeout(() => downloadFile(data.download_url, "converted.docx"), 600);
}

function downloadFile(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}

// Lightbox — uses native <dialog> element
function openLightbox(src, altText) {
  lbImg.src = src;
  lbImg.alt = altText || "";
  lightbox.showModal();
}

lightbox.addEventListener("click", e => {
  if (e.target === lightbox) lightbox.close();
});
lightbox.querySelector(".lb-close").addEventListener("click", () => lightbox.close());
lightbox.addEventListener("close", () => { lbImg.src = ""; lbImg.alt = ""; });

// Toast
function showToast(msg, type = "") {
  if (toastTimer) clearTimeout(toastTimer);
  toast.textContent = msg;
  toast.className = "toast" + (type ? " " + type : "");
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}
