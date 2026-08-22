from datetime import datetime, timezone

import pytest

from watcher import callbacks
from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.score import Evaluation
from watcher.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init_schema()
    return s


def _record(store) -> str:
    group = ListingGroup(primary=Listing(
        source="t", source_id="1", url="u", title="Stan", price_eur=450, m2=38,
        rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    ))
    store.record(group, Evaluation(passed=True, score=70))
    return group.primary.fingerprint


def test_apply_updates_sets_status(store):
    fingerprint = _record(store)
    updates = [{"update_id": 1, "callback_query": {"data": f"contacted:{fingerprint}"}}]
    assert callbacks.apply_updates(store, updates) == 1
    assert store.get_status(fingerprint) == "contacted"


def test_apply_updates_handles_multiple(store):
    fingerprint = _record(store)
    updates = [
        {"update_id": 1, "callback_query": {"data": f"viewing:{fingerprint}"}},
        {"update_id": 2, "callback_query": {"data": f"rejected:{fingerprint}"}},
    ]
    assert callbacks.apply_updates(store, updates) == 2
    assert store.get_status(fingerprint) == "rejected"  # sonuncusu kazanir


def test_apply_updates_ignores_unknown_fingerprint(store):
    updates = [{"update_id": 1, "callback_query": {"data": "contacted:yokboyle"}}]
    assert callbacks.apply_updates(store, updates) == 0


def test_apply_updates_ignores_malformed_payload(store):
    _record(store)
    updates = [
        {"update_id": 1, "callback_query": {"data": "bozuk"}},
        {"update_id": 2, "message": {"text": "merhaba"}},
        {"update_id": 3, "callback_query": {"data": "uydurma:abc"}},
        {"update_id": 4, "callback_query": {}},
        {"update_id": 5},
    ]
    assert callbacks.apply_updates(store, updates) == 0


def test_apply_updates_on_empty_list(store):
    assert callbacks.apply_updates(store, []) == 0


def test_offset_roundtrip(tmp_path, monkeypatch):
    path = str(tmp_path / "offset.txt")
    monkeypatch.setattr(callbacks, "OFFSET_PATH", path)
    assert callbacks.read_offset() == 0
    callbacks.write_offset(42)
    assert callbacks.read_offset() == 42


def test_read_offset_survives_corrupt_file(tmp_path, monkeypatch):
    path = tmp_path / "offset.txt"
    path.write_text("bozuk", encoding="utf-8")
    monkeypatch.setattr(callbacks, "OFFSET_PATH", str(path))
    assert callbacks.read_offset() == 0


def test_sync_advances_offset_past_last_update(store, tmp_path, monkeypatch):
    fingerprint = _record(store)
    monkeypatch.setattr(callbacks, "OFFSET_PATH", str(tmp_path / "offset.txt"))
    monkeypatch.setattr(callbacks, "fetch_updates", lambda offset: [
        {"update_id": 7, "callback_query": {"data": f"contacted:{fingerprint}"}},
    ])
    assert callbacks.sync(store) == 1
    assert callbacks.read_offset() == 8


def test_sync_leaves_offset_when_no_updates(store, tmp_path, monkeypatch):
    monkeypatch.setattr(callbacks, "OFFSET_PATH", str(tmp_path / "offset.txt"))
    callbacks.write_offset(5)
    monkeypatch.setattr(callbacks, "fetch_updates", lambda offset: [])
    assert callbacks.sync(store) == 0
    assert callbacks.read_offset() == 5
