import json
from pathlib import Path

from watcher.sources import cityexpert

FIXTURE = Path(__file__).parent / "fixtures" / "cityexpert_search.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_extracts_listings():
    listings = cityexpert.parse(_payload())
    assert len(listings) > 0, "fixture bos donmemeli - sema degismis olabilir"
    first = listings[0]
    assert first.source == "cityexpert"
    assert first.price_eur > 0
    assert first.url.startswith("https://cityexpert.rs/")
    assert first.published_at is not None


def test_parse_reads_coordinates():
    listings = cityexpert.parse(_payload())
    with_coords = [x for x in listings if x.lat is not None]
    assert with_coords, "en az bir ilanda koordinat olmali"
    assert 44.6 < with_coords[0].lat < 45.0
    assert 20.2 < with_coords[0].lng < 20.7


def test_parse_sets_city_to_belgrade():
    """cityId=1 sorguladigimiz icin tum sonuclar Belgrad; filtre buna guveniyor."""
    listings = cityexpert.parse(_payload())
    assert all(x.city == "Beograd" for x in listings)


def test_parse_survives_malformed_entry():
    """Tek bozuk kayit tum partiyi dusurmemeli."""
    assert cityexpert.parse({"result": [{"uniqueID": "X", "price": "bozuk"}]}) == []


def test_parse_handles_empty_payload():
    assert cityexpert.parse({}) == []
    assert cityexpert.parse({"result": []}) == []


def test_parse_location_splits_lat_lng():
    listings = cityexpert.parse({"result": [{
        "uniqueID": "1-BR", "price": 400.0, "size": 40,
        "location": "44.80124, 20.47985", "municipality": "Vracar",
        "structure": "2.0", "furnished": 1, "firstPublished": "2026-08-21T14:03:36Z",
    }]})
    assert len(listings) == 1
    assert listings[0].lat == 44.80124
    assert listings[0].lng == 20.47985
