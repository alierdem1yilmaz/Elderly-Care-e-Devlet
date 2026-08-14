// Sahiplik: Kişi 3 (Frontend & Demo)
// API_CONTRACT.md ile aynı şemaya göre çalışır.

// Electron dosyayı file:// ile açıyor (yerel backend'e gitmeli) — web/Railway
// dağıtımında ise aynı backend arayüzü de kendi üzerinden sunduğu için
// (bkz. backend/main.py'deki StaticFiles mount) sayfanın kendi origin'i yeterli.
const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : window.location.origin;

// --- Vaka kimliği (case_id) ---
// Backend artık her yaşlı profili için ayrı bir vaka dosyası tutuyor (Supabase'e
// taşındı), bu yüzden her istek "hangi kişiye ait" olduğunu bir case_id ile
// belirtmeli. Aile hesabına GERÇEK bağlama (telefon numarası eşleştirme, mobil
// app'ten görünme vb.) ileride bir eşleştirme koduyla yapılabilir (bkz.
// POST /pair) — ama masaüstü uygulamasının ilk açılışta çalışabilmesi için bunu
// beklemiyoruz: cihazda kalıcı, yerel bir kimlik kendiliğinden oluşturuluyor.
const CASE_ID_STORAGE_KEY = "bakim_rehber_case_id";
let CASE_ID = localStorage.getItem(CASE_ID_STORAGE_KEY);
if (!CASE_ID) {
  CASE_ID = crypto.randomUUID();
  localStorage.setItem(CASE_ID_STORAGE_KEY, CASE_ID);
}

// Case'e özel endpoint'lere X-Case-Id başlığını otomatik ekleyen fetch sarmalayıcısı.
function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}), "X-Case-Id": CASE_ID };
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

// --- Tabs ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "tracking") {
      lastSeenNotificationCount = currentNotificationCount;
      updateFamilyBadge();
    }
  });
});

// --- Mikrofon: konuşmayı kaydedip yazıya çevirme (Speech-to-Text) ---
// Not: Tarayıcının/Electron'un yerleşik webkitSpeechRecognition'ı Google'ın
// kendi (lisanslı) API anahtarını gerektiriyor ve Electron'da bu anahtar
// bulunmadığı için hep "network" hatasıyla başarısız oluyordu. Bunun yerine
// mikrofonu kendimiz kaydedip (MediaRecorder) backend'deki YEREL Whisper
// modeline gönderiyoruz — API anahtarı/internet gerekmez, backend/speech.py'ye bakın.
function setupMicButton(micBtn, inputEl, statusEl) {
  if (!micBtn || !inputEl) return;

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
    micBtn.disabled = true;
    micBtn.title = "Bu cihazda sesli yazma desteklenmiyor";
    return;
  }

  const label = micBtn.querySelector(".mic-btn-label");
  let mediaRecorder = null;
  let mediaStream = null;
  let audioChunks = [];
  let state = "idle"; // idle | recording | processing

  function setStatus(text) {
    if (!statusEl) return;
    if (text) {
      statusEl.textContent = text;
      statusEl.hidden = false;
    } else {
      statusEl.hidden = true;
    }
  }

  function setState(next) {
    state = next;
    micBtn.classList.toggle("listening", next === "recording");
    micBtn.disabled = next === "processing";
    if (label) label.textContent = next === "recording" ? "Bitir" : next === "processing" ? "..." : "Konuş";
    if (next === "recording") setStatus("🎙️ Dinliyorum... bitirmek için tekrar basın");
    else if (next === "processing") setStatus("✍️ Yazıya çevriliyor...");
    else setStatus("");
  }

  async function startRecording() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.warn("Mikrofon izni alınamadı:", err);
      setStatus("Mikrofon izni verilmedi. Sistem ayarlarından bu uygulamaya mikrofon erişimi vermeniz gerekiyor.");
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined);
    audioChunks = [];
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start();
    setState("recording");
  }

  async function stopRecordingAndTranscribe() {
    setState("processing");

    await new Promise((resolve) => {
      mediaRecorder.onstop = resolve;
      mediaRecorder.stop();
    });
    mediaStream.getTracks().forEach((track) => track.stop());

    if (audioChunks.length === 0) {
      setStatus("Ses kaydedilemedi, tekrar deneyin.");
      setState("idle");
      return;
    }

    const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
    try {
      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");
      const res = await fetch(`${API_BASE}/speech-to-text`, { method: "POST", body: formData });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.text) {
        inputEl.value = data.text;
        setStatus("");
      } else {
        setStatus("Ses algılanamadı, tekrar deneyebilir ya da yazabilirsiniz.");
      }
    } catch (err) {
      console.warn("Sesli yazma başarısız:", err);
      setStatus("Sesli yazma şu an çalışmadı (backend'e ulaşılamadı). Lütfen yazarak deneyin.");
    } finally {
      setState("idle");
    }
  }

  micBtn.addEventListener("click", () => {
    if (state === "idle") startRecording();
    else if (state === "recording") stopRecordingAndTranscribe();
  });
}

// --- Yazı boyutu kontrolü ---
const FONT_MIN = 16;
const FONT_MAX = 30;
const FONT_STEP = 2;
let currentFontSize = 20;

function applyFontSize() {
  document.documentElement.style.setProperty("--base-font-size", `${currentFontSize}px`);
}

document.getElementById("font-increase-btn").addEventListener("click", () => {
  currentFontSize = Math.min(FONT_MAX, currentFontSize + FONT_STEP);
  applyFontSize();
});
document.getElementById("font-decrease-btn").addEventListener("click", () => {
  currentFontSize = Math.max(FONT_MIN, currentFontSize - FONT_STEP);
  applyFontSize();
});

// --- "Süreç Takibi & SMS" bildirim rozeti ---
let currentNotificationCount = 0;
let lastSeenNotificationCount = 0;
const familyBadge = document.getElementById("family-badge");

function updateFamilyBadge() {
  const unseen = currentNotificationCount - lastSeenNotificationCount;
  if (unseen > 0) {
    familyBadge.textContent = String(unseen);
    familyBadge.hidden = false;
  } else {
    familyBadge.hidden = true;
  }
}

// --- Markdown temizliği: LLM çıktısında kalabilecek ##, **, madde imi gibi ham
// sembolleri hem ekrandan hem sesli okumadan temizler (yaşlı kullanıcı için
// "##" gibi karakterlerin sesli/yazılı görünmesi kafa karıştırıcı olur).
function stripMarkdown(text) {
  return text
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/^[-*•🔹]\s+/gm, "")
    .replace(/[🔹🔸▪️]/g, "")
    .trim();
}

// --- TTS (sesli çıktı) ---
let voiceEnabled = true;
const voiceToggle = document.getElementById("voice-toggle");
const stopVoiceBtn = document.getElementById("stop-voice-btn");
const voiceSelect = document.getElementById("voice-select");
let lastSpokenText = "";
let selectedVoice = null;
let availableTurkishVoices = [];

voiceToggle.addEventListener("change", () => {
  voiceEnabled = voiceToggle.checked;
  if (!voiceEnabled) speechSynthesis.cancel();
});

// Varsayılan sistem sesi genelde robotik duruyor — mümkünse doğal, bilinen
// bir Türkçe kadın sesini (macOS'ta "Yelda" gibi) otomatik seçip kullanıcıya
// da elle değiştirme imkanı veriyoruz.
function pickBestTurkishVoice(voices) {
  if (voices.length === 0) return null;
  const knownNatural = voices.find((v) => /yelda|filiz/i.test(v.name));
  if (knownNatural) return knownNatural;
  const notCompact = voices.find((v) => !/compact/i.test(v.name));
  return notCompact || voices[0];
}

function populateVoiceOptions() {
  const allVoices = speechSynthesis.getVoices();
  availableTurkishVoices = allVoices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("tr"));

  voiceSelect.innerHTML = "";
  if (availableTurkishVoices.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "Sistem varsayılan sesi";
    voiceSelect.appendChild(opt);
    selectedVoice = null;
    return;
  }

  availableTurkishVoices.forEach((v, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = v.name;
    voiceSelect.appendChild(opt);
  });

  selectedVoice = pickBestTurkishVoice(availableTurkishVoices);
  const bestIndex = availableTurkishVoices.indexOf(selectedVoice);
  if (bestIndex >= 0) voiceSelect.value = String(bestIndex);
}

voiceSelect.addEventListener("change", () => {
  selectedVoice = availableTurkishVoices[Number(voiceSelect.value)] || null;
});

// Bazı tarayıcılarda ses listesi async hazırlanır (onvoiceschanged), bazılarında
// senkron da olabilir — ikisini de dene.
speechSynthesis.onvoiceschanged = populateVoiceOptions;
populateVoiceOptions();

// Emoji yerine SVG kullanıyoruz — bazı sistemlerde emoji fontu eksik/bozuk
// olabiliyor ve buton tamamen boş görünebiliyor (ikonun ne işe yaradığı
// anlaşılmaz hale geliyor). SVG her sistemde garanti aynı görünür.
const SPEAKER_ICON_SVG =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4h3.5l4.5 4V6l-4.5 4H4z"/><path d="M16.5 12a3.5 3.5 0 0 0-2-3.16v6.32A3.5 3.5 0 0 0 16.5 12z"/><path d="M14.5 4.35v2.07a6.5 6.5 0 0 1 0 11.16v2.07a8.5 8.5 0 0 0 0-15.3z"/></svg>';
const STOP_ICON_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';

// Sohbetteki tek genel "Sesi Durdur" butonuna ek olarak, her "sesli oku" butonu
// kendi başına da durdurma görevi görsün istiyoruz — kullanıcı hangi metni
// dinliyorsa, tam o butona tekrar basarak durdurabilsin (irite edici olmasın diye).
let activeReadAloudBtn = null;

function setReadAloudButtonState(btn, speaking) {
  if (!btn) return;
  btn.classList.toggle("speaking", speaking);
  btn.innerHTML = speaking ? STOP_ICON_SVG : SPEAKER_ICON_SVG;
  btn.title = speaking ? "Sesi durdur" : "Sesli oku";
}

function speak(text, triggerBtn) {
  if (!voiceEnabled) return;
  try {
    speechSynthesis.cancel(); // önceki ses hâlâ çalıyorsa üst üste binmesin
    if (activeReadAloudBtn) setReadAloudButtonState(activeReadAloudBtn, false);
    activeReadAloudBtn = triggerBtn || null;
    lastSpokenText = text;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "tr-TR";
    utter.rate = 0.92; // biraz daha yavaş, daha doğal ve anlaşılır
    utter.pitch = 1.0;
    if (selectedVoice) utter.voice = selectedVoice;

    if (triggerBtn) {
      setReadAloudButtonState(triggerBtn, true);
      utter.onend = () => setReadAloudButtonState(triggerBtn, false);
      utter.onerror = () => setReadAloudButtonState(triggerBtn, false);
    }

    speechSynthesis.speak(utter);
  } catch (e) {
    console.warn("TTS kullanılamıyor:", e);
  }
}

stopVoiceBtn.addEventListener("click", () => {
  speechSynthesis.cancel();
  if (activeReadAloudBtn) setReadAloudButtonState(activeReadAloudBtn, false);
  activeReadAloudBtn = null;
});

document.getElementById("replay-voice-btn").addEventListener("click", () => {
  if (lastSpokenText) speak(lastSpokenText);
});

// Haklarınız kartları, e-Devlet Kılavuzu bölümleri gibi okuma zor olabilecek
// herhangi bir metin bloğunun yanına, o metni sesli okuyan/durduran bir buton üretir.
function buildReadAloudButton(text) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "read-aloud-btn";
  btn.innerHTML = SPEAKER_ICON_SVG;
  btn.title = "Sesli oku";
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (btn.classList.contains("speaking")) {
      speechSynthesis.cancel();
      setReadAloudButtonState(btn, false);
      activeReadAloudBtn = null;
    } else {
      speak(text, btn);
    }
  });
  return btn;
}

// --- Chat ---
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = role === "assistant" ? stripMarkdown(text) : text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

// --- Aktif uzman göstergesi ---
const SUBAGENT_LABELS = {
  eligibility: "🔎 Uygunluk uzmanı bakıyor...",
  guide: "📋 Rehber uzmanı bakıyor...",
  tracking: "📌 Takip uzmanı bakıyor...",
  security: "🛡️ Güvenlik uzmanı bakıyor...",
};

const subagentIndicator = document.getElementById("active-subagent-indicator");

function renderActiveSubagent(activeSubagent) {
  const label = SUBAGENT_LABELS[activeSubagent];
  if (label) {
    subagentIndicator.textContent = label;
    subagentIndicator.hidden = false;
  } else {
    subagentIndicator.hidden = true;
  }
}

function showTypingIndicator() {
  const div = document.createElement("div");
  div.className = "msg assistant typing-indicator";
  div.id = "typing-indicator";
  div.textContent = "Düşünüyor...";
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function hideTypingIndicator() {
  document.getElementById("typing-indicator")?.remove();
}

async function sendChatMessage(message) {
  if (!message) return;
  appendMessage("user", message);
  // Uzman bir subagent'a danışması gerektiğinde cevap 20-60 saniye sürebilir
  // (bkz. backend/agents/orchestrator.py — artık arka plan görevinin
  // gerçekten bitmesini bekliyoruz, hızlı ama eksik veri döndürmüyoruz).
  // Kullanıcı bu süre boyunca hiçbir şey görmesin diye bir gösterge koyuyoruz.
  showTypingIndicator();

  try {
    const res = await apiFetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    hideTypingIndicator();
    if (!res.ok) {
      // Backend'den gelen gerçek hatayı göster (ör. eksik .env ayarı) — genel
      // "bağlantı sorunu" mesajı asıl sebebi gizleyip debug'ı zorlaştırıyordu.
      appendMessage("assistant", `Bir sorun oluştu: ${JSON.stringify(data.detail || data)}`);
      console.error("Backend hatası:", data);
      return;
    }
    appendMessage("assistant", data.reply);
    speak(stripMarkdown(data.reply));
    renderActiveSubagent(data.active_subagent);
    if (data.case) renderCase(data.case);
  } catch (err) {
    hideTypingIndicator();
    appendMessage("assistant", "Bağlantı sorunu oluştu. (backend çalışıyor mu?)");
    console.error(err);
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  chatInput.value = "";
  sendChatMessage(message);
});

// --- Hızlı başlangıç çipleri: yaşlı kullanıcı ne yazacağını düşünmek zorunda
// kalmasın diye, tek dokunuşla sohbeti başlatan hazır cümleler. ---
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => sendChatMessage(chip.dataset.message));
});

// --- Durum bildirimi (POST /case/status) ---
const statusForm = document.getElementById("status-form");
const statusInput = document.getElementById("status-input");

statusForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const update = statusInput.value.trim();
  if (!update) return;
  statusInput.value = "";

  try {
    const res = await apiFetch("/case/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ update }),
    });
    const data = await res.json();
    renderCase(data);
  } catch (err) {
    console.error("Durum bildirilemedi:", err);
  }
});

// --- "Haklarım" formu ---
const profileForm = document.getElementById("profile-form");
const profileResults = document.getElementById("profile-results");
const resultsPlaceholder = document.getElementById("results-placeholder");

profileForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const exactPercentValue = document.getElementById("profile-disability-percent").value;
  const severityEstimateValue = document.getElementById("profile-disability-severity").value;
  const householdIncomeValue = document.getElementById("profile-household-income").value;
  const householdSizeValue = document.getElementById("profile-household-size").value;

  // Tam yüzdeyi biliyorsa onu kullan; bilmiyorsa Hafif/Orta/Ağır seçiminden gelen
  // kaba tahmini kullan ve backend'e bunun bir tahmin olduğunu bildir.
  const disabilityPercent = exactPercentValue
    ? Number(exactPercentValue)
    : severityEstimateValue
      ? Number(severityEstimateValue)
      : null;
  const disabilityPercentIsEstimate = !exactPercentValue && !!severityEstimateValue;

  const profile = {
    age: Number(document.getElementById("profile-age").value),
    disability_status: document.getElementById("profile-disability").value,
    disability_percent: disabilityPercent,
    disability_percent_is_estimate: disabilityPercentIsEstimate,
    household_income_tl: householdIncomeValue ? Number(householdIncomeValue) : null,
    household_size: householdSizeValue ? Number(householdSizeValue) : null,
    income_band: document.getElementById("profile-income").value,
    city: document.getElementById("profile-city").value.trim(),
    living_situation: document.getElementById("profile-living").value,
    housing_status: document.getElementById("profile-housing").value,
    needs_daily_care: document.getElementById("profile-needs-care").checked,
    has_active_social_security: document.getElementById("profile-has-social-security").checked,
    notes: document.getElementById("profile-notes").value.trim(),
  };

  resultsPlaceholder.hidden = true;
  profileResults.innerHTML = "<p>Değerlendiriliyor...</p>";
  try {
    const res = await apiFetch("/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    const data = await res.json();
    renderCase(data);
  } catch (err) {
    profileResults.innerHTML = "<p>Bağlantı sorunu oluştu. Backend çalışıyor mu?</p>";
    console.error(err);
  }
});

// --- "Haklarınız" — hak sahibi / uygun görünmeyen olarak gruplu kart görünümü ---
function renderEligibility(eligibility) {
  profileResults.innerHTML = "";

  if (!eligibility || eligibility.length === 0) {
    resultsPlaceholder.hidden = false;
    return;
  }
  resultsPlaceholder.hidden = true;

  const eligibleEntries = eligibility.filter((e) => e.eligible);
  const notEligibleEntries = eligibility.filter((e) => !e.eligible);

  function buildCard(entry) {
    const card = document.createElement("div");
    card.className = `result-card ${entry.eligible ? "eligible" : "not-eligible"}`;

    const titleRow = document.createElement("div");
    titleRow.className = "result-title-row";
    const title = document.createElement("div");
    title.className = "result-title";
    title.textContent = `${entry.eligible ? "✅" : "❌"} ${entry.program}`;
    titleRow.appendChild(title);

    const fullText = [entry.program, entry.reason, entry.notes].filter(Boolean).join(". ");
    titleRow.appendChild(buildReadAloudButton(fullText));
    card.appendChild(titleRow);

    const reason = document.createElement("div");
    reason.className = "result-reason";
    reason.textContent = entry.reason;
    card.appendChild(reason);
    if (entry.eligible && entry.notes) {
      const notes = document.createElement("div");
      notes.className = "result-notes";
      notes.textContent = entry.notes;
      card.appendChild(notes);
    }
    return card;
  }

  if (eligibleEntries.length > 0) {
    const heading = document.createElement("div");
    heading.className = "results-group-title eligible";
    heading.textContent = "✅ Hak Sahibi Olabilecekleriniz";
    profileResults.appendChild(heading);
    eligibleEntries.forEach((entry) => profileResults.appendChild(buildCard(entry)));
  }

  if (notEligibleEntries.length > 0) {
    const heading = document.createElement("div");
    heading.className = "results-group-title not-eligible";
    heading.textContent = "Şu An İçin Uygun Görünmeyenler";
    profileResults.appendChild(heading);
    notEligibleEntries.forEach((entry) => profileResults.appendChild(buildCard(entry)));
  }
}

// --- Sıradaki Adımınız banner ---
const nextStepBanner = document.getElementById("next-step-banner");
const nextStepText = document.getElementById("next-step-text");

function renderNextStep(step) {
  if (!step) {
    nextStepBanner.hidden = true;
    return;
  }
  nextStepText.textContent = step;
  nextStepBanner.hidden = false;
}

// --- Üst istatistik kutuları ---
const statMatchedRights = document.getElementById("stat-matched-rights");
const statActiveTracking = document.getElementById("stat-active-tracking");

function renderHeaderStats(caseData) {
  const matched = (caseData.eligibility || []).filter((e) => e.eligible).length;
  statMatchedRights.textContent = String(matched);
  statActiveTracking.textContent = String((caseData.appointments || []).length);
}

// --- Yol Haritası kartları ---
function renderRoadmap(roadmap) {
  const section = document.getElementById("roadmap-section");
  const list = document.getElementById("roadmap-list");
  list.innerHTML = "";

  if (!roadmap || roadmap.length === 0) {
    section.hidden = true;
    return;
  }
  section.hidden = false;

  roadmap.forEach((entry) => {
    const card = document.createElement("div");
    card.className = "roadmap-card";

    const titleRow = document.createElement("div");
    titleRow.className = "result-title-row";
    const title = document.createElement("h4");
    title.textContent = entry.program;
    titleRow.appendChild(title);
    const fullText = [entry.program, ...(entry.steps || [])].join(". ");
    titleRow.appendChild(buildReadAloudButton(fullText));
    card.appendChild(titleRow);

    const stepsList = document.createElement("ol");
    stepsList.className = "roadmap-steps";
    (entry.steps || []).forEach((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      stepsList.appendChild(li);
    });
    card.appendChild(stepsList);

    if (entry.administered_by) {
      const admin = document.createElement("div");
      admin.className = "checklist-item-tip";
      admin.textContent = `Kurum: ${entry.administered_by}`;
      card.appendChild(admin);
    }

    list.appendChild(card);
  });
}

// --- Rehber & Aile Görünümü paneli ---
function renderCase(caseData) {
  renderEligibility(caseData.eligibility || []);
  renderNextStep(caseData.next_step);
  renderHeaderStats(caseData);
  renderRoadmap(caseData.roadmap);

  const checklist = document.getElementById("checklist-list");
  checklist.innerHTML = "";
  (caseData.checklist || []).forEach((c) => {
    const li = document.createElement("li");
    if (c.done) li.classList.add("done");

    const row = document.createElement("div");
    row.className = "checklist-item-row";
    const text = document.createElement("span");
    text.className = "checklist-item-text";
    text.textContent = c.item;
    row.appendChild(text);

    if (!c.done) {
      const markReadyBtn = document.createElement("button");
      markReadyBtn.type = "button";
      markReadyBtn.className = "mark-ready-btn";
      markReadyBtn.textContent = "✅ Hazır";
      markReadyBtn.title = "Bu belgeyi hazırladığınızı bildirin";
      markReadyBtn.addEventListener("click", () => markChecklistItemReady(c.item));
      row.appendChild(markReadyBtn);
    }
    li.appendChild(row);

    const tip = findDocumentTip(c.item);
    if (tip) {
      const tipEl = document.createElement("div");
      tipEl.className = "checklist-item-tip";
      tipEl.textContent = tip;
      li.appendChild(tipEl);
    }

    checklist.appendChild(li);
  });

  const appointments = document.getElementById("appointments-list");
  appointments.innerHTML = "";
  (caseData.appointments || []).forEach((a) => {
    const li = document.createElement("li");
    li.textContent = a.due_date ? `${a.description} — ${a.due_date}` : a.description;
    appointments.appendChild(li);
  });
  if (appointments.children.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Henüz kayıtlı randevu/son tarih yok.";
    appointments.appendChild(li);
  }

  const notifications = document.getElementById("notifications-list");
  notifications.innerHTML = "";
  (caseData.notifications || []).slice().reverse().forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n.message;
    li.classList.add(n.type);
    notifications.appendChild(li);
  });

  currentNotificationCount = (caseData.notifications || []).length;
  updateFamilyBadge();
}

async function loadCase() {
  try {
    const res = await apiFetch("/case");
    renderCase(await res.json());
  } catch (err) {
    console.warn("Case yüklenemedi:", err);
  }
}

// --- Belge hazırlama ipuçları + tek tıkla "hazır" işaretleme ---
let documentTips = [];
let documentTipsDefault = "";

async function loadDocumentTips() {
  try {
    const res = await fetch(`${API_BASE}/document-tips`);
    const data = await res.json();
    documentTips = data.tips || [];
    documentTipsDefault = data.default_tip || "";
  } catch (err) {
    console.warn("Belge ipuçları yüklenemedi:", err);
  }
}

function findDocumentTip(itemText) {
  const lowered = itemText.toLowerCase();
  const match = documentTips.find((t) => lowered.includes(t.match));
  return (match ? match.tip : documentTipsDefault) || "";
}

async function markChecklistItemReady(itemText) {
  try {
    const res = await apiFetch("/case/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ update: `${itemText} belgesini hazırladım` }),
    });
    const data = await res.json();
    renderCase(data);
  } catch (err) {
    console.error("Belge hazır olarak işaretlenemedi:", err);
  }
}

// --- Belge Yükle (yerel/cihazda saklanır — belge içeriği hiçbir yere
// gönderilmez, sadece dosya adı ve tarih Yapılacaklar sekmesinde listelenir) ---
const UPLOADED_DOCS_KEY = `bakim_rehber_uploaded_docs_${CASE_ID}`;
const uploadDocBtn = document.getElementById("upload-doc-btn");
const uploadDocInput = document.getElementById("upload-doc-input");
const uploadedDocsList = document.getElementById("uploaded-docs-list");

function loadUploadedDocs() {
  try {
    return JSON.parse(localStorage.getItem(UPLOADED_DOCS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveUploadedDocs(docs) {
  localStorage.setItem(UPLOADED_DOCS_KEY, JSON.stringify(docs));
}

function renderUploadedDocs() {
  const docs = loadUploadedDocs();
  uploadedDocsList.innerHTML = "";
  docs.forEach((doc, index) => {
    const li = document.createElement("li");
    const text = document.createElement("span");
    text.textContent = `${doc.name} — ${doc.date}`;
    li.appendChild(text);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "doc-remove-btn";
    removeBtn.textContent = "Sil";
    removeBtn.title = "Bu belgeyi listeden kaldır";
    removeBtn.addEventListener("click", () => {
      const current = loadUploadedDocs();
      current.splice(index, 1);
      saveUploadedDocs(current);
      renderUploadedDocs();
    });
    li.appendChild(removeBtn);

    uploadedDocsList.appendChild(li);
  });
}

if (uploadDocBtn && uploadDocInput) {
  uploadDocBtn.addEventListener("click", () => uploadDocInput.click());
  uploadDocInput.addEventListener("change", () => {
    const file = uploadDocInput.files[0];
    if (!file) return;
    const docs = loadUploadedDocs();
    docs.push({
      name: file.name,
      date: new Date().toLocaleDateString("tr-TR"),
    });
    saveUploadedDocs(docs);
    renderUploadedDocs();
    uploadDocInput.value = "";
  });
}

// --- e-Devlet Kılavuzu (akordiyon) ---
async function loadEdevletGuide() {
  const container = document.getElementById("edevlet-guide-list");
  try {
    const res = await fetch(`${API_BASE}/edevlet-guide`);
    const data = await res.json();
    container.innerHTML = "";
    (data.sections || []).forEach((section, index) => {
      const item = document.createElement("div");
      item.className = "accordion-item";
      if (index === 0) item.classList.add("open");

      const header = document.createElement("button");
      header.type = "button";
      header.className = "accordion-header";
      const titleSpan = document.createElement("span");
      titleSpan.className = "accordion-header-title";
      titleSpan.textContent = section.title;
      const arrowSpan = document.createElement("span");
      arrowSpan.textContent = index === 0 ? "▲" : "▼";
      header.appendChild(titleSpan);
      header.appendChild(arrowSpan);
      header.addEventListener("click", () => {
        const willOpen = !item.classList.contains("open");
        item.classList.toggle("open", willOpen);
        arrowSpan.textContent = willOpen ? "▲" : "▼";
      });

      const body = document.createElement("div");
      body.className = "accordion-body";
      const bodyText = document.createElement("div");
      bodyText.textContent = section.body;
      body.appendChild(bodyText);

      const actions = document.createElement("div");
      actions.className = "accordion-body-actions";
      actions.appendChild(buildReadAloudButton(`${section.title}. ${section.body}`));
      body.appendChild(actions);

      item.appendChild(header);
      item.appendChild(body);
      container.appendChild(item);
    });
  } catch (err) {
    container.innerHTML = "<p>e-Devlet Kılavuzu yüklenemedi. Backend çalışıyor mu?</p>";
    console.warn("edevlet-guide yüklenemedi:", err);
  }
}

// --- Scripted demo senaryoları ---
document.getElementById("btn-missing-doc").addEventListener("click", async () => {
  const res = await apiFetch("/scenario/missing-document", { method: "POST" });
  const data = await res.json();
  renderCase(data);
  const last = data.notifications[data.notifications.length - 1];
  if (last) speak(last.message);
});

document.getElementById("btn-suspicious-sms").addEventListener("click", async () => {
  const res = await apiFetch("/scenario/suspicious-sms", { method: "POST" });
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
        // Karşılama mesajı artık .hero-welcome'da sabit olarak duruyor —
        // sohbet günlüğü boş başlar, kullanıcı ilk mesajını yazınca dolar.
        await loadDocumentTips();
        loadCase();
        loadEdevletGuide();
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
renderUploadedDocs(); // yerelde saklandığı için backend'i beklemeye gerek yok

setupMicButton(document.getElementById("mic-btn"), chatInput, document.getElementById("mic-status"));
setupMicButton(document.getElementById("status-mic-btn"), statusInput, null);
