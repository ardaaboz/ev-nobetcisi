"""Telegram bildirimi.

SPEC 10: her ilan icin IKI ayri mesaj gonderilir.
  1) Ilan karti  - bilgiler + link + butonlar
  2) Hazir mesaj - Sirpca <pre> blogunda (Telegram tek dokunusla kopyalama
     dugmesi koyar ve sadece blok icini kopyalar), altinda duz metin Turkce ceviri

Ayri olmalarinin sebebi kopyalanabilirlik: ayni balonda olsalardi kullanici
taslagi kopyalarken ilan bilgilerini de alirdi.

Bildirim hatalari pipeline'i dusurmez - loglanir ve kosu devam eder. Bir
bildirimin gitmemesi kotu, ama tum taramanin durmasi cok daha kotu.
"""
from __future__ import annotations

import html as html_lib

import httpx

from . import config
from .dedupe import ListingGroup
from .outreach import Draft
from .score import Evaluation

API_ROOT = "https://api.telegram.org/bot{token}/{method}"


def _api(method: str) -> str:
    return API_ROOT.format(token=config.TELEGRAM_BOT_TOKEN, method=method)


def _escape(value: str | None) -> str:
    return html_lib.escape(value or "")


def format_card(group: ListingGroup, evaluation: Evaluation) -> str:
    listing = group.primary
    lines = []

    headline = f"<b>{listing.price_eur} EUR</b>"
    if evaluation.is_stretch:
        headline += " (esnek butce)"
    if listing.m2:
        headline += f" · {listing.m2} m2"
    if listing.municipality:
        headline += f" · {_escape(listing.municipality)}"
    lines.append(headline)

    if evaluation.commute_minutes is not None:
        lines.append(f"Fakulteye ~{evaluation.commute_minutes} dk")

    detail = f"Skor {evaluation.score}"
    if evaluation.flags:
        detail += " · " + " · ".join(_escape(flag) for flag in evaluation.flags)
    lines.append(detail)

    lines.extend(group.all_urls)
    return "\n".join(lines)


def format_draft(draft: Draft) -> str:
    """Sirpca <pre> icinde (kopyalanan sadece bu), Turkce ceviri disinda."""
    return f"<pre>{_escape(draft.serbian)}</pre>\n\nTR:\n{_escape(draft.turkish)}"


def _keyboard(fingerprint: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "Yazdim", "callback_data": f"contacted:{fingerprint}"},
            {"text": "Elendi", "callback_data": f"rejected:{fingerprint}"},
            {"text": "Favori", "callback_data": f"viewing:{fingerprint}"},
        ]]
    }


def _post(method: str, payload: dict) -> None:
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            response = client.post(_api(method), json=payload)
        if response.status_code >= 400:
            print(f"[notify] {method} HTTP {response.status_code}: {response.text[:200]}")
    except httpx.HTTPError as exc:
        print(f"[notify] {method} basarisiz: {exc}")


def _message(text: str, **extra) -> dict:
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    payload.update(extra)
    return payload


def send_text(text: str) -> None:
    _post("sendMessage", _message(text))


def send_listing(group: ListingGroup, evaluation: Evaluation) -> None:
    """Ilan basina TEK mesaj: kart.

    Mesaj taslagi bilerek gonderilmiyor. Metin her ilanda neredeyse ayni
    oldugu icin her kartin altina eklemek sohbeti sisiriyor ve asil bilgiyi
    (fiyat, semt, sure, link) gorunmez kiliyor. Taslak gruba bir kez
    sabitleniyor; oradan kopyalaniyor.

    format_draft hala duruyor: sabitlenecek metni uretmek icin kullaniliyor
    (scripts/sabit-mesaj.py).
    """
    _post("sendMessage", _message(
        format_card(group, evaluation),
        reply_markup=_keyboard(group.primary.fingerprint),
    ))
