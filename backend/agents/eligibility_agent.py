# Subagent A — Uygunluk & Bilgi Toplama
#
# Serbest sohbet mantığı backend/agents/orchestrator.py içinde AgentDefinition
# olarak tanımlı (ELIGIBILITY_PROMPT + record_eligibility tool'u, bkz. backend/tools.py).
#
# Aşağıdaki assess_profile() ise "Profilim" formu için AYRI, LLM'siz/deterministik
# bir değerlendirme yolu: kural-tabanlı olması bilinçli bir tercih (tracking_agent'ın
# aynı prensiple kural-tabanlı olması gibi) — yapılandırılmış form verisi için cevap
# anlık ve her seferinde tutarlı olmalı, bir LLM çağrısını beklemeye gerek yok.

# 2026 net asgari ücret — Ocak 2026'da belirlendi, Temmuz-Aralık için ayrı bir zam
# yapılmadı, yıl boyunca sabit. Kaynak: QNB İnvest Araştırma (2026-08-13'te doğrulandı).
# TODO: yıl değişince (Ocak ayı asgari ücret açıklamasıyla) güncellenmeli.
NET_ASGARI_UCRET_TL = 28075.50

_INCOME_BAND_TO_FRACTION = {
    # Sayısal hane geliri girilmediğinde kullanılan kaba, muhafazakar yedek tahmin.
    "none": 0.0,
    "below_minimum": 0.5,
    "around_minimum": 1.0,
    "above_minimum": 1.5,
}

_INCOME_BAND_LABELS = {
    "none": "hiç geliriniz yok",
    "below_minimum": "geliriniz asgari ücretin altında",
    "around_minimum": "geliriniz asgari ücrete yakın",
    "above_minimum": "geliriniz asgari ücretin üstünde",
}


def _tl(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", ".")


def _income_ok(profile: dict, criteria: dict) -> tuple[bool | None, str]:
    limit_fraction = criteria.get("income_limit_fraction_of_net_minimum_wage")
    if limit_fraction is None:
        return None, ""

    limit_tl = NET_ASGARI_UCRET_TL * limit_fraction
    household_income = profile.get("household_income_tl")
    household_size = profile.get("household_size")

    if household_income is not None and household_size:
        # Kesin hesap: gerçek 2026 asgari ücret rakamıyla kişi başı hane geliri.
        per_capita = household_income / household_size
        if per_capita <= limit_tl:
            return True, f"hane geliriniz kişi başı ~{_tl(per_capita)} TL, gelir sınırı olan {_tl(limit_tl)} TL'nin altında"
        return False, f"hane geliriniz kişi başı ~{_tl(per_capita)} TL, gelir sınırı olan {_tl(limit_tl)} TL'nin üzerinde"

    # Yedek: kaba gelir bandı tahmini (sayısal hane geliri girilmediyse).
    band = profile.get("income_band", "around_minimum")
    user_fraction = _INCOME_BAND_TO_FRACTION.get(band, 1.0)
    label = _INCOME_BAND_LABELS.get(band, "gelir durumunuz")
    if user_fraction <= limit_fraction:
        return True, f"beyanınıza göre {label}, gelir sınırının (kişi başı ~{_tl(limit_tl)} TL) altında kalıyor olabilirsiniz"
    return False, f"beyanınıza göre {label}, gelir sınırının (kişi başı ~{_tl(limit_tl)} TL) üzerinde kalabilir"


def _disability_ok(profile: dict, criteria: dict) -> tuple[bool | None, str]:
    if not criteria.get("requires_disability_report"):
        return None, ""
    status = profile.get("disability_status", "none")
    if status == "none":
        return False, "bu program sağlık kurulu raporuyla belgelenmiş bir engellilik durumu gerektiriyor"
    min_pct = criteria.get("min_disability_percentage")
    percent = profile.get("disability_percent")
    is_estimate = bool(profile.get("disability_percent_is_estimate"))
    if status == "unreported":
        return False, "engellilik durumunuz var ama henüz sağlık kurulu raporunuz yok — önce rapor almanız gerekiyor"

    if min_pct is not None and percent is not None:
        estimate_note = " (bu, tam yüzde değil kaba bir tahmin — kesin oran raporunuzda yazar)" if is_estimate else ""
        if percent >= min_pct:
            return True, f"%{percent} engel oranınız{estimate_note}, bu programın %{min_pct} eşiğini karşılıyor"
        return False, f"%{percent} engel oranınız{estimate_note}, bu programın %{min_pct} eşiğinin altında kalıyor"

    # Kullanıcı raporu olduğunu söyledi ama oranı (tahmini bile) bilmiyor —
    # yaşlı bir kullanıcının bunu ezbere bilmesi beklenemez. Onu haksız yere
    # caydırmamak için varsayılan olarak uygun kabul ediyoruz, ama bunu açıkça
    # bir varsayım olarak belirtip raporuna bakmasını öneriyoruz.
    return True, "sağlık kurulu raporunuz olduğunu belirttiniz; engel oranınızı bilmediğiniz için bu programın oran şartını kesin karşılayıp karşılamadığınızı söyleyemiyoruz — raporunuzdaki orana bakmanızı öneririz, yine de başvurmanızda bir sakınca yoktur"


def _excludes_ok(profile: dict, criteria: dict) -> tuple[bool | None, str]:
    """benefits.json'daki `excludes` listesi (ör. SGK/emekli maaşı alanlar) daha
    önce hiç kullanılmıyordu — kullanıcı aktif bir sosyal güvencesi olduğunu
    belirtirse, bu programlarda bunu artık gerçekten dikkate alıyoruz."""
    excludes = criteria.get("excludes")
    if not excludes or not profile.get("has_active_social_security"):
        return None, ""
    return False, f"aktif bir sosyal güvenceniz (SGK/emekli maaşı) olduğunu belirttiniz — bu program şunları kapsam dışı bırakıyor: {excludes[0]}"


def _care_assessment_note(profile: dict, criteria: dict) -> str:
    """requires_care_assessment=true olan programlarda (ör. Evde Bakım Ödeneği),
    kullanıcının günlük bakım/refakat ihtiyacını belirtip belirtmediğine göre
    uygunluğu güçlendiren ya da uyaran ek bir açıklama cümlesi döner."""
    if not criteria.get("requires_care_assessment"):
        return ""
    if profile.get("needs_daily_care"):
        return "günlük bakım/refakat ihtiyacınız olması bu programa uygunluğunuzu güçlendiriyor"
    return "bu program ayrıca günlük bakım/refakat ihtiyacının yerinde değerlendirilmesini gerektiriyor — böyle bir ihtiyacınız yoksa başvurunuz sonuçlanmayabilir"


def assess_profile(profile: dict, benefits: list[dict]) -> list[dict]:
    """Profilim formundan gelen yapılandırılmış veriyi (yaş, engellilik, gelir bandı,
    il) her programın backend/data/schema.py::BenefitCriteria alanlarıyla karşılaştırır.
    Kesin olarak karar verilemeyen (örn. rapor bekleyen) durumlar eligible=False,
    reason'da nedeni açık şekilde belirtir — asla tahmin uydurmaz."""
    age = profile.get("age")
    results = []

    for program in benefits:
        criteria = program.get("criteria", {})
        reasons: list[str] = []
        eligible = True

        min_age = criteria.get("min_age")
        if min_age is not None:
            if age is None:
                eligible = False
                reasons.append("yaşınız belirtilmedi")
            elif age < min_age:
                eligible = False
                reasons.append(f"{min_age} yaş şartını henüz karşılamıyorsunuz (yaşınız: {age})")
            else:
                reasons.append(f"{min_age} yaş şartını karşılıyorsunuz")

        disability_result, disability_reason = _disability_ok(profile, criteria)
        if disability_result is not None:
            eligible = eligible and disability_result
        if disability_reason:
            reasons.append(disability_reason)

        income_result, income_reason = _income_ok(profile, criteria)
        if income_result is not None:
            eligible = eligible and income_result
        if income_reason:
            reasons.append(income_reason)

        excludes_result, excludes_reason = _excludes_ok(profile, criteria)
        if excludes_result is not None:
            eligible = eligible and excludes_result
        if excludes_reason:
            reasons.append(excludes_reason)

        care_note = _care_assessment_note(profile, criteria)
        if care_note:
            reasons.append(care_note)

        if criteria.get("municipality_dependent"):
            city = profile.get("city")
            if city:
                reasons.append(f"{city} belediyesinin güncel prosedürüyle teyit edilmelidir")
            else:
                reasons.append("hangi ilde yaşadığınızı belirtirseniz size özel yönlendirebiliriz")

        if not reasons:
            reasons.append("belirttiğiniz bilgilere göre ön koşulları karşılıyor görünüyorsunuz")

        results.append(
            {
                "program": program["name"],
                "eligible": eligible,
                "reason": "; ".join(reasons) + ". (Kesin sonuç değildir, ön değerlendirmedir.)",
                "notes": program.get("notes"),
            }
        )

    return results
