from datetime import datetime, timezone

import pytest

from watcher import config
from watcher.models import Listing, SourceResult
from watcher.pipeline import run
from watcher.store import Store


class FakeNotifier:
    def __init__(self):
        self.listings = []
        self.texts = []

    def send_listing(self, group, evaluation):
        self.listings.append((group, evaluation))

    def send_text(self, text):
        self.texts.append(text)


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(config, "INTER_SOURCE_DELAY", 0)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init_schema()
    return s


@pytest.fixture
def notifier():
    return FakeNotifier()


def _listing(sid="1", price=400, muni="Vracar", city="Beograd", m2=40, **kwargs) -> Listing:
    base = dict(
        source="4zida", source_id=sid, url=f"https://x/{sid}", title=f"Stan {sid}",
        price_eur=price, m2=m2, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality=muni, published_at=datetime.now(timezone.utc),
        image_url=None, description="namesten", is_agency=True, city=city,
    )
    base.update(kwargs)
    return Listing(**base)


def _source(*listings, error=None):
    return lambda: SourceResult(source="4zida", listings=list(listings), error=error)


def test_first_run_is_silent(store, notifier):
    """Ilk kosuda gecmis ilanlarla telefonu bombalamak istemiyoruz."""
    report = run(store, [_source(_listing())], notifier)
    assert report.silent is True
    assert report.notified == 0
    assert notifier.listings == []
    assert store.count() == 1


def test_second_run_notifies_new_listings(store, notifier):
    run(store, [_source(_listing("1"))], notifier)
    report = run(store, [_source(_listing("2", price=420, m2=41))], notifier)
    assert report.silent is False
    assert report.notified == 1
    assert len(notifier.listings) == 1


def test_known_listing_not_renotified(store, notifier):
    run(store, [_source(_listing("1"))], notifier)
    run(store, [_source(_listing("1"))], notifier)
    assert notifier.listings == []


def test_rejected_listings_are_not_recorded(store, notifier):
    run(store, [_source(_listing("seed"))], notifier)
    report = run(store, [_source(
        _listing("2", price=900, m2=80),
        _listing("3", price=420, m2=41, description="suteren stan"),
    )], notifier)
    assert report.passed == 0
    assert notifier.listings == []


def test_low_score_listings_are_filtered(store, notifier, monkeypatch):
    monkeypatch.setattr(config, "SCORE_THRESHOLD", 95)
    run(store, [_source(_listing("seed"))], notifier)
    report = run(store, [_source(_listing("2", price=540, muni="Zemun", m2=20))], notifier)
    assert report.passed == 0


def test_source_error_is_reported_not_raised(store, notifier):
    report = run(store, [_source(error="HTTP 503")], notifier)
    assert any("HTTP 503" in e for e in report.errors)


def test_empty_source_is_reported_as_possible_schema_change(store, notifier):
    report = run(store, [_source()], notifier)
    assert any("bos" in e for e in report.errors)


def test_one_broken_source_does_not_block_others(store, notifier):
    run(store, [_source(_listing("seed"))], notifier)
    report = run(store, [
        _source(error="HTTP 503"),
        _source(_listing("2", price=420, m2=41)),
    ], notifier)
    assert report.notified == 1


def test_notification_cap_is_respected(store, notifier, monkeypatch):
    monkeypatch.setattr(config, "MAX_NOTIFICATIONS_PER_RUN", 2)
    run(store, [_source(_listing("seed"))], notifier)
    many = [_listing(str(i), price=380 + i, m2=40 + i) for i in range(6)]
    report = run(store, [_source(*many)], notifier)
    assert report.notified == 2
    assert len(notifier.texts) == 1, "kalanlar icin ozet mesaji gitmeli"


def test_higher_score_notified_first(store, notifier):
    run(store, [_source(_listing("seed"))], notifier)
    run(store, [_source(
        _listing("far", price=540, muni="Zemun", m2=45),
        _listing("near", price=380, muni="Savski venac", m2=44),
    )], notifier)
    assert notifier.listings[0][0].primary.source_id == "near"


def test_duplicates_across_sources_notified_once(store, notifier):
    run(store, [_source(_listing("seed"))], notifier)
    same_a = _listing("a", price=450, m2=38, title="Dvosoban stan Njegoseva")
    same_b = _listing("b", price=450, m2=38, title="Dvosoban stan Njegoseva")
    report = run(store, [_source(same_a, same_b)], notifier)
    assert report.notified == 1


def test_overflow_listings_arrive_on_the_next_run(store, notifier, monkeypatch):
    """Ust sinira takilan ilanlar KAYBOLMAMALI.

    Onceki hata: fresh'in tamami kaydediliyordu, bu yuzden sinira takilanlar
    bir sonraki kosuda is_known olup dusuyordu ve hicbir zaman bildirilmiyordu.
    Ozet mesaji "bir sonraki kosuda gelecek" diyordu ama gelmiyorlardi.
    """
    monkeypatch.setattr(config, "MAX_NOTIFICATIONS_PER_RUN", 3)
    run(store, [_source(_listing("seed"))], notifier)

    many = [_listing(str(i), price=380 + i, m2=40 + i) for i in range(8)]
    first = run(store, [_source(*many)], notifier)
    assert first.notified == 3

    second = run(store, [_source(*many)], notifier)
    assert second.notified == 3, "kalanlar bir sonraki kosuda gelmeli"

    third = run(store, [_source(*many)], notifier)
    assert third.notified == 2

    fourth = run(store, [_source(*many)], notifier)
    assert fourth.notified == 0, "hepsi bildirildikten sonra susmalı"

    notified_ids = {g.primary.source_id for g, _ in notifier.listings}
    assert notified_ids == {str(i) for i in range(8)}, "her ilan tam olarak bir kez gelmeli"


def test_first_run_records_everything_without_notifying(store, notifier, monkeypatch):
    monkeypatch.setattr(config, "MAX_NOTIFICATIONS_PER_RUN", 2)
    many = [_listing(str(i), price=380 + i, m2=40 + i) for i in range(5)]
    report = run(store, [_source(*many)], notifier)
    assert report.silent is True
    assert report.notified == 0
    assert store.count() == 5, "ilk kosuda hepsi gorulmus sayilmali"


def test_force_notify_overrides_first_run_silence(store, notifier):
    """Bilerek sifirdan liste istendiginde ilk kosu sessizligi devre disi."""
    report = run(store, [_source(_listing("1"), _listing("2", price=420, m2=41))],
                 notifier, force_notify=True)
    assert report.silent is False
    assert report.notified == 2


def test_first_run_still_silent_without_the_flag(store, notifier):
    report = run(store, [_source(_listing("1"))], notifier)
    assert report.silent is True
    assert report.notified == 0
