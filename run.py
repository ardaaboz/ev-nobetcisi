"""Giris noktasi. GitHub Actions bunu calistirir.

Kullanim:
    python run.py            # normal kosu
    python run.py --dry-run  # Telegram'a hicbir sey gondermeden ne olacagini goster
"""
from __future__ import annotations

import sys

from watcher import callbacks, config, notify
from watcher.pipeline import run
from watcher.sources import cityexpert, fourzida, halooglasi
from watcher.store import Store

SOURCES = [cityexpert.fetch, fourzida.fetch, halooglasi.fetch]


class DryRunNotifier:
    """Gercek bildirim yerine terminale basar. Ayarlari dogrulamak icin."""

    def send_listing(self, group, evaluation, draft) -> None:
        print("\n" + notify.format_card(group, evaluation))
        print("-- taslak --")
        print(draft.serbian)

    def send_text(self, text: str) -> None:
        print(f"\n[metin] {text}")


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv

    if not dry_run and (not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID):
        print("HATA: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekli.")
        return 2

    store = Store(config.DB_PATH)
    store.init_schema()

    if not dry_run:
        applied = callbacks.sync(store)
        if applied:
            print(f"{applied} durum guncellemesi uygulandi")

    notifier = DryRunNotifier() if dry_run else notify
    report = run(store, SOURCES, notifier)

    print(
        f"cekilen={report.fetched} gecen={report.passed} "
        f"yeni={report.new} bildirilen={report.notified} sessiz={report.silent}"
    )
    for error in report.errors:
        print(f"UYARI: {error}")

    # Uc kaynagin ucu birden bos donduyse bu sessiz olumdur - haber ver.
    if len(report.errors) == len(SOURCES) and not report.silent and not dry_run:
        notify.send_text("UYARI: uc kaynak da sonuc dondurmedi. Semalar degismis olabilir.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
