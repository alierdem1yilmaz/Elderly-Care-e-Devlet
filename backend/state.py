# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# Vaka dosyası (case file) — tek oturumluk in-memory state. Demo için kalıcı DB gerekmiyor.

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.data.schema import BenefitsFile

_case = {
    "eligibility": [],
    "checklist": [],
    "notifications": [],
    "appointments": [],
}

_BENEFITS_PATH = Path(__file__).parent / "data" / "benefits.json"
_benefits_cache: list[dict] | None = None

_DEADLINE_WARNING_DAYS = 3  # son tarihe bu kadar gün veya daha az kaldıysa hatırlat


def load_benefits() -> list[dict]:
    """backend/data/benefits.json içindeki program listesini döner (cache'lenir).
    Şema backend/data/schema.py ile doğrulanır — bozuk veri burada net bir
    hata olarak patlar, tüketen kod (guide_agent, eligibility_agent) içinde
    sessiz KeyError'a dönüşmez."""
    global _benefits_cache
    if _benefits_cache is None:
        with open(_BENEFITS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        validated = BenefitsFile.model_validate(raw)
        _benefits_cache = [p.model_dump() for p in validated.programs]
    return _benefits_cache


def get_case() -> dict:
    _check_due_appointments()
    return _case


def set_eligibility(results: list[dict]) -> None:
    _case["eligibility"] = results


def set_checklist(items: list[dict]) -> None:
    _case["checklist"] = items


def add_notification(type_: str, message: str) -> None:
    _case["notifications"].append(
        {"type": type_, "message": message, "timestamp": datetime.now().isoformat()}
    )


def mark_checklist_item(item_substring: str, done: bool) -> dict | None:
    """checklist'te adı item_substring'i içeren ilk kalemi işaretler. Eşleşen kalemi
    (veya bulunamazsa None) döner — tracking_agent buna göre yanıt üretir."""
    needle = item_substring.casefold()
    for entry in _case["checklist"]:
        if needle in entry["item"].casefold():
            entry["done"] = done
            return entry
    return None


def next_pending_checklist_item() -> dict | None:
    """checklist'te henüz 'done' olmayan ilk kalemi döner — proaktif hatırlatma için."""
    return next((entry for entry in _case["checklist"] if not entry["done"]), None)


def add_appointment(description: str, due_date: str) -> dict:
    """Kullanıcının bildirdiği bir randevu/son tarihi ("MHRS randevusu 20.08.2026")
    case'e ekler. due_date ISO formatında ("YYYY-MM-DD") olmalı."""
    date.fromisoformat(due_date)  # erken ve net hata versin, sessizce bozuk veri saklamasın
    appointment = {"description": description, "due_date": due_date, "reminded": False}
    _case["appointments"].append(appointment)
    return appointment


def _check_due_appointments() -> None:
    """Süresi yaklaşan/geçen randevular için, kişi başına yalnızca bir kez
    proaktif hatırlatma bildirimi üretir (reminded bayrağıyla tekrar önlenir)."""
    today = date.today()
    for appt in _case["appointments"]:
        if appt["reminded"]:
            continue
        due = date.fromisoformat(appt["due_date"])
        if due - today > timedelta(days=_DEADLINE_WARNING_DAYS):
            continue
        if due < today:
            message = f"Hatırlatma: \"{appt['description']}\" için son tarih geçmiş görünüyor ({due.strftime('%d.%m.%Y')}). Lütfen en kısa sürede ilgilenin."
        else:
            message = f"Hatırlatma: \"{appt['description']}\" için son tarih yaklaşıyor ({due.strftime('%d.%m.%Y')})."
        add_notification("reminder", message)
        appt["reminded"] = True


def reset_case() -> None:
    _case["eligibility"] = []
    _case["checklist"] = []
    _case["notifications"] = []
    _case["appointments"] = []
