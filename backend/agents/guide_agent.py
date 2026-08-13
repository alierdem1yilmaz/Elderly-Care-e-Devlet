# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# Subagent B — Başvuru Rehberi
#
# TODO(Kişi 2): ÖNEMLİ İLKE — form DOLDURMAZ, başvuru GÖNDERMEZ. Sadece kullanıcıya
# "e-Devlet'te şu hizmeti arayın, şu alana şunu yazacaksınız, şu belge lazım, şu
# sırayla şu kurumlara gidin" şeklinde referans niteliğinde bir rehber üretir.
# Çıktı checklist öğeleri backend/state.py::set_checklist ile case'e yazılır.


def build_checklist(program: str, benefits: list[dict]) -> list[dict]:
    # --- MOCK ---
    match = next((b for b in benefits if b["name"] == program), None)
    docs = match.get("required_documents", []) if match else []
    return [{"item": doc, "done": False} for doc in docs]


def build_steps(program: str) -> str:
    # --- MOCK ---
    return (
        f"{program} için e-Devlet'te ilgili hizmeti arayın, gerekli belgeleri "
        "hazırlayın ve sırasıyla ilgili kurumlara başvurun. (mock rehber metni)"
    )
