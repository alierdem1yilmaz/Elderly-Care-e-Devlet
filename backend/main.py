# Sahiplik: Kişi 1 (Backend Omurga) — endpoint iskeleti, şemayı değiştirmeden
# içini gerçek orchestrator/subagent çağrılarıyla doldurun (bkz. TODO'lar).
#
# Çalıştırma: uvicorn backend.main:app --reload --port 8000
# (proje kök dizininden çalıştırın ki `backend.` importları çalışsın)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import state
from backend.agents import orchestrator, tracking_agent, security_agent

app = FastAPI(title="Yaşlı Bakım Rehberlik Asistanı")

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
def chat(req: ChatRequest):
    return orchestrator.handle_message(req.message)


@app.get("/case")
def get_case():
    return state.get_case()


@app.post("/case/status")
def case_status(req: StatusUpdateRequest):
    tracking_agent.handle_status_update(req.update)
    state.add_notification("status_ack", f"Bildirdiğiniz durum kaydedildi: {req.update}")
    return state.get_case()


@app.post("/scenario/missing-document")
def scenario_missing_document():
    state.add_notification("reminder", tracking_agent.MISSING_DOCUMENT_MESSAGE)
    return state.get_case()


@app.post("/scenario/suspicious-sms")
def scenario_suspicious_sms():
    state.add_notification("security_alert", security_agent.suspicious_sms_alert())
    return state.get_case()
