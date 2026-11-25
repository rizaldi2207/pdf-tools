const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const selectedFilename = document.getElementById("selected-filename");
const clearBtn = document.getElementById("clear-btn");
const convertBtn = document.getElementById("convert-btn");
const progressSection = document.getElementById("progress-section");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const pdfResultSection = document.getElementById("pdf-result-section");
const mdResultSection = document.getElementById("md-result-section");
const pdfDownloadBtn = document.getElementById("pdf-download-btn");
const mdDownloadBtn = document.getElementById("md-download-btn");
const toast = document.getElementById("toast");

let selectedOutput = "pdf";
let currentFile = null;
let toastTimer = null;

document.querySelectorAll("#output-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#output-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedOutput = btn.dataset.value;
  });
});

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
  if (!file.name.toLowerCase().endsWith(".docx")) {
    showToast("Only DOCX files are supported", "error"); return;
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
  selectedFile.classList.add("hidden");
  convertBtn.disabled = true;
  hideResults();
  progressSection.classList.add("hidden");
});

function hideResults() {
  pdfResultSection.classList.add("hidden");
  mdResultSection.classList.add("hidden");
}

convertBtn.addEventListener("click", async () => {
  if (!currentFile) return;
  convertBtn.disabled = true;
  progressSection.classList.remove("hidden");
  hideResults();
  animateProgress();

  const form = new FormData();
  form.append("file", currentFile);

  const endpoint = selectedOutput === "pdf" ? "/convert-docx-to-pdf" : "/convert-docx-to-md";

  try {
    const res = await fetch(endpoint, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Conversion failed");
    finishProgress();
    setTimeout(() => {
      progressSection.classList.add("hidden");
      if (selectedOutput === "pdf") {
        showPdfResult(data);
      } else {
        showMdResult(data);
      }
    }, 400);
  } catch (err) {
    progressSection.classList.add("hidden");
    showToast(err.message, "error");
  } finally {
    convertBtn.disabled = false;
  }
});

function animateProgress() {
  progressBar.value = 0;
  progressLabel.textContent = "Converting...";
  let pct = 0;
  const interval = setInterval(() => {
    pct += Math.random() * 8;
    if (pct >= 90) { clearInterval(interval); pct = 90; }
    progressBar.value = pct;
  }, 400);
  progressBar._interval = interval;
}

function finishProgress() {
  if (progressBar._interval) clearInterval(progressBar._interval);
  progressBar.value = 100;
  progressLabel.textContent = "Done!";
}

function showPdfResult(data) {
  pdfDownloadBtn.onclick = e => {
    e.preventDefault();
    downloadFile(data.download_url, "converted.pdf");
  };
  pdfResultSection.classList.remove("hidden");
  pdfResultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  setTimeout(() => downloadFile(data.download_url, "converted.pdf"), 600);
}

function showMdResult(data) {
  mdDownloadBtn.onclick = e => {
    e.preventDefault();
    downloadFile(data.download_url, "converted.md");
  };
  mdResultSection.classList.remove("hidden");
  mdResultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  setTimeout(() => downloadFile(data.download_url, "converted.md"), 600);
}

function downloadFile(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}

function showToast(msg, type = "") {
  if (toastTimer) clearTimeout(toastTimer);
  toast.textContent = msg;
  toast.className = "toast" + (type ? " " + type : "");
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}
