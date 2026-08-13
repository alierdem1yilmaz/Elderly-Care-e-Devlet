# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# _case tek bir modül seviyesi global olduğu için (bkz. backend/state.py),
# testler arası sızıntı olmasın diye her testten önce sıfırlanır.

import pytest

from backend import state


@pytest.fixture(autouse=True)
def _reset_case():
    state.reset_case()
    yield
    state.reset_case()
