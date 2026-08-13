# Sahiplik: Kişi 1 (ali-erdem)
#
# Çalıştırma: uvicorn backend.main:app --reload --port 8000
# (proje kök dizininden çalıştırın ki `backend.` importları çalışsın)
# Not: claude-agent-sdk, sistemde giriş yapılmış bir `claude` CLI'ı kullanır —
# her takım üyesinin kendi makinesinde `claude` ile giriş yapmış olması gerekir.

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import speech, state
from backend.agents import orchestrator, tracking_agent, security_agent, eligibility_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await orchestrator.connect()
    # Whisper modelini şimdiden yükle (ilk indirmesi dahil) — demo sırasında
    # ilk mikrofon denemesinde sürpriz bir bekleme/indirme olmasın.
    await asyncio.to_thread(speech.warm_up)
    try:
        yield
    finally:
        await orchestrator.disconnect()


app = FastAPI(title="Yaşlı Bakım Rehberlik Asistanı", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class StatusUpdateRequest(BaseModel):
    update: str


class ProfileRequest(BaseModel):
    age: int
    disability_status: str  # "none" | "unreported" | "reported"
    disability_percent: int | None = None
    disability_percent_is_estimate: bool = False  # "Hafif/Orta/Ağır" seçiminden gelen kaba tahmin mi
    income_band: str  # "none" | "below_minimum" | "around_minimum" | "above_minimum" — TL alanları boşsa yedek tahmin
    household_income_tl: float | None = None  # doluysa öncelikli, kesin hesap için kullanılır
    household_size: int | None = None
    city: str = ""
    living_situation: str = ""
    housing_status: str = ""  # "own" | "rent" | "family_home" | "other" | ""
    needs_daily_care: bool = False
    has_active_social_security: bool = False
    notes: str = ""


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    return await orchestrator.handle_message(req.message)


@app.get("/case")
def get_case():
    return state.get_case()


@app.get("/edevlet-guide")
def get_edevlet_guide():
    return {"sections": state.load_edevlet_guide()}


@app.get("/document-tips")
def get_document_tips():
    return state.load_document_tips()


@app.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    text = await asyncio.to_thread(speech.transcribe_audio, audio_bytes, audio.filename or "recording.webm")
    return {"text": text}


@app.post("/case/status")
def case_status(req: StatusUpdateRequest):
    # tracking_agent.handle_status_update zaten uygun bildirimi (reminder/status_update)
    # case'e yazıyor — burada ayrıca genel bir "status_ack" eklemek çift bildirime yol açıyordu.
    tracking_agent.handle_status_update(req.update)
    return state.get_case()


@app.post("/profile")
async def submit_profile(req: ProfileRequest):
    profile = req.model_dump()
    state.set_profile(profile)

    # Deterministik, LLM'siz değerlendirme — form gönderir göndermez anında ve
    # tutarlı bir sonuç garanti eder (bkz. backend/agents/eligibility_agent.py).
    benefits = state.load_benefits()
    results = eligibility_agent.assess_profile(profile, benefits)
    state.set_eligibility(results)

    # Orchestrator'ın sohbet geçmişine bu bilgiyi arka planda, kullanıcıyı
    # bekletmeden ekliyoruz — amaç sadece kullanıcı sonra sohbete geçerse aynı
    # soruları tekrar sormaması; yanıtı response'a dahil etmiyoruz.
    summary = (
        f"(Sistem notu: kullanıcı Profilim formunu doldurdu — yaş={profile['age']}, "
        f"engellilik_durumu={profile['disability_status']}"
        + (f" (%{profile['disability_percent']})" if profile.get("disability_percent") else "")
        + f", gelir_bandı={profile['income_band']}, il={profile.get('city') or 'belirtilmedi'}, "
        f"yaşam_durumu={profile.get('living_situation') or 'belirtilmedi'}, "
        f"barınma_durumu={profile.get('housing_status') or 'belirtilmedi'}, "
        f"günlük_bakım_ihtiyacı={'var' if profile.get('needs_daily_care') else 'yok/belirtilmedi'}, "
        f"aktif_sosyal_güvence={'var' if profile.get('has_active_social_security') else 'yok/belirtilmedi'}"
        + (f", ek_not=\"{profile['notes']}\"" if profile.get("notes") else "")
        + ". Uygunluk değerlendirmesi zaten deterministik olarak yapıldı ve kaydedildi — tekrar "
        "record_eligibility çağırma, bu bilgileri sadece hatırla ve kullanıcı sohbete geçerse tekrar sorma.)"
    )
    asyncio.create_task(orchestrator.handle_message(summary))

    return state.get_case()


@app.post("/scenario/missing-document")
def scenario_missing_document():
    state.add_notification("reminder", tracking_agent.MISSING_DOCUMENT_MESSAGE)
    return state.get_case()


@app.post("/scenario/suspicious-sms")
def scenario_suspicious_sms():
    state.add_notification("security_alert", security_agent.suspicious_sms_alert())
    return state.get_case()
