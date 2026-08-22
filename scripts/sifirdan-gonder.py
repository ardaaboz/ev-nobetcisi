"""Durumu sifirlayip su an esigi gecen TUM ilanlari tek seferde gonderir.

Ne zaman ise yarar: grup gecmisi temizlendikten sonra, elde ne varsa duzgun
bir liste halinde bastan gormek icin.

Normalde bos veritabani "ilk kosu" sayilir ve hicbir sey gonderilmez; burada
o koruma bilerek devre disi (force_notify). Kosu basina bildirim ust siniri
da bu islem icin kaldirilir, yoksa liste turlere bolunur.

    python scripts/sifirdan-gonder.py --kuru    # gondermeden ne olacagini goster
    python scripts/sifirdan-gonder.py           # gercekten gonder
"""
from __future__ import annotations

import sqlite3
import sys
import time

from watcher import config, notify
from watcher.pipeline import run
from watcher.sources import cityexpert, fourzida, halooglasi
from watcher.store import Store

SOURCES = [cityexpert.fetch, fourzida.fetch, halooglasi.fetch]


class YavasBildirici:
    """Gercek bildirici, ama mesajlar arasinda bekliyor.

    Telegram tek sohbete dakikada ~20 mesaj kabul ediyor. 25 ilani arka arkaya
    atarsak sonuncular 429 alip duser ve sessizce kaybolur. 3.5 saniye ara
    dakikada ~17 mesaj demek, sinirin altinda.
    """

    ARA = 3.5

    def __init__(self):
        self.sayi = 0

    def send_listing(self, group, evaluation) -> None:
        if self.sayi:
            time.sleep(self.ARA)
        self.sayi += 1
        print(f"  {self.sayi:>2}. {group.primary.price_eur}EUR "
              f"{group.primary.municipality} ({evaluation.score})")
        notify.send_listing(group, evaluation)

    def send_text(self, text: str) -> None:
        notify.send_text(text)


class KuruBildirici:
    """Gondermeden ekrana basar."""

    def __init__(self):
        self.sayi = 0

    def send_listing(self, group, evaluation) -> None:
        self.sayi += 1
        listing = group.primary
        sure = f"~{evaluation.commute_minutes}dk" if evaluation.commute_minutes else "?"
        print(f"  [{evaluation.score:3}] {listing.price_eur:>4}EUR "
              f"{str(listing.m2 or '?'):>3}m2 {sure:>6} "
              f"{(listing.municipality or '-')[:18]:<18} {listing.source}")

    def send_text(self, text: str) -> None:
        print(f"  [metin] {text}")


def _durumu_sifirla(store: Store) -> int:
    with sqlite3.connect(store.path) as connection:
        onceki = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        connection.execute("DELETE FROM listings")
        connection.execute("DELETE FROM outreach")
    return onceki


def main(argv: list[str]) -> int:
    kuru = "--kuru" in argv

    if not kuru and (not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID):
        print("HATA: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekli.")
        return 2

    store = Store(config.DB_PATH)
    store.init_schema()

    if kuru:
        # Kuru modda gercek veritabanina dokunmuyoruz; gecici bir kopya uzerinde
        # calisip "hicbiri bilinmiyor" durumunu taklit ediyoruz.
        import tempfile
        gecici = Store(tempfile.mkdtemp() + "/kuru.db")
        gecici.init_schema()
        store = gecici
        print("KURU MOD: hicbir sey gonderilmiyor, veritabani degismiyor\n")
    else:
        silinen = _durumu_sifirla(store)
        print(f"Durum sifirlandi ({silinen} kayit silindi)\n")

    # Ust siniri kaldir: amac tek seferde tam liste.
    config.MAX_NOTIFICATIONS_PER_RUN = 10_000

    bildirici = KuruBildirici() if kuru else YavasBildirici()
    report = run(store, SOURCES, bildirici, force_notify=True)

    print(f"\ncekilen={report.fetched} gecen={report.passed} "
          f"gonderilen={report.notified}")
    for hata in report.errors:
        print(f"UYARI: {hata}")

    if not kuru and report.notified:
        print(f"\n{report.notified} ilan gonderildi. Durumu repoya yazmak icin:")
        print("  git add state/ && git commit -m \"durum sifirlandi\" && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
