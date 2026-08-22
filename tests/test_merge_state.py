from datetime import datetime, timezone

import pytest

from watcher.dedupe import ListingGroup
from watcher.merge_state import merge
from watcher.models import Listing
from watcher.score import Evaluation
from watcher.store import Store


def _store(tmp_path, ad):
    s = Store(str(tmp_path / f"{ad}.db"))
    s.init_schema()
    return s


def _kaydet(store, sid, price=450, m2=38):
    group = ListingGroup(primary=Listing(
        source="t", source_id=sid, url=f"https://x/{sid}", title=f"Stan {sid}",
        price_eur=price, m2=m2, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    ))
    store.record(group, Evaluation(passed=True, score=70))
    return group.primary.fingerprint


def test_merge_is_a_union(tmp_path):
    """Iki tarafin kayitlari birlesmeli, hicbiri kaybolmamali."""
    yerel = _store(tmp_path, "yerel")
    bulut = _store(tmp_path, "bulut")
    a = _kaydet(yerel, "1", price=400, m2=30)
    b = _kaydet(bulut, "2", price=500, m2=60)

    eklenen, _ = merge(yerel.path, bulut.path)

    assert eklenen == 1
    assert yerel.is_known(a) and yerel.is_known(b)
    assert yerel.count() == 2


def test_merge_does_not_duplicate_shared_rows(tmp_path):
    yerel = _store(tmp_path, "yerel")
    bulut = _store(tmp_path, "bulut")
    _kaydet(yerel, "1")
    _kaydet(bulut, "1")   # ayni parmak izi

    eklenen, _ = merge(yerel.path, bulut.path)

    assert eklenen == 0
    assert yerel.count() == 1


def test_real_status_beats_new(tmp_path):
    """'Yazdim' kullanici girdisi; 'new' onu ezmemeli."""
    yerel = _store(tmp_path, "yerel")
    bulut = _store(tmp_path, "bulut")
    parmak = _kaydet(yerel, "1")
    _kaydet(bulut, "1")
    bulut.set_status(parmak, "contacted")

    _, guncellenen = merge(yerel.path, bulut.path)

    assert guncellenen == 1
    assert yerel.get_status(parmak) == "contacted"


def test_new_does_not_overwrite_real_status(tmp_path):
    yerel = _store(tmp_path, "yerel")
    bulut = _store(tmp_path, "bulut")
    parmak = _kaydet(yerel, "1")
    yerel.set_status(parmak, "viewing")
    _kaydet(bulut, "1")   # bulutta hala 'new'

    merge(yerel.path, bulut.path)

    assert yerel.get_status(parmak) == "viewing"


def test_merge_of_empty_source_changes_nothing(tmp_path):
    yerel = _store(tmp_path, "yerel")
    bos = _store(tmp_path, "bos")
    _kaydet(yerel, "1")

    eklenen, guncellenen = merge(yerel.path, bos.path)

    assert (eklenen, guncellenen) == (0, 0)
    assert yerel.count() == 1


def test_merge_into_empty_target(tmp_path):
    bos = _store(tmp_path, "bos")
    dolu = _store(tmp_path, "dolu")
    _kaydet(dolu, "1")
    _kaydet(dolu, "2", price=500, m2=60)

    eklenen, _ = merge(bos.path, dolu.path)

    assert eklenen == 2
    assert bos.count() == 2
