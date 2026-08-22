"""halooglasi adaptoru. En yuksek ilan hacmi burada.

Sema notu (2026-08-21'de canli dogrulandi): sayfada
`QuidditaEnvironment.serverListData` JSON blob'u var, ama Ads[] girdilerinde
Address / City / OtherFields / ImageURLs / ValidFrom hep null. Dolu olan tek
alanlar Id, Title, RelativeUrl, AdvertiserId. Gercek veri her ilanin `ListHTML`
alaninda HTML-escape edilmis parca halinde duruyor.

Akis: blob -> JSON -> her ListHTML'i unescape -> selectolax ile parse.

Parca yapisi:
  .central-feature                          -> fiyat, "400 €"
  .publish-date                             -> "21.08.2026."
  [data-field-name=oglasivac_nekretnine_s]  -> data-field-value="vlasnik" | "agencija"
  ul.subtitle-places > li                   -> ["Beograd", "Opstina Vozdovac",
                                                "Lekino brdo", "Gospodara Vucica"]
  ul.product-features > li                  -> deger + span.legend ("Kvadratura",
                                                "Broj soba", "Spratnost")
  .text-description-list                    -> aciklama ozeti
"""
from __future__ import annotations

import html as html_lib
import json
import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from .. import config
from ..http import SourceFetchError, get_text_via_curl
from ..models import Listing, SourceResult

SOURCE = "halooglasi"
SITE_ROOT = "https://www.halooglasi.com"
LIST_URL = f"{SITE_ROOT}/nekretnine/izdavanje-stanova/beograd"

_BLOB_RE = re.compile(r"QuidditaEnvironment\.serverListData\s*=\s*(\{.*?\});", re.S)
_NUMBER_RE = re.compile(r"\d[\d.,]*")
_OWNER_FIELD = "[data-field-name='oglasivac_nekretnine_s']"


def _text(node) -> str:
    return node.text(strip=True).replace("\xa0", " ") if node else ""


def _to_int(raw: str | None) -> int | None:
    """'400 €' -> 400 ; '1.250 €' -> 1250 ; '40 m2' -> 40 ; 'yok' -> None"""
    match = _NUMBER_RE.search(raw or "")
    if not match:
        return None
    cleaned = match.group(0).rstrip(".,").replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _to_float(raw: str | None) -> float | None:
    match = _NUMBER_RE.search(raw or "")
    if not match:
        return None
    try:
        return float(match.group(0).rstrip(".,").replace(",", "."))
    except ValueError:
        return None


def _parse_date(raw: str) -> datetime:
    """'21.08.2026.' -> datetime. Cozulemezse simdiki zaman (ilan yine gorulur)."""
    try:
        return datetime.strptime(raw.strip().rstrip("."), "%d.%m.%Y").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _features(tree) -> dict[str, str]:
    """product-features listesini {legend: deger} sozlugune cevirir.

    Pozisyona degil etikete gore okuyoruz - alan sirasi ilandan ilana degisebilir.
    """
    result = {}
    for item in tree.css("ul.product-features li"):
        legend_node = item.css_first("span.legend")
        if not legend_node:
            continue
        legend = _text(legend_node)
        whole = _text(item)
        value = whole[: whole.rfind(legend)] if legend in whole else whole
        result[legend.lower()] = value.strip()
    return result


# halooglasi yapisal mobilya alani vermiyor. Aciklama ozeti kisaltilmis oldugu
# icin ipucu her ilanda yok (canli olcum: 20 ilanin 7'sinde). Bulundugunda
# kullaniyoruz, bulunmadiginda None kalip "masa dogrulanmali" bayragi aliyor.
# DIKKAT: 'nenamesten' icinde 'namesten' geciyor, once olumsuz kontrol edilmeli.
_UNFURNISHED_HINTS = ("nenamesten", "nenamešten", "prazan", "neopremljen", "bez namestaja")
_FURNISHED_HINTS = ("namesten", "namešten", "opremljen", "nameštena", "namestena")


def _infer_furnished(title: str, description: str) -> bool | None:
    blob = f"{title} {description}".lower()
    if any(word in blob for word in _UNFURNISHED_HINTS):
        return False
    if any(word in blob for word in _FURNISHED_HINTS):
        return True
    return None


def _parse_fragment(ad: dict) -> Listing | None:
    fragment = ad.get("ListHTML")
    if not fragment:
        return None
    tree = HTMLParser(html_lib.unescape(fragment))

    price = _to_int(_text(tree.css_first(".central-feature")))
    if not price:
        return None  # fiyatsiz ilan ise yaramaz

    places = [_text(node) for node in tree.css("ul.subtitle-places li")]
    places = [p for p in places if p]

    features = _features(tree)

    description = _text(tree.css_first(".text-description-list"))

    owner_node = tree.css_first(_OWNER_FIELD)
    owner_value = (owner_node.attributes.get("data-field-value") or "").lower() if owner_node else ""

    relative = ad.get("RelativeUrl") or ""
    return Listing(
        source=SOURCE,
        source_id=str(ad["Id"]),
        url=f"{SITE_ROOT}{relative}",
        title=ad.get("Title") or _text(tree.css_first(".product-title")),
        price_eur=price,
        m2=_to_int(features.get("kvadratura")),
        rooms=_to_float(features.get("broj soba")),
        furnished=_infer_furnished(ad.get("Title") or "", description),
        lat=None,
        lng=None,
        # places = ['Beograd', 'Opstina Vozdovac', 'Lekino brdo', 'Gospodara Vucica']
        address=places[3] if len(places) > 3 else None,
        municipality=places[2] if len(places) > 2 else (places[1] if len(places) > 1 else None),
        district=places[1] if len(places) > 1 else None,
        city=places[0] if places else None,
        published_at=_parse_date(_text(tree.css_first(".publish-date"))),
        image_url=None,
        description=description,
        is_agency=(owner_value != "vlasnik") if owner_value else None,
    )


def parse(page_html: str) -> list[Listing]:
    match = _BLOB_RE.search(page_html)
    if not match:
        return []
    try:
        blob = json.loads(match.group(1))
    except ValueError:
        return []

    listings = []
    for ad in blob.get("Ads") or []:
        try:
            listing = _parse_fragment(ad)
        except (KeyError, TypeError, ValueError):
            continue
        if listing:
            listings.append(listing)
    return listings


def fetch() -> SourceResult:
    params = {
        "cena_d_to": config.PRICE_CEILING_EUR,
        "cena_d_unit": 4,   # EUR
        "sort": "D",        # en yeni once
    }
    try:
        page_html = get_text_via_curl(LIST_URL, params=params)
    except SourceFetchError as exc:
        return SourceResult(source=SOURCE, error=str(exc))
    return SourceResult(source=SOURCE, listings=parse(page_html))
