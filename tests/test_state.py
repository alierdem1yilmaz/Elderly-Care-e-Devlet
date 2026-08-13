# Sahiplik: Kişi 2 (Backend İçerik & Takip)

from datetime import date, timedelta

import pytest

from backend import state


def test_load_benefits_returns_validated_programs():
    benefits = state.load_benefits()
    assert len(benefits) == 3
    for program in benefits:
        assert program["name"]
        assert program["required_documents"]
        assert program["steps"]
        assert program["source"]["url"].startswith("http")


def test_mark_checklist_item_matches_substring_and_toggles_done():
    state.set_checklist([{"item": "Nüfus cüzdanı fotokopisi", "done": False}])

    matched = state.mark_checklist_item("nüfus cüzdanı", done=True)

    assert matched["done"] is True
    assert state.get_case()["checklist"][0]["done"] is True


def test_mark_checklist_item_no_match_returns_none():
    state.set_checklist([{"item": "Nüfus cüzdanı fotokopisi", "done": False}])

    assert state.mark_checklist_item("alakasız belge", done=True) is None


def test_next_pending_checklist_item_returns_first_undone():
    state.set_checklist([
        {"item": "A belgesi", "done": True},
        {"item": "B belgesi", "done": False},
        {"item": "C belgesi", "done": False},
    ])

    pending = state.next_pending_checklist_item()

    assert pending["item"] == "B belgesi"


def test_next_pending_checklist_item_none_when_all_done():
    state.set_checklist([{"item": "A belgesi", "done": True}])

    assert state.next_pending_checklist_item() is None


def test_add_appointment_rejects_non_iso_date():
    with pytest.raises(ValueError):
        state.add_appointment("Randevu", "20.08.2026")


def test_get_case_generates_reminder_for_near_appointment():
    soon = (date.today() + timedelta(days=1)).isoformat()
    state.add_appointment("Heyet raporu randevusu", soon)

    case = state.get_case()

    reminder_messages = [n["message"] for n in case["notifications"] if n["type"] == "reminder"]
    assert any("Heyet raporu randevusu" in m for m in reminder_messages)


def test_get_case_no_reminder_for_far_appointment():
    far = (date.today() + timedelta(days=30)).isoformat()
    state.add_appointment("Uzak randevu", far)

    case = state.get_case()

    assert case["notifications"] == []


def test_get_case_does_not_repeat_reminder_on_second_call():
    soon = (date.today() + timedelta(days=1)).isoformat()
    state.add_appointment("Heyet raporu randevusu", soon)

    state.get_case()
    case = state.get_case()

    reminder_count = sum(1 for n in case["notifications"] if n["type"] == "reminder")
    assert reminder_count == 1
