import json
from pathlib import Path

from watcher.sources import fourzida

FIXTURE = Path(__file__).parent / "fixtures" / "fourzida_search.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _ad(**kwargs) -> dict:
    base = {
        "id": "1", "price": 400, "m2": 30, "furnished": "yes",
        "placeNames": ["Vracar", "Beograd"], "urlPath": "/izdavanje-stanova/a/1",
        "createdAt": "2026-08-21T10:00:00+00:00", "title": "Stan",
    }
    base.update(kwargs)
    return base


def test_parse_extracts_listings():
    listings = fourzida.parse(_payload())
    assert len(listings) > 0, "fixture bos donmemeli - sema degismis olabilir"
    assert listings[0].source == "4zida"
    assert listings[0].url.startswith("https://www.4zida.rs/")


def test_parse_maps_furnished_enum():
    """4zida furnished alani string enum: yes / semi / no / eksik."""
    payload = {"ads": [
        _ad(id="1", furnished="yes"),
        _ad(id="2", furnished="no"),
        _ad(id="3", furnished="semi"),
        _ad(id="4", furnished=None),
    ]}
    got = {x.source_id: x.furnished for x in fourzida.parse(payload)}
    assert got == {"1": True, "2": False, "3": True, "4": None}


def test_parse_uses_place_hierarchy():
    """placeNames ['Sava Centar', 'Novi Beograd', 'Beograd'] seklinde:
    son eleman sehir, ilk eleman semt."""
    payload = {"ads": [_ad(placeNames=["Sava Centar", "Novi Beograd", "Beograd"])]}
    listing = fourzida.parse(payload)[0]
    assert listing.city == "Beograd"
    assert listing.municipality == "Sava Centar"


def test_parse_keeps_non_belgrade_listings_for_downstream_filter():
    """API tum Sirbistan'i donuyor. Adaptor elemez, city alanini doldurur;
    Belgrad filtresi score.py'de uygulanir."""
    payload = {"ads": [_ad(placeNames=["Telep", "Gradske lokacije", "Novi Sad"])]}
    listing = fourzida.parse(payload)[0]
    assert listing.city == "Novi Sad"


def test_parse_detects_agency():
    with_agency = fourzida.parse({"ads": [_ad(agencyUrl="https://x/agencija")]})[0]
    without_agency = fourzida.parse({"ads": [_ad()]})[0]
    assert with_agency.is_agency is True
    assert without_agency.is_agency is False


def test_parse_extracts_image_url():
    payload = {"ads": [_ad(image={"search": {"380x0_fill_0_webp": "https://cdn/x.webp"}})]}
    assert fourzida.parse(payload)[0].image_url == "https://cdn/x.webp"


def test_parse_survives_malformed_entry():
    assert fourzida.parse({"ads": [{"id": "X", "price": "bozuk"}]}) == []


def test_parse_handles_empty_payload():
    assert fourzida.parse({}) == []
