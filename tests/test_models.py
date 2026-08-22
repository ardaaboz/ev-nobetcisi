from datetime import datetime, timezone

from watcher.models import Listing


def test_listing_fingerprint_is_stable_across_sources():
    """Ayni daire farkli kaynakta ayni parmak izini uretmeli."""
    a = Listing(
        source="4zida", source_id="abc", url="https://x/1", title="Dvosoban stan",
        price_eur=450, m2=38, rooms=2.0, furnished=True,
        lat=44.80, lng=20.47, address="Njegoseva 5", municipality="Vracar",
        published_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        image_url=None, description="", is_agency=True,
    )
    b = Listing(
        source="halooglasi", source_id="999", url="https://y/2", title="Dvosoban stan",
        price_eur=450, m2=38, rooms=2.0, furnished=True,
        lat=44.80, lng=20.47, address="Njegoseva 5", municipality="Vracar",
        published_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        image_url=None, description="", is_agency=False,
    )
    assert a.fingerprint == b.fingerprint


def test_listing_fingerprint_differs_on_price():
    base = dict(
        source="4zida", source_id="abc", url="https://x/1", title="Dvosoban stan",
        m2=38, rooms=2.0, furnished=True, lat=44.80, lng=20.47,
        address="Njegoseva 5", municipality="Vracar",
        published_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        image_url=None, description="", is_agency=True,
    )
    assert Listing(price_eur=450, **base).fingerprint != Listing(price_eur=600, **base).fingerprint


def test_normalize_text_strips_diacritics():
    from watcher.models import normalize_text

    assert normalize_text("Vračar") == "vracar"
    assert normalize_text("Voždovac") == "vozdovac"
    assert normalize_text("Đorđe") == "dorde"
    assert normalize_text(None) == ""
