# Subagent B — Başvuru Rehberi
#
# ÖNEMLİ İLKE: form DOLDURMAZ, başvuru GÖNDERMEZ. Sadece kullanıcıya
# "e-Devlet'te/kurumda şu hizmeti arayın, şu belge lazım, şu sırayla şu kurumlara
# gidin" şeklinde referans niteliğinde bir rehber üretir. Çıktı checklist öğeleri
# backend/state.py::set_checklist ile case'e yazılır.
#
# Not: Canlı sohbette (POST /chat) rehberlik hâlâ orchestrator.py'deki GUIDE_PROMPT
# subagent'ı üzerinden LLM ile üretiliyor — bu modül orada çağrılmıyor. Burası
# benefits.json'dan deterministik checklist/adım metni üreten, test edilmiş bir
# yardımcı katman; ileride scripted-demo/fallback akışına (ör. /scenario/*) veya
# GUIDE_PROMPT'un LLM yerine buna dayanmasına bağlanabilir.

from backend.state import load_benefits


def _find_program(program: str, benefits: list[dict]) -> dict | None:
    return next((b for b in benefits if b["name"] == program), None)


def build_checklist(program: str, benefits: list[dict] | None = None) -> list[dict]:
    benefits = benefits if benefits is not None else load_benefits()
    match = _find_program(program, benefits)
    docs = match.get("required_documents", []) if match else []
    return [{"item": doc, "done": False} for doc in docs]


def build_steps(program: str, benefits: list[dict] | None = None) -> str:
    benefits = benefits if benefits is not None else load_benefits()
    match = _find_program(program, benefits)
    if match is None:
        return (
            f"\"{program}\" için elimde kayıtlı bir rehber bulamadım. Bunun yerine "
            "size en yakın Sosyal Yardımlaşma ve Dayanışma Vakfı'na veya Aile ve "
            "Sosyal Hizmetler İl Müdürlüğü'ne danışmanızı öneririm."
        )

    lines = [f"{program} için izlemeniz gereken adımlar (siz kendiniz yapacaksınız):"]
    for i, step in enumerate(match.get("steps", []), start=1):
        lines.append(f"{i}. {step}")

    docs = match.get("required_documents", [])
    if docs:
        lines.append("Yanınızda bulundurmanız gereken belgeler: " + ", ".join(docs) + ".")

    admin = match.get("administered_by")
    if admin:
        lines.append(f"Bu programı yürüten kurum: {admin}")

    notes = match.get("notes")
    if notes:
        lines.append(f"Not: {notes}")

    return "\n".join(lines)
