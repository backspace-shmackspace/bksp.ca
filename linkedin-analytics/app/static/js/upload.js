/**
 * upload.js — Drag-and-drop file upload handling.
 *
 * Wires up the drop zone on /upload to:
 *   - Accept drag-and-drop of .xlsx/.xls/.csv files
 *   - Display the selected filename
 *   - Show an upload progress state on submit
 */

(function () {
  "use strict";

  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileNameDisplay = document.getElementById("file-name-display");
  const fileNameText = document.getElementById("file-name-text");
  const submitBtn = document.getElementById("submit-btn");
  const uploadForm = document.getElementById("upload-form");

  if (!dropZone || !fileInput) return;

  // ---------------------------------------------------------------------------
  // Show selected filename
  // ---------------------------------------------------------------------------

  function showFileName(name) {
    if (!name) return;
    fileNameText.textContent = name;
    fileNameDisplay.classList.remove("hidden");
  }

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) {
      showFileName(fileInput.files[0].name);
    }
  });

  // ---------------------------------------------------------------------------
  // Drag-and-drop events
  // ---------------------------------------------------------------------------

  function preventDefault(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ["dragenter", "dragover"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      preventDefault(e);
      dropZone.classList.add("border-accent/60", "bg-accent/10");
      dropZone.classList.remove("border-white/10");
    });
  });

  ["dragleave", "dragend"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      preventDefault(e);
      dropZone.classList.remove("border-accent/60", "bg-accent/10");
      dropZone.classList.add("border-white/10");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    preventDefault(e);
    dropZone.classList.remove("border-accent/60", "bg-accent/10");
    dropZone.classList.add("border-white/10");

    const files = e.dataTransfer && e.dataTransfer.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const allowed = [".xlsx", ".xls", ".csv"];
    const ext = "." + file.name.split(".").pop().toLowerCase();

    if (!allowed.includes(ext)) {
      alert(`Unsupported file type: ${ext}\nAllowed: ${allowed.join(", ")}`);
      return;
    }

    // Assign to the file input via DataTransfer
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    showFileName(file.name);
  });

  // ---------------------------------------------------------------------------
  // Submit state
  // ---------------------------------------------------------------------------

  if (uploadForm) {
    uploadForm.addEventListener("submit", () => {
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Importing…";
      }
    });
  }
})();
