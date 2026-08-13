# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# Vaka dosyası (case file) — tek oturumluk in-memory state. Demo için kalıcı DB gerekmiyor.

from datetime import datetime

_case = {
    "eligibility": [],
    "checklist": [],
    "notifications": [],
}


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


def reset_case() -> None:
    _case["eligibility"] = []
    _case["checklist"] = []
    _case["notifications"] = []
