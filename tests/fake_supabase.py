# Sahiplik: Kişi 1 (ali-erdem)
#
# Gerçek supabase-py Client'ının test için hafif bir sahtesi. Sadece
# backend/state.py ve backend/auth.py'nin kullandığı dar API yüzeyini
# taklit eder: table(name).select().eq().execute() / .insert().execute() /
# .update().eq().execute() — hepsi .data alanı olan bir sonuç döner.
#
# Testler gerçek bir Supabase projesine bağlanmadan, eskisi gibi anlık ve
# izole çalışsın diye backend.db.get_client() bu sınıfın bir örneğiyle
# monkeypatch'lenir (bkz. tests/conftest.py).

import uuid


class _FakeResult:
    def __init__(self, data: list[dict]):
        self.data = data


class _FakeQuery:
    def __init__(self, table: "_FakeTable", op: str, payload=None, conflict_col: str | None = None):
        self._table = table
        self._op = op
        self._payload = payload
        self._conflict_col = conflict_col
        self._filters: list[tuple[str, object]] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value):
        self._filters.append((column, value))
        return self

    def _matching_rows(self) -> list[dict]:
        rows = self._table._rows
        return [r for r in rows if all(r.get(col) == val for col, val in self._filters)]

    def execute(self) -> _FakeResult:
        if self._op == "select":
            return _FakeResult(list(self._matching_rows()))

        if self._op == "insert":
            row = {"id": str(uuid.uuid4()), **self._payload}
            self._table._rows.append(row)
            return _FakeResult([row])

        if self._op == "update":
            matched = self._matching_rows()
            for row in matched:
                row.update(self._payload)
            return _FakeResult(matched)

        if self._op == "upsert":
            conflict_val = self._payload.get(self._conflict_col)
            existing = next(
                (r for r in self._table._rows if r.get(self._conflict_col) == conflict_val), None
            )
            if existing is not None:
                existing.update(self._payload)
                return _FakeResult([existing])
            row = {"id": str(uuid.uuid4()), **self._payload}
            self._table._rows.append(row)
            return _FakeResult([row])

        raise NotImplementedError(self._op)


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def select(self, *_args, **_kwargs) -> _FakeQuery:
        return _FakeQuery(self, "select")

    def insert(self, payload: dict) -> _FakeQuery:
        return _FakeQuery(self, "insert", payload)

    def update(self, payload: dict) -> _FakeQuery:
        return _FakeQuery(self, "update", payload)

    def upsert(self, payload: dict, on_conflict: str = "id", **_kwargs) -> _FakeQuery:
        return _FakeQuery(self, "upsert", payload, conflict_col=on_conflict)


class FakeAuthUser:
    def __init__(self, id: str):
        self.id = id


class _FakeUserResponse:
    def __init__(self, user: FakeAuthUser | None):
        self.user = user


class FakeAuth:
    """auth.get_user(token) çağrısını taklit eder — test'ler token'ı doğrudan
    kullanıcı id'si olarak kaydedebilir (bkz. tests/conftest.py fake_auth_tokens)."""

    def __init__(self):
        self.tokens: dict[str, str] = {}  # token -> auth_user_id

    def get_user(self, token: str) -> _FakeUserResponse:
        user_id = self.tokens.get(token)
        return _FakeUserResponse(FakeAuthUser(user_id) if user_id else None)


class FakeSupabaseClient:
    def __init__(self):
        self._tables: dict[str, list[dict]] = {}
        self.auth = FakeAuth()

    def table(self, name: str) -> _FakeTable:
        self._tables.setdefault(name, [])
        return _FakeTable(self._tables[name])
