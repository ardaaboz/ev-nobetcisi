from pathlib import Path

from watcher.sources import halooglasi

FIXTURE = Path(__file__).parent / "fixtures" / "halooglasi_list.html"


def _page() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_extracts_listings():
    listings = halooglasi.parse(_page())
    assert len(listings) > 0, "fixture bos donmemeli - sema degismis olabilir"
    assert listings[0].source == "halooglasi"
    assert listings[0].price_eur > 0


def test_parse_reads_price_and_size():
    listings = halooglasi.parse(_page())
    priced = [x for x in listings if x.price_eur and x.m2]
    assert priced, "en az bir ilanda hem fiyat hem m2 olmali"
    assert all(50 <= x.price_eur <= 5000 for x in priced)
    assert all(5 <= x.m2 <= 500 for x in priced)


def test_parse_reads_place_chain_not_title():
    """Basliklar guvenilmez: 'izdavanje Vracar' baslikli ilan Vozdovac'ta.
    Semt daima .subtitle-places li zincirinden alinmali."""
    listings = halooglasi.parse(_page())
    misleading = [x for x in listings if "vracar" in x.title.lower()]
    if misleading:
        # baslikta Vracar gecen ilanin semti baslik degil, zincirden gelmeli
        assert all(x.municipality is not None for x in misleading)
    assert any(x.municipality for x in listings)


def test_parse_detects_direct_owner_from_data_attribute():
    """oglasivac_nekretnine_s='vlasnik' -> dogrudan ev sahibi."""
    listings = halooglasi.parse(_page())
    assert any(x.is_agency is False for x in listings), "Vlasnik ilani bulunmali"


def test_parse_sets_city_from_first_place():
    listings = halooglasi.parse(_page())
    assert any(x.city == "Beograd" for x in listings)


def test_parse_builds_absolute_url():
    listings = halooglasi.parse(_page())
    assert all(x.url.startswith("https://www.halooglasi.com/") for x in listings)


def test_parse_reads_publish_date():
    listings = halooglasi.parse(_page())
    assert all(x.published_at.year >= 2020 for x in listings)


def test_parse_returns_empty_on_missing_blob():
    assert halooglasi.parse("<html><body>hicbir sey</body></html>") == []


def test_parse_returns_empty_on_broken_json():
    assert halooglasi.parse("QuidditaEnvironment.serverListData = {bozuk;") == []


def test_to_int_handles_thousand_separator():
    assert halooglasi._to_int("1.250 €") == 1250
    assert halooglasi._to_int("400 €") == 400
    assert halooglasi._to_int("yok") is None


def test_parse_captures_district_separately_from_neighbourhood():
    """Zincir: Beograd > Opstina Vozdovac > Lekino brdo > Gospodara Vucica.
    municipality mahalleyi, district opstinayi tutar - geo.py ikisine de bakar."""
    listings = halooglasi.parse(_page())
    with_district = [x for x in listings if x.district]
    assert with_district, "en az bir ilanda opstina olmali"
    assert any("opstina" in (x.district or "").lower() or "opština" in (x.district or "").lower()
               for x in with_district)


def test_infer_furnished_checks_negative_first():
    """'nenamesten' icinde 'namesten' geciyor - sira onemli."""
    assert halooglasi._infer_furnished("", "nenamesten stan") is False
    assert halooglasi._infer_furnished("", "lepo namesten stan") is True
    assert halooglasi._infer_furnished("", "opremljen stan") is True
    assert halooglasi._infer_furnished("", "stan u centru") is None


def test_furnishing_inferred_from_real_fixture():
    listings = halooglasi.parse(_page())
    known = [x for x in listings if x.furnished is not None]
    assert known, "en az bir ilanda mobilya cikarimi yapilabilmeli"
