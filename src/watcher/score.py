"""Sert filtreler ve yumusak skor.

Tasarim ilkesi: yanlis negatif (iyi ilani elemek) yanlis pozitiften
(fazladan ilan gostermek) daha pahali. Esikler bu yuzden gevsek ve
bilinmeyen degerler eleme sebebi degil.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .geo import commute_minutes
from .models import Listing, normalize_text

# Sert eleme anahtar kelimeleri (normalize edilmis: kucuk harf, diyakritiksiz)
_BASEMENT_WORDS = ("podrum", "suteren")
_NO_WINDOW_WORDS = ("bez prozora", "nema prozor", "bez prozor")
_DAILY_WORDS = ("na dan", "dnevno", "dnevni najam", "po danu", "kratkorocno")
_UNFURNISHED_WORDS = ("nenamesten", "prazan stan", "bez namestaja", "neopremljen")

# Arti puan sinyalleri
_BALCONY_WORDS = ("terasa", "terasom", "terase", "balkon", "balkonom", "lodja", "loda")
_LIGHT_WORDS = ("svetao", "svetla", "suncan", "prostran", "vazdusast", "lux")

_BELGRADE = "beograd"


@dataclass
class Evaluation:
    passed: bool
    score: int = 0
    reject_reason: str | None = None
    commute_minutes: int | None = None
    is_stretch: bool = False
    flags: list[str] = field(default_factory=list)


def _haystack(listing: Listing) -> str:
    return normalize_text(f"{listing.title} {listing.description}")


def _hard_filters(listing: Listing, text: str) -> str | None:
    """Elenme sebebini doner, elenmiyorsa None."""
    if listing.price_eur > config.PRICE_CEILING_EUR:
        return f"butce asildi ({listing.price_eur} EUR)"

    # Sehir bilinmiyorsa elemiyoruz - bazi kaynaklar bu alani vermiyor.
    city = normalize_text(listing.city)
    if city and _BELGRADE not in city:
        return f"Belgrad disi ({listing.city})"

    if any(word in text for word in _NO_WINDOW_WORDS):
        return "penceresiz"
    if any(word in text for word in _BASEMENT_WORDS):
        return "bodrum/suteren"
    if any(word in text for word in _DAILY_WORDS):
        return "gunluk/turistik kiralama"

    if listing.furnished is False or any(word in text for word in _UNFURNISHED_WORDS):
        return "mobilyasiz"
    return None


def _price_points(price: int) -> int:
    """400 EUR ve alti tam puan, 550'de sifira iner."""
    if price <= config.PRICE_TARGET_EUR:
        return 25
    span = config.PRICE_CEILING_EUR - config.PRICE_TARGET_EUR
    over = price - config.PRICE_TARGET_EUR
    return max(0, round(25 * (1 - over / span)))


def _commute_points(minutes: int | None) -> int:
    """10 dk ve alti tam puan, 45 dk'da sifir. Bilinmiyorsa orta puan -
    bilinmemek eleme sebebi degil, sadece belirsizlik."""
    if minutes is None:
        return 15
    if minutes <= 10:
        return 35
    return max(0, round(35 * (1 - (minutes - 10) / 35)))


def _place_points(listing: Listing) -> int:
    key = normalize_text(f"{listing.municipality} {listing.district}")
    if any(name in key for name in ("savski venac", "vracar", "stari grad", "vozdovac")):
        return 15
    if "novi beograd" in key:
        return 8
    return 3


def _m2_points(m2: int | None) -> int:
    if m2 is None:
        return 4
    if m2 < 18:
        return 0
    if m2 < 25:
        return 4
    return 7


def evaluate(listing: Listing) -> Evaluation:
    text = _haystack(listing)

    reason = _hard_filters(listing, text)
    if reason:
        return Evaluation(passed=False, reject_reason=reason)

    minutes = commute_minutes(listing)
    flags: list[str] = []

    score = (
        _commute_points(minutes)
        + _price_points(listing.price_eur)
        + _place_points(listing)
        + _m2_points(listing.m2)
    )

    if any(word in text for word in _BALCONY_WORDS):
        score += 10
        flags.append("balkon")
    if any(word in text for word in _LIGHT_WORDS):
        score += 8
        flags.append("aydinlik")
    if listing.is_agency is False:
        flags.append("dogrudan-ev-sahibi")
    if listing.furnished is None:
        flags.append("masa-dogrulanmali")

    return Evaluation(
        passed=True,
        score=min(100, score),
        commute_minutes=minutes,
        is_stretch=listing.price_eur > config.PRICE_SOFT_EUR,
        flags=flags,
    )
