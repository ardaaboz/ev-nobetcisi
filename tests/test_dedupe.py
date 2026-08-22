from datetime import datetime, timedelta, timezone

from watcher.dedupe import merge
from watcher.models import Listing

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _listing(source="4zida", sid="1", price=450, m2=38, muni="Vracar",
             title="Dvosoban stan Njegoseva", is_agency=True, published=NOW) -> Listing:
    return Listing(
        source=source, source_id=sid, url=f"https://{source}/{sid}", title=title,
        price_eur=price, m2=m2, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality=muni, published_at=published,
        image_url=None, description="", is_agency=is_agency, city="Beograd",
    )


def test_merges_same_flat_across_sources():
    groups = merge([_listing("4zida", "1"), _listing("halooglasi", "2")])
    assert len(groups) == 1
    assert len(groups[0].duplicates) == 1
    assert len(groups[0].all_urls) == 2


def test_keeps_different_flats_separate():
    groups = merge([
        _listing(sid="1", price=450, m2=38),
        _listing(sid="2", price=900, m2=80, title="Trosoban stan Bulevar"),
    ])
    assert len(groups) == 2


def test_same_price_and_size_but_different_address_not_merged():
    """Ayni fiyat ve m2 tesaduf olabilir - baslik benzemiyorsa birlestirme."""
    groups = merge([
        _listing(sid="1", title="Dvosoban stan Njegoseva"),
        _listing(sid="2", title="Garsonjera Bulevar Kralja Aleksandra"),
    ])
    assert len(groups) == 2


def test_primary_prefers_direct_owner():
    """Dogrudan ev sahibi ilani birincil secilmeli - iletisim sansi daha iyi."""
    groups = merge([
        _listing("4zida", "1", is_agency=True),
        _listing("halooglasi", "2", is_agency=False),
    ])
    assert len(groups) == 1
    assert groups[0].primary.is_agency is False
    assert groups[0].primary.source == "halooglasi"


def test_primary_prefers_earlier_when_both_agencies():
    earlier = _listing("4zida", "1", published=NOW - timedelta(hours=3))
    later = _listing("halooglasi", "2", published=NOW)
    groups = merge([later, earlier])
    assert groups[0].primary.source == "4zida"


def test_all_urls_includes_every_source():
    groups = merge([
        _listing("4zida", "1"),
        _listing("halooglasi", "2"),
        _listing("cityexpert", "3"),
    ])
    assert len(groups) == 1
    assert sorted(groups[0].sources) == ["4zida", "cityexpert", "halooglasi"]
    assert len(groups[0].all_urls) == 3


def test_empty_input_returns_empty():
    assert merge([]) == []


def test_single_listing_becomes_single_group():
    groups = merge([_listing()])
    assert len(groups) == 1
    assert groups[0].duplicates == []
    assert groups[0].all_urls == ["https://4zida/1"]


def _with_address(source, sid, address, title, price=450, m2=38):
    return Listing(
        source=source, source_id=sid, url=f"https://{source}/{sid}", title=title,
        price_eur=price, m2=m2, rooms=2.0, furnished=True, lat=None, lng=None,
        address=address, municipality="Vracar", published_at=NOW,
        image_url=None, description="", is_agency=True, city="Beograd",
    )


def test_merges_on_address_when_titles_differ():
    """Gercek veri: CityExpert basligi '2.0 Njegoseva', 4zida'ninki 'Dvosoban stan'.
    Basliklar asla eslesmiyor - adres eslesmeli."""
    groups = merge([
        _with_address("cityexpert", "1", "Njegoseva", "2.0 Njegoseva"),
        _with_address("4zida", "2", "Njegoseva 5", "Dvosoban stan u centru"),
    ])
    assert len(groups) == 1


def test_does_not_merge_different_streets():
    groups = merge([
        _with_address("cityexpert", "1", "Njegoseva", "2.0 Njegoseva"),
        _with_address("4zida", "2", "Kneza Milosa", "Dvosoban stan"),
    ])
    assert len(groups) == 2


def test_falls_back_to_title_when_address_missing():
    """4zida bazen adres vermiyor - o zaman baslik karsilastirilir."""
    groups = merge([
        _with_address("4zida", "1", None, "Dvosoban stan Njegoseva"),
        _with_address("halooglasi", "2", None, "Dvosoban stan Njegoseva"),
    ])
    assert len(groups) == 1


def test_address_mismatch_wins_over_similar_titles():
    """Adresler farkliysa basliklar benzese bile birlestirme."""
    groups = merge([
        _with_address("cityexpert", "1", "Njegoseva", "Dvosoban stan"),
        _with_address("4zida", "2", "Kneza Milosa", "Dvosoban stan"),
    ])
    assert len(groups) == 2


def test_merges_across_sources_despite_different_place_granularity():
    """Canli veriden gercek vaka: ayni daire CityExpert'te opstina adiyla
    ('Zemun'), halooglasi'de mahalle adiyla ('Kalvarija') geliyor. Kaba anahtar
    semt icerdiginde farkli kovalara dusup hic karsilastirilmiyorlardi."""
    groups = merge([
        _with_address("cityexpert", "1", "Karla Soprona", "2.0 Karla Soprona", price=400, m2=43),
        _with_address("halooglasi", "2", "Karla Soprona", "Stan Kalvarija", price=400, m2=43),
    ])
    assert len(groups) == 1, "ayni sokak, ayni fiyat, ayni m2 - ayni daire"
    assert len(groups[0].all_urls) == 2


def test_same_price_and_size_different_street_stays_separate():
    """Kova genisledi, yanlis birlestirme olmamali."""
    groups = merge([
        _with_address("cityexpert", "1", "Karla Soprona", "2.0 Karla Soprona", price=400, m2=43),
        _with_address("halooglasi", "2", "Jastrebacka", "Stan Karaburma", price=400, m2=43),
    ])
    assert len(groups) == 2
