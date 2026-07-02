import pytest

from app.services.rag_result_filter import filter_live_rag_results


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        self._iter = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self, rows):
        self._rows = list(rows)

    def find(self, query):
        matched = []
        allowed_ids = set(query.get("_id", {}).get("$in", []))
        school_id = query.get("school_id")
        for row in self._rows:
            row_id = str(row.get("_id"))
            if allowed_ids and row_id not in allowed_ids:
                continue
            if school_id and str(row.get("school_id") or "") != school_id:
                continue
            matched.append(row)
        return FakeCursor(matched)


class FakeDb:
    def __init__(self, chunks, docs):
        self._collections = {
            "rag_chunks": FakeCollection(chunks),
            "rag_documents": FakeCollection(docs),
        }

    def __getitem__(self, key):
        return self._collections[key]


@pytest.mark.asyncio
async def test_filter_live_rag_results_removes_deleted_chunks_and_orphan_docs():
    db = FakeDb(
        chunks=[
            {"_id": "chunk-live", "doc_id": "doc-live", "school_id": "school-a", "knowledge_base_id": "kb-1"},
            {"_id": "chunk-orphan", "doc_id": "doc-deleted", "school_id": "school-a", "knowledge_base_id": "kb-1"},
        ],
        docs=[
            {"_id": "doc-live", "school_id": "school-a"},
        ],
    )
    items = [
        {"id": "chunk-live", "doc_id": "doc-live", "content": "live"},
        {"id": "chunk-deleted", "doc_id": "doc-deleted", "content": "deleted"},
        {"id": "parent-1", "doc_id": "doc-live", "matched_chunk_ids": ["chunk-orphan", "chunk-live"], "content": "parent"},
    ]

    filtered = await filter_live_rag_results(
        db,
        school_id="school-a",
        items=items,
        knowledge_base_ids=["kb-1"],
    )

    assert [item["id"] for item in filtered] == ["chunk-live", "parent-1"]
    assert filtered[1]["matched_chunk_ids"] == ["chunk-live"]
