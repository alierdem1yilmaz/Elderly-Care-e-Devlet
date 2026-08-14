# Sahiplik: Kişi 1 (ali-erdem)
#
# İki farklı kimlik doğrulama yolu:
#   1. Aile üyesi -> Supabase Auth JWT (magic link ile giriş yapar, mobil/web
#      istemci bu token'ı her istekte gönderir).
#   2. Yaşlı kullanıcının masaüstü uygulaması -> ASLA gerçek bir giriş ekranı
#      görmez. Kurulumda BİR KERE bir eşleştirme kodu (pairing code) girer,
#      karşılığında elderly_profile_id alır ve yerel bir dosyada saklar
#      (bkz. frontend/main.js). Sonraki her açılışta doğrudan bu id'yi kullanır.

import random
import string
from datetime import datetime, timezone

from fastapi import Header, HTTPException

from backend.db import get_client

_PAIRING_CODE_LENGTH = 6


def create_pairing_code(elderly_profile_id: str) -> str:
    """Aile üyesi tarafında (yetkilendirilmiş bir istekle) çağrılır — yaşlı
    kullanıcının masaüstü uygulamasına bir kere girmesi için kısa bir kod üretir."""
    code = "".join(random.choices(string.digits, k=_PAIRING_CODE_LENGTH))
    get_client().table("pairing_codes").insert(
        {"code": code, "elderly_profile_id": elderly_profile_id}
    ).execute()
    return code


def redeem_pairing_code(code: str) -> str:
    """Electron'un ilk açılışta (bkz. POST /pair) çağırdığı fonksiyon. Kod
    geçerliyse elderly_profile_id döner ve kodu bir daha kullanılamaz yapar."""
    result = get_client().table("pairing_codes").select("*").eq("code", code).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Eşleştirme kodu bulunamadı.")

    row = result.data[0]
    if row["used_at"] is not None:
        raise HTTPException(status_code=400, detail="Bu kod daha önce kullanılmış.")

    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Bu kodun süresi dolmuş, yeni bir kod isteyin.")

    get_client().table("pairing_codes").update(
        {"used_at": datetime.now(timezone.utc).isoformat()}
    ).eq("code", code).execute()

    return row["elderly_profile_id"]


def get_family_id_for_user(auth_user_id: str) -> str:
    result = get_client().table("family_members").select("family_id").eq("auth_user_id", auth_user_id).execute()
    if not result.data:
        raise HTTPException(status_code=403, detail="Bu kullanıcı hiçbir aileye bağlı değil.")
    return result.data[0]["family_id"]


async def require_user_id(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: `Authorization: Bearer <supabase-jwt>` başlığını
    doğrular, çağıran kullanıcının Supabase auth_user_id'sini döner. Henüz
    bir aileye bağlı olmasa bile geçerli — bootstrap akışında kullanılır."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization: Bearer <token> başlığı gerekli.")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        user_response = get_client().auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş oturum.") from exc

    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş oturum.")

    return user_response.user.id


async def require_family(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: çağıran aile üyesinin family_id'sini döner. Aile
    üyesine özel endpoint'lerde (ör. eşleştirme kodu üretme) kullanılır."""
    auth_user_id = await require_user_id(authorization)
    return get_family_id_for_user(auth_user_id)
