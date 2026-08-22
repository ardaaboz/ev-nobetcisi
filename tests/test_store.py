from datetime import datetime, timezone

import pytest

from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.score import Evaluation
from watcher.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    s.init_schema()
    return s


def _listing(sid="1", price=450, m2=38) -> Listing:
    return Listing(
        source="t", source_id=sid, url=f"https://x/{sid}", title="Stan",
        price_eur=price, m2=m2, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    )


def _group(sid="1", price=450, m2=38) -> ListingGroup:
    return ListingGroup(primary=_listing(sid, price, m2))


def test_new_store_is_first_run(store):
    assert store.is_first_run() is True


def test_recorded_listing_becomes_known(store):
    group = _group()
    assert store.is_known(group.primary.fingerprint) is False
    store.record(group, Evaluation(passed=True, score=70))
    assert store.is_known(group.primary.fingerprint) is True
    assert store.is_first_run() is False


def test_record_is_idempotent(store):
    group = _group()
    store.record(group, Evaluation(passed=True, score=70))
    store.record(group, Evaluation(passed=True, score=70))
    assert store.count() == 1


def test_record_persists_all_urls(store):
    group = _group()
    group.duplicates.append(_listing("2"))
    store.record(group, Evaluation(passed=True, score=70))
    assert store.get_all_urls(group.primary.fingerprint) == ["https://x/1", "https://x/2"]


def test_status_transitions(store):
    group = _group()
    store.record(group, Evaluation(passed=True, score=70))
    fingerprint = group.primary.fingerprint
    assert store.get_status(fingerprint) == "new"
    store.mark_notified(fingerprint)
    assert store.get_status(fingerprint) == "notified"
    store.set_status(fingerprint, "contacted")
    assert store.get_status(fingerprint) == "contacted"


def test_set_status_rejects_unknown_value(store):
    group = _group()
    store.record(group, Evaluation(passed=True, score=70))
    with pytest.raises(ValueError):
        store.set_status(group.primary.fingerprint, "uydurma")


def test_get_status_of_unknown_returns_none(store):
    assert store.get_status("yokboyle") is None


def test_persists_across_instances(tmp_path):
    """Actions'ta db dosyasi commit'lenip geri yukleniyor - kalicilik sart."""
    path = str(tmp_path / "p.db")
    first = Store(path)
    first.init_schema()
    group = _group()
    first.record(group, Evaluation(passed=True, score=70))

    second = Store(path)
    assert second.is_known(group.primary.fingerprint) is True
    assert second.count() == 1


def test_init_schema_is_idempotent(tmp_path):
    path = str(tmp_path / "p.db")
    store = Store(path)
    store.init_schema()
    store.record(_group(), Evaluation(passed=True, score=70))
    store.init_schema()
    assert store.count() == 1
