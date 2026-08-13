# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# Subagent C — Takip & Proaktif Bildirim
#
# TODO(Kişi 2): Gerçek sistem entegrasyonu YOK. Kullanıcı/aile durumu kendisi
# bildirir ("başvurdum", "bu belge bende yok"), bu subagent buna göre eksik
# belge / yaklaşan son tarih hatırlatması üretir. backend/state.py::add_notification
# ile case'e yazılır.


def handle_status_update(update_text: str) -> str:
    # --- MOCK ---
    return f"Not aldım: \"{update_text}\". Size en kısa sürede bir sonraki adımı hatırlatacağım."


MISSING_DOCUMENT_MESSAGE = (
    "Hatırlatma: Nüfus cüzdanı fotokopisi başvuru için hâlâ eksik görünüyor. "
    "Bir an önce temin etmenizi öneririm."
)
