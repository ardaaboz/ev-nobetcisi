from datetime import datetime, timezone

from watcher import geo
from watcher.models import Listing


def _listing(**kwargs) -> Listing:
    base = dict(
        source="t", source_id="1", url="u", title="t", price_eur=400, m2=40,
        rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality=None, published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=False, city="Beograd",
    )
    base.update(kwargs)
    return Listing(**base)


def test_haversine_known_distance():
    """Fakulte -> Slavija yaklasik 0.5-1.2 km."""
    km = geo.haversine_km(44.7974, 20.4611, 44.8025, 20.4656)
    assert 0.4 < km < 1.2


def test_haversine_is_zero_for_same_point():
    assert geo.haversine_km(44.7974, 20.4611, 44.7974, 20.4611) == 0.0


def test_commute_from_coordinates_is_short_when_near():
    minutes = geo.commute_minutes(_listing(lat=44.7980, lng=20.4620))
    assert minutes is not None
    assert minutes <= 5


def test_commute_from_coordinates_grows_with_distance():
    near = geo.commute_minutes(_listing(lat=44.7980, lng=20.4620))
    far = geo.commute_minutes(_listing(lat=44.8400, lng=20.4000))
    assert far > near


def test_commute_falls_back_to_municipality_table():
    assert geo.commute_minutes(_listing(municipality="Vracar")) == geo.PLACE_MINUTES["vracar"]


def test_commute_lookup_is_diacritic_insensitive():
    assert geo.commute_minutes(_listing(municipality="Vračar")) == geo.PLACE_MINUTES["vracar"]


def test_commute_falls_back_to_district_when_neighbourhood_unknown():
    """halooglasi 'Dorcol' gibi mahalle adi veriyor; tabloda yoksa opstinaya bakilir."""
    listing = _listing(municipality="Bilinmeyen Mahalle", district="Opština Vračar")
    assert geo.commute_minutes(listing) == geo.PLACE_MINUTES["vracar"]


def test_commute_matches_opstina_prefix():
    assert geo.commute_minutes(_listing(municipality="Opština Voždovac")) == geo.PLACE_MINUTES["vozdovac"]


def test_commute_unknown_place_returns_none():
    assert geo.commute_minutes(_listing(municipality="Kragujevac Centar")) is None


def test_coordinates_take_priority_over_table():
    """Koordinat daha kesin; tablo sadece fallback."""
    listing = _listing(lat=44.7980, lng=20.4620, municipality="Zemun")
    assert geo.commute_minutes(listing) < geo.PLACE_MINUTES["zemun"]


def test_outer_neighbourhoods_beat_optimistic_district_value():
    """Borca, Palilula opstinasinda ama Tuna'nin kuzeyinde. Opstina degerini
    miras alsaydi 26 dk cikardi - gercekte cok daha uzak."""
    borca = _listing(municipality="Borča", district="Opština Palilula")
    palilula_center = _listing(municipality="Bilinmeyen", district="Opština Palilula")
    assert geo.commute_minutes(borca) > geo.commute_minutes(palilula_center)


def test_batajnica_is_far():
    assert geo.commute_minutes(_listing(municipality="Batajnica", district="Opština Zemun")) >= 50
