"""Uzaktaki durum veritabanini cekip yereldekiyle birlestirir.

Ezmek yerine birlestiriyoruz: iki taraf da kendi gordugu ilanlari kaydediyor
(bulut isi halooglasi'yi goremiyor, yerel kosu goruyor). Biri digerini ezerse
kaybolan kayitlar tekrar "yeni" sayilir ve mukerrer bildirim gider.

Binary dosyayi PowerShell borusundan gecirmek bozuyor, bu yuzden `git show`
ciktisini burada ikili modda aliyoruz.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from watcher import config
from watcher.merge_state import merge
from watcher.store import Store

UZAK_YOL = "origin/master:state/listings.db"


def main() -> int:
    subprocess.run(["git", "fetch", "--quiet", "origin", "master"],
                   capture_output=True, timeout=120)

    sonuc = subprocess.run(["git", "show", UZAK_YOL], capture_output=True, timeout=120)
    if sonuc.returncode != 0 or not sonuc.stdout:
        print("  uzakta durum dosyasi yok, birlestirme atlandi")
        return 0

    gecici = os.path.join(tempfile.mkdtemp(), "uzak.db")
    with open(gecici, "wb") as handle:
        handle.write(sonuc.stdout)

    yerel = Store(config.DB_PATH)
    yerel.init_schema()

    try:
        eklenen, guncellenen = merge(config.DB_PATH, gecici)
    except Exception as exc:                      # bozuk/eksik uzak dosya
        print(f"  UYARI: birlestirilemedi ({exc}), yerel durum korundu")
        return 0
    finally:
        try:
            os.remove(gecici)
        except OSError:
            pass

    if eklenen or guncellenen:
        print(f"  uzaktan birlestirildi: +{eklenen} ilan, {guncellenen} durum")
    return 0


if __name__ == "__main__":
    sys.exit(main())
