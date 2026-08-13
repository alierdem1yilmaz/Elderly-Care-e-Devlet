# Sahiplik: Kişi 1 (ali-erdem)

from backend.agents import eligibility_agent
from backend.state import load_benefits

YASLILIK_AYLIGI = "65 Yaş Üstü Aylığı (Yaşlılık Aylığı)"
EVDE_BAKIM = "Evde Bakım Ödeneği (Engelli Bakım Ödeneği)"
ENGELLI_MAASI = "Engelli Maaşı (Engelli Aylığı)"
ULASIM_KARTI = "65 Yaş Üstü Ücretsiz Toplu Taşıma Kartı"


def _result_for(results, program_name):
    return next(r for r in results if r["program"] == program_name)


def test_under_age_not_eligible_for_age_gated_program():
    profile = {"age": 50, "disability_status": "none", "income_band": "none", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, YASLILIK_AYLIGI)["eligible"] is False


def test_elderly_low_income_eligible_for_yaslilik_ayligi():
    profile = {"age": 70, "disability_status": "none", "income_band": "none", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, YASLILIK_AYLIGI)["eligible"] is True


def test_no_disability_not_eligible_for_disability_program():
    profile = {"age": 70, "disability_status": "none", "income_band": "none", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, EVDE_BAKIM)["eligible"] is False


def test_unreported_disability_not_eligible_but_explains_report_needed():
    profile = {"age": 70, "disability_status": "unreported", "income_band": "none", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    result = _result_for(results, EVDE_BAKIM)
    assert result["eligible"] is False
    assert "rapor" in result["reason"].casefold()


def test_disability_percent_below_threshold_not_eligible_for_engelli_maasi():
    profile = {
        "age": 40,
        "disability_status": "reported",
        "disability_percent": 30,
        "income_band": "none",
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, ENGELLI_MAASI)["eligible"] is False


def test_disability_percent_above_threshold_eligible_for_engelli_maasi():
    profile = {
        "age": 40,
        "disability_status": "reported",
        "disability_percent": 60,
        "income_band": "none",
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, ENGELLI_MAASI)["eligible"] is True


def test_engelli_maasi_has_no_age_requirement():
    profile = {
        "age": 25,
        "disability_status": "reported",
        "disability_percent": 70,
        "income_band": "none",
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, ENGELLI_MAASI)["eligible"] is True


def test_high_income_not_eligible_despite_age():
    profile = {"age": 70, "disability_status": "none", "income_band": "above_minimum", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, YASLILIK_AYLIGI)["eligible"] is False


def test_municipality_dependent_program_mentions_city_in_reason():
    profile = {"age": 70, "disability_status": "none", "income_band": "none", "city": "İstanbul"}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert "İstanbul" in _result_for(results, ULASIM_KARTI)["reason"]


def test_household_income_precise_calc_below_threshold_eligible():
    # 2026 net asgari ücret 28.075,50 TL; 1/3 eşiği ~9.359 TL kişi başı.
    # 20.000 TL / 3 kişi = ~6.667 TL kişi başı -> eşiğin altında, uygun olmalı.
    profile = {
        "age": 70,
        "disability_status": "none",
        "income_band": "above_minimum",  # doluysa bile household_income_tl önceliklidir
        "household_income_tl": 20000,
        "household_size": 3,
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    result = _result_for(results, YASLILIK_AYLIGI)
    assert result["eligible"] is True
    assert "kişi başı" in result["reason"]


def test_household_income_precise_calc_above_threshold_not_eligible():
    # 60.000 TL / 2 kişi = 30.000 TL kişi başı -> 1/3 eşiğinin (~9.359 TL) çok üzerinde.
    profile = {
        "age": 70,
        "disability_status": "none",
        "income_band": "none",  # household alanları öncelikli olduğu için band göz ardı edilmeli
        "household_income_tl": 60000,
        "household_size": 2,
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, YASLILIK_AYLIGI)["eligible"] is False


def test_eligibility_result_includes_program_notes():
    profile = {"age": 70, "disability_status": "none", "income_band": "none", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, YASLILIK_AYLIGI)["notes"]


def test_active_social_security_excludes_from_yaslilik_ayligi():
    # excludes alanı benefits.json'da her zaman vardı ama daha önce hiç kullanılmıyordu.
    profile = {
        "age": 70,
        "disability_status": "none",
        "income_band": "none",
        "has_active_social_security": True,
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    result = _result_for(results, YASLILIK_AYLIGI)
    assert result["eligible"] is False
    assert "sosyal güvence" in result["reason"].casefold()


def test_no_active_social_security_does_not_block_eligibility():
    profile = {
        "age": 70,
        "disability_status": "none",
        "income_band": "none",
        "has_active_social_security": False,
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    assert _result_for(results, YASLILIK_AYLIGI)["eligible"] is True


def test_needs_daily_care_strengthens_evde_bakim_reason():
    profile = {
        "age": 70,
        "disability_status": "reported",
        "disability_percent": 80,
        "income_band": "none",
        "needs_daily_care": True,
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    reason = _result_for(results, EVDE_BAKIM)["reason"].casefold()
    assert "güçlendiriyor" in reason


def test_no_daily_care_need_warns_for_evde_bakim():
    profile = {
        "age": 70,
        "disability_status": "reported",
        "disability_percent": 80,
        "income_band": "none",
        "needs_daily_care": False,
        "city": "",
    }

    results = eligibility_agent.assess_profile(profile, load_benefits())

    reason = _result_for(results, EVDE_BAKIM)["reason"].casefold()
    assert "sonuçlanmayabilir" in reason


def test_all_reasons_include_preliminary_disclaimer():
    profile = {"age": 70, "disability_status": "none", "income_band": "none", "city": ""}

    results = eligibility_agent.assess_profile(profile, load_benefits())

    for result in results:
        assert "ön değerlendirme" in result["reason"].casefold()
