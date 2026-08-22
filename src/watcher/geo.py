"""Fakulteye (Dr Subotica 8) ulasim suresi tahmini.

Iki katmanli:
  1) Koordinat varsa haversine mesafesinden yurume suresi (sadece CityExpert veriyor)
  2) Yoksa yer adi tablosu - once mahalle (municipality), sonra opstina (district)

Harici geocoding servisi bilerek kullanilmiyor: her kosuda 40+ adres geocode
etmek hem yavas, hem Nominatim'in kullanim politikasina aykiri olurdu.
Tahminler kaba ama siralama icin yeterli - kesin sure zaten Google Maps'te bakilir.
"""
from __future__ import annotations

import math

from . import config
from .models import Listing, normalize_text

WALK_KMH = 5.0
# Kus ucusu mesafeyi gercek yuruyus rotasina yaklastiran carpan.
ROUTE_FACTOR = 1.3

# Dr Subotica 8'e kabaca kapidan kapiya dakika (yurume + toplu tasima karisik).
# Anahtarlar normalize_text() formatinda: kucuk harf, diyakritiksiz.
# Hem opstina hem sik gecen mahalle adlari var; lookup once mahalleye bakiyor.
PLACE_MINUTES: dict[str, int] = {
    # opstinalar
    "savski venac": 8,
    "vracar": 14,
    "stari grad": 18,
    "vozdovac": 22,
    "zvezdara": 28,
    "palilula": 26,
    "cukarica": 28,
    "novi beograd": 30,
    "rakovica": 33,
    "zemun": 40,
    "surcin": 55,
    "grocka": 60,
    "mladenovac": 75,
    "obrenovac": 65,
    # sik gecen mahalleler
    "slavija": 12,
    "cvetni trg": 12,
    "kalenic pijaca": 15,
    "neimar": 16,
    "dorcol": 22,
    "kalemegdan": 22,
    "terazije": 15,
    "lekino brdo": 25,
    "konjarnik": 30,
    "mirijevo": 38,
    "banovo brdo": 30,
    "kumodraz": 35,
    "olimp": 30,
    "blok 45": 40,
    "bezanijska kosa": 38,
    # Buyuk opstinalarin dis mahalleleri. Bunlar olmadan opstina degerini miras
    # aliyorlardi ve sistematik olarak fazla iyimser cikiyorlardi: Borca
    # Palilula'dan 26 dk aliyordu ama Tuna'nin kuzeyinde, gercekte ~50 dk.
    "borca": 50,
    "krnjaca": 40,
    "karaburma": 26,
    "visnjica": 35,
    "banjica": 20,
    "pasino brdo": 24,
    "kumodraska": 26,
    "medakovic": 28,
    "zeleznik": 40,
    "zarkovo": 33,
    "cerak": 33,
    "resnik": 45,
    "batajnica": 55,
    "altina": 48,
    "kaludjerica": 50,
    "vinca": 50,
    "ripanj": 55,
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def _lookup(place: str | None) -> int | None:
    key = normalize_text(place)
    if not key:
        return None
    if key in PLACE_MINUTES:
        return PLACE_MINUTES[key]
    # 'Opstina Vozdovac' gibi onekli/ekli degerler icin kismi eslesme
    for name, minutes in PLACE_MINUTES.items():
        if name in key:
            return minutes
    return None


def commute_minutes(listing: Listing) -> int | None:
    """Fakulteye tahmini dakika. Bilinemiyorsa None."""
    if listing.lat is not None and listing.lng is not None:
        km = haversine_km(listing.lat, listing.lng, config.FACULTY_LAT, config.FACULTY_LNG)
        return max(1, round(km * ROUTE_FACTOR / WALK_KMH * 60))

    return _lookup(listing.municipality) or _lookup(listing.district)
