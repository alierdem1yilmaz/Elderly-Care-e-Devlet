# Sahiplik: Kişi 1 (ali-erdem)
#
# Aile üyesine özel endpoint'ler — Supabase Auth JWT ile korunur (bkz.
# backend/auth.py::require_family / require_user_id). Yaşlı kullanıcının
# masaüstü uygulaması bu endpoint'leri hiç kullanmaz; sadece aile üyesinin
# kendi (mobil/web) istemcisi kullanır (ileride yapılacak Faz 2, mobil app).

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend import auth
from backend.db import get_client

router = APIRouter(prefix="/family", tags=["family"])


@router.post("/bootstrap")
async def bootstrap_family(auth_user_id: str = Depends(auth.require_user_id)):
    """Bir aile üyesi ilk kez giriş yaptığında çağrılır: henüz bir aileye
    bağlı değilse yeni bir aile oluşturup onu ilk üye yapar; zaten bağlıysa
    mevcut family_id'yi döner (idempotent)."""
    existing = get_client().table("family_members").select("family_id").eq("auth_user_id", auth_user_id).execute()
    if existing.data:
        return {"family_id": existing.data[0]["family_id"]}

    family = get_client().table("families").insert({}).execute()
    family_id = family.data[0]["id"]
    get_client().table("family_members").insert(
        {"family_id": family_id, "auth_user_id": auth_user_id}
    ).execute()
    return {"family_id": family_id}


class CreateElderlyProfileRequest(BaseModel):
    name: str
    phone_number: str = ""  # E.164 formatında (+905xxxxxxxxx) — telefon eşleştirmesi için


@router.post("/elderly-profiles")
async def create_elderly_profile(req: CreateElderlyProfileRequest, family_id: str = Depends(auth.require_family)):
    payload = {"family_id": family_id, "name": req.name}
    if req.phone_number:
        payload["phone_number"] = req.phone_number
    result = get_client().table("elderly_profiles").insert(payload).execute()
    return result.data[0]


@router.get("/elderly-profiles")
async def list_elderly_profiles(family_id: str = Depends(auth.require_family)):
    result = get_client().table("elderly_profiles").select("*").eq("family_id", family_id).execute()
    return result.data


class CreatePairingCodeRequest(BaseModel):
    elderly_profile_id: str


@router.post("/pairing-codes")
async def create_pairing_code_endpoint(req: CreatePairingCodeRequest, family_id: str = Depends(auth.require_family)):
    # RLS backend'de (service_role ile bağlandığı için) bypass edildiğinden,
    # bu profilin gerçekten çağıran ailenin olduğunu burada elle doğruluyoruz.
    profile_check = (
        get_client()
        .table("elderly_profiles")
        .select("id")
        .eq("id", req.elderly_profile_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not profile_check.data:
        raise HTTPException(status_code=404, detail="Bu profil bulunamadı ya da size ait değil.")

    code = auth.create_pairing_code(req.elderly_profile_id)
    return {"code": code}
