# Sahiplik: Kişi 1 (ali-erdem)
#
# Supabase bağlantısı. Backend, `service_role` anahtarıyla bağlanır — yani
# Postgres RLS kurallarını bypass eder (bkz. supabase/schema.sql). Yetkilendirme
# (bir aile üyesinin sadece kendi ailesinin verisine erişmesi) burada, Python
# tarafında `backend/auth.py` içinde uygulanır.
#
# SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY, proje kökündeki `.env` dosyasından
# okunur (bkz. `.env.example`) — `.env` asla commit'lenmez.

import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY tanımlı değil. "
                "Proje kökünde bir .env dosyası oluşturup .env.example'daki alanları doldurun."
            )
        _client = create_client(url, key)
    return _client
