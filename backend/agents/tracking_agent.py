# Subagent C — Takip & Proaktif Bildirim
#
# ÖNEMLİ İLKE: Gerçek sistem entegrasyonu YOK, harici bir kuruma bağlanmaz.
# Kullanıcı/aile durumu kendisi bildirir ("başvurdum", "bu belge bende yok"), bu
# subagent buna göre eksik belge / sonraki adım hatırlatması üretir ve
# backend/state.py::add_notification + mark_checklist_item ile case'i günceller.
#
# POST /case/status bu modülü doğrudan çağırır (bkz. backend/main.py) — LLM
# orchestrator'a gitmiyor: kural tabanlı olduğu için hızlı ve deterministik,
# ayrıca hem burada hem orchestrator'da bildirim yazmak çift kayda yol açardı.
# Serbest sohbette ("başvuru durumumu merak ediyorum" gibi) kullanıcı orchestrator
# ile konuşmaya devam eder; TRACKING_PROMPT (bkz. orchestrator.py) o tarafı kapsar.

import re
from datetime import date, timedelta

from backend.state import (
    add_appointment,
    add_notification,
    get_case,
    mark_checklist_item,
    next_pending_checklist_item,
)

_DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")

# Yaşlı kullanıcılar tarihi çoğunlukla "15 Ağustos" gibi ay ismiyle söyler,
# "15.08.2026" gibi rakamla değil — bu yüzden ay isimlerini de tanımak şart.
_TURKISH_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
    "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
}
_TURKISH_DATE_RE = re.compile(
    r"(\d{1,2})\s*(" + "|".join(_TURKISH_MONTHS.keys()) + r")(?:\s+(\d{4}))?",
)


def _extract_date(text: str) -> date | None:
    lowered = text.casefold()

    if "bugün" in lowered or "bugun" in lowered:
        return date.today()
    if "yarın" in lowered or "yarin" in lowered:
        return date.today() + timedelta(days=1)

    match = _DATE_RE.search(text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None

    match = _TURKISH_DATE_RE.search(lowered)
    if match:
        day = int(match.group(1))
        month = _TURKISH_MONTHS[match.group(2)]
        year = int(match.group(3)) if match.group(3) else date.today().year
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if match.group(3) is None and candidate < date.today():
            # Yıl söylenmediyse ve bu tarih bu yıl için geçmişte kaldıysa,
            # kullanıcı büyük olasılıkla gelecek yılı kastediyordur.
            candidate = date(year + 1, month, day)
        return candidate

    return None


_APPLIED_SIGNALS = ["başvurdum", "başvuru yaptım", "gönderdim"]
_MISSING_SIGNALS = ["yok", "bulamadım", "alamadım", "elimde değil", "temin edemedim", "henüz almadım"]
_DONE_SIGNALS = ["aldım", "hallettim", "tamamladım", "elimde", "hazırladım"]

_STEM_LEN = 5  # Türkçe ek varyasyonlarını tolere eden basit gövde karşılaştırması

# Belge adlarında sık geçen ama ayırt edici olmayan bağlaç/dolgu kelimeleri —
# bunlar yüzünden alakasız bir checklist kalemi yanlışlıkla eşleşmesin diye elenir.
_STOPWORDS = {
    "veya", "için", "ile", "gibi", "varsa", "adet", "aslı", "bulunan",
    "bazı", "önceden", "istenir", "genelde", "vb", "olan",
}


def _stem(word: str) -> str:
    return word.casefold()[:_STEM_LEN]


def _significant_words(text: str) -> set[str]:
    return {_stem(w) for w in text.split() if len(w) > 3 and w.casefold() not in _STOPWORDS}


def _match_checklist_item(update_text: str) -> dict | None:
    """checklist'teki kalemler arasından, kullanıcının cümlesiyle en çok ortak
    (gövdelenmiş) kelimesi olan kalemi döner — tek ortak kelimeye değil, en güçlü
    örtüşmeye göre seçer ki benzer isimli belgeler birbirine karışmasın."""
    text_stems = _significant_words(update_text)
    if not text_stems:
        return None

    best_entry, best_score = None, 0
    for entry in get_case()["checklist"]:
        score = len(text_stems & _significant_words(entry["item"]))
        if score > best_score:
            best_entry, best_score = entry, score
    return best_entry


def _with_pending_hint(message: str) -> str:
    """Eşleşme bulunamadığında, checklist'te bekleyen bir kalem varsa proaktif
    olarak hatırlatır — "Takip & Proaktif Bildirim" ilkesine hizmet eder."""
    pending = next_pending_checklist_item()
    if pending:
        message += f" Bu arada, checklist'te hâlâ bekleyen bir kaleminiz var: \"{pending['item']}\"."
    return message


def handle_status_update(update_text: str) -> str:
    lowered = update_text.casefold()

    if "randevu" in lowered:
        found_date = _extract_date(update_text)
        if found_date:
            add_appointment(f"Randevu: {update_text.strip()}", found_date.isoformat())
            message = (
                f"Randevunuzu not ettim: {found_date.strftime('%d.%m.%Y')}. Tarih "
                "yaklaşınca size hatırlatma göndereceğim."
            )
            add_notification("status_update", message)
            return message

        # Tarih yok — "bir randevu aldım" gibi belirsiz bir mesajı sessizce
        # atlamak yerine hedefe yönelik bir netleştirme sorusu dön; kullanıcı
        # tarihi söylediğinde yukarıdaki dallanma gerçek bir appointment kaydeder.
        message = (
            "Randevunuzu not aldım ama tarihini anlayamadım — hangi tarihte? "
            "(örn. 20.08.2026 ya da \"yarın\" diyebilirsiniz.)"
        )
        add_notification("status_update", message)
        return message

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
            message = _with_pending_hint(
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

    message = _with_pending_hint(
        f"Not aldım: \"{update_text}\". Size en kısa sürede bir sonraki adımı hatırlatacağım."
    )
    add_notification("status_update", message)
    return message


MISSING_DOCUMENT_MESSAGE = (
    "Hatırlatma: Evde Bakım Ödeneği başvurusu için gereken sağlık kurulu (heyet) "
    "raporu hâlâ eksik görünüyor. MHRS üzerinden hastaneden randevu alıp bir an önce "
    "temin etmenizi öneririm — bu belge olmadan başvuru değerlendirilemez."
)
