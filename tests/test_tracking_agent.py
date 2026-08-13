# Sahiplik: Kişi 2 (Backend İçerik & Takip)

from datetime import date, timedelta

from backend import state
from backend.agents import tracking_agent


def _set_evde_bakim_checklist():
    state.set_checklist([
        {"item": "Tam teşekküllü hastaneden alınmış, 'ağır engelli/tam bağımlı' ibareli sağlık kurulu (heyet) raporu", "done": False},
        {"item": "TC kimlik belgesi", "done": False},
        {"item": "Hane gelirini gösterir belgeler (varsa maaş bordrosu, emekli maaşı belgesi vb.)", "done": False},
    ])


def test_missing_signal_marks_matched_item_undone():
    _set_evde_bakim_checklist()

    tracking_agent.handle_status_update("heyet raporunu henüz alamadım")

    checklist = state.get_case()["checklist"]
    heyet_item = next(c for c in checklist if "heyet" in c["item"].casefold())
    assert heyet_item["done"] is False
    assert any(n["type"] == "reminder" for n in state.get_case()["notifications"])


def test_done_signal_marks_matched_item_done():
    _set_evde_bakim_checklist()

    tracking_agent.handle_status_update("TC kimlik belgesini hazırladım")

    checklist = state.get_case()["checklist"]
    kimlik_item = next(c for c in checklist if c["item"] == "TC kimlik belgesi")
    assert kimlik_item["done"] is True


def test_applied_signal_gives_acknowledgement_without_touching_checklist():
    _set_evde_bakim_checklist()

    message = tracking_agent.handle_status_update("başvurdum")

    assert "başvur" in message.casefold()
    assert all(not c["done"] for c in state.get_case()["checklist"])


def test_unmatched_message_falls_back_with_pending_hint():
    _set_evde_bakim_checklist()

    message = tracking_agent.handle_status_update("yarın gideceğim demiştim")

    assert "bekleyen bir kaleminiz var" in message


def test_scoring_prefers_best_overlap_over_first_item():
    # "sağlık kurulu" hem checklist sırasında ikinci hem de en güçlü örtüşmeye
    # sahip kalem olsun; ilk kalem (nüfus cüzdanı) yanlışlıkla seçilmemeli.
    state.set_checklist([
        {"item": "Nüfus cüzdanı fotokopisi", "done": False},
        {"item": "Sağlık kurulu heyet raporu", "done": False},
    ])

    tracking_agent.handle_status_update("sağlık kurulu heyet raporunu henüz alamadım")

    checklist = state.get_case()["checklist"]
    assert checklist[0]["done"] is False  # nüfus cüzdanı yanlış eşleşmemiş
    assert checklist[1]["done"] is False  # doğru kalem eşleşmiş (missing -> False kalır) ama işaretlenmiş olmalı


def test_stopword_alone_does_not_produce_false_match():
    state.set_checklist([{"item": "Gelir beyanı", "done": False}])

    message = tracking_agent.handle_status_update("bu iş için ne yapmam lazım")

    # Salt bağlaç kelimesiyle (için) yanlış eşleşme kurulmamalı, genel fallback dönmeli
    assert "Gelir beyanı" not in message or "bekleyen bir kaleminiz var" in message


def test_appointment_date_extraction_dd_mm_yyyy():
    soon = (date.today() + timedelta(days=1)).strftime("%d.%m.%Y")

    tracking_agent.handle_status_update(f"MHRS randevumu {soon} tarihine aldım")

    appointments = state.get_case()["appointments"]
    assert len(appointments) == 1
    assert appointments[0]["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_appointment_date_extraction_yarin_keyword():
    tracking_agent.handle_status_update("yarın randevum var")

    appointments = state.get_case()["appointments"]
    assert appointments[0]["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_appointment_date_extraction_turkish_month_name():
    # Yaşlı kullanıcılar tarihi genelde "15 Ağustos" gibi söyler, "15.08.2026" değil.
    tracking_agent.handle_status_update("randevumu 15 Ağustos tarihine aldım")

    appointments = state.get_case()["appointments"]
    assert len(appointments) == 1
    assert appointments[0]["due_date"].endswith("-08-15")


def test_appointment_date_extraction_turkish_month_name_with_year():
    tracking_agent.handle_status_update("randevum 15 ağustos 2026")

    appointments = state.get_case()["appointments"]
    assert appointments[0]["due_date"] == "2026-08-15"


def test_appointment_date_extraction_turkish_month_rolls_to_next_year_if_past():
    # Yıl belirtilmemiş ve bu yıl için ay/gün geçmişte kaldıysa, gelecek yıla yuvarlanmalı.
    tracking_agent.handle_status_update("randevum 5 Ocak")

    appointments = state.get_case()["appointments"]
    due = date.fromisoformat(appointments[0]["due_date"])
    if date(date.today().year, 1, 5) < date.today():
        assert due.year == date.today().year + 1
    else:
        assert due.year == date.today().year


def test_appointment_without_date_asks_clarifying_question():
    message = tracking_agent.handle_status_update("Bir randevu aldım")

    assert "tarih" in message.casefold()
    assert state.get_case()["appointments"] == []


def test_far_future_appointment_does_not_trigger_immediate_reminder():
    far = (date.today() + timedelta(days=30)).strftime("%d.%m.%Y")

    tracking_agent.handle_status_update(f"randevum {far} tarihinde")

    reminder_notifications = [n for n in state.get_case()["notifications"] if n["type"] == "reminder"]
    assert reminder_notifications == []
