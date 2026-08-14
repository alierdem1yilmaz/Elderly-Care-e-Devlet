# Subagent B — Başvuru Rehberi
#
# ÖNEMLİ İLKE: form DOLDURMAZ, başvuru GÖNDERMEZ. Sadece kullanıcıya
# "e-Devlet'te/kurumda şu hizmeti arayın, şu belge lazım, şu sırayla şu kurumlara
# gidin" şeklinde referans niteliğinde bir rehber üretir. Çıktı checklist öğeleri
# backend/state.py::set_checklist ile case'e yazılır.
#
# Bu modülün fonksiyonları artık canlı sohbete BAĞLI: backend/tools.py'deki
# get_program_guide MCP tool'u bunları sarmalıyor, guide subagent (GUIDE_PROMPT,
# bkz. orchestrator.py) checklist eklemeden/adımları anlatmadan önce bu tool'u
# çağırıyor. Amaç: belge isimleri/kurum/sıra gibi olgusal bilgi LLM'in hafızasından
# değil, doğrudan benefits.json'dan (Kişi 2'nin doğruladığı veri) gelsin — LLM
# sadece bu kesin veriyi sıcak bir dille kullanıcıya anlatıyor.

from backend.state import load_benefits


def _find_program(program: str, benefits: list[dict]) -> dict | None:
    # LLM çağıran taraf bazen tam görünen ad ("65 Yaş Üstü Aylığı ..."), bazen
    # benefits.json'daki kısa id'yi ("yaslilik-ayligi") geçiyor — ikisini de kabul et.
    needle = program.strip().casefold()
    for b in benefits:
        if b["name"].casefold() == needle or b.get("id", "").casefold() == needle:
            return b
    return None


def build_checklist(program: str, benefits: list[dict] | None = None) -> list[dict]:
    benefits = benefits if benefits is not None else load_benefits()
    match = _find_program(program, benefits)
    docs = match.get("required_documents", []) if match else []
    return [{"item": doc, "done": False} for doc in docs]


def build_roadmap(program: str, benefits: list[dict] | None = None) -> dict | None:
    """Yol haritası kartı için YAPILANDIRILMIŞ veri döner (metin paragrafı değil) —
    kullanıcı arayüzünde numaralı, kalıcı adım kartları olarak gösterilir; sohbette
    kaybolan bir paragraftan çok daha takip edilebilir. Program bulunamazsa None."""
    benefits = benefits if benefits is not None else load_benefits()
    match = _find_program(program, benefits)
    if match is None:
        return None
    return {
        "program": match["name"],
        "steps": list(match.get("steps", [])),
        "administered_by": match.get("administered_by"),
    }


def build_steps(program: str, benefits: list[dict] | None = None) -> str:
    benefits = benefits if benefits is not None else load_benefits()
    match = _find_program(program, benefits)
    if match is None:
        return (
            f"\"{program}\" için elimde kayıtlı bir rehber bulamadım. Bunun yerine "
            "size en yakın Sosyal Yardımlaşma ve Dayanışma Vakfı'na veya Aile ve "
            "Sosyal Hizmetler İl Müdürlüğü'ne danışmanızı öneririm."
        )

    lines = [f"{match['name']} için izlemeniz gereken adımlar (siz kendiniz yapacaksınız):"]
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
