# Sahiplik: Kişi 2 (Backend İçerik & Takip)

from backend.agents import guide_agent
from backend.state import load_benefits

PROGRAM = "Evde Bakım Ödeneği (Engelli Bakım Ödeneği)"

# "guide-only" ilkesi: sistem bir eylemi kendi adına yaptığını iddia edemez.
_FORBIDDEN_SELF_ACTION_PHRASES = ["başvurunuzu gönderdim", "formu doldurdum", "sizin adınıza"]


def test_build_checklist_known_program_uses_real_documents():
    checklist = guide_agent.build_checklist(PROGRAM)

    items = [c["item"] for c in checklist]
    assert any("heyet" in i.casefold() for i in items)
    assert all(c["done"] is False for c in checklist)


def test_build_checklist_unknown_program_returns_empty():
    assert guide_agent.build_checklist("Var olmayan program") == []


def test_build_steps_includes_numbered_steps_from_dataset():
    text = guide_agent.build_steps(PROGRAM)

    assert "1. " in text
    assert "MHRS" in text


def test_build_steps_includes_required_documents_summary():
    text = guide_agent.build_steps(PROGRAM)

    assert "Yanınızda bulundurmanız gereken belgeler" in text
    for doc in load_benefits()[1]["required_documents"]:
        assert doc in text


def test_build_steps_unknown_program_gives_fallback_referral():
    text = guide_agent.build_steps("Var olmayan program")

    assert "Sosyal Yardımlaşma" in text or "Aile ve Sosyal Hizmetler" in text


def test_build_steps_never_claims_system_performed_the_action():
    for program in load_benefits():
        text = guide_agent.build_steps(program["name"]).casefold()
        for phrase in _FORBIDDEN_SELF_ACTION_PHRASES:
            assert phrase not in text
