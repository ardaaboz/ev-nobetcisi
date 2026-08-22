"""Iki durum veritabanini birlestirir.

Neden gerekiyor: hem bulut isi hem yerel kosu ayni state/listings.db dosyasini
git uzerinden paylasiyor. Ikisi de kendi kopyasina yazip push ediyor, yani
klasik bir cakisma durumu. Binary dosyada git birlestirme yapamaz; biri
digerini ezer ve ezilen taraftaki kayitlar kaybolur. Kaybolan kayit "bu ilani
gonderdim" bilgisi demek, yani o ilan tekrar gonderilir.

Dogru davranis birlestirmek: veritabani ozunde bir "gorulmus ilanlar" kumesi,
iki tarafin birlesimi her zaman dogru cevap.

Durum (outreach) icin: 'new' disinda bir durum kullanici girdisidir
("Yazdim", "Elendi"), bu yuzden 'new' olan taraf digerine yenik duser.
"""
from __future__ import annotations

import sqlite3


def merge(hedef_yol: str, kaynak_yol: str) -> tuple[int, int]:
    """kaynak'taki kayitlari hedef'e ekler. (eklenen_ilan, guncellenen_durum) doner."""
    # `with sqlite3.connect(...)` islemi commit eder ama baglantiyi kapatmaz;
    # acik transaction icinde DETACH "database is locked" veriyor. Bu yuzden
    # baglantiyi elle yonetiyoruz: once commit, sonra detach, sonra kapat.
    connection = sqlite3.connect(hedef_yol)
    try:
        connection.execute("ATTACH DATABASE ? AS kaynak", (kaynak_yol,))
        try:
            onceki = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

            connection.execute(
                "INSERT OR IGNORE INTO listings SELECT * FROM kaynak.listings"
            )
            connection.execute(
                "INSERT OR IGNORE INTO outreach SELECT * FROM kaynak.outreach"
            )

            # Bizde 'new', karsida gercek bir durum varsa karsidakini al.
            guncellenen = connection.execute(
                """UPDATE outreach
                   SET status = (SELECT k.status FROM kaynak.outreach k
                                 WHERE k.fingerprint = outreach.fingerprint),
                       updated_at = (SELECT k.updated_at FROM kaynak.outreach k
                                     WHERE k.fingerprint = outreach.fingerprint)
                   WHERE status = 'new'
                     AND EXISTS (SELECT 1 FROM kaynak.outreach k
                                 WHERE k.fingerprint = outreach.fingerprint
                                   AND k.status != 'new')"""
            ).rowcount

            sonraki = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            connection.commit()
        finally:
            connection.execute("DETACH DATABASE kaynak")
    finally:
        connection.close()

    return sonraki - onceki, guncellenen
