# Sahiplik: Kişi 1 (ali-erdem)
#
# Çalıştırma: uvicorn backend.main:app --reload --port 8000
# (proje kök dizininden çalıştırın ki `backend.` importları çalışsın)
# Not: claude-agent-sdk, sistemde giriş yapılmış bir `claude` CLI'ı kullanır —
# her takım üyesinin kendi makinesinde `claude` ile giriş yapmış olması gerekir.
# Ayrıca proje kökünde .env.example'daki alanları doldurulmuş bir .env gerekir
# (Supabase + Twilio bağlantı bilgileri).

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import auth, family_routes, speech, state, twilio_voice
from backend.agents import orchestrator, tracking_agent, security_agent, eligibility_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Artık başlangıçta tek bir global orchestrator client'ı bağlamıyoruz —
    # her case_id kendi client'ını ilk mesajında lazy olarak kuruyor (bkz.
    # orchestrator.py::_get_or_create_client). Whisper modelini ise şimdiden
    # yüklüyoruz (ilk indirmesi dahil) — demo sırasında ilk mikrofon
    # denemesinde sürpriz bir bekleme/indirme olmasın.
    await asyncio.to_thread(speech.warm_up)
    try:
        yield
    finally:
        await orchestrator.disconnect_all()


app = FastAPI(title="Yaşlı Bakım Rehberlik Asistanı", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(family_routes.router)
app.include_router(twilio_voice.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Varsayılan davranışta beklenmeyen hatalar düz metin "Internal Server
    # Error" döner — frontend bunu JSON olarak ayrıştırmaya çalışınca patlar
    # ve asıl sebep (ör. eksik .env değişkeni) gizlenir. Burada her zaman JSON
    # döndürüp gerçek hata mesajını response'a koyuyoruz ki hem frontend'de
    # anlamlı gösterilsin hem de terminal loguna zaten düşüyor.
    return JSONResponse(status_code=500, content={"detail": str(exc)})


async def get_case_id(x_case_id: str = Header(...)) -> str:
    """Electron (eşleştirme sonrası yerelde sakladığı elderly_profile_id'yi
    gönderir) ve gelecekteki mobil app için ortak case kimliği. Telefon
    kanalında (Twilio) buna gerek yok — orada case_id, arayan numaradan
    bulunuyor (bkz. backend/twilio_voice.py)."""
    return x_case_id


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


class PairRequest(BaseModel):
    code: str


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/pair")
def pair(req: PairRequest):
    """Electron'un ilk açılışta (ya da 'Bağlantıyı sıfırla' ile tekrar)
    çağırdığı, kimlik doğrulaması GEREKTİRMEYEN tek endpoint — yaşlı kullanıcı
    hiçbir zaman gerçek bir giriş ekranı görmediği için, bunun yerine aile
    üyesinin ürettiği kısa kodu bir kere girer (bkz. backend/auth.py)."""
    case_id = auth.redeem_pairing_code(req.code)
    return {"case_id": case_id}


@app.post("/chat")
async def chat(req: ChatRequest, case_id: str = Depends(get_case_id)):
    return await orchestrator.handle_message(case_id, req.message)


@app.get("/case")
def get_case(case_id: str = Depends(get_case_id)):
    return state.get_case(case_id)


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
def case_status(req: StatusUpdateRequest, case_id: str = Depends(get_case_id)):
    # tracking_agent.handle_status_update zaten uygun bildirimi (reminder/status_update)
    # case'e yazıyor — burada ayrıca genel bir "status_ack" eklemek çift bildirime yol açıyordu.
    tracking_agent.handle_status_update(case_id, req.update)
    return state.get_case(case_id)


@app.post("/profile")
async def submit_profile(req: ProfileRequest, case_id: str = Depends(get_case_id)):
    profile = req.model_dump()
    state.set_profile(case_id, profile)

    # Deterministik, LLM'siz değerlendirme — form gönderir göndermez anında ve
    # tutarlı bir sonuç garanti eder (bkz. backend/agents/eligibility_agent.py).
    benefits = state.load_benefits()
    results = eligibility_agent.assess_profile(profile, benefits)
    state.set_eligibility(case_id, results)

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
    asyncio.create_task(orchestrator.handle_message(case_id, summary))

    return state.get_case(case_id)


@app.post("/scenario/missing-document")
def scenario_missing_document(case_id: str = Depends(get_case_id)):
    state.add_notification(case_id, "reminder", tracking_agent.MISSING_DOCUMENT_MESSAGE)
    return state.get_case(case_id)


@app.post("/scenario/suspicious-sms")
def scenario_suspicious_sms(case_id: str = Depends(get_case_id)):
    state.add_notification(case_id, "security_alert", security_agent.suspicious_sms_alert())
    return state.get_case(case_id)


# Electron aynı arayüzü dosya sisteminden (file://) açıyor; web/Railway
# dağıtımında ise aynı frontend/renderer klasörünü bu backend'in kendisi
# statik olarak sunuyor — jüri için tek bir HTTPS linki yeterli olsun, ikinci
# bir hosting hesabı ya da CORS derdi olmasın diye. Yukarıdaki tüm route'lardan
# SONRA tanımlanmalı; aksi halde bu genel "/" mount'u onları gölgelerdi.
_RENDERER_DIR = Path(__file__).resolve().parent.parent / "frontend" / "renderer"
app.mount("/", StaticFiles(directory=_RENDERER_DIR, html=True), name="static")
