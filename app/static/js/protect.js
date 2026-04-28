const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const selectedFilename = document.getElementById("selected-filename");
const clearBtn = document.getElementById("clear-btn");
const protectBtn = document.getElementById("protect-btn");
const progressSection = document.getElementById("progress-section");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const resultSection = document.getElementById("protect-result-section");
const downloadBtn = document.getElementById("protected-download-btn");
const toast = document.getElementById("toast");

const currentPwInput = document.getElementById("current-password");
const userPwInput = document.getElementById("user-password");
const ownerPwInput = document.getElementById("owner-password");

let selectedEnc = "256";
let currentFile = null;
let toastTimer = null;

// Encryption toggle
document.querySelectorAll("#enc-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#enc-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedEnc = btn.dataset.value;
  });
});

// Password show/hide — handles all three fields via data-target
document.querySelectorAll(".pw-eye-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const input = document.getElementById(btn.dataset.target);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.querySelector(".eye-open").classList.toggle("hidden", show);
    btn.querySelector(".eye-closed").classList.toggle("hidden", !show);
  });
});

// Enable protect button when user password has a value
userPwInput.addEventListener("input", () => {
  protectBtn.disabled = !currentFile || !userPwInput.value.trim();
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
  protectBtn.disabled = !userPwInput.value.trim();
  resultSection.classList.add("hidden");
  progressSection.classList.add("hidden");
}

clearBtn.addEventListener("click", () => {
  currentFile = null;
  fileInput.value = "";
  currentPwInput.value = "";
  userPwInput.value = "";
  ownerPwInput.value = "";
  selectedFile.classList.add("hidden");
  protectBtn.disabled = true;
  resultSection.classList.add("hidden");
  progressSection.classList.add("hidden");
});

// Protect
protectBtn.addEventListener("click", async () => {
  if (!currentFile || !userPwInput.value.trim()) return;

  protectBtn.disabled = true;
  progressSection.classList.remove("hidden");
  resultSection.classList.add("hidden");
  animateProgress();

  const form = new FormData();
  form.append("file", currentFile);
  form.append("current_password", currentPwInput.value.trim());
  form.append("user_password", userPwInput.value.trim());
  form.append("owner_password", ownerPwInput.value.trim());
  form.append("encryption", selectedEnc);

  try {
    const res = await fetch("/add-password", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to protect PDF");

    finishProgress();
    setTimeout(() => {
      progressSection.classList.add("hidden");
      showResult(data);
    }, 400);
  } catch (err) {
    progressSection.classList.add("hidden");
    showToast(err.message, "error");
  } finally {
    protectBtn.disabled = !userPwInput.value.trim();
  }
});

function animateProgress() {
  progressBar.value = 0;
  progressLabel.textContent = "Protecting...";
  let pct = 0;
  const interval = setInterval(() => {
    pct += Math.random() * 15;
    if (pct >= 90) { clearInterval(interval); pct = 90; }
    progressBar.value = pct;
  }, 200);
  progressBar._interval = interval;
}

function finishProgress() {
  if (progressBar._interval) clearInterval(progressBar._interval);
  progressBar.value = 100;
  progressLabel.textContent = "Done!";
}

function showResult(data) {
  downloadBtn.onclick = e => {
    e.preventDefault();
    downloadFile(data.download_url, "protected.pdf");
  };
  resultSection.classList.remove("hidden");
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  setTimeout(() => downloadFile(data.download_url, "protected.pdf"), 600);
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
