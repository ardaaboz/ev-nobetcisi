"""Ilk temas mesaji taslaklari (Sirpca + Turkce ceviri).

Metinler kodda DEGIL, templates/ altindaki duz metin dosyalarinda. Boylece
kullanici kod acmadan mesaji degistirebiliyor. Dosya bicimi ve kurallar:
templates/README.md

SPEC 11.2 KISITI - kalici karar:
Vergi, ev sahibinin mali durumu ve beli karton (prijava boravista) ILK MESAJDA
GECMEZ. Gerekce: ev sahibine "beyan etmedigini biliyorum" mesaji verir ve zaten
ilk temasta siradan gorunme hedefinin tersine calisir. Beli karton konusu ev gezildikten sonra ayrica ele alinir
(docs/kiralama-rehberi/beli-karton-notu.md). Bu kisit teste baglanmistir.

DOGRULUK KISITI:
Sablonlar dogru olmayan hicbir sey iddia etmemeli. "Sigara icmiyorum" ve
"pesin odeyebilirim" ifadeleri bilerek cikarildi: ilki dogru degil, ikincisi
belirsiz. Yuz yuze gorusmede aciga cikacak bir iddia, ilanı kazanmaktan
daha pahaliya mal olur.

USLUP:
Uzun tire (em dash) kullanilmiyor. Yapay zeka ciktisi izlenimi veriyor ve
metnin elle yazilmis gibi durmasi burada dogrudan ise yariyor.

Cinsiyet: Sirpcada sifatlar ve meslek adlari cekimleniyor (uredan/uredna,
Student/Studentkinja). Yanlis cekim metnin anadili olmayan biri tarafindan
yazildigini ilk cumlede ele verir.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config
from .dedupe import ListingGroup

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

# Cinsiyete gore cekimlenen sifatlar ve meslek adi
_FORMS = {
    "m": {"uredan": "uredan", "miran": "miran", "student": "Student"},
    "f": {"uredan": "uredna", "miran": "mirna", "student": "Studentkinja"},
}


class TemplateError(Exception):
    """Sablon okunamadi veya bilinmeyen yer tutucu iceriyor."""


@dataclass(frozen=True)
class Draft:
    serbian: str
    turkish: str


def _load(name: str) -> str:
    path = TEMPLATE_DIR / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TemplateError(f"sablon okunamadi: {path}") from exc


def _render(name: str, fields: dict) -> str:
    template = _load(name)
    try:
        return template.format(**fields)
    except KeyError as exc:
        raise TemplateError(
            f"{name}: bilinmeyen yer tutucu {exc}. "
            f"Kullanilabilirler: {', '.join(sorted(fields))}"
        ) from exc


def draft(group: ListingGroup, gender: str | None = None) -> Draft:
    listing = group.primary
    forms = _FORMS.get(gender or config.USER_GENDER, _FORMS["m"])

    fields = {
        "muni": listing.municipality or "Beograd",
        "price": listing.price_eur,
        "uredan_c": forms["uredan"].capitalize(),  # cumle basinda buyuk harf
        "miran": forms["miran"],
        "student": forms["student"],
    }

    # Dogrudan ev sahibine biraz daha sicak, emlakciya daha islevsel bir ton.
    stem = "ev_sahibi" if listing.is_agency is False else "emlakci"

    return Draft(
        serbian=_render(f"{stem}.sr.txt", fields),
        turkish=_render(f"{stem}.tr.txt", fields),
    )
