# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# Subagent C — Takip & Proaktif Bildirim
#
# ÖNEMLİ İLKE: Gerçek sistem entegrasyonu YOK, harici bir kuruma bağlanmaz.
# Kullanıcı/aile durumu kendisi bildirir ("başvurdum", "bu belge bende yok"), bu
# subagent buna göre eksik belge / sonraki adım hatırlatması üretir ve
# backend/state.py::add_notification + mark_checklist_item ile case'i günceller.

from backend.state import add_notification, get_case, mark_checklist_item

_APPLIED_SIGNALS = ["başvurdum", "başvuru yaptım", "gönderdim"]
_MISSING_SIGNALS = ["yok", "bulamadım", "alamadım", "elimde değil", "temin edemedim", "henüz almadım"]
_DONE_SIGNALS = ["aldım", "hallettim", "tamamladım", "elimde", "hazırladım"]

_STEM_LEN = 5  # Türkçe ek varyasyonlarını tolere eden basit gövde karşılaştırması


def _stem(word: str) -> str:
    return word.casefold()[:_STEM_LEN]


def _significant_words(text: str) -> list[str]:
    return [w for w in text.split() if len(w) > 3]


def _match_checklist_item(update_text: str) -> dict | None:
    text_stems = {_stem(w) for w in _significant_words(update_text)}
    for entry in get_case()["checklist"]:
        item_stems = {_stem(w) for w in _significant_words(entry["item"])}
        if text_stems & item_stems:
            return entry
    return None


def handle_status_update(update_text: str) -> str:
    lowered = update_text.casefold()

    if any(sig in lowered for sig in _APPLIED_SIGNALS):
        message = (
            "Başvurunuzu aldığımı not ettim. İlgili kurum genelde başvuruları birkaç "
            "hafta içinde sonuçlandırır; sonuç gelmezse ben size hatırlatma göndereceğim."
        )
        add_notification("status_update", message)
        return message

    if any(sig in lowered for sig in _MISSING_SIGNALS):
        matched = _match_checklist_item(update_text)
        if matched:
            mark_checklist_item(matched["item"], done=False)
            message = (
                f"Not aldım: \"{matched['item']}\" belgesi henüz sizde yok. Bu belge "
                "olmadan başvurunuz tamamlanamaz — bir an önce ilgili kurumdan temin "
                "etmenizi öneririm."
            )
        else:
            message = (
                f"Not aldım: \"{update_text}\". Hangi belgenin eksik olduğunu tam "
                "olarak anlayamadım; checklist'teki belge adlarından birini "
                "söylerseniz onu işaretleyip hatırlatabilirim."
            )
        add_notification("reminder", message)
        return message

    if any(sig in lowered for sig in _DONE_SIGNALS):
        matched = _match_checklist_item(update_text)
        if matched:
            mark_checklist_item(matched["item"], done=True)
            message = f"Harika, \"{matched['item']}\" belgesini tamamlanmış olarak işaretledim."
            add_notification("status_update", message)
            return message

    message = f"Not aldım: \"{update_text}\". Size en kısa sürede bir sonraki adımı hatırlatacağım."
    add_notification("status_update", message)
    return message


MISSING_DOCUMENT_MESSAGE = (
    "Hatırlatma: Evde Bakım Ödeneği başvurusu için gereken sağlık kurulu (heyet) "
    "raporu hâlâ eksik görünüyor. MHRS üzerinden hastaneden randevu alıp bir an önce "
    "temin etmenizi öneririm — bu belge olmadan başvuru değerlendirilemez."
)
