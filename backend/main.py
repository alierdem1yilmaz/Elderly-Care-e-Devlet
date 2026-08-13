# Sahiplik: Kişi 1 (ali-erdem)
#
# Çalıştırma: uvicorn backend.main:app --reload --port 8000
# (proje kök dizininden çalıştırın ki `backend.` importları çalışsın)
# Not: claude-agent-sdk, sistemde giriş yapılmış bir `claude` CLI'ı kullanır —
# her takım üyesinin kendi makinesinde `claude` ile giriş yapmış olması gerekir.

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import state
from backend.agents import orchestrator, tracking_agent, security_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await orchestrator.connect()
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


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    return await orchestrator.handle_message(req.message)


@app.get("/case")
def get_case():
    return state.get_case()


@app.post("/case/status")
def case_status(req: StatusUpdateRequest):
    # tracking_agent.handle_status_update zaten uygun bildirimi (reminder/status_update)
    # case'e yazıyor — burada ayrıca genel bir "status_ack" eklemek çift bildirime yol açıyordu.
    tracking_agent.handle_status_update(req.update)
    return state.get_case()


@app.post("/scenario/missing-document")
def scenario_missing_document():
    state.add_notification("reminder", tracking_agent.MISSING_DOCUMENT_MESSAGE)
    return state.get_case()


@app.post("/scenario/suspicious-sms")
def scenario_suspicious_sms():
    state.add_notification("security_alert", security_agent.suspicious_sms_alert())
    return state.get_case()
