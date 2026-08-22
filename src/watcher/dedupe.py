"""Siteler arasi ayni daireyi tekillestirme.

Belgrad'da ayni daire tipik olarak 3-5 emlakcida birden listeleniyor.
Manuel aramada en cok vakit yiyen seylerden biri bu.

Iki asamali yaklasim:
  1) (fiyat/10, m2, semt) kaba anahtariyla grupla - ucuz on eleme
  2) Grup icinde baslik benzerligine bak - yanlis birlestirmeyi onler

Sadece bulanik eslesme pahali (O(n^2) tum ilanlar uzerinde), sadece kaba
anahtar ise ayni fiyat/m2'ye sahip farkli daireleri yanlis birlestirir.

Not: birlestirilen ilanlarin TUM linkleri saklaniyor. Bu bir avantaj -
ayni daireyi farkli emlakciya sormak, "verildi" cevabini dogrulamanin
bilinen yolu.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .models import Listing, normalize_text

TITLE_SIMILARITY_THRESHOLD = 85
# Adres daha guclu bir sinyal; esik biraz daha yuksek tutuluyor ki
# 'Njegoseva' ile 'Njegoseva 5' eslesirken 'Njegoseva' ile 'Njegoseva put' eslesmesin.
ADDRESS_SIMILARITY_THRESHOLD = 90


@dataclass
class ListingGroup:
    primary: Listing
    duplicates: list[Listing] = field(default_factory=list)

    @property
    def all_urls(self) -> list[str]:
        return [self.primary.url] + [d.url for d in self.duplicates]

    @property
    def sources(self) -> list[str]:
        return [self.primary.source] + [d.source for d in self.duplicates]


def _coarse_key(listing: Listing) -> tuple:
    """Kaba on eleme anahtari: sadece fiyat ve metrekare.

    Semt BILEREK yok. Kaynaklar semti farkli granulariteyle veriyor:
    CityExpert opstina ("Zvezdara"), 4zida ve halooglasi mahalle ("Banjica",
    "Karaburma"). Anahtara girdiginde ayni daire farkli kovalara dusuyor ve
    adres karsilastirmasi hic calismiyordu - canli veride 79 kovanin sifiri
    birden fazla kaynak iceriyordu, yani siteler arasi dedupe tamamen olu idi.

    Kova genisledigi icin daha cok bulanik karsilastirma yapiliyor, ama
    _is_same_flat adres/baslik esigi yanlis birlestirmeyi zaten engelliyor.
    """
    return (round(listing.price_eur / 10), listing.m2 or 0)


def _is_same_flat(a: Listing, b: Listing) -> bool:
    """Once adres, yoksa baslik.

    Canli veride basliklar kaynaga gore tamamen farkli bicimde geliyor:
    CityExpert '2.0 Njegoseva', 4zida 'Dvosoban stan u centru', halooglasi
    serbest metin. Baslik karsilastirmasi bu yuzden siteler arasi kopyalari
    hemen hic yakalamiyordu. Sokak adi ise ucunde de ayni alanda duruyor
    (4zida bazen kapi numarasi ekliyor, bulanik eslesme bunu tolere eder).
    """
    address_a, address_b = normalize_text(a.address), normalize_text(b.address)
    if address_a and address_b:
        return fuzz.token_set_ratio(address_a, address_b) >= ADDRESS_SIMILARITY_THRESHOLD

    return (
        fuzz.token_set_ratio(normalize_text(a.title), normalize_text(b.title))
        >= TITLE_SIMILARITY_THRESHOLD
    )


def _better_primary(a: Listing, b: Listing) -> Listing:
    """Dogrudan ev sahibi tercih edilir; esitlikte once yayinlanan."""
    if a.is_agency is False and b.is_agency is not False:
        return a
    if b.is_agency is False and a.is_agency is not False:
        return b
    return a if a.published_at <= b.published_at else b


def merge(listings: list[Listing]) -> list[ListingGroup]:
    buckets: dict[tuple, list[ListingGroup]] = {}

    for listing in listings:
        groups = buckets.setdefault(_coarse_key(listing), [])
        for group in groups:
            if _is_same_flat(group.primary, listing):
                winner = _better_primary(group.primary, listing)
                loser = listing if winner is group.primary else group.primary
                group.duplicates.append(loser)
                group.primary = winner
                break
        else:
            groups.append(ListingGroup(primary=listing))

    return [group for groups in buckets.values() for group in groups]
