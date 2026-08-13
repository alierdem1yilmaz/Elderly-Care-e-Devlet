// Sahiplik: Kişi 3 (Frontend & Demo)
// API_CONTRACT.md ile aynı şemaya göre çalışır.

const API_BASE = "http://127.0.0.1:8000";

// --- Tabs ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// --- TTS (sesli çıktı) ---
function speak(text) {
  try {
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "tr-TR";
    speechSynthesis.speak(utter);
  } catch (e) {
    console.warn("TTS kullanılamıyor:", e);
  }
}

// --- Chat ---
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  appendMessage("user", message);
  chatInput.value = "";

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    appendMessage("assistant", data.reply);
    speak(data.reply);
    if (data.case) renderCase(data.case);
  } catch (err) {
    appendMessage("assistant", "Bağlantı sorunu oluştu. (backend çalışıyor mu?)");
    console.error(err);
  }
});

// --- Rehber & Aile Görünümü paneli ---
function renderCase(caseData) {
  const eligibilityList = document.getElementById("eligibility-list");
  eligibilityList.innerHTML = "";
  (caseData.eligibility || []).forEach((e) => {
    const li = document.createElement("li");
    li.textContent = `${e.program}: ${e.eligible ? "Hak sahibi olabilirsiniz" : "Şu an uygun görünmüyor"} — ${e.reason}`;
    eligibilityList.appendChild(li);
  });

  const checklist = document.getElementById("checklist-list");
  checklist.innerHTML = "";
  (caseData.checklist || []).forEach((c) => {
    const li = document.createElement("li");
    li.textContent = c.item;
    if (c.done) li.classList.add("done");
    checklist.appendChild(li);
  });

  const notifications = document.getElementById("notifications-list");
  notifications.innerHTML = "";
  (caseData.notifications || []).slice().reverse().forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n.message;
    li.classList.add(n.type);
    notifications.appendChild(li);
  });
}

async function loadCase() {
  try {
    const res = await fetch(`${API_BASE}/case`);
    renderCase(await res.json());
  } catch (err) {
    console.warn("Case yüklenemedi:", err);
  }
}

// --- Scripted demo senaryoları ---
document.getElementById("btn-missing-doc").addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/scenario/missing-document`, { method: "POST" });
  const data = await res.json();
  renderCase(data);
  const last = data.notifications[data.notifications.length - 1];
  if (last) speak(last.message);
});

document.getElementById("btn-suspicious-sms").addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/scenario/suspicious-sms`, { method: "POST" });
  const data = await res.json();
  renderCase(data);
  const last = data.notifications[data.notifications.length - 1];
  if (last) speak(last.message);
});

// --- Açılışta backend'e bağlan ---
async function waitForBackend(retries = 15) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${API_BASE}/ping`);
      if (res.ok) {
        appendMessage("assistant", "Merhaba! Size sosyal yardımlar konusunda nasıl yardımcı olabilirim?");
        loadCase();
        return;
      }
    } catch (e) {
      /* backend henüz hazır değil, tekrar dene */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  appendMessage("assistant", "Backend'e bağlanılamadı. Lütfen backend'in çalıştığından emin olun (uvicorn backend.main:app --port 8000).");
}

waitForBackend();
