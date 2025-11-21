import pytest
from fastapi import HTTPException

from modal_backend import app as memory_app


UserMemoryBackend = memory_app.MemoryBackend._get_user_cls()
VECTOR_DIM = memory_app.VECTOR_DIM


class DummyVector(list):
    def tolist(self):
        return list(self)


class DummyModel:
    def encode(self, text: str, normalize_embeddings: bool = True):
        return DummyVector([float(len(text))] * VECTOR_DIM)


class InMemoryTable:
    def __init__(self):
        self.records = []

    def add(self, rows):
        self.records.extend(rows)

    def search(self, vector):
        table = self

        class _SearchResult:
            def __init__(self, records):
                self._records = records

            def limit(self, count):
                class _LimitedResult:
                    def __init__(self, subset):
                        self._subset = subset

                    def to_list(self):
                        return list(self._subset)

                return _LimitedResult(self._records[:count])

        return _SearchResult(list(table.records))


@pytest.fixture
def backend(monkeypatch):
    instance = UserMemoryBackend()
    instance.model = DummyModel()
    instance.table = InMemoryTable()
    monkeypatch.setattr(memory_app.volume, "commit", lambda: None)
    return instance


def test_add_endpoint_persists_record(backend):
    payload = {"text": "hello world", "user_id": "user-1"}

    response = backend.add(payload)

    assert response["status"] == "success"
    assert isinstance(response["id"], str)
    assert backend.table.records[-1]["text"] == payload["text"]
    assert backend.table.records[-1]["user_id"] == payload["user_id"]


def test_search_endpoint_returns_matching_texts(backend):
    backend.add({"text": "alpha memory", "user_id": "u1"})
    backend.add({"text": "beta thought", "user_id": "u2"})

    result = backend.search({"query": "alpha"})

    assert "results" in result
    assert result["results"][0] == "alpha memory"


def test_add_endpoint_validates_inputs(backend):
    with pytest.raises(HTTPException):
        backend.add({"text": "missing user"})

    with pytest.raises(HTTPException):
        backend.search({})
