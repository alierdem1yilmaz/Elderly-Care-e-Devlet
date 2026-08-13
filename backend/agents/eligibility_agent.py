# Sahiplik: Kişi 1 (Backend Omurga)
# Subagent A — Uygunluk & Bilgi Toplama
#
# TODO(Kişi 1): Kullanıcıdan yaş/gelir/sağlık/yaşam koşulu bilgisini toplayıp
# backend/data/benefits.json içindeki kriterlerle eşleştir (bkz. Kişi 2'nin veri seti).
# Çıktı: [{"program": str, "eligible": bool, "reason": str}, ...]
# Bu SADECE bir değerlendirmedir, bir eylem değildir — "guide-only" ilkesine aykırılık yok.


def assess(user_info: dict, benefits: list[dict]) -> list[dict]:
    # --- MOCK ---
    return [
        {"program": b["name"], "eligible": True, "reason": "mock değerlendirme"}
        for b in benefits
    ]
