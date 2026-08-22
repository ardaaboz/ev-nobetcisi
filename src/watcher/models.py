"""Tum kaynaklarin indirgendigi ortak veri modeli."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime


def normalize_text(value: str | None) -> str:
    """Diyakritikleri duzler, kucultur, bosluklari sadelestirir.

    Dedupe ve anahtar kelime aramasi icin; 'Vracar' ve 'Vracar' esit olmali.
    'd' harfi NFKD ile ayrismadigi icin ayrica elle degistiriliyor.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", stripped).strip().lower()


@dataclass(frozen=True)
class Listing:
    source: str
    source_id: str
    url: str
    title: str
    price_eur: int
    m2: int | None
    rooms: float | None
    furnished: bool | None
    lat: float | None
    lng: float | None
    address: str | None
    municipality: str | None
    published_at: datetime
    image_url: str | None
    description: str
    is_agency: bool | None
    city: str | None = None
    # Opstina (Vozdovac, Vracar...). `municipality` en ince taneli mahalle adini
    # tutar (Lekino brdo, Dorcol); ulasim tablosu opstina seviyesinde oldugu icin
    # geo.py once mahalleye, bulamazsa buraya bakar.
    district: str | None = None

    @property
    def fingerprint(self) -> str:
        """Kaynaktan bagimsiz kimlik. Ayni daire farkli sitede ayni degeri uretir.

        Fiyat 10'a, m2 tam sayiya yuvarlanir; kucuk ilan farkliliklari
        ayni daireyi ikiye bolmesin diye.
        """
        parts = [
            str(round(self.price_eur / 10)),
            str(self.m2 or 0),
            normalize_text(self.municipality),
        ]
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


@dataclass
class SourceResult:
    """Bir kaynagin tek kosudaki ciktisi. Hata pipeline'i dusurmez, burada tasinir."""
    source: str
    listings: list[Listing] = field(default_factory=list)
    error: str | None = None
