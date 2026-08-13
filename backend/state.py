# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# Vaka dosyası (case file) — tek oturumluk in-memory state. Demo için kalıcı DB gerekmiyor.

import json
from datetime import datetime
from pathlib import Path

_case = {
    "eligibility": [],
    "checklist": [],
    "notifications": [],
}

_BENEFITS_PATH = Path(__file__).parent / "data" / "benefits.json"
_benefits_cache: list[dict] | None = None


def load_benefits() -> list[dict]:
    """backend/data/benefits.json içindeki program listesini döner (cache'lenir)."""
    global _benefits_cache
    if _benefits_cache is None:
        with open(_BENEFITS_PATH, encoding="utf-8") as f:
            _benefits_cache = json.load(f)["programs"]
    return _benefits_cache


def get_case() -> dict:
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


def reset_case() -> None:
    _case["eligibility"] = []
    _case["checklist"] = []
    _case["notifications"] = []
