# Sahiplik: Kişi 1 (Backend Omurga)
#
# TODO(Kişi 1): Bu mock mantığını Claude Agent SDK orchestrator ile değiştir.
# Orchestrator kuralları:
#   - Kullanıcıyla konuşan tek katman budur (subagent'lar doğrudan kullanıcıya konuşmaz).
#   - "Guide-only" ilkesi burada merkezi olarak uygulanır: hiçbir yanıt kullanıcı adına
#     bir eylemi "yaptığını" iddia edemez (form doldurmaz, başvuru göndermez).
#     Yanıtlar hep "siz yapacaksınız / şunu yapmanız gerekiyor" diliyle olmalı.
#   - Mesaja göre hangi subagent'ın (eligibility/guide/tracking/security) devreye
#     gireceğine karar verir, o subagent'ın çıktısını sade/sıcak dile çevirip döner.
#
# Sözleşme: handle_message(message) -> {"reply": str, "active_subagent": str | None}
# Şema API_CONTRACT.md ile birebir aynı kalmalı.

from backend.state import get_case


def handle_message(message: str) -> dict:
    # --- MOCK: gerçek orchestrator/subagent çağrıları ile değiştirilecek ---
    reply = (
        "Merhaba, size yardımcı olmak için buradayım. "
        "(mock yanıt — Kişi 1 orchestrator'ı buraya bağlayacak) "
        f"Söylediğiniz: \"{message}\""
    )
    return {"reply": reply, "active_subagent": "eligibility", "case": get_case()}
