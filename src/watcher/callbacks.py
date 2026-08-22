"""Telegram buton basislarini toplama.

Actions cron'u webhook tutamaz, bu yuzden her kosuda getUpdates ile son
kosudan beri gelen callback'ler cekilir. Telegram guncellemeleri 24 saat
sakliyor; 5 dakikalik cron icin fazlasiyla yeterli.

Offset state/telegram_offset.txt icinde tutulur ve db ile birlikte repoya
commit'lenir - yoksa her kosu ayni butonlari tekrar isler.
"""
from __future__ import annotations

import os

import httpx

from . import config
from .store import VALID_STATUSES, Store

OFFSET_PATH = "state/telegram_offset.txt"


def read_offset() -> int:
    try:
        with open(OFFSET_PATH, encoding="utf-8") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return 0


def write_offset(offset: int) -> None:
    parent = os.path.dirname(OFFSET_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(OFFSET_PATH, "w", encoding="utf-8") as handle:
        handle.write(str(offset))


def fetch_updates(offset: int) -> list[dict]:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            response = client.get(url, params={"offset": offset, "timeout": 0})
        if response.status_code >= 400:
            print(f"[callbacks] getUpdates HTTP {response.status_code}")
            return []
        return response.json().get("result", [])
    except (httpx.HTTPError, ValueError) as exc:
        print(f"[callbacks] getUpdates basarisiz: {exc}")
        return []


def apply_updates(store: Store, updates: list[dict]) -> int:
    """Uygulanan durum degisikligi sayisini doner. Bozuk payload sessizce atlanir."""
    applied = 0
    for update in updates:
        query = update.get("callback_query") or {}
        status, _, fingerprint = (query.get("data") or "").partition(":")
        if not fingerprint or status not in VALID_STATUSES:
            continue
        if not store.is_known(fingerprint):
            continue
        store.set_status(fingerprint, status)
        applied += 1
    return applied


def sync(store: Store) -> int:
    updates = fetch_updates(read_offset())
    applied = apply_updates(store, updates)
    if updates:
        write_offset(max(u["update_id"] for u in updates) + 1)
    return applied
