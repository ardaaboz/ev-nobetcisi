from datetime import datetime, timezone

from watcher.models import Listing
from watcher.score import evaluate


def _listing(**kwargs) -> Listing:
    base = dict(
        source="t", source_id="1", url="u", title="Stan", price_eur=400, m2=40,
        rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="namesten stan", is_agency=False,
        city="Beograd", district="Opština Vračar",
    )
    base.update(kwargs)
    return Listing(**base)


# --- sert filtreler ---

def test_rejects_over_ceiling():
    result = evaluate(_listing(price_eur=700))
    assert result.passed is False
    assert "butce" in result.reject_reason


def test_accepts_exactly_at_ceiling():
    assert evaluate(_listing(price_eur=550)).passed is True


def test_rejects_basement():
    result = evaluate(_listing(description="lep suteren stan"))
    assert result.passed is False
    assert "bodrum" in result.reject_reason


def test_rejects_windowless():
    result = evaluate(_listing(description="soba bez prozora"))
    assert result.passed is False
    assert "pencere" in result.reject_reason


def test_rejects_non_belgrade():
    assert evaluate(_listing(city="Novi Sad", municipality="Telep")).passed is False


def test_rejects_daily_rental():
    assert evaluate(_listing(description="izdajem stan na dan, dnevno")).passed is False


def test_rejects_unfurnished_flag():
    assert evaluate(_listing(furnished=False)).passed is False


def test_rejects_unfurnished_keyword():
    assert evaluate(_listing(furnished=None, description="prazan nenamesten stan")).passed is False


def test_missing_city_is_not_rejected():
    """halooglasi bazen sehir vermeyebilir - bilinmiyor diye elemiyoruz."""
    assert evaluate(_listing(city=None)).passed is True


# --- skorlama ---

def test_accepts_good_listing():
    result = evaluate(_listing(price_eur=380, municipality="Savski venac"))
    assert result.passed is True
    assert result.score > 60


def test_marks_stretch_above_soft_ceiling():
    result = evaluate(_listing(price_eur=530))
    assert result.passed is True
    assert result.is_stretch is True


def test_target_price_is_not_stretch():
    assert evaluate(_listing(price_eur=400)).is_stretch is False


def test_cheaper_and_closer_scores_higher():
    near = evaluate(_listing(price_eur=380, municipality="Savski venac"))
    far = evaluate(_listing(price_eur=520, municipality="Zemun", district="Opština Zemun"))
    assert near.score > far.score


def test_score_is_capped_at_100():
    result = evaluate(_listing(
        price_eur=300, municipality="Savski venac",
        description="svetao prostran namesten stan sa velikom terasom, suncan",
    ))
    assert result.score <= 100


# --- bayraklar ---

def test_flags_balcony():
    assert "balkon" in evaluate(_listing(description="namesten stan sa velikom terasom")).flags


def test_flags_light():
    assert "aydinlik" in evaluate(_listing(description="svetao namesten stan")).flags


def test_flags_direct_owner():
    assert "dogrudan-ev-sahibi" in evaluate(_listing(is_agency=False)).flags
    assert "dogrudan-ev-sahibi" not in evaluate(_listing(is_agency=True)).flags


def test_flags_unverified_desk_when_furnishing_unknown():
    """Yatak/masa sarti ilandan kesin cikarilamiyor - kullaniciya uyari gitmeli."""
    result = evaluate(_listing(furnished=None, description="stan u centru"))
    assert "masa-dogrulanmali" in result.flags


def test_commute_is_reported():
    result = evaluate(_listing(municipality="Vracar"))
    assert result.commute_minutes == 14
