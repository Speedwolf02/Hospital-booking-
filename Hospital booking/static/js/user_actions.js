// static/js/user_actions.js

let aiMode = false;
let voiceBookingActive = false;
let listening = false;
let currentStep = 0;

let bookingData = {
  name: null,
  email: null,
  booking_time: null,
  issue_description: null,
  session_type: null
};

// DOM Elements
let chatLog, statusText;
let userNameInput, userEmailInput, bookingTimeInput, sessionTypeSelect, issueTextarea;
let doctorIdInput, bookingStatus;
let btnCheckSlot, btnOpenConfirm;

// Modal Elements
let confirmModal, btnConfirmSave, btnConfirmCancel;

/* ================= CHAT HELPER ================= */

function appendChat(speaker, text) {
  if (!chatLog || !text) return;
  const div = document.createElement("div");
  div.className = "chat-line";
  div.textContent = `${speaker}: ${text}`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

/* ================= TTS (TEXT TO SPEECH) ================= */

async function speakText(text) {
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (!data.audio_url) return;

    return new Promise(resolve => {
      const audio = new Audio(data.audio_url);
      audio.onended = resolve;
      audio.play();
    });
  } catch (err) {
    console.error("TTS error:", err);
  }
}

/* ================= VOICE FLOW LOGIC ================= */

function getNextIncompleteStep() {
  if (!bookingData.name) return 0;
  if (!bookingData.email) return 1;
  if (!bookingData.booking_time) return 2;
  if (!bookingData.issue_description) return 3;
  if (!bookingData.session_type) return 4;
  return 5;
}

function sanitizeAIText(text) {
  if (!text) return "Please answer.";
  return text
    .split("\n")[0]
    .replace(/[^\x00-\x7F]/g, "")
    .replace(/\[.*?\]/g, "")
    .trim();
}

async function getQuestionText(step) {
  if (!aiMode) {
    return [
      "What is your name?",
      "Please say your email address.",
      "Please say your booking date and time like 10 December 12 PM.",
      "Please describe your issue.",
      "Say online or offline for the session type."
    ][step];
  }

  const prompts = [
    "Ask only the patient's name.",
    "Ask only the patient's email address.",
    "Ask booking date and time. Example: 10 December 12 PM.",
    "Ask the patient's health issue.",
    "Ask whether the session is online or offline."
  ];

  try {
    const res = await fetch("/api/tinyllama/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompts[step] })
    });
    const data = await res.json();
    return sanitizeAIText(data.reply);
  } catch {
    return "Please answer.";
  }
}

async function runNextQuestion() {
  if (!voiceBookingActive) return;

  currentStep = getNextIncompleteStep();
  if (currentStep >= 5) {
    const msg = "All details collected. Please review and confirm the booking.";
    appendChat("Assistant", msg);
    await speakText(msg);
    voiceBookingActive = false;
    listening = false;
    return;
  }

  const question = await getQuestionText(currentStep);
  appendChat("Assistant", question);

  listening = false;
  await speakText(question);

  if (!voiceBookingActive) return;
  listening = true;
  // Assumes you have a helper function 'startRecording' defined elsewhere or imported
  if (typeof startRecording === "function") {
    startRecording("/api/stt/whisper");
  } else {
    console.error("startRecording function is missing. Check your recorder.js or audio script.");
  }
}

/* ================= PROCESS VOICE REPLY ================= */

async function processReply(text) {
  if (!voiceBookingActive) return;

  if (!text || text === "[BLANK_AUDIO]") {
    listening = true;
    if (typeof startRecording === "function") startRecording("/api/stt/whisper");
    return;
  }

  appendChat("User", text);

  if (currentStep === 0) {
    bookingData.name = text;
    userNameInput.value = text;
  } else if (currentStep === 1) {
    bookingData.email = text.replace(/\s+/g, "").toLowerCase();
    userEmailInput.value = bookingData.email;
  } else if (currentStep === 2) {
    const res = await fetch("/api/parse_booking_time", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spoken: text })
    });
    const data = await res.json();

    if (!data.ok) {
      const msg = "I could not understand the date. Please say it like 10 December 12 PM.";
      appendChat("Assistant", msg);
      await speakText(msg);
      listening = true;
      if (typeof startRecording === "function") startRecording("/api/stt/whisper");
      return;
    }

    const chosen = new Date(data.iso.replace(" ", "T"));
    if (chosen < new Date()) {
      const msg = "That date has already passed. Please say a future date.";
      appendChat("Assistant", msg);
      await speakText(msg);
      listening = true;
      if (typeof startRecording === "function") startRecording("/api/stt/whisper");
      return;
    }

    bookingData.booking_time = data.iso;
    bookingTimeInput.value = data.iso;
  } else if (currentStep === 3) {
    bookingData.issue_description = text;
    issueTextarea.value = text;
  } else if (currentStep === 4) {
    bookingData.session_type = text.toLowerCase().includes("online") ? "online" : "offline";
    sessionTypeSelect.value = bookingData.session_type;
  }

  await runNextQuestion();
}

/* ================= DOM CONTENT LOADED ================= */

document.addEventListener("DOMContentLoaded", () => {
  // --- Initialize Elements ---
  chatLog = document.getElementById("chat-log");
  statusText = document.getElementById("stt-text");

  userNameInput = document.getElementById("user-name");
  userEmailInput = document.getElementById("user-email");
  bookingTimeInput = document.getElementById("booking-time");
  sessionTypeSelect = document.getElementById("session-type");
  issueTextarea = document.getElementById("issue");

  doctorIdInput = document.getElementById("selected-doctor-id");
  bookingStatus = document.getElementById("booking-status");

  btnCheckSlot = document.getElementById("btn-check-slot");
  btnOpenConfirm = document.getElementById("btn-open-confirm");

  // Modal elements
  confirmModal = document.getElementById("booking-confirm-modal");
  btnConfirmSave = document.getElementById("btn-confirm-save");
  btnConfirmCancel = document.getElementById("btn-confirm-cancel");

  /* ================= DOCTOR SELECTION ================= */
  document.querySelectorAll(".doctor-card").forEach(card => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".doctor-card").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      doctorIdInput.value = card.dataset.doctorId;
      bookingStatus.textContent = "";
      btnOpenConfirm.disabled = true; // Reset confirm button if doctor changes
    });
  });

  /* ================= AI & VOICE CONTROLS ================= */
  document.getElementById("ai-toggle")?.addEventListener("change", e => {
    aiMode = e.target.checked;
    appendChat("System", aiMode ? "AI mode enabled." : "AI mode disabled.");
  });

  document.getElementById("btn-start-voice-booking")?.addEventListener("click", async () => {
    voiceBookingActive = true;
    listening = false;

    // Reset data
    bookingData = {
      name: null,
      email: null,
      booking_time: null,
      issue_description: null,
      session_type: null
    };

    currentStep = 0;
    appendChat("System", "Voice booking started.");
    await runNextQuestion();
  });

  document.getElementById("btn-stop-voice-booking")?.addEventListener("click", () => {
    voiceBookingActive = false;
    listening = false;
    appendChat("System", "Voice booking stopped.");
  });

  document.addEventListener("stt-response", async e => {
    if (!voiceBookingActive || !listening) return;
    listening = false;
    await processReply(e.detail || "");
  });

  /* ================= CHECK SLOT ================= */
  btnCheckSlot?.addEventListener("click", async () => {
    if (!doctorIdInput.value) {
      bookingStatus.textContent = "Please select a doctor.";
      bookingStatus.style.color = "#ef4444";
      return;
    }
    if (!bookingTimeInput.value) {
      bookingStatus.textContent = "Please enter booking time.";
      bookingStatus.style.color = "#ef4444";
      return;
    }

    bookingStatus.textContent = "Checking availability...";
    bookingStatus.style.color = "#9ca3af";

    try {
      const res = await fetch("/api/check_slot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctor_id: doctorIdInput.value,
          booking_time: bookingTimeInput.value
        })
      });

      const data = await res.json();

      bookingStatus.textContent = data.reason || "Slot Available!";
      bookingStatus.style.color = data.available ? "#22c55e" : "#ef4444";
      btnOpenConfirm.disabled = !data.available;
    } catch {
      bookingStatus.textContent = "Error checking slot.";
      bookingStatus.style.color = "#ef4444";
      btnOpenConfirm.disabled = true;
    }
  });

  /* ================= CONFIRM MODAL LOGIC (THE MISSING PART) ================= */

  // 1. Open Modal
  btnOpenConfirm?.addEventListener("click", () => {
    if (confirmModal) {
      // Fill modal data
      document.getElementById("confirm-name").textContent = userNameInput.value;
      document.getElementById("confirm-email").textContent = userEmailInput.value;
      document.getElementById("confirm-time").textContent = bookingTimeInput.value;
      document.getElementById("confirm-session").textContent = sessionTypeSelect.value;
      document.getElementById("confirm-issue").textContent = issueTextarea.value;

      const selectedDoc = document.querySelector(".doctor-card.selected h3");
      document.getElementById("confirm-doctor").textContent = selectedDoc ? selectedDoc.textContent : "Unknown";

      // Show modal
      confirmModal.classList.remove("hidden");
    }
  });

  // 2. Close Modal
  btnConfirmCancel?.addEventListener("click", () => {
    if (confirmModal) confirmModal.classList.add("hidden");
  });

  // 3. Save Booking (API Call)
  btnConfirmSave?.addEventListener("click", async () => {
    const payload = {
      doctor_id: doctorIdInput.value,
      booking_time: bookingTimeInput.value,
      issue_description: issueTextarea.value,
      session_type: sessionTypeSelect.value
    };

    btnConfirmSave.textContent = "Booking...";
    btnConfirmSave.disabled = true;

    try {
      const res = await fetch("/api/book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        alert("Booking Successful!");
        window.location.reload();
      } else {
        alert("Error: " + data.message);
        btnConfirmSave.textContent = "Confirm";
        btnConfirmSave.disabled = false;
      }
    } catch (err) {
      console.error(err);
      alert("Server error occurred.");
      btnConfirmSave.textContent = "Confirm";
      btnConfirmSave.disabled = false;
    }
  });

  /* ================= CANCEL BOOKING LOGIC ================= */
  document.querySelectorAll(".btn-cancel-booking").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to cancel?")) return;
      
      const bookingId = btn.dataset.id;
      const reason = prompt("Enter reason for cancellation:");
      if (!reason) return;

      try {
        const res = await fetch(`/api/booking/${bookingId}/cancel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason })
        });
        const data = await res.json();
        if (data.success) window.location.reload();
        else alert("Failed to cancel booking.");
      } catch (err) {
        console.error(err);
        alert("Error cancelling booking.");
      }
    });
  });
  /* ================= PRESCRIPTION UPLOAD & SCAN ================= */
  document.querySelectorAll(".btn-upload-presc").forEach(btn => {
    btn.addEventListener("click", async () => {
      const bookingId = btn.dataset.id;
      const fileInput = document.getElementById(`presc-file-${bookingId}`);
      const resultDiv = document.getElementById(`scan-result-${bookingId}`);
      const aiText = resultDiv.querySelector(".ai-text");

      if (!fileInput.files[0]) {
        alert("Please select an image first.");
        return;
      }

      const formData = new FormData();
      formData.append("prescription", fileInput.files[0]);
      formData.append("booking_id", bookingId);

      btn.textContent = "Scanning...";
      btn.disabled = true;

      try {
        const res = await fetch("/api/upload_scan_prescription", {
          method: "POST",
          body: formData
        });
        const data = await res.json();

        if (data.success) {
          resultDiv.classList.remove("hidden");
          aiText.textContent = data.analysis;
          alert("Upload and Scan Complete!");
        } else {
          alert("Error: " + data.message);
        }
      } catch (err) {
        console.error(err);
        alert("Scan failed.");
      } finally {
        btn.textContent = "Upload & Scan";
        btn.disabled = false;
      }
    });
  });
  /* ================= TRANSFER BOOKING ================= */
  // document.querySelectorAll(".btn-doc-transfer").forEach(btn => {
  //   btn.addEventListener("click", async () => {
  //     // 1. Get list of doctors (You can also pre-load this)
  //     const newDocId = prompt("Enter the ID of the Doctor you want to transfer to:");
  //     if (!newDocId) return;

  //     const res = await fetch(`/api/doctor/booking/${btn.dataset.id}/transfer`, {
  //       method: "POST",
  //       headers: { "Content-Type": "application/json" },
  //       body: JSON.stringify({ new_doctor_id: newDocId })
  //     });

  //     const data = await res.json();
  //     alert(data.message);
  //     if (data.success) location.reload();
  //   });
  // });
});