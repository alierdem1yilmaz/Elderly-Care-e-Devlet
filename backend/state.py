# Sahiplik: Kişi 2 (Backend İçerik & Takip) — Supabase'e taşıma: Kişi 1 (ali-erdem)
#
# Vaka dosyası (case file) artık Supabase'deki `cases` tablosunda saklanıyor,
# `case_id` ile anahtarlanıyor (`case_id` == `elderly_profiles.id`, bkz.
# supabase/schema.sql). Eskiden tek bir global in-memory dict vardı; artık her
# yaşlı profili kendi satırına/kendi durumuna sahip — birden fazla aile/telefon
# hattı/mobil oturum aynı anda birbirine karışmadan çalışabiliyor.
#
# `backend/db.py::get_client()` normalde gerçek Supabase'e bağlanır; testlerde
# `tests/fake_supabase.py` ile monkeypatch'lenir (bkz. tests/conftest.py) —
# böylece testler gerçek ağ/Supabase'e ihtiyaç duymadan, eskisi gibi anlık çalışır.

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.data.schema import BenefitsFile
from backend.db import get_client

_BENEFITS_PATH = Path(__file__).parent / "data" / "benefits.json"
_benefits_cache: list[dict] | None = None

_EDEVLET_GUIDE_PATH = Path(__file__).parent / "data" / "edevlet_guide.json"
_edevlet_guide_cache: list[dict] | None = None

_DOCUMENT_TIPS_PATH = Path(__file__).parent / "data" / "document_tips.json"
_document_tips_cache: dict | None = None

_DEADLINE_WARNING_DAYS = 3  # son tarihe bu kadar gün veya daha az kaldıysa hatırlat
_NEXT_STEP_LOOKAHEAD_DAYS = 7  # bu kadar gün içindeki randevu "sıradaki adım" sayılır

_EMPTY_CASE_COLUMNS = {
    "eligibility": [],
    "checklist": [],
    "notifications": [],
    "appointments": [],
    "profile": None,
    "roadmap": [],
}


def load_edevlet_guide() -> list[dict]:
    """backend/data/edevlet_guide.json içindeki statik, doğrulanmış e-Devlet
    okuryazarlığı bölümlerini döner (cache'lenir). Chat'in o anki üretimine
    bırakılmayan, sabit/güvenilir referans içeriktir."""
    global _edevlet_guide_cache
    if _edevlet_guide_cache is None:
        with open(_EDEVLET_GUIDE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _edevlet_guide_cache = raw["sections"]
    return _edevlet_guide_cache


def load_document_tips() -> dict:
    """backend/data/document_tips.json içindeki, belge adı anahtar kelimesine göre
    "nasıl temin ederim" ipuçlarını döner (cache'lenir). Statik/deterministik —
    checklist'teki her belge için LLM'e sormaya gerek kalmadan anında bir ipucu verir."""
    global _document_tips_cache
    if _document_tips_cache is None:
        with open(_DOCUMENT_TIPS_PATH, encoding="utf-8") as f:
            _document_tips_cache = json.load(f)
    return _document_tips_cache


def load_benefits() -> list[dict]:
    """backend/data/benefits.json içindeki program listesini döner (cache'lenir).
    Şema backend/data/schema.py ile doğrulanır — bozuk veri burada net bir
    hata olarak patlar, tüketen kod (guide_agent, eligibility_agent) içinde
    sessiz KeyError'a dönüşmez."""
    global _benefits_cache
    if _benefits_cache is None:
        with open(_BENEFITS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        validated = BenefitsFile.model_validate(raw)
        _benefits_cache = [p.model_dump() for p in validated.programs]
    return _benefits_cache


def _ensure_elderly_profile_exists(case_id: str) -> None:
    """`cases.elderly_profile_id` bir foreign key olduğu için, önce karşılık
    gelen elderly_profiles satırının var olduğundan emin olmalıyız. Masaüstü
    uygulaması hiçbir aileye bağlanmadan (family_id boş) kendi kendine bir
    case_id üretip kullanmaya başlıyor — bu yüzden burada family_id'siz,
    "sahipsiz" bir profil otomatik oluşturuluyor; kullanıcı daha sonra bir
    eşleştirme koduyla gerçek bir aileye bağlanınca bu satır güncellenir,
    geçmiş verisi kaybolmaz."""
    existing = get_client().table("elderly_profiles").select("id").eq("id", case_id).execute()
    if not existing.data:
        get_client().table("elderly_profiles").insert({"id": case_id}).execute()


def _fetch_case_row(case_id: str) -> dict:
    """Supabase'deki `cases` satırını döner; henüz yoksa (bu profil için ilk
    erişimse) boş bir satır oluşturur."""
    result = get_client().table("cases").select("*").eq("elderly_profile_id", case_id).execute()
    if result.data:
        return result.data[0]

    _ensure_elderly_profile_exists(case_id)
    insert_result = (
        get_client()
        .table("cases")
        .insert({"elderly_profile_id": case_id, **_EMPTY_CASE_COLUMNS})
        .execute()
    )
    return insert_result.data[0]


def _save_case_row(case_id: str, patch: dict) -> None:
    # Önce mevcut satırı (yoksa boş halini) okuyup patch'i üstüne uygulayarak
    # HER ZAMAN tam bir satır upsert ediyoruz — kısmi bir patch'i doğrudan
    # upsert etmek, satır ilk kez oluşturuluyorsa diğer sütunları (ör.
    # notifications) hiç göndermeden bırakabilir, sonraki bir okuma o alanı
    # bulamayıp hataya düşerdi.
    current = _fetch_case_row(case_id)
    payload = {
        "elderly_profile_id": case_id,
        "eligibility": current["eligibility"],
        "checklist": current["checklist"],
        "notifications": current["notifications"],
        "appointments": current["appointments"],
        "profile": current["profile"],
        "roadmap": current["roadmap"],
        **patch,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    get_client().table("cases").upsert(payload, on_conflict="elderly_profile_id").execute()


def get_case(case_id: str) -> dict:
    row = _fetch_case_row(case_id)
    case = {
        "eligibility": row["eligibility"],
        "checklist": row["checklist"],
        "notifications": row["notifications"],
        "appointments": row["appointments"],
        "profile": row["profile"],
        "roadmap": row["roadmap"],
    }
    case = _check_due_appointments(case_id, case)
    case["next_step"] = get_next_step(case_id, case)
    return case


def get_next_step(case_id: str, case: dict | None = None) -> str:
    """Checklist/randevu/profil durumuna bakarak kullanıcıya tek, net bir
    "şimdi ne yapmalıyım" cevabı üretir — birden fazla listeyi kendi başına
    önceliklendirmek zorunda kalmasın diye (bilişsel yükü azaltan özet kart)."""
    if case is None:
        row = _fetch_case_row(case_id)
        case = {"checklist": row["checklist"], "appointments": row["appointments"], "profile": row["profile"]}

    today = date.today()
    upcoming = sorted(
        (a for a in case["appointments"] if not a.get("done", False)),
        key=lambda a: a["due_date"],
    )
    if upcoming:
        nearest = upcoming[0]
        due = date.fromisoformat(nearest["due_date"])
        if due - today <= timedelta(days=_NEXT_STEP_LOOKAHEAD_DAYS):
            return f"{nearest['description']} — {due.strftime('%d.%m.%Y')} tarihine dikkat edin."

    pending = next((entry for entry in case["checklist"] if not entry["done"]), None)
    if pending:
        return f"Şimdi yapmanız gereken: {pending['item']}"

    if case["profile"] is None:
        return "Önce \"Haklarım\" sekmesinden birkaç bilgi girin, size özel haklarınızı bulalım."

    return "Şu anda bekleyen bir işleminiz yok. Yeni bir konuda yardım isterseniz Sohbet'ten yazabilirsiniz."


def set_eligibility(case_id: str, results: list[dict]) -> None:
    _save_case_row(case_id, {"eligibility": results})


def set_roadmap(case_id: str, program: str, steps: list[str], administered_by: str | None) -> None:
    """Bir programın yol haritasını (numaralı, kalıcı adım kartları için)
    kaydeder — aynı program için tekrar çağrılırsa günceller, farklı bir
    program için çağrılırsa listeye ekler (kullanıcı birden fazla hakka aynı
    anda başvuruyor olabilir)."""
    current = [r for r in _fetch_case_row(case_id)["roadmap"] if r["program"] != program]
    current.append({"program": program, "steps": steps, "administered_by": administered_by})
    _save_case_row(case_id, {"roadmap": current})


def set_checklist(case_id: str, items: list[dict]) -> None:
    _save_case_row(case_id, {"checklist": items})


def set_profile(case_id: str, profile: dict) -> None:
    _save_case_row(case_id, {"profile": profile})


def get_profile(case_id: str) -> dict | None:
    return _fetch_case_row(case_id)["profile"]


def add_notification(case_id: str, type_: str, message: str) -> None:
    row = _fetch_case_row(case_id)
    notifications = [*row["notifications"], {"type": type_, "message": message, "timestamp": datetime.now().isoformat()}]
    _save_case_row(case_id, {"notifications": notifications})


def mark_checklist_item(case_id: str, item_substring: str, done: bool) -> dict | None:
    """checklist'te adı item_substring'i içeren ilk kalemi işaretler. Eşleşen kalemi
    (veya bulunamazsa None) döner — tracking_agent buna göre yanıt üretir."""
    row = _fetch_case_row(case_id)
    checklist = row["checklist"]
    needle = item_substring.casefold()
    for entry in checklist:
        if needle in entry["item"].casefold():
            entry["done"] = done
            _save_case_row(case_id, {"checklist": checklist})
            return entry
    return None


def next_pending_checklist_item(case_id: str) -> dict | None:
    """checklist'te henüz 'done' olmayan ilk kalemi döner — proaktif hatırlatma için."""
    checklist = _fetch_case_row(case_id)["checklist"]
    return next((entry for entry in checklist if not entry["done"]), None)


def add_appointment(case_id: str, description: str, due_date: str) -> dict:
    """Kullanıcının bildirdiği bir randevu/son tarihi ("MHRS randevusu 20.08.2026")
    case'e ekler. due_date ISO formatında ("YYYY-MM-DD") olmalı."""
    date.fromisoformat(due_date)  # erken ve net hata versin, sessizce bozuk veri saklamasın
    row = _fetch_case_row(case_id)
    appointment = {"description": description, "due_date": due_date, "reminded": False}
    appointments = [*row["appointments"], appointment]
    _save_case_row(case_id, {"appointments": appointments})
    return appointment


def _check_due_appointments(case_id: str, case: dict) -> dict:
    """Süresi yaklaşan/geçen randevular için, kişi başına yalnızca bir kez
    proaktif hatırlatma bildirimi üretir (reminded bayrağıyla tekrar önlenir)."""
    today = date.today()
    appointments = case["appointments"]
    notifications = case["notifications"]
    changed = False

    for appt in appointments:
        if appt.get("reminded"):
            continue
        due = date.fromisoformat(appt["due_date"])
        if due - today > timedelta(days=_DEADLINE_WARNING_DAYS):
            continue
        if due < today:
            message = f"Hatırlatma: \"{appt['description']}\" için son tarih geçmiş görünüyor ({due.strftime('%d.%m.%Y')}). Lütfen en kısa sürede ilgilenin."
        else:
            message = f"Hatırlatma: \"{appt['description']}\" için son tarih yaklaşıyor ({due.strftime('%d.%m.%Y')})."
        notifications = [*notifications, {"type": "reminder", "message": message, "timestamp": datetime.now().isoformat()}]
        appt["reminded"] = True
        changed = True

    if changed:
        _save_case_row(case_id, {"appointments": appointments, "notifications": notifications})
        case = {**case, "appointments": appointments, "notifications": notifications}
    return case


def reset_case(case_id: str) -> None:
    _save_case_row(case_id, dict(_EMPTY_CASE_COLUMNS))
