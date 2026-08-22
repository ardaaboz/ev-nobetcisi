"""CityExpert adaptoru. Temiz JSON POST API'si; koordinat ve mobilya bilgisi guvenilir.

Not: sunucu tarafi `municipality` filtresi guvenilir calismiyor (Vracar isterken
Palilula donuyor), bu yuzden semt filtresi istemci tarafinda (score.py) koordinat
ve semt adi uzerinden yapilir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import config
from ..http import SourceFetchError, post_json
from ..models import Listing, SourceResult

SOURCE = "cityexpert"
API_URL = "https://cityexpert.rs/api/Search/"
LISTING_URL = "https://cityexpert.rs/en/s/{unique_id}"


def _payload(page_size: int) -> dict:
    return {
        "ptId": [1, 2],           # stan + kuca
        "cityId": 1,              # Beograd
        "rentOrSale": "r",
        "currentPage": 1,
        "resultsPerPage": page_size,
        "sort": "datedsc",        # en yeni once
        "minPrice": 100,
        "maxPrice": config.PRICE_CEILING_EUR,
    }


def _parse_location(raw: str | None) -> tuple[float | None, float | None]:
    """'44.80124, 20.47985' -> (44.80124, 20.47985)"""
    if not raw or "," not in raw:
        return None, None
    lat_s, _, lng_s = raw.partition(",")
    try:
        return float(lat_s.strip()), float(lng_s.strip())
    except ValueError:
        return None, None


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_one(item: dict) -> Listing:
    lat, lng = _parse_location(item.get("location"))
    unique_id = item["uniqueID"]
    published = item.get("firstPublished")
    street = item.get("street") or ""
    structure = item.get("structure")

    return Listing(
        source=SOURCE,
        source_id=str(unique_id),
        url=LISTING_URL.format(unique_id=unique_id),
        title=f"{structure or ''} {street}".strip(),
        price_eur=int(float(item["price"])),
        m2=int(item["size"]) if item.get("size") else None,
        rooms=_as_float(structure),
        furnished=bool(item.get("furnished")),
        lat=lat,
        lng=lng,
        address=street or None,
        municipality=item.get("municipality"),
        district=item.get("municipality"),  # CityExpert zaten opstina seviyesi veriyor
        city="Beograd",  # sorgu cityId=1 ile yapiliyor
        published_at=(
            datetime.fromisoformat(published.replace("Z", "+00:00"))
            if published else datetime.now(timezone.utc)
        ),
        image_url=None,  # coverPhoto CDN sablonu gerektiriyor, v1'de atlandi
        description=" ".join(item.get("furnishingArray") or []),
        is_agency=True,  # CityExpert bir ajans, tum ilanlari araciyla
    )


def parse(payload: dict) -> list[Listing]:
    """Tek bozuk kayit tum partiyi dusurmez; atlanir."""
    listings = []
    for item in payload.get("result") or []:
        try:
            listings.append(_parse_one(item))
        except (KeyError, TypeError, ValueError):
            continue
    return listings


def fetch(page_size: int = 40) -> SourceResult:
    try:
        payload = post_json(API_URL, _payload(page_size))
    except SourceFetchError as exc:
        return SourceResult(source=SOURCE, error=str(exc))
    return SourceResult(source=SOURCE, listings=parse(payload))
