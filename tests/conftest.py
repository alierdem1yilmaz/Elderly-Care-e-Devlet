# Sahiplik: Kişi 2 (Backend İçerik & Takip) — Supabase'e taşıma: Kişi 1 (ali-erdem)
#
# Vaka dosyası artık Supabase'de saklandığı için (bkz. backend/state.py),
# testler gerçek bir Supabase projesine bağlanmadan çalışabilsin diye
# backend.db.get_client() her testten önce sahte/in-memory bir client ile
# (tests/fake_supabase.py) değiştirilir — testler eskisi gibi anlık ve
# izole çalışmaya devam eder.

import pytest

from backend import db
from tests.fake_supabase import FakeSupabaseClient

TEST_CASE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _fake_supabase(monkeypatch):
    fake_client = FakeSupabaseClient()
    monkeypatch.setattr(db, "_client", fake_client)
    monkeypatch.setattr(db, "get_client", lambda: fake_client)
    yield fake_client
