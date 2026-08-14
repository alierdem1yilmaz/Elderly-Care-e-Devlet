# Sahiplik: Kişi 1 (ali-erdem)
#
# Twilio webhook — gelen telefon çağrısını doğrudan mevcut orchestrator'a
# bağlar (aynı orchestrator.handle_message, Electron'un kullandığıyla birebir
# aynı). "Guide-only" ilkesi telefon kanalında da geçerli: sistem hiçbir işlemi
# arayan adına yapmaz, sadece konuşarak bilgilendirir/yönlendirir.
#
# Konuşma toplama için Twilio'nun kendi <Gather input="speech"> özelliği
# kullanılıyor — telefon hattı zaten internete bağlı bir sunucu gerektirdiği
# için masaüstündeki "yerel Whisper" kısıtı burada geçerli değil; Twilio'nun
# STT'si en düşük gecikmeli, en basit yol.
#
# NOT (production'a geçmeden önce yapılacak): Twilio istek imzası
# (X-Twilio-Signature) doğrulanmıyor — şu an herhangi biri bu endpoint'e POST
# atıp sahte bir çağrı simüle edebilir. Demo/prototip kapsamında kabul edildi.

from fastapi import APIRouter, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import Gather, VoiceResponse

from backend.agents import orchestrator
from backend.db import get_client

router = APIRouter(prefix="/twilio", tags=["twilio"])

_GREETING = "Merhaba, size sosyal yardımlar konusunda nasıl yardımcı olabilirim?"
_UNKNOWN_CALLER_MESSAGE = (
    "Merhaba. Bu numara ailenizde kayıtlı görünmüyor. Lütfen aile üyenizden "
    "sizi uygulamaya eklemesini isteyin."
)


def _find_case_id_by_phone(phone_number: str) -> str | None:
    result = get_client().table("elderly_profiles").select("id").eq("phone_number", phone_number).execute()
    if result.data:
        return result.data[0]["id"]
    return None


@router.post("/voice")
async def twilio_voice(From: str = Form(...), SpeechResult: str | None = Form(default=None)):
    response = VoiceResponse()
    case_id = _find_case_id_by_phone(From)

    if case_id is None:
        response.say(_UNKNOWN_CALLER_MESSAGE, language="tr-TR")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    if SpeechResult:
        result = await orchestrator.handle_message(case_id, SpeechResult)
        reply_text = result["reply"]
    else:
        reply_text = _GREETING

    gather = Gather(input="speech", language="tr-TR", speech_timeout="auto", action="/twilio/voice", method="POST")
    gather.say(reply_text, language="tr-TR")
    response.append(gather)
    # Kullanıcı bir şey söylemeden bu noktaya gelinirse (sessizlik/timeout),
    # aramayı kapatmadan aynı akışı tekrar başlatır.
    response.redirect("/twilio/voice")

    return Response(content=str(response), media_type="application/xml")
