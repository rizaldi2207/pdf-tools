const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const selectedFilename = document.getElementById("selected-filename");
const clearBtn = document.getElementById("clear-btn");
const progressSection = document.getElementById("progress-section");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const resultSection = document.getElementById("protect-result-section");
const downloadBtn = document.getElementById("protected-download-btn");
const downloadBtnLabel = document.getElementById("download-btn-label");
const resultTitle = document.getElementById("result-title");
const resultSub = document.getElementById("result-sub");
const resultIcon = document.getElementById("result-icon");
const toast = document.getElementById("toast");

// Protect mode elements
const protectOptions = document.getElementById("protect-options");
const protectBtn = document.getElementById("protect-btn");
const currentPwInput = document.getElementById("current-password");
const userPwInput = document.getElementById("user-password");
const ownerPwInput = document.getElementById("owner-password");

// Unprotect mode elements
const unprotectOptions = document.getElementById("unprotect-options");
const unprotectBtn = document.getElementById("unprotect-btn");
const removePwInput = document.getElementById("remove-password");

let selectedEnc = "256";
let currentFile = null;
let currentMode = "protect";
let toastTimer = null;

// Mode toggle
document.querySelectorAll("#mode-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#mode-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentMode = btn.dataset.mode;
    switchMode(currentMode);
  });
});

function switchMode(mode) {
  resultSection.classList.add("hidden");
  progressSection.classList.add("hidden");

  if (mode === "protect") {
    protectOptions.classList.remove("hidden");
    unprotectOptions.classList.add("hidden");
    protectBtn.disabled = !currentFile || !userPwInput.value.trim();
  } else {
    protectOptions.classList.add("hidden");
    unprotectOptions.classList.remove("hidden");
    unprotectBtn.disabled = !currentFile || !removePwInput.value.trim();
  }
}

// Encryption toggle
document.querySelectorAll("#enc-toggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#enc-toggle .seg-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedEnc = btn.dataset.value;
  });
});

// Password show/hide — handles all fields via data-target
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

// Enable unprotect button when remove password has a value
removePwInput.addEventListener("input", () => {
  unprotectBtn.disabled = !currentFile || !removePwInput.value.trim();
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
  unprotectBtn.disabled = !removePwInput.value.trim();
  resultSection.classList.add("hidden");
  progressSection.classList.add("hidden");
}

clearBtn.addEventListener("click", () => {
  currentFile = null;
  fileInput.value = "";
  currentPwInput.value = "";
  userPwInput.value = "";
  ownerPwInput.value = "";
  removePwInput.value = "";
  selectedFile.classList.add("hidden");
  protectBtn.disabled = true;
  unprotectBtn.disabled = true;
  resultSection.classList.add("hidden");
  progressSection.classList.add("hidden");
});

// Protect
protectBtn.addEventListener("click", async () => {
  if (!currentFile || !userPwInput.value.trim()) return;

  protectBtn.disabled = true;
  progressSection.classList.remove("hidden");
  resultSection.classList.add("hidden");
  animateProgress("Protecting...");

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
      showResult(data, "protect");
    }, 400);
  } catch (err) {
    progressSection.classList.add("hidden");
    showToast(err.message, "error");
  } finally {
    protectBtn.disabled = !userPwInput.value.trim();
  }
});

// Unprotect
unprotectBtn.addEventListener("click", async () => {
  if (!currentFile || !removePwInput.value.trim()) return;

  unprotectBtn.disabled = true;
  progressSection.classList.remove("hidden");
  resultSection.classList.add("hidden");
  animateProgress("Removing password...");

  const form = new FormData();
  form.append("file", currentFile);
  form.append("password", removePwInput.value.trim());

  try {
    const res = await fetch("/remove-password", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to remove password");

    finishProgress();
    setTimeout(() => {
      progressSection.classList.add("hidden");
      showResult(data, "unprotect");
    }, 400);
  } catch (err) {
    progressSection.classList.add("hidden");
    showToast(err.message, "error");
  } finally {
    unprotectBtn.disabled = !removePwInput.value.trim();
  }
});

function animateProgress(label) {
  progressBar.value = 0;
  progressLabel.textContent = label;
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

const PROTECT_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
  <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
</svg>`;

const UNPROTECT_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
  <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 119 0v3.75M3.75 21.75h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
</svg>`;

function showResult(data, mode) {
  if (mode === "protect") {
    resultIcon.innerHTML = PROTECT_ICON_SVG;
    resultIcon.className = "result-card-icon icon-accent";
    resultTitle.textContent = "PDF protected successfully";
    resultSub.textContent = "Your PDF is now password-protected";
    downloadBtnLabel.textContent = "Download Protected PDF";
    downloadBtn.onclick = e => {
      e.preventDefault();
      downloadFile(data.download_url, "protected.pdf");
    };
    setTimeout(() => downloadFile(data.download_url, "protected.pdf"), 600);
  } else {
    resultIcon.innerHTML = UNPROTECT_ICON_SVG;
    resultIcon.className = "result-card-icon icon-green";
    resultTitle.textContent = "Password removed successfully";
    resultSub.textContent = "Your PDF is now unlocked and password-free";
    downloadBtnLabel.textContent = "Download Unlocked PDF";
    downloadBtn.onclick = e => {
      e.preventDefault();
      downloadFile(data.download_url, "unprotected.pdf");
    };
    setTimeout(() => downloadFile(data.download_url, "unprotected.pdf"), 600);
  }

  resultSection.classList.remove("hidden");
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
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
