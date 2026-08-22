"""Gruba sabitlenecek mesaj taslagini gonderir.

Bildirimler ilan basina tek kart. Mesaj metni her ilanda ayni oldugu icin
her kartin altina eklenmiyor; bunun yerine gruba BIR KEZ gonderilip
sabitleniyor (Telegram: mesaja uzun bas -> Pin).

Sablonlari degistirdikten sonra bu betigi tekrar calistirip yeni mesaji
sabitlemek gerekiyor.

    python scripts/sabit-mesaj.py            # ev sahibi metni (varsayilan)
    python scripts/sabit-mesaj.py emlakci    # emlakci metni
    python scripts/sabit-mesaj.py --goster   # gondermeden ekrana bas
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from watcher import config, notify
from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.outreach import draft


def _ornek(is_agency: bool) -> ListingGroup:
    """Sablon artik ilana ozel alan kullanmiyor; bu sadece draft()'i cagirmak icin."""
    return ListingGroup(primary=Listing(
        source="-", source_id="-", url="-", title="-", price_eur=0, m2=None,
        rooms=None, furnished=None, lat=None, lng=None, address=None,
        municipality=None, published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=is_agency, city="Beograd",
    ))


def main(argv: list[str]) -> int:
    goster = "--goster" in argv
    kime = "emlakci" if "emlakci" in argv else "ev_sahibi"
    metin = draft(_ornek(is_agency=(kime == "emlakci")))

    baslik = "Emlakçıya" if kime == "emlakci" else "Ev sahibine"
    print(f"--- {baslik} ---\n{metin.serbian}\n\nTR:\n{metin.turkish}")

    if goster:
        return 0

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("\nHATA: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekli.")
        return 2

    notify.send_text(f"<b>Hazır mesaj: {baslik}</b>\nBunu sabitle, her ilanda kullan.")
    notify._post("sendMessage", notify._message(notify.format_draft(metin)))
    print("\nGruba gonderildi. Telegram'da mesaja uzun basip Pin ile sabitle.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
