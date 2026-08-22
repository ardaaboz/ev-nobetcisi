"""4zida adaptoru. Public JSON API, en yeni once siralanabiliyor.

Uyari: API tum Sirbistan'i kapsiyor (Kragujevac, Novi Sad dahil). Adaptor
bunlari elemez - `city` alanini doldurur ve Belgrad filtresi score.py'de
uygulanir. Boylece eleme mantigi tek yerde kalir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import config
from ..http import SourceFetchError, get_json
from ..models import Listing, SourceResult

SOURCE = "4zida"
API_URL = "https://api.4zida.rs/v6/search/apartments"
SITE_ROOT = "https://www.4zida.rs"

# 'semi' (yari mobilyali) True sayiliyor: yatak/masa bulunma ihtimali var,
# eleme yerine gostermeyi tercih ediyoruz.
_FURNISHED_MAP = {"yes": True, "semi": True, "no": False}


def _parse_one(item: dict) -> Listing:
    places = item.get("placeNames") or []
    created = item.get("createdAt")
    search_images = (item.get("image") or {}).get("search") or {}

    return Listing(
        source=SOURCE,
        source_id=str(item["id"]),
        url=f"{SITE_ROOT}{item['urlPath']}",
        title=item.get("title") or item.get("detailedTitle") or "",
        price_eur=int(float(item["price"])),
        m2=int(item["m2"]) if item.get("m2") else None,
        rooms=float(item["roomCount"]) if item.get("roomCount") else None,
        furnished=_FURNISHED_MAP.get(item.get("furnished")),
        lat=None,   # 4zida liste API'si koordinat vermiyor
        lng=None,
        address=item.get("safeAddress"),
        municipality=places[0] if places else None,
        # placeNames = ['Sava Centar', 'Novi Beograd', 'Beograd'] -> ortadaki opstina
        district=places[1] if len(places) > 2 else None,
        city=places[-1] if places else None,
        published_at=(
            datetime.fromisoformat(created) if created else datetime.now(timezone.utc)
        ),
        image_url=search_images.get("380x0_fill_0_webp"),
        description=item.get("description100") or "",
        is_agency=bool(item.get("agencyUrl")),
    )


def parse(payload: dict) -> list[Listing]:
    listings = []
    for item in payload.get("ads") or []:
        try:
            listings.append(_parse_one(item))
        except (KeyError, TypeError, ValueError):
            continue
    return listings


def fetch() -> SourceResult:
    params = {
        "for": "rent",
        "priceTo": config.PRICE_CEILING_EUR,
        "sort": "createdAtDesc",
    }
    try:
        payload = get_json(API_URL, params=params)
    except SourceFetchError as exc:
        return SourceResult(source=SOURCE, error=str(exc))
    return SourceResult(source=SOURCE, listings=parse(payload))
