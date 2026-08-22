"""Tek noktadan HTTP. Tum kaynaklar buradan gecer; UA ve timeout burada zorlanir."""
from __future__ import annotations

import subprocess
import time

import httpx

from . import config


class SourceFetchError(Exception):
    """Kaynak cekilemedi. Adaptor yakalar, pipeline dusmez."""


_HEADERS = {"User-Agent": config.USER_AGENT}

# Gelistirme sirasinda gozlendi: DNS cozumlemesi ara sira tek seferlik
# basarisiz oluyor ve hemen ardindan calisiyor. Tek gecici hata yuzunden
# bir tarama turunu kaybetmemek icin transport hatalarinda tekrar deniyoruz.
# HTTP durum kodu hatalari (4xx/5xx) tekrarlanmaz - onlar gercek cevaplardir.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 1.0

# 429/503 gecici yuk sinyalleridir - biraz bekleyip tekrar denemek dogru davranis.
# (403 bilerek burada DEGIL: halooglasi'nin 403'u gecici degildi, TLS parmak izi
# kaynakliydi ve get_text_via_curl ile cozuldu. 403'u burada tekrar denemek
# sadece 12 saniye bosa beklemeye yol aciyordu.)
_THROTTLE_CODES = {429, 503}
_THROTTLE_BACKOFF = 4.0


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    last_error: Exception | str | None = None

    for attempt in range(_MAX_ATTEMPTS):
        is_last = attempt == _MAX_ATTEMPTS - 1
        try:
            with httpx.Client(timeout=config.HTTP_TIMEOUT, follow_redirects=True) as client:
                response = client.request(method, url, headers=_HEADERS, **kwargs)
        except httpx.HTTPError as exc:
            last_error = exc
            if not is_last:
                time.sleep(_RETRY_BACKOFF * (attempt + 1))
            continue

        if response.status_code in _THROTTLE_CODES:
            last_error = f"HTTP {response.status_code}"
            if not is_last:
                time.sleep(_THROTTLE_BACKOFF * (attempt + 1))
            continue

        if response.status_code >= 400:
            raise SourceFetchError(f"{method} {url}: HTTP {response.status_code}")
        return response

    raise SourceFetchError(f"{method} {url}: {last_error}")


def get_json(url: str, params: dict | None = None) -> dict:
    try:
        return _request("GET", url, params=params).json()
    except ValueError as exc:
        raise SourceFetchError(f"GET {url}: gecersiz JSON") from exc


def post_json(url: str, payload: dict) -> dict:
    try:
        return _request("POST", url, json=payload).json()
    except ValueError as exc:
        raise SourceFetchError(f"POST {url}: gecersiz JSON") from exc


def get_text(url: str, params: dict | None = None) -> str:
    return _request("GET", url, params=params).text


def get_text_via_curl(url: str, params: dict | None = None) -> str:
    """halooglasi icin ayri tasima katmani.

    Neden: halooglasi httpx'ten gelen istekleri 403'luyor ama ayni URL'e ayni
    User-Agent ile curl'den istek atinca 200 donuyor. Sebebi tam olarak
    bilinmiyor; muhtemelen istemci parmak izi. Kendimizi yine dogru tanitiyoruz
    (ayni User-Agent), tarayici taklidi yapmiyoruz.

    ONEMLI - Actions'ta calismaz:
    2026-08-21'de GitHub Actions'tan olculdu: bes farkli curl varyanti (bizim UA,
    tarayici UA, ek basliklar, http1.1, tlsv1.2) ve hatta site ana sayfasi dahil
    HEPSI 403 dondu. Cikis IP'si 172.183.95.150 (Azure). Ayni komutlar ev
    baglantisindan 200 donuyor. Yani halooglasi veri merkezi IP bloklarini
    tamamen engelliyor - istemci tarafinda cozulecek bir sey degil ve kasitli
    bir engeli asmaya calismiyoruz.

    Sonuc: Actions kosularinda bu kaynak hata bildirir ve pipeline diger iki
    kaynakla devam eder. halooglasi'yi almak icin nobetci normal bir internet
    baglantisindan calistirilmali (bkz. scripts/yerel-kosu.ps1).
    """
    command = ["curl", "-s", "-S", "--compressed", "-m", str(int(config.HTTP_TIMEOUT * 3)),
               "-A", config.USER_AGENT, "-w", "\n%{http_code}"]
    if params:
        for key, value in params.items():
            command += ["--data-urlencode", f"{key}={value}"]
        command.append("--get")
    command.append(url)

    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceFetchError(f"curl {url}: {exc}") from exc

    if result.returncode != 0:
        raise SourceFetchError(f"curl {url}: cikis kodu {result.returncode} {result.stderr[:120]}")

    body, _, status = (result.stdout or "").rpartition("\n")
    if status.strip() != "200":
        raise SourceFetchError(f"curl {url}: HTTP {status.strip() or 'bilinmiyor'}")
    return body
