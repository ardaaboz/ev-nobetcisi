# Belgrad Kiralık Ev Nöbetçisi - Implementasyon Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Belgrad'daki kiralık ilanları 3 kaynaktan 5 dakikada bir tarayıp, filtreleyip, tekilleştirip, uygun olanları hazır Sırpça mesaj taslağıyla birlikte Telegram'a düşüren bir nöbetçi kurmak.

**Architecture:** GitHub Actions cron'unda çalışan saf Python pipeline'ı. Kaynak adaptörleri → normalize → filtre/skor → dedupe → store → Telegram. Her aşama saf fonksiyon, bağımsız test edilebilir. Durum SQLite'ta, her koşuda repoya commit'lenir.

**Tech Stack:** Python 3.10.11, `httpx` (HTTP), `selectolax` (HTML parse), `rapidfuzz` (dedupe), `pytest`, `python-dotenv`.

**Spec:** `docs/superpowers/specs/2026-08-21-belgrade-rental-watcher-design.md`

## Global Constraints

- Python **3.10** hedefi. `X | None` tip sözdizimi kullanılabilir, `match` kullanılabilir. 3.11+ özellikleri (`tomllib`, `ExceptionGroup`) **kullanılmaz**.
- Fakülte referans koordinatı: **`44.7974, 20.4611`** (Dr Subotića 8, Savski Venac). Sabit olarak `config.py` içinde.
- Sert bütçe tavanı: **550 EUR**. 500 EUR üstü ilanlar `is_stretch=True` etiketiyle gösterilir, elenmez.
- Tüm HTTP istekleri `User-Agent: belgrade-rental-watcher/1.0 (personal use)` ve **10 sn timeout** ile yapılır. Kaynaklar arası istekler sıralı, aralarında **1 sn** bekleme.
- Hiçbir kaynak adaptörü exception fırlatarak pipeline'ı düşürmez - hata durumunda boş liste döner ve `SourceResult.error` doldurulur.
- Secret'lar **asla** repoya girmez. `.env` gitignored; CI'da `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` GitHub Actions secret'ı.
- Sırpça metinler Latin alfabesiyle yazılır (Kiril değil). Diyakritikler korunur: `š č ć ž đ`.
- Commit mesajları Türkçe, ASCII (Türkçe karakter kullanma - Windows git konsolunda bozuluyor).

---

### Task 1: Proje iskeleti ve `Listing` modeli

**Files:**
- Create: `pyproject.toml`
- Create: `src/watcher/__init__.py`
- Create: `src/watcher/config.py`
- Create: `src/watcher/models.py`
- Create: `tests/__init__.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: yok (ilk task)
- Produces: `Listing` dataclass (§6'daki alanlar), `SourceResult` dataclass, `config.FACULTY_LAT/FACULTY_LNG/PRICE_CEILING_EUR/PRICE_TARGET_EUR/USER_AGENT/HTTP_TIMEOUT`

- [ ] **Step 1: `pyproject.toml` yaz**

```toml
[project]
name = "belgrade-rental-watcher"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "httpx>=0.27",
    "selectolax>=0.3.21",
    "rapidfuzz>=3.9",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Failing test yaz**

`tests/test_models.py`:

```python
from datetime import datetime, timezone
from watcher.models import Listing


def test_listing_fingerprint_is_stable_across_sources():
    """Ayni daire farkli kaynakta ayni parmak izini uretmeli."""
    a = Listing(
        source="4zida", source_id="abc", url="https://x/1", title="Dvosoban stan",
        price_eur=450, m2=38, rooms=2.0, furnished=True,
        lat=44.80, lng=20.47, address="Njegoseva 5", municipality="Vracar",
        published_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        image_url=None, description="", is_agency=True,
    )
    b = Listing(
        source="halooglasi", source_id="999", url="https://y/2", title="Dvosoban stan",
        price_eur=450, m2=38, rooms=2.0, furnished=True,
        lat=44.80, lng=20.47, address="Njegoseva 5", municipality="Vracar",
        published_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        image_url=None, description="", is_agency=False,
    )
    assert a.fingerprint == b.fingerprint


def test_listing_fingerprint_differs_on_price():
    base = dict(
        source="4zida", source_id="abc", url="https://x/1", title="Dvosoban stan",
        m2=38, rooms=2.0, furnished=True, lat=44.80, lng=20.47,
        address="Njegoseva 5", municipality="Vracar",
        published_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        image_url=None, description="", is_agency=True,
    )
    assert Listing(price_eur=450, **base).fingerprint != Listing(price_eur=600, **base).fingerprint
```

- [ ] **Step 3: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher'`

- [ ] **Step 4: `src/watcher/config.py` yaz**

```python
"""Proje geneli sabitler. Ortam degiskenleri .env'den okunur."""
import os
from dotenv import load_dotenv

load_dotenv()

# Tip Fakultesi, Dr Suboticа 8, Savski Venac (Nominatim ile dogrulandi)
FACULTY_LAT = 44.7974
FACULTY_LNG = 20.4611

PRICE_TARGET_EUR = 400    # ideal butce
PRICE_SOFT_EUR = 500      # bu ustu "esnek" etiketi alir
PRICE_CEILING_EUR = 550   # bu ustu tamamen elenir

USER_AGENT = "belgrade-rental-watcher/1.0 (personal use)"
HTTP_TIMEOUT = 10.0
INTER_SOURCE_DELAY = 1.0

MAX_NOTIFICATIONS_PER_RUN = 8
SCORE_THRESHOLD = 45

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_PATH = os.getenv("DB_PATH", "state/listings.db")
```

- [ ] **Step 5: `src/watcher/models.py` yaz**

```python
"""Tum kaynaklarin indirgendigi ortak veri modeli."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime


def normalize_text(value: str | None) -> str:
    """Diyakritikleri duzler, kucultur, bosluklari sadelestirir.

    Dedupe ve anahtar kelime aramasi icin; 'Vracar' ve 'Vracar' esit olmali.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", stripped).strip().lower()


@dataclass(frozen=True)
class Listing:
    source: str
    source_id: str
    url: str
    title: str
    price_eur: int
    m2: int | None
    rooms: float | None
    furnished: bool | None
    lat: float | None
    lng: float | None
    address: str | None
    municipality: str | None
    published_at: datetime
    image_url: str | None
    description: str
    is_agency: bool | None

    @property
    def fingerprint(self) -> str:
        """Kaynaktan bagimsiz kimlik. Ayni daire farkli sitede ayni degeri uretir.

        Fiyat 10'a, m2 tam sayiya yuvarlanir; kucuk ilan farkliliklari
        ayni daireyi ikiye bolmesin diye.
        """
        parts = [
            str(round(self.price_eur / 10)),
            str(self.m2 or 0),
            normalize_text(self.municipality),
        ]
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


@dataclass
class SourceResult:
    """Bir kaynagin tek kosudaki ciktisi. Hata pipeline'i dusurmez, burada tasinir."""
    source: str
    listings: list[Listing] = field(default_factory=list)
    error: str | None = None
```

- [ ] **Step 6: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pip install -e ".[dev]" && python -m pytest tests/test_models.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src tests
git commit -m "feat: proje iskeleti, Listing modeli ve config sabitleri"
```

---

### Task 2: HTTP istemcisi ve kaynak adaptörü arayüzü

**Files:**
- Create: `src/watcher/http.py`
- Create: `src/watcher/sources/__init__.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Consumes: `config.USER_AGENT`, `config.HTTP_TIMEOUT`
- Produces: `http.get_json(url, params) -> dict`, `http.post_json(url, payload) -> dict`, `http.get_text(url, params) -> str`. Hepsi hata durumunda `SourceFetchError` fırlatır (adaptörler yakalar).

- [ ] **Step 1: Failing test yaz**

`tests/test_http.py`:

```python
import pytest
import httpx
from watcher.http import get_json, SourceFetchError


def test_get_json_returns_parsed_body(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    assert get_json("https://example.test/x") == {"ok": True}


def test_get_json_raises_on_http_error(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return httpx.Response(503, text="down", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_http.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.http'`

- [ ] **Step 3: `src/watcher/http.py` yaz**

```python
"""Tek noktadan HTTP. Tum kaynaklar buradan gecer; UA ve timeout burada zorlanir."""
from __future__ import annotations

import httpx

from . import config


class SourceFetchError(Exception):
    """Kaynak cekilemedi. Adaptor yakalar, pipeline dusmez."""


_HEADERS = {"User-Agent": config.USER_AGENT}


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT, follow_redirects=True) as client:
            response = client.request(method, url, headers=_HEADERS, **kwargs)
    except httpx.HTTPError as exc:
        raise SourceFetchError(f"{method} {url}: {exc}") from exc
    if response.status_code >= 400:
        raise SourceFetchError(f"{method} {url}: HTTP {response.status_code}")
    return response


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
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_http.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/http.py src/watcher/sources tests/test_http.py
git commit -m "feat: ortak HTTP istemcisi ve SourceFetchError"
```

---

### Task 3: CityExpert adaptörü

**Files:**
- Create: `src/watcher/sources/cityexpert.py`
- Create: `tests/fixtures/cityexpert_search.json`
- Test: `tests/test_cityexpert.py`

**Interfaces:**
- Consumes: `Listing`, `SourceResult`, `http.post_json`
- Produces: `cityexpert.fetch() -> SourceResult`, `cityexpert.parse(payload: dict) -> list[Listing]`

- [ ] **Step 1: Fixture'ı gerçek API'den al**

```bash
mkdir -p tests/fixtures
curl -s -X POST "https://cityexpert.rs/api/Search/" \
  -H "Content-Type: application/json" \
  -A "belgrade-rental-watcher/1.0 (personal use)" \
  -d '{"ptId":[1,2],"cityId":1,"rentOrSale":"r","currentPage":1,"resultsPerPage":20,"sort":"datedsc","minPrice":100,"maxPrice":550}' \
  -o tests/fixtures/cityexpert_search.json
python -c "import json;d=json.load(open('tests/fixtures/cityexpert_search.json',encoding='utf-8'));print(len(d['result']),'ilan')"
```

Beklenen: `20 ilan`

- [ ] **Step 2: Failing test yaz**

`tests/test_cityexpert.py`:

```python
import json
from pathlib import Path

from watcher.sources import cityexpert

FIXTURE = Path(__file__).parent / "fixtures" / "cityexpert_search.json"


def test_parse_extracts_listings():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    listings = cityexpert.parse(payload)
    assert len(listings) > 0, "fixture bos donmemeli - sema degismis olabilir"
    first = listings[0]
    assert first.source == "cityexpert"
    assert first.price_eur > 0
    assert first.url.startswith("https://cityexpert.rs/")
    assert first.published_at is not None


def test_parse_reads_coordinates():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    listings = cityexpert.parse(payload)
    with_coords = [x for x in listings if x.lat is not None]
    assert with_coords, "en az bir ilanda koordinat olmali"
    assert 44.6 < with_coords[0].lat < 45.0
    assert 20.2 < with_coords[0].lng < 20.7


def test_parse_survives_malformed_entry():
    """Tek bozuk kayit tum parti dusurmemeli."""
    payload = {"result": [{"uniqueID": "X", "price": "bozuk"}, ]}
    assert cityexpert.parse(payload) == []
```

- [ ] **Step 3: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_cityexpert.py -v`
Expected: FAIL - `ImportError: cannot import name 'cityexpert'`

- [ ] **Step 4: `src/watcher/sources/cityexpert.py` yaz**

```python
"""CityExpert adaptoru. Temiz JSON POST API'si; koordinat ve mobilya bilgisi guvenilir.

Not: sunucu tarafi `municipality` filtresi guvenilir calismiyor,
semt filtresi istemci tarafinda (score.py) koordinat uzerinden yapilir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import config
from ..http import SourceFetchError, post_json
from ..models import Listing, SourceResult

SOURCE = "cityexpert"
API_URL = "https://cityexpert.rs/api/Search/"
LISTING_URL = "https://cityexpert.rs/en/s/{unique_id}"


def _payload(page_size: int) -> dict:
    return {
        "ptId": [1, 2],           # stan + kuca
        "cityId": 1,              # Beograd
        "rentOrSale": "r",
        "currentPage": 1,
        "resultsPerPage": page_size,
        "sort": "datedsc",        # en yeni once
        "minPrice": 100,
        "maxPrice": config.PRICE_CEILING_EUR,
    }


def _parse_location(raw: str | None) -> tuple[float | None, float | None]:
    """'44.80124, 20.47985' -> (44.80124, 20.47985)"""
    if not raw or "," not in raw:
        return None, None
    lat_s, _, lng_s = raw.partition(",")
    try:
        return float(lat_s.strip()), float(lng_s.strip())
    except ValueError:
        return None, None


def _parse_one(item: dict) -> Listing:
    lat, lng = _parse_location(item.get("location"))
    unique_id = item["uniqueID"]
    published = item.get("firstPublished")
    return Listing(
        source=SOURCE,
        source_id=str(unique_id),
        url=LISTING_URL.format(unique_id=unique_id),
        title=f"{item.get('structure', '')} {item.get('street', '')}".strip(),
        price_eur=int(float(item["price"])),
        m2=int(item["size"]) if item.get("size") else None,
        rooms=float(item["structure"]) if _is_number(item.get("structure")) else None,
        furnished=bool(item.get("furnished")),
        lat=lat,
        lng=lng,
        address=item.get("street"),
        municipality=item.get("municipality"),
        published_at=(
            datetime.fromisoformat(published.replace("Z", "+00:00"))
            if published else datetime.now(timezone.utc)
        ),
        image_url=None,  # coverPhoto CDN sablonu gerektiriyor, v1'de atlandi
        description=" ".join(item.get("furnishingArray") or []),
        is_agency=True,  # CityExpert bir ajans, tum ilanlari araciyla
    )


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def parse(payload: dict) -> list[Listing]:
    """Tek bozuk kayit tum partiyi dusurmez; atlanir."""
    listings = []
    for item in payload.get("result") or []:
        try:
            listings.append(_parse_one(item))
        except (KeyError, TypeError, ValueError):
            continue
    return listings


def fetch(page_size: int = 40) -> SourceResult:
    try:
        payload = post_json(API_URL, _payload(page_size))
    except SourceFetchError as exc:
        return SourceResult(source=SOURCE, error=str(exc))
    return SourceResult(source=SOURCE, listings=parse(payload))
```

- [ ] **Step 5: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_cityexpert.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/watcher/sources/cityexpert.py tests/test_cityexpert.py tests/fixtures/cityexpert_search.json
git commit -m "feat: CityExpert kaynak adaptoru"
```

---

### Task 4: 4zida adaptörü

**Files:**
- Create: `src/watcher/sources/fourzida.py`
- Create: `tests/fixtures/fourzida_search.json`
- Test: `tests/test_fourzida.py`

**Interfaces:**
- Consumes: `Listing`, `SourceResult`, `http.get_json`
- Produces: `fourzida.fetch() -> SourceResult`, `fourzida.parse(payload: dict) -> list[Listing]`

- [ ] **Step 1: Fixture'ı gerçek API'den al**

```bash
curl -s "https://api.4zida.rs/v6/search/apartments?for=rent&priceTo=550&sort=createdAtDesc" \
  -A "belgrade-rental-watcher/1.0 (personal use)" \
  -o tests/fixtures/fourzida_search.json
python -c "import json;d=json.load(open('tests/fixtures/fourzida_search.json',encoding='utf-8'));print(len(d['ads']),'ilan')"
```

Beklenen: `20 ilan`

- [ ] **Step 2: Failing test yaz**

`tests/test_fourzida.py`:

```python
import json
from pathlib import Path

from watcher.sources import fourzida

FIXTURE = Path(__file__).parent / "fixtures" / "fourzida_search.json"


def test_parse_extracts_listings():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    listings = fourzida.parse(payload)
    assert len(listings) > 0, "fixture bos donmemeli - sema degismis olabilir"
    assert listings[0].source == "4zida"
    assert listings[0].url.startswith("https://www.4zida.rs/")


def test_parse_maps_furnished_enum():
    """4zida furnished alani string enum: yes / semi / no / eksik."""
    payload = {"ads": [
        {"id": "1", "price": 400, "m2": 30, "furnished": "yes",
         "placeNames": ["Vracar", "Beograd"], "urlPath": "/a/1",
         "createdAt": "2026-08-21T10:00:00+00:00", "title": "t"},
        {"id": "2", "price": 400, "m2": 30, "furnished": "no",
         "placeNames": ["Vracar", "Beograd"], "urlPath": "/a/2",
         "createdAt": "2026-08-21T10:00:00+00:00", "title": "t"},
        {"id": "3", "price": 400, "m2": 30,
         "placeNames": ["Vracar", "Beograd"], "urlPath": "/a/3",
         "createdAt": "2026-08-21T10:00:00+00:00", "title": "t"},
    ]}
    got = {x.source_id: x.furnished for x in fourzida.parse(payload)}
    assert got == {"1": True, "2": False, "3": None}


def test_parse_uses_last_place_name_as_city():
    """placeNames hiyerarsisi ['Centar', 'Gradske lokacije', 'Kragujevac'] seklinde:
    son eleman sehir, ilk eleman semt."""
    payload = {"ads": [
        {"id": "1", "price": 400, "m2": 30, "furnished": "yes",
         "placeNames": ["Sava Centar", "Novi Beograd", "Beograd"],
         "urlPath": "/a/1", "createdAt": "2026-08-21T10:00:00+00:00", "title": "t"},
    ]}
    listing = fourzida.parse(payload)[0]
    assert listing.city == "Beograd"
    assert listing.municipality == "Sava Centar"
```

- [ ] **Step 3: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_fourzida.py -v`
Expected: FAIL - `ImportError` ve `city` alanı yok

- [ ] **Step 4: `Listing`'e `city` alanı ekle**

`src/watcher/models.py` içinde `municipality` alanının hemen altına:

```python
    city: str | None = None
```

`city` varsayılanlı olduğu için mevcut çağrıları bozmaz. `models.py` içindeki diğer alanlar varsayılansız olduğundan `city` **en sona** eklenmeli:

```python
    is_agency: bool | None
    city: str | None = None
```

- [ ] **Step 5: `src/watcher/sources/fourzida.py` yaz**

```python
"""4zida adaptoru. Public JSON API, en yeni once siralanabiliyor.

Uyari: API tum Sirbistan'i kapsiyor (Kragujevac, Novi Sad dahil).
Belgrad filtresi placeNames uzerinden burada uygulanir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import config
from ..http import SourceFetchError, get_json
from ..models import Listing, SourceResult

SOURCE = "4zida"
API_URL = "https://api.4zida.rs/v6/search/apartments"
SITE_ROOT = "https://www.4zida.rs"

_FURNISHED_MAP = {"yes": True, "semi": True, "no": False}


def _parse_one(item: dict) -> Listing:
    places = item.get("placeNames") or []
    created = item.get("createdAt")
    image = item.get("image") or {}
    search_images = image.get("search") or {}
    return Listing(
        source=SOURCE,
        source_id=str(item["id"]),
        url=f"{SITE_ROOT}{item['urlPath']}",
        title=item.get("title") or item.get("detailedTitle") or "",
        price_eur=int(float(item["price"])),
        m2=int(item["m2"]) if item.get("m2") else None,
        rooms=float(item["roomCount"]) if item.get("roomCount") else None,
        furnished=_FURNISHED_MAP.get(item.get("furnished")),
        lat=None,   # 4zida liste API'si koordinat vermiyor
        lng=None,
        address=item.get("safeAddress"),
        municipality=places[0] if places else None,
        city=places[-1] if places else None,
        published_at=(
            datetime.fromisoformat(created) if created else datetime.now(timezone.utc)
        ),
        image_url=search_images.get("380x0_fill_0_webp"),
        description=item.get("description100") or "",
        is_agency=bool(item.get("agencyUrl")),
    )


def parse(payload: dict) -> list[Listing]:
    listings = []
    for item in payload.get("ads") or []:
        try:
            listings.append(_parse_one(item))
        except (KeyError, TypeError, ValueError):
            continue
    return listings


def fetch() -> SourceResult:
    params = {
        "for": "rent",
        "priceTo": config.PRICE_CEILING_EUR,
        "sort": "createdAtDesc",
    }
    try:
        payload = get_json(API_URL, params=params)
    except SourceFetchError as exc:
        return SourceResult(source=SOURCE, error=str(exc))
    return SourceResult(source=SOURCE, listings=parse(payload))
```

- [ ] **Step 6: Testleri çalıştır**

Run: `python -m pytest tests/test_fourzida.py tests/test_models.py -v`
Expected: hepsi passed (models testleri `city` eklendikten sonra da geçmeli)

- [ ] **Step 7: Commit**

```bash
git add src/watcher/sources/fourzida.py src/watcher/models.py tests/test_fourzida.py tests/fixtures/fourzida_search.json
git commit -m "feat: 4zida kaynak adaptoru ve Listing.city alani"
```

---

### Task 5: halooglasi adaptörü

**Files:**
- Create: `src/watcher/sources/halooglasi.py`
- Create: `tests/fixtures/halooglasi_list.html`
- Test: `tests/test_halooglasi.py`

**Interfaces:**
- Consumes: `Listing`, `SourceResult`, `http.get_text`
- Produces: `halooglasi.fetch() -> SourceResult`, `halooglasi.parse(html: str) -> list[Listing]`

**Kritik bağlam:** `serverListData` JSON blob'undaki `Ads[]` girdilerinde `Address`, `City`, `OtherFields`, `ValidFrom` **null**. Gerçek veri her ilanın `ListHTML` alanında HTML-escape edilmiş parça olarak. Akış: regex ile blob'u çıkar → JSON parse → her `ListHTML`'i `html.unescape` → selectolax ile parse.

- [ ] **Step 1: Fixture'ı gerçek siteden al**

```bash
curl -s -A "belgrade-rental-watcher/1.0 (personal use)" \
  "https://www.halooglasi.com/nekretnine/izdavanje-stanova/beograd?cena_d_to=550&cena_d_unit=4&sort=D" \
  -o tests/fixtures/halooglasi_list.html
python -c "import re;h=open('tests/fixtures/halooglasi_list.html',encoding='utf-8').read();print('blob var:',bool(re.search(r'serverListData',h)))"
```

Beklenen: `blob var: True`

- [ ] **Step 2: Failing test yaz**

`tests/test_halooglasi.py`:

```python
from pathlib import Path

from watcher.sources import halooglasi

FIXTURE = Path(__file__).parent / "fixtures" / "halooglasi_list.html"


def test_parse_extracts_listings():
    listings = halooglasi.parse(FIXTURE.read_text(encoding="utf-8"))
    assert len(listings) > 0, "fixture bos donmemeli - sema degismis olabilir"
    assert listings[0].source == "halooglasi"
    assert listings[0].price_eur > 0


def test_parse_reads_price_and_size():
    listings = halooglasi.parse(FIXTURE.read_text(encoding="utf-8"))
    priced = [x for x in listings if x.price_eur and x.m2]
    assert priced, "en az bir ilanda hem fiyat hem m2 olmali"
    assert all(50 <= x.price_eur <= 5000 for x in priced)
    assert all(5 <= x.m2 <= 500 for x in priced)


def test_parse_detects_direct_owner():
    """'.product-type' Vlasnik ise dogrudan ev sahibi, emlakci degil."""
    listings = halooglasi.parse(FIXTURE.read_text(encoding="utf-8"))
    assert any(x.is_agency is False for x in listings), "Vlasnik ilani bulunmali"


def test_parse_prefers_subtitle_places_over_title():
    """Basliklar guvenilmez: 'izdavanje Vracar' baslikli ilan Vozdovac'ta olabilir.
    Semt daima .subtitle-places zincirinden alinmali."""
    listings = halooglasi.parse(FIXTURE.read_text(encoding="utf-8"))
    located = [x for x in listings if x.municipality]
    assert located, "en az bir ilanda semt olmali"


def test_parse_returns_empty_on_missing_blob():
    assert halooglasi.parse("<html><body>hicbir sey</body></html>") == []
```

- [ ] **Step 3: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_halooglasi.py -v`
Expected: FAIL - `ImportError: cannot import name 'halooglasi'`

- [ ] **Step 4: `src/watcher/sources/halooglasi.py` yaz**

```python
"""halooglasi adaptoru. En yuksek ilan hacmi burada.

Sema notu: sayfada `QuidditaEnvironment.serverListData` JSON blob'u var, ama
Ads[] girdilerinde Address/City/OtherFields/ValidFrom hep null. Gercek veri her
ilanin `ListHTML` alaninda HTML-escape edilmis parca halinde. Bu yuzden:
blob -> JSON -> her ListHTML'i unescape -> selectolax ile parse.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from .. import config
from ..http import SourceFetchError, get_text
from ..models import Listing, SourceResult

SOURCE = "halooglasi"
SITE_ROOT = "https://www.halooglasi.com"
LIST_URL = f"{SITE_ROOT}/nekretnine/izdavanje-stanova/beograd"

_BLOB_RE = re.compile(r"QuidditaEnvironment\.serverListData\s*=\s*(\{.*?\});", re.S)
_DIGITS_RE = re.compile(r"[\d.,]+")


def _clean(node) -> str:
    return node.text(strip=True).replace("\xa0", " ") if node else ""


def _to_int(raw: str) -> int | None:
    """'400 €' -> 400 ; '1.250 €' -> 1250 ; '40 m2' -> 40"""
    match = _DIGITS_RE.search(raw or "")
    if not match:
        return None
    cleaned = match.group(0).replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _parse_date(raw: str) -> datetime:
    """'21.08.2026.' -> datetime"""
    try:
        return datetime.strptime(raw.strip().rstrip("."), "%d.%m.%Y").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _parse_fragment(ad: dict) -> Listing | None:
    fragment = ad.get("ListHTML")
    if not fragment:
        return None
    tree = HTMLParser(html_lib.unescape(fragment))

    price = _to_int(_clean(tree.css_first(".central-feature")))
    if not price:
        return None

    places = [_clean(n) for n in tree.css(".subtitle-places")]
    places = [p for p in places if p]

    features = [_clean(n) for n in tree.css(".product-features li")]
    m2 = _to_int(features[0]) if features else None

    owner_label = _clean(tree.css_first(".product-type"))
    description = _clean(tree.css_first(".text-description-list"))

    relative = ad.get("RelativeUrl") or ""
    return Listing(
        source=SOURCE,
        source_id=str(ad["Id"]),
        url=f"{SITE_ROOT}{relative}",
        title=ad.get("Title") or _clean(tree.css_first(".product-title")),
        price_eur=price,
        m2=m2,
        rooms=None,
        furnished=None,  # ilan metninden score.py cikarim yapar
        lat=None,
        lng=None,
        address=places[-1] if len(places) > 2 else None,
        # places = ['Beograd', 'Opstina Vozdovac', 'Lekino brdo', 'Gospodara Vucica']
        municipality=places[2] if len(places) > 2 else (places[1] if len(places) > 1 else None),
        city=places[0] if places else None,
        published_at=_parse_date(_clean(tree.css_first(".publish-date"))),
        image_url=None,
        description=description,
        is_agency=(owner_label.lower() != "vlasnik") if owner_label else None,
    )


def parse(page_html: str) -> list[Listing]:
    match = _BLOB_RE.search(page_html)
    if not match:
        return []
    try:
        blob = json.loads(match.group(1))
    except ValueError:
        return []

    listings = []
    for ad in blob.get("Ads") or []:
        try:
            listing = _parse_fragment(ad)
        except (KeyError, TypeError, ValueError):
            continue
        if listing:
            listings.append(listing)
    return listings


def fetch() -> SourceResult:
    params = {
        "cena_d_to": config.PRICE_CEILING_EUR,
        "cena_d_unit": 4,   # EUR
        "sort": "D",        # en yeni once
    }
    try:
        page_html = get_text(LIST_URL, params=params)
    except SourceFetchError as exc:
        return SourceResult(source=SOURCE, error=str(exc))
    return SourceResult(source=SOURCE, listings=parse(page_html))
```

- [ ] **Step 5: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_halooglasi.py -v`
Expected: 5 passed

Eğer `test_parse_reads_price_and_size` veya semt testi kırılırsa: fixture'daki gerçek `ListHTML` parçasını yazdırıp CSS seçicileri düzelt - ```bash
python -c "
import re,json,html
from selectolax.parser import HTMLParser
h=open('tests/fixtures/halooglasi_list.html',encoding='utf-8').read()
d=json.loads(re.search(r'QuidditaEnvironment\.serverListData\s*=\s*(\{.*?\});',h,re.S).group(1))
t=HTMLParser(html.unescape(d['Ads'][1]['ListHTML']))
for sel in ['.central-feature','.publish-date','.product-type','.subtitle-places','.product-features li']:
    print(sel,'->',[n.text(strip=True) for n in t.css(sel)])
"
```

- [ ] **Step 6: Commit**

```bash
git add src/watcher/sources/halooglasi.py tests/test_halooglasi.py tests/fixtures/halooglasi_list.html
git commit -m "feat: halooglasi adaptoru (ListHTML parcasi parse ediliyor)"
```

---

### Task 6: Mesafe ve ulaşım skoru

**Files:**
- Create: `src/watcher/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Consumes: `config.FACULTY_LAT`, `config.FACULTY_LNG`, `models.normalize_text`
- Produces: `geo.haversine_km(lat, lng, lat2, lng2) -> float`, `geo.commute_minutes(listing) -> int | None`, `geo.MUNICIPALITY_MINUTES: dict[str, int]`

**Tasarım kararı:** 4zida ve halooglasi koordinat vermiyor, sadece CityExpert veriyor. Bu yüzden iki katmanlı: koordinat varsa haversine'den yürüme süresi tahmini (5 km/sa), yoksa semt adından önceden hesaplanmış tablo. Harici geocoding API'si v1'de yok - her koşuda 40+ adres geocode etmek hem yavaş hem Nominatim'in kullanım politikasına aykırı.

- [ ] **Step 1: Failing test yaz**

`tests/test_geo.py`:

```python
from datetime import datetime, timezone

import pytest

from watcher import geo
from watcher.models import Listing


def _listing(**kwargs) -> Listing:
    base = dict(
        source="t", source_id="1", url="u", title="t", price_eur=400, m2=40,
        rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality=None, published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=False, city="Beograd",
    )
    base.update(kwargs)
    return Listing(**base)


def test_haversine_known_distance():
    """Fakulte -> Slavija yaklasik 1.1 km."""
    km = geo.haversine_km(44.7974, 20.4611, 44.8025, 20.4656)
    assert 0.4 < km < 1.2


def test_commute_from_coordinates():
    """Fakulteye cok yakin bir koordinat kisa sure vermeli."""
    minutes = geo.commute_minutes(_listing(lat=44.7980, lng=20.4620))
    assert minutes is not None
    assert minutes <= 5


def test_commute_falls_back_to_municipality_table():
    assert geo.commute_minutes(_listing(municipality="Vracar")) == geo.MUNICIPALITY_MINUTES["vracar"]


def test_commute_municipality_lookup_is_diacritic_insensitive():
    assert geo.commute_minutes(_listing(municipality="Vračar")) == geo.MUNICIPALITY_MINUTES["vracar"]


def test_commute_unknown_municipality_returns_none():
    assert geo.commute_minutes(_listing(municipality="Kragujevac Centar")) is None
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_geo.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.geo'`

- [ ] **Step 3: `src/watcher/geo.py` yaz**

```python
"""Fakulteye ulasim suresi tahmini.

Iki katmanli: koordinat varsa haversine'den yurume suresi, yoksa semt tablosu.
Harici geocoding v1'de yok - her kosuda 40+ adres geocode etmek hem yavas hem
Nominatim kullanim politikasina aykiri olurdu.
"""
from __future__ import annotations

import math

from . import config
from .models import Listing, normalize_text

WALK_KMH = 5.0

# Dr Suboticа 8'e kabaca kapidan kapiya dakika (yurume + toplu tasima karisik).
# Anahtarlar normalize_text() ciktisi formatinda: kucuk harf, diyakritiksiz.
MUNICIPALITY_MINUTES: dict[str, int] = {
    "savski venac": 8,
    "vracar": 14,
    "stari grad": 18,
    "vozdovac": 22,
    "lekino brdo": 25,
    "cukarica": 28,
    "novi beograd": 30,
    "zvezdara": 28,
    "palilula": 26,
    "rakovica": 33,
    "zemun": 40,
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def commute_minutes(listing: Listing) -> int | None:
    """Fakulteye tahmini dakika. Bilinemiyorsa None."""
    if listing.lat is not None and listing.lng is not None:
        km = haversine_km(listing.lat, listing.lng, config.FACULTY_LAT, config.FACULTY_LNG)
        # kus ucusu mesafeyi 1.3 ile carpip gercek yuruyus rotasina yaklastiriyoruz
        return max(1, round(km * 1.3 / WALK_KMH * 60))

    key = normalize_text(listing.municipality)
    if key in MUNICIPALITY_MINUTES:
        return MUNICIPALITY_MINUTES[key]

    # 'Opstina Vozdovac' gibi onekli degerler icin kismi eslesme
    for name, minutes in MUNICIPALITY_MINUTES.items():
        if name in key:
            return minutes
    return None
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_geo.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/geo.py tests/test_geo.py
git commit -m "feat: fakulteye ulasim suresi tahmini (haversine + semt tablosu)"
```

---

### Task 7: Filtre ve skorlama

**Files:**
- Create: `src/watcher/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: `Listing`, `geo.commute_minutes`, `config.PRICE_*`, `models.normalize_text`
- Produces: `score.evaluate(listing) -> Evaluation`, `Evaluation` dataclass (`passed: bool`, `reject_reason: str | None`, `score: int`, `commute_minutes: int | None`, `is_stretch: bool`, `flags: list[str]`)

- [ ] **Step 1: Failing test yaz**

`tests/test_score.py`:

```python
from datetime import datetime, timezone

from watcher.models import Listing
from watcher.score import evaluate


def _listing(**kwargs) -> Listing:
    base = dict(
        source="t", source_id="1", url="u", title="Stan", price_eur=400, m2=40,
        rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="namesten stan sa terasom", is_agency=False,
        city="Beograd",
    )
    base.update(kwargs)
    return Listing(**base)


def test_rejects_over_ceiling():
    result = evaluate(_listing(price_eur=700))
    assert result.passed is False
    assert "butce" in result.reject_reason


def test_rejects_basement():
    result = evaluate(_listing(description="lep suteren stan, bez prozora"))
    assert result.passed is False
    assert "bodrum" in result.reject_reason or "pencere" in result.reject_reason


def test_rejects_non_belgrade():
    result = evaluate(_listing(city="Novi Sad", municipality="Telep"))
    assert result.passed is False


def test_rejects_daily_rental():
    result = evaluate(_listing(description="izdajem stan na dan, dnevno"))
    assert result.passed is False


def test_rejects_unfurnished():
    result = evaluate(_listing(furnished=False, description="prazan nenamesten stan"))
    assert result.passed is False


def test_accepts_good_listing():
    result = evaluate(_listing(price_eur=380, municipality="Savski venac"))
    assert result.passed is True
    assert result.score > 60


def test_marks_stretch_above_soft_ceiling():
    result = evaluate(_listing(price_eur=530))
    assert result.passed is True
    assert result.is_stretch is True


def test_cheaper_and_closer_scores_higher():
    near = evaluate(_listing(price_eur=380, municipality="Savski venac"))
    far = evaluate(_listing(price_eur=520, municipality="Zemun"))
    assert near.score > far.score


def test_flags_balcony():
    result = evaluate(_listing(description="svetao stan sa velikom terasom"))
    assert "balkon" in result.flags


def test_flags_unverified_desk_when_furnishing_unknown():
    result = evaluate(_listing(furnished=None, description="stan u centru"))
    assert "masa-dogrulanmali" in result.flags
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_score.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.score'`

- [ ] **Step 3: `src/watcher/score.py` yaz**

```python
"""Sert filtreler ve yumusak skor.

Tasarim ilkesi: yanlis negatif (iyi ilani elemek) yanlis pozitiften
(fazladan ilan gostermek) daha pahali. Esikler bu yuzden gevsek.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .geo import commute_minutes
from .models import Listing, normalize_text

# Sert eleme anahtar kelimeleri (normalize edilmis, diyakritiksiz)
_BASEMENT_WORDS = ("podrum", "suteren")
_NO_WINDOW_WORDS = ("bez prozora", "nema prozor")
_DAILY_WORDS = ("na dan", "dnevno", "dnevni najam", "po danu")
_UNFURNISHED_WORDS = ("nenamesten", "prazan stan", "bez namestaja")

# Artı puan sinyalleri
_BALCONY_WORDS = ("terasa", "terasom", "balkon", "balkonom", "lodja", "loda")
_LIGHT_WORDS = ("svetao", "svetla", "suncan", "prostran", "vazdusast", "lux")

_BELGRADE = "beograd"


@dataclass
class Evaluation:
    passed: bool
    score: int = 0
    reject_reason: str | None = None
    commute_minutes: int | None = None
    is_stretch: bool = False
    flags: list[str] = field(default_factory=list)


def _haystack(listing: Listing) -> str:
    return normalize_text(f"{listing.title} {listing.description}")


def _hard_filters(listing: Listing, text: str) -> str | None:
    """Elenme sebebini doner, elenmiyorsa None."""
    if listing.price_eur > config.PRICE_CEILING_EUR:
        return f"butce asildi ({listing.price_eur} EUR)"

    city = normalize_text(listing.city)
    if city and _BELGRADE not in city:
        return f"Belgrad disi ({listing.city})"

    if any(word in text for word in _NO_WINDOW_WORDS):
        return "penceresiz"
    if any(word in text for word in _BASEMENT_WORDS):
        return "bodrum/suteren"
    if any(word in text for word in _DAILY_WORDS):
        return "gunluk/turistik kiralama"

    if listing.furnished is False or any(w in text for w in _UNFURNISHED_WORDS):
        return "mobilyasiz"
    return None


def _price_points(price: int) -> int:
    """400 EUR ve alti tam puan, 550'de sifira iner."""
    if price <= config.PRICE_TARGET_EUR:
        return 25
    span = config.PRICE_CEILING_EUR - config.PRICE_TARGET_EUR
    over = price - config.PRICE_TARGET_EUR
    return max(0, round(25 * (1 - over / span)))


def _commute_points(minutes: int | None) -> int:
    """10 dk ve alti tam puan, 45 dk'da sifir. Bilinmiyorsa orta puan."""
    if minutes is None:
        return 15
    if minutes <= 10:
        return 35
    return max(0, round(35 * (1 - (minutes - 10) / 35)))


def _municipality_points(listing: Listing) -> int:
    key = normalize_text(listing.municipality)
    preferred = ("savski venac", "vracar", "stari grad", "vozdovac")
    if any(name in key for name in preferred):
        return 15
    if "novi beograd" in key:
        return 8
    return 3


def _m2_points(m2: int | None) -> int:
    if m2 is None:
        return 4
    if m2 < 18:
        return 0
    if m2 < 25:
        return 4
    return 7


def evaluate(listing: Listing) -> Evaluation:
    text = _haystack(listing)

    reason = _hard_filters(listing, text)
    if reason:
        return Evaluation(passed=False, reject_reason=reason)

    minutes = commute_minutes(listing)
    flags: list[str] = []

    score = (
        _commute_points(minutes)
        + _price_points(listing.price_eur)
        + _municipality_points(listing)
        + _m2_points(listing.m2)
    )

    if any(word in text for word in _BALCONY_WORDS):
        score += 10
        flags.append("balkon")
    if any(word in text for word in _LIGHT_WORDS):
        score += 8
        flags.append("aydinlik")
    if listing.is_agency is False:
        flags.append("dogrudan-ev-sahibi")
    if listing.furnished is None:
        flags.append("masa-dogrulanmali")

    return Evaluation(
        passed=True,
        score=min(100, score),
        commute_minutes=minutes,
        is_stretch=listing.price_eur > config.PRICE_SOFT_EUR,
        flags=flags,
    )
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_score.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/score.py tests/test_score.py
git commit -m "feat: sert filtreler ve yumusak skorlama"
```

---

### Task 8: Dedupe

**Files:**
- Create: `src/watcher/dedupe.py`
- Test: `tests/test_dedupe.py`

**Interfaces:**
- Consumes: `Listing`, `models.normalize_text`, `rapidfuzz`
- Produces: `dedupe.merge(listings) -> list[ListingGroup]`, `ListingGroup` dataclass (`primary: Listing`, `duplicates: list[Listing]`, `all_urls: list[str]`)

- [ ] **Step 1: Failing test yaz**

`tests/test_dedupe.py`:

```python
from datetime import datetime, timezone

from watcher.dedupe import merge
from watcher.models import Listing


def _listing(source, sid, price=450, m2=38, muni="Vracar", title="Dvosoban stan Njegoseva"):
    return Listing(
        source=source, source_id=sid, url=f"https://{source}/{sid}", title=title,
        price_eur=price, m2=m2, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality=muni, published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    )


def test_merges_same_flat_across_sources():
    groups = merge([_listing("4zida", "1"), _listing("halooglasi", "2")])
    assert len(groups) == 1
    assert len(groups[0].duplicates) == 1
    assert len(groups[0].all_urls) == 2


def test_keeps_different_flats_separate():
    groups = merge([_listing("4zida", "1", price=450), _listing("4zida", "2", price=900, m2=80)])
    assert len(groups) == 2


def test_similar_price_different_title_not_merged():
    """Ayni fiyat ve m2 ama tamamen farkli adres - birlestirmemeli."""
    a = _listing("4zida", "1", title="Dvosoban stan Njegoseva")
    b = _listing("4zida", "2", title="Garsonjera Bulevar Kralja Aleksandra")
    groups = merge([a, b])
    assert len(groups) == 2


def test_primary_prefers_direct_owner():
    """Dogrudan ev sahibi ilani birincil secilmeli - pazarlik sansi daha yuksek."""
    agency = _listing("4zida", "1")
    owner = Listing(**{**agency.__dict__, "source": "halooglasi", "source_id": "2",
                       "url": "https://halooglasi/2", "is_agency": False})
    groups = merge([agency, owner])
    assert len(groups) == 1
    assert groups[0].primary.is_agency is False
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_dedupe.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.dedupe'`

- [ ] **Step 3: `src/watcher/dedupe.py` yaz**

```python
"""Siteler arasi ayni daireyi tekillestirme.

Belgrad'da ayni daire tipik olarak 3-5 emlakcida birden listeleniyor.
Manuel aramada en cok vakit yiyen seylerden biri bu.

Yaklasim: once (fiyat/10, m2, semt) kaba anahtariyla grupla, sonra grup
icinde baslik benzerligine bak. Iki asamali cunku sadece bulanik eslesme
pahali, sadece kaba anahtar ise farkli daireleri yanlis birlestirir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .models import Listing, normalize_text

TITLE_SIMILARITY_THRESHOLD = 85


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
    return (
        round(listing.price_eur / 10),
        listing.m2 or 0,
        normalize_text(listing.municipality),
    )


def _is_same_flat(a: Listing, b: Listing) -> bool:
    similarity = fuzz.token_set_ratio(normalize_text(a.title), normalize_text(b.title))
    return similarity >= TITLE_SIMILARITY_THRESHOLD


def _better_primary(a: Listing, b: Listing) -> Listing:
    """Dogrudan ev sahibi ilani tercih edilir - pazarlik ve iletisim sansi daha iyi."""
    if a.is_agency is False and b.is_agency is not False:
        return a
    if b.is_agency is False and a.is_agency is not False:
        return b
    return a if a.published_at <= b.published_at else b


def merge(listings: list[Listing]) -> list[ListingGroup]:
    buckets: dict[tuple, list[ListingGroup]] = {}

    for listing in listings:
        key = _coarse_key(listing)
        groups = buckets.setdefault(key, [])
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
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_dedupe.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/dedupe.py tests/test_dedupe.py
git commit -m "feat: siteler arasi ilan tekillestirme"
```

---

### Task 9: Sırpça mesaj şablonları ve Türkçe çeviri

**Files:**
- Create: `src/watcher/outreach.py`
- Test: `tests/test_outreach.py`

**Interfaces:**
- Consumes: `Listing`, `dedupe.ListingGroup`
- Produces: `outreach.draft(group) -> Draft`, `Draft` dataclass (`serbian: str`, `turkish: str`)

**Spec kısıtı (§11.2):** Vergi konusu, ev sahibinin mali durumu, para teklifi **hiçbir şablonda geçmez**. Beli karton ilk mesajda **açılmaz**. Sırpça sade tutulur - kullanıcının Sırpçası temel seviye, konuşamayacağı bir metin göndermek yüz yüze görüşmede tutarsızlık yaratır.

- [ ] **Step 1: Failing test yaz**

`tests/test_outreach.py`:

```python
from datetime import datetime, timezone

from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.outreach import draft

FORBIDDEN = ["porez", "poresk", "prijav", "beli karton", "boravist", "vergi"]


def _group(is_agency=True, price=450, muni="Vracar") -> ListingGroup:
    return ListingGroup(primary=Listing(
        source="t", source_id="1", url="u", title="Dvosoban stan", price_eur=price,
        m2=38, rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality=muni, published_at=datetime.now(timezone.utc), image_url=None,
        description="", is_agency=is_agency, city="Beograd",
    ))


def test_draft_has_both_languages():
    result = draft(_group())
    assert result.serbian.strip()
    assert result.turkish.strip()


def test_draft_never_mentions_tax_or_registration():
    """Spec 11.2: vergi ve beli karton ilk mesajda kesinlikle gecmez."""
    for is_agency in (True, False):
        result = draft(_group(is_agency=is_agency))
        blob = (result.serbian + " " + result.turkish).lower()
        for word in FORBIDDEN:
            assert word not in blob, f"yasakli kelime bulundu: {word}"


def test_draft_mentions_medical_faculty():
    assert "medicin" in draft(_group()).serbian.lower()


def test_agency_and_owner_drafts_differ():
    assert draft(_group(is_agency=True)).serbian != draft(_group(is_agency=False)).serbian


def test_draft_is_short():
    """Uzun ve savunmaci metin yanlis sinyal verir."""
    assert len(draft(_group()).serbian.split()) < 90
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_outreach.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.outreach'`

- [ ] **Step 3: `src/watcher/outreach.py` yaz**

```python
"""Ilk temas mesaji taslaklari.

Spec 11.2 kisiti: vergi, ev sahibinin mali durumu ve beli karton (prijava
boravista) ILK MESAJDA GECMEZ. Bu konu ev gezildikten sonra, sozlesme
imzalanmadan once ayrica ele alinir - docs/ altindaki notta.

Ton: kisa, sakin, siradan. Asiri aciklama ve savunmaci dil yanlis sinyal verir.
Sirpca sade tutulur; kullanicinin Sirpcasi temel seviye ve yuz yuze
gorusmede yazdigi metnin seviyesini tutturamazsa tutarsizlik olur.
"""
from __future__ import annotations

from dataclasses import dataclass

from .dedupe import ListingGroup

_AGENCY_SR = """Poštovanje,

zanima me stan koji ste oglasili ({muni}, {price} EUR). Da li je još uvek slobodan?

Student sam Medicinskog fakulteta u Beogradu. Tražim stan na duži period, uredan sam i miran, ne pušim. Plaćam redovno, a mogu i unapred za više meseci.

Da li bih mogao da ga pogledam ovih dana?

Hvala unapred."""

_AGENCY_TR = """Merhaba,

İlan verdiğiniz daireyle ilgileniyorum ({muni}, {price} EUR). Hâlâ müsait mi?

Belgrad Tıp Fakültesi öğrencisiyim. Uzun süreli kiracı arıyorum, düzenli ve sessizim, sigara kullanmıyorum. Ödemelerimi düzenli yaparım, istenirse birkaç ay peşin de ödeyebilirim.

Bu günlerde görebilir miyim?

Şimdiden teşekkürler."""

_OWNER_SR = """Poštovanje,

video sam Vaš oglas za stan u {muni} ({price} EUR) i mnogo mi se dopada. Da li je još slobodan?

Student sam Medicinskog fakulteta. Miran sam i uredan, ne pušim, i tražim stan na duži period - ne selim se često. Plaćanje je uvek na vreme, a mogu i unapred ako Vam tako više odgovara.

Bilo bi mi drago da ga pogledam kad Vama odgovara.

Srdačan pozdrav."""

_OWNER_TR = """Merhaba,

{muni} bölgesindeki daire ilanınızı gördüm ({price} EUR), çok beğendim. Hâlâ müsait mi?

Tıp Fakültesi öğrencisiyim. Sessiz ve düzenliyim, sigara kullanmıyorum ve uzun süreli kalacak bir yer arıyorum - sık taşınmıyorum. Ödemeler her zaman zamanında olur, sizin için uygunsa peşin de ödeyebilirim.

Size uygun bir zamanda daireyi görmek isterim.

Saygılarımla."""


@dataclass(frozen=True)
class Draft:
    serbian: str
    turkish: str


def draft(group: ListingGroup) -> Draft:
    listing = group.primary
    fields = {
        "muni": listing.municipality or "Beograd",
        "price": listing.price_eur,
    }
    # Dogrudan ev sahibine biraz daha sicak, emlakciya daha islevsel bir ton.
    if listing.is_agency is False:
        return Draft(serbian=_OWNER_SR.format(**fields), turkish=_OWNER_TR.format(**fields))
    return Draft(serbian=_AGENCY_SR.format(**fields), turkish=_AGENCY_TR.format(**fields))
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_outreach.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/outreach.py tests/test_outreach.py
git commit -m "feat: Sirpca mesaj taslaklari ve Turkce cevirileri"
```

---

### Task 10: SQLite durum deposu

**Files:**
- Create: `src/watcher/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `Listing`, `dedupe.ListingGroup`, `score.Evaluation`
- Produces: `store.Store(path)` sınıfı; metotlar: `init_schema()`, `is_known(fingerprint) -> bool`, `record(group, evaluation)`, `mark_notified(fingerprint)`, `set_status(fingerprint, status)`, `count()`, `is_first_run() -> bool`

- [ ] **Step 1: Failing test yaz**

`tests/test_store.py`:

```python
from datetime import datetime, timezone

import pytest

from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.score import Evaluation
from watcher.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    s.init_schema()
    return s


def _group(sid="1", price=450) -> ListingGroup:
    return ListingGroup(primary=Listing(
        source="t", source_id=sid, url=f"https://x/{sid}", title="Stan",
        price_eur=price, m2=38, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    ))


def test_new_store_is_first_run(store):
    assert store.is_first_run() is True


def test_recorded_listing_becomes_known(store):
    group = _group()
    assert store.is_known(group.primary.fingerprint) is False
    store.record(group, Evaluation(passed=True, score=70))
    assert store.is_known(group.primary.fingerprint) is True
    assert store.is_first_run() is False


def test_record_is_idempotent(store):
    group = _group()
    store.record(group, Evaluation(passed=True, score=70))
    store.record(group, Evaluation(passed=True, score=70))
    assert store.count() == 1


def test_status_transitions(store):
    group = _group()
    store.record(group, Evaluation(passed=True, score=70))
    fingerprint = group.primary.fingerprint
    assert store.get_status(fingerprint) == "new"
    store.mark_notified(fingerprint)
    assert store.get_status(fingerprint) == "notified"
    store.set_status(fingerprint, "contacted")
    assert store.get_status(fingerprint) == "contacted"


def test_set_status_rejects_unknown_value(store):
    group = _group()
    store.record(group, Evaluation(passed=True, score=70))
    with pytest.raises(ValueError):
        store.set_status(group.primary.fingerprint, "uydurma")
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.store'`

- [ ] **Step 3: `src/watcher/store.py` yaz**

```python
"""SQLite durum deposu.

GitHub Actions'ta kalici disk yok; bu dosya her kosu sonunda repoya
commit'lenir (bkz. .github/workflows/watch.yml).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from .dedupe import ListingGroup
from .score import Evaluation

VALID_STATUSES = {"new", "notified", "contacted", "replied", "viewing", "rejected", "dead"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    fingerprint   TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    url           TEXT NOT NULL,
    all_urls      TEXT NOT NULL,
    title         TEXT,
    price_eur     INTEGER NOT NULL,
    m2            INTEGER,
    municipality  TEXT,
    published_at  TEXT,
    first_seen_at TEXT NOT NULL,
    score         INTEGER NOT NULL,
    commute_min   INTEGER,
    flags         TEXT
);

CREATE TABLE IF NOT EXISTS outreach (
    fingerprint TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'new',
    updated_at  TEXT NOT NULL,
    note        TEXT
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def is_first_run(self) -> bool:
        """Ilk kosuda gecmis ilanlarla telefonu bombalamamak icin sessiz mod tetiklenir."""
        return self.count() == 0

    def count(self) -> int:
        with self._connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

    def is_known(self, fingerprint: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM listings WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return row is not None

    def record(self, group: ListingGroup, evaluation: Evaluation) -> None:
        listing = group.primary
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO listings
                   (fingerprint, source, source_id, url, all_urls, title, price_eur,
                    m2, municipality, published_at, first_seen_at, score, commute_min, flags)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    listing.fingerprint, listing.source, listing.source_id, listing.url,
                    json.dumps(group.all_urls), listing.title, listing.price_eur,
                    listing.m2, listing.municipality, listing.published_at.isoformat(),
                    now, evaluation.score, evaluation.commute_minutes,
                    json.dumps(evaluation.flags),
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO outreach (fingerprint, status, updated_at) VALUES (?,?,?)",
                (listing.fingerprint, "new", now),
            )

    def get_status(self, fingerprint: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM outreach WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return row["status"] if row else None

    def set_status(self, fingerprint: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"gecersiz durum: {status}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE outreach SET status = ?, updated_at = ? WHERE fingerprint = ?",
                (status, datetime.now(timezone.utc).isoformat(), fingerprint),
            )

    def mark_notified(self, fingerprint: str) -> None:
        self.set_status(fingerprint, "notified")
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_store.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/store.py tests/test_store.py
git commit -m "feat: SQLite durum deposu ve temas durumu takibi"
```

---

### Task 11: Telegram bildirimi (iki mesajlı format)

**Files:**
- Create: `src/watcher/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `dedupe.ListingGroup`, `score.Evaluation`, `outreach.Draft`, `config.TELEGRAM_*`
- Produces: `notify.format_card(group, evaluation) -> str`, `notify.format_draft(draft) -> str`, `notify.send_listing(group, evaluation, draft) -> None`, `notify.send_text(text) -> None`

**Spec kısıtı (§10):** İki ayrı mesaj. Kart ve taslak aynı balonda **olmamalı** - kopyalarken istenmeyen metin de alınır. Taslak `<pre>` bloğunda (Telegram tek dokunuşla kopyalama düğmesi koyar), Türkçe çeviri bloğun **altında** düz metin.

- [ ] **Step 1: Failing test yaz**

`tests/test_notify.py`:

```python
from datetime import datetime, timezone

from watcher import notify
from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.outreach import Draft
from watcher.score import Evaluation


def _group(**kwargs) -> ListingGroup:
    base = dict(
        source="4zida", source_id="1", url="https://x/1", title="Dvosoban stan",
        price_eur=450, m2=38, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    )
    base.update(kwargs)
    return ListingGroup(primary=Listing(**base))


def test_card_contains_key_facts():
    card = notify.format_card(_group(), Evaluation(passed=True, score=82, commute_minutes=14))
    assert "450" in card
    assert "38" in card
    assert "Vracar" in card
    assert "14" in card
    assert "82" in card
    assert "https://x/1" in card


def test_card_marks_stretch_price():
    card = notify.format_card(
        _group(price_eur=530), Evaluation(passed=True, score=60, is_stretch=True)
    )
    assert "esnek" in card.lower()


def test_card_lists_all_urls_when_duplicated():
    group = _group()
    group.duplicates.append(_group(source="halooglasi", source_id="2").primary)
    card = notify.format_card(group, Evaluation(passed=True, score=70))
    assert "https://x/1" in card
    assert "https://halooglasi/2" in card or "2" in card


def test_draft_message_wraps_serbian_in_pre_block():
    """Sirpca metin <pre> icinde olmali - Telegram kopyalama dugmesi koyuyor."""
    message = notify.format_draft(Draft(serbian="Postovanje, zanima me stan.", turkish="Merhaba."))
    assert message.startswith("<pre>")
    assert "Postovanje, zanima me stan." in message
    assert message.index("</pre>") < message.index("Merhaba.")


def test_draft_message_escapes_html_in_serbian():
    message = notify.format_draft(Draft(serbian="a < b & c", turkish="x"))
    assert "&lt;" in message and "&amp;" in message
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_notify.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.notify'`

- [ ] **Step 3: `src/watcher/notify.py` yaz**

```python
"""Telegram bildirimi.

Spec 10: her ilan icin IKI mesaj gonderilir.
  1) Ilan karti (bilgiler + link + butonlar)
  2) Hazir mesaj: Sirpca <pre> blogunda (tek dokunusla kopyalanir),
     altinda duz metin Turkce cevirisi.

Ayri olmalarinin sebebi kopyalanabilirlik: ayni balonda olsalar kullanici
taslagi kopyalarken ilan bilgilerini de alir.
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


def format_card(group: ListingGroup, evaluation: Evaluation) -> str:
    listing = group.primary
    lines = []

    price_line = f"<b>{listing.price_eur} EUR</b>"
    if evaluation.is_stretch:
        price_line += " (esnek butce)"
    if listing.m2:
        price_line += f" · {listing.m2} m2"
    if listing.municipality:
        price_line += f" · {html_lib.escape(listing.municipality)}"
    lines.append(price_line)

    if evaluation.commute_minutes is not None:
        lines.append(f"Fakulteye ~{evaluation.commute_minutes} dk")

    detail = f"Skor {evaluation.score}"
    if evaluation.flags:
        detail += " · " + " · ".join(evaluation.flags)
    lines.append(detail)

    for url in group.all_urls:
        lines.append(url)

    return "\n".join(lines)


def format_draft(draft: Draft) -> str:
    """Sirpca <pre> icinde (kopyalanan sadece bu), Turkce disinda."""
    serbian = html_lib.escape(draft.serbian)
    turkish = html_lib.escape(draft.turkish)
    return f"<pre>{serbian}</pre>\n\nTR:\n{turkish}"


def _keyboard(fingerprint: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "Yazdim", "callback_data": f"contacted:{fingerprint}"},
            {"text": "Elendi", "callback_data": f"rejected:{fingerprint}"},
            {"text": "Favori", "callback_data": f"viewing:{fingerprint}"},
        ]]
    }


def _post(method: str, payload: dict) -> None:
    """Bildirim hatasi pipeline'i dusurmez - loglanir, kosu devam eder."""
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            response = client.post(_api(method), json=payload)
        if response.status_code >= 400:
            print(f"[notify] {method} HTTP {response.status_code}: {response.text[:200]}")
    except httpx.HTTPError as exc:
        print(f"[notify] {method} basarisiz: {exc}")


def send_text(text: str) -> None:
    _post("sendMessage", {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })


def send_listing(group: ListingGroup, evaluation: Evaluation, draft: Draft) -> None:
    _post("sendMessage", {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": format_card(group, evaluation),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": _keyboard(group.primary.fingerprint),
    })
    _post("sendMessage", {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": format_draft(draft),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_notify.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/notify.py tests/test_notify.py
git commit -m "feat: Telegram bildirimi - kart ve kopyalanabilir taslak ayri mesajlarda"
```

---

### Task 12: Buton geri bildirimlerini toplama

**Files:**
- Create: `src/watcher/callbacks.py`
- Test: `tests/test_callbacks.py`

**Interfaces:**
- Consumes: `store.Store`, `config.TELEGRAM_BOT_TOKEN`
- Produces: `callbacks.apply_updates(store, updates) -> int`, `callbacks.fetch_updates(offset) -> list[dict]`, `callbacks.OFFSET_PATH`

**Bağlam:** Actions cron'u webhook tutamaz. Her koşuda `getUpdates` ile son koşudan beri gelen callback'ler toplanır (Telegram güncellemeleri 24 saat saklar). Offset `state/telegram_offset.txt` içinde tutulur ve state ile birlikte commit'lenir.

- [ ] **Step 1: Failing test yaz**

`tests/test_callbacks.py`:

```python
from datetime import datetime, timezone

import pytest

from watcher.callbacks import apply_updates
from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.score import Evaluation
from watcher.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init_schema()
    return s


def _record(store) -> str:
    group = ListingGroup(primary=Listing(
        source="t", source_id="1", url="u", title="Stan", price_eur=450, m2=38,
        rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    ))
    store.record(group, Evaluation(passed=True, score=70))
    return group.primary.fingerprint


def test_apply_updates_sets_status(store):
    fingerprint = _record(store)
    updates = [{"update_id": 1, "callback_query": {"data": f"contacted:{fingerprint}"}}]
    assert apply_updates(store, updates) == 1
    assert store.get_status(fingerprint) == "contacted"


def test_apply_updates_ignores_unknown_fingerprint(store):
    updates = [{"update_id": 1, "callback_query": {"data": "contacted:yokboyle"}}]
    assert apply_updates(store, updates) == 0


def test_apply_updates_ignores_malformed_payload(store):
    updates = [
        {"update_id": 1, "callback_query": {"data": "bozuk"}},
        {"update_id": 2, "message": {"text": "merhaba"}},
        {"update_id": 3, "callback_query": {"data": "uydurma:abc"}},
    ]
    assert apply_updates(store, updates) == 0
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_callbacks.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.callbacks'`

- [ ] **Step 3: `src/watcher/callbacks.py` yaz**

```python
"""Telegram buton basislarini toplama.

Actions cron'u webhook tutamaz, bu yuzden her kosuda getUpdates ile
son kosudan beri gelen callback'ler cekilir. Telegram guncellemeleri
24 saat sakliyor, 5 dakikalik cron icin fazlasiyla yeterli.
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
    os.makedirs(os.path.dirname(OFFSET_PATH), exist_ok=True)
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
    """Uygulanan durum degisikligi sayisini doner."""
    applied = 0
    for update in updates:
        query = update.get("callback_query") or {}
        data = query.get("data") or ""
        status, _, fingerprint = data.partition(":")
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
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `python -m pytest tests/test_callbacks.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/watcher/callbacks.py tests/test_callbacks.py
git commit -m "feat: getUpdates ile buton geri bildirimlerini toplama"
```

---

### Task 13: Pipeline birleştirme ve sağlık kontrolü

**Files:**
- Create: `src/watcher/pipeline.py`
- Create: `run.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: tüm önceki modüller
- Produces: `pipeline.run(store, sources, notifier) -> RunReport`, `RunReport` dataclass (`fetched: int`, `passed: int`, `new: int`, `notified: int`, `errors: list[str]`, `silent: bool`)

- [ ] **Step 1: Failing test yaz**

`tests/test_pipeline.py`:

```python
from datetime import datetime, timezone

import pytest

from watcher.models import Listing, SourceResult
from watcher.pipeline import run
from watcher.store import Store


class FakeNotifier:
    def __init__(self):
        self.listings = []
        self.texts = []

    def send_listing(self, group, evaluation, draft):
        self.listings.append((group, evaluation, draft))

    def send_text(self, text):
        self.texts.append(text)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init_schema()
    return s


def _listing(sid="1", price=400, muni="Vracar", city="Beograd", **kwargs):
    base = dict(
        source="4zida", source_id=sid, url=f"https://x/{sid}", title=f"Stan {sid}",
        price_eur=price, m2=40, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality=muni, published_at=datetime.now(timezone.utc),
        image_url=None, description="namesten", is_agency=True, city=city,
    )
    base.update(kwargs)
    return Listing(**base)


def test_first_run_is_silent(store):
    notifier = FakeNotifier()
    source = lambda: SourceResult(source="4zida", listings=[_listing()])
    report = run(store, [source], notifier)
    assert report.silent is True
    assert report.notified == 0
    assert notifier.listings == []
    assert store.count() == 1


def test_second_run_notifies_new_listings(store):
    notifier = FakeNotifier()
    run(store, [lambda: SourceResult("4zida", [_listing("1")])], notifier)
    report = run(store, [lambda: SourceResult("4zida", [_listing("2", price=420)])], notifier)
    assert report.silent is False
    assert report.notified == 1
    assert len(notifier.listings) == 1


def test_known_listing_not_renotified(store):
    notifier = FakeNotifier()
    source = lambda: SourceResult("4zida", [_listing("1")])
    run(store, [source], notifier)
    run(store, [source], notifier)
    assert notifier.listings == []


def test_rejected_listings_are_not_recorded(store):
    notifier = FakeNotifier()
    run(store, [lambda: SourceResult("4zida", [_listing("1")])], notifier)
    report = run(store, [lambda: SourceResult(
        "4zida", [_listing("2", price=900, description="suteren")])], notifier)
    assert report.passed == 0
    assert notifier.listings == []


def test_source_error_is_reported_not_raised(store):
    notifier = FakeNotifier()
    report = run(store, [lambda: SourceResult("4zida", [], error="HTTP 503")], notifier)
    assert "HTTP 503" in report.errors[0]


def test_notification_cap_is_respected(store, monkeypatch):
    from watcher import config
    monkeypatch.setattr(config, "MAX_NOTIFICATIONS_PER_RUN", 2)
    notifier = FakeNotifier()
    run(store, [lambda: SourceResult("4zida", [_listing("seed")])], notifier)
    many = [_listing(str(i), price=380 + i, m2=40 + i) for i in range(6)]
    report = run(store, [lambda: SourceResult("4zida", many)], notifier)
    assert report.notified == 2
    assert len(notifier.texts) == 1, "kalanlar icin ozet mesaji gitmeli"
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'watcher.pipeline'`

- [ ] **Step 3: `src/watcher/pipeline.py` yaz**

```python
"""Pipeline birlestirme: fetch -> filtre/skor -> dedupe -> store -> bildir."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from . import config
from .dedupe import merge
from .models import SourceResult
from .outreach import draft as make_draft
from .score import evaluate
from .store import Store


class Notifier(Protocol):
    def send_listing(self, group, evaluation, draft) -> None: ...
    def send_text(self, text: str) -> None: ...


@dataclass
class RunReport:
    fetched: int = 0
    passed: int = 0
    new: int = 0
    notified: int = 0
    silent: bool = False
    errors: list[str] = field(default_factory=list)


def run(store: Store, sources: list[Callable[[], SourceResult]], notifier: Notifier) -> RunReport:
    report = RunReport()
    silent = store.is_first_run()
    report.silent = silent

    all_listings = []
    for index, fetch in enumerate(sources):
        if index:
            time.sleep(config.INTER_SOURCE_DELAY)
        result = fetch()
        if result.error:
            report.errors.append(f"{result.source}: {result.error}")
        elif not result.listings:
            report.errors.append(f"{result.source}: sonuc bos - sema degismis olabilir")
        all_listings.extend(result.listings)

    report.fetched = len(all_listings)

    evaluated = []
    for group in merge(all_listings):
        evaluation = evaluate(group.primary)
        if evaluation.passed and evaluation.score >= config.SCORE_THRESHOLD:
            evaluated.append((group, evaluation))

    report.passed = len(evaluated)
    evaluated.sort(key=lambda pair: pair[1].score, reverse=True)

    fresh = [(g, e) for g, e in evaluated if not store.is_known(g.primary.fingerprint)]
    report.new = len(fresh)

    for group, evaluation in fresh:
        store.record(group, evaluation)

    if silent:
        return report

    cap = config.MAX_NOTIFICATIONS_PER_RUN
    for group, evaluation in fresh[:cap]:
        notifier.send_listing(group, evaluation, make_draft(group))
        store.mark_notified(group.primary.fingerprint)
        report.notified += 1

    overflow = len(fresh) - cap
    if overflow > 0:
        notifier.send_text(f"+{overflow} ilan daha eslesti, bir sonraki kosuda gelecek.")

    return report
```

- [ ] **Step 4: `run.py` (giriş noktası) yaz**

```python
"""Giris noktasi. GitHub Actions bunu calistirir."""
import sys

from watcher import callbacks, config, notify
from watcher.pipeline import run
from watcher.sources import cityexpert, fourzida, halooglasi
from watcher.store import Store


def main() -> int:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("HATA: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekli.")
        return 2

    store = Store(config.DB_PATH)
    store.init_schema()

    applied = callbacks.sync(store)
    if applied:
        print(f"{applied} durum guncellemesi uygulandi")

    report = run(store, [cityexpert.fetch, fourzida.fetch, halooglasi.fetch], notify)

    print(
        f"cekilen={report.fetched} gecen={report.passed} "
        f"yeni={report.new} bildirilen={report.notified} sessiz={report.silent}"
    )
    for error in report.errors:
        print(f"UYARI: {error}")

    # Uc kaynagin ucu birden bos donduyse bu sessiz olum demektir - haber ver.
    if len(report.errors) == 3 and not report.silent:
        notify.send_text("UYARI: uc kaynak da sonuc dondurmedi. Semalar degismis olabilir.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Tüm testleri çalıştır**

Run: `python -m pytest -v`
Expected: hepsi passed

- [ ] **Step 6: Commit**

```bash
git add src/watcher/pipeline.py run.py tests/test_pipeline.py
git commit -m "feat: pipeline birlestirme, giris noktasi ve saglik kontrolu"
```

---

### Task 14: Canlı duman testi ve ilk gerçek koşu

**Files:**
- Create: `scripts/smoke.py`

**Interfaces:**
- Consumes: tüm kaynak adaptörleri
- Produces: elle çalıştırılan doğrulama betiği (CI'da çalışmaz)

- [ ] **Step 1: `scripts/smoke.py` yaz**

```python
"""Canli duman testi. CI'da CALISMAZ - elle calistirilir.

Amac: kaynaklarin hala ayakta ve semalarinin bozulmamis oldugunu dogrulamak.
"""
import sys

sys.path.insert(0, "src")

from watcher.dedupe import merge
from watcher.outreach import draft
from watcher.score import evaluate
from watcher.sources import cityexpert, fourzida, halooglasi


def main() -> int:
    all_listings = []
    for module in (cityexpert, fourzida, halooglasi):
        result = module.fetch()
        status = result.error or f"{len(result.listings)} ilan"
        print(f"{result.source:12} -> {status}")
        all_listings.extend(result.listings)

    groups = merge(all_listings)
    print(f"\ntoplam {len(all_listings)} ilan -> {len(groups)} tekil daire")

    passing = [(g, e) for g in groups if (e := evaluate(g.primary)).passed]
    passing.sort(key=lambda pair: pair[1].score, reverse=True)
    print(f"filtreden gecen: {len(passing)}\n")

    for group, evaluation in passing[:5]:
        listing = group.primary
        print(f"[{evaluation.score:3}] {listing.price_eur} EUR · {listing.m2} m2 · "
              f"{listing.municipality} · ~{evaluation.commute_minutes} dk · {listing.url}")

    if passing:
        print("\n--- ornek taslak ---")
        print(draft(passing[0][0]).serbian)

    return 0 if any(g for g in groups) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Duman testini çalıştır**

Run: `python scripts/smoke.py`

Expected: üç kaynak da ilan sayısı bildirmeli, tekilleştirme sonrası sayı toplamdan **küçük** olmalı, en az birkaç ilan filtreden geçmeli ve örnek Sırpça taslak basılmalı.

Eğer bir kaynak `0 ilan` derse: o kaynağın fixture testini çalıştır. Test geçip canlı sıfır dönüyorsa şema değişmiştir - fixture'ı yenile ve parser'ı düzelt.

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke.py
git commit -m "feat: canli duman testi betigi"
```

---

### Task 15: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/watch.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `run.py`, secret'lar
- Produces: 5 dakikada bir çalışan cron job'ı

- [ ] **Step 1: `.github/workflows/watch.yml` yaz**

```yaml
name: ev-nobetcisi

on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: watcher
  cancel-in-progress: false

jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Bagimliliklari kur
        run: pip install -e .

      - name: Nobetciyi calistir
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          PYTHONPATH: src
        run: python run.py

      - name: Durumu commit'le
        run: |
          git config user.name "ev-nobetcisi"
          git config user.email "actions@github.com"
          git add state/
          git diff --staged --quiet || git commit -m "durum guncellendi [skip ci]"
          git push
```

- [ ] **Step 2: `README.md` yaz**

```markdown
# Belgrad Ev Nöbetçisi

Belgrad'daki kiralık ilanları 3 kaynaktan 5 dakikada bir tarar, filtreler,
tekilleştirir ve uygun olanları hazır Sırpça mesaj taslağıyla Telegram'a düşürür.

- Tasarım: `docs/superpowers/specs/2026-08-21-belgrade-rental-watcher-design.md`
- Plan: `docs/superpowers/plans/2026-08-21-belgrade-rental-watcher.md`

## Kurulum

```bash
python -m pip install -e ".[dev]"
cp .env.example .env   # TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID doldur
```

## Kullanım

```bash
python -m pytest          # testler
python scripts/smoke.py   # canli duman testi
python run.py             # tek kosu
```

## GitHub Actions

`TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` repo secret'i olarak eklenmeli.
Workflow 5 dakikada bir çalışır; durum `state/listings.db` içinde tutulur ve
her koşuda repoya commit'lenir.

## Kaynaklar

| Kaynak | Erişim |
|---|---|
| CityExpert | JSON POST API |
| 4zida | JSON GET API |
| halooglasi | `serverListData` blob + `ListHTML` parçası parse |

Bir kaynağın şeması değişirse ilgili fixture testi kırılır. Fixture'ları yenilemek
için Task 3/4/5'teki `curl` komutlarını çalıştır.
```

- [ ] **Step 3: `.env.example` yaz**

```bash
printf 'TELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n' > .env.example
```

- [ ] **Step 4: Testleri son kez çalıştır**

Run: `python -m pytest -v`
Expected: hepsi passed

- [ ] **Step 5: Commit**

```bash
git add .github README.md .env.example
git commit -m "feat: GitHub Actions workflow ve README"
```

---

### Task 16: Döküman paketi

**Files:**
- Create: `docs/kiralama-rehberi/sozlesme-kontrol-listesi.md`
- Create: `docs/kiralama-rehberi/ev-gezerken-sorular.md`
- Create: `docs/kiralama-rehberi/beli-karton-notu.md`
- Create: `docs/kiralama-rehberi/semt-ulasim.md`

**Interfaces:**
- Consumes: spec §11.3
- Produces: kod değil, referans dökümanlar

**Spec kısıtı (§11.2):** `beli-karton-notu.md` içinde vergi, ev sahibinin mali durumu veya para teklifi **geçmez**. Nötr, prosedürel, ikna etmeye çalışmayan bir metin. Kullanım talimatı açıkça yazılır: ilk mesajda açma, ev gezildikten sonra ve sözleşme imzalanmadan önce aç, sadece sorulursa Sırpça metni gönder.

- [ ] **Step 1: `sozlesme-kontrol-listesi.md` yaz**

İçerik: depozito tutarı ve iade koşulları, fesih ihbar süresi, faturaların (struja, infostan, grejanje, internet) kime ait olduğu, envanter tutanağı (eşya listesi + fotoğraf), kira artış maddesi, sözleşme süresi, erken çıkış cezası. Her madde Sırpça terim + Türkçe açıklama.

- [ ] **Step 2: `ev-gezerken-sorular.md` yaz**

İçerik: küf/rutubet (`vlaga`, `buđ`) izleri, ısıtma tipi ve aylık maliyeti (`centralno` / `etažno` / `TA peć` - sonuncusu pahalı), sıcak su, su basıncı, internet altyapısı, pencerelerin hangi yöne baktığı, gürültü (ana cadde, kafe), komşu profili, asansör, bina giriş güvenliği. Her soru Sırpça + Türkçe.

- [ ] **Step 3: `beli-karton-notu.md` yaz**

İçerik:
- Türkçe bölüm: beli kartonun ne olduğu, neden zorunlu olduğu (her giriş-çıkışta), **ne zaman gündeme getirileceği** (ilk mesajda değil; ev gezildikten sonra, imzadan önce)
- Sırpça bölüm: sadece ev sahibi sorarsa gönderilecek, kaydın eUprava üzerinden online yapılabildiğini anlatan 3-4 cümlelik nötr metin
- **Yasak:** vergi, gelir beyanı, para teklifi, ev sahibinin durumuna dair ima

- [ ] **Step 4: `semt-ulasim.md` yaz**

İçerik: `geo.MUNICIPALITY_MINUTES` tablosundaki her semt için Dr Subotića 8'e gerçekçi ulaşım - yürüme mi toplu taşıma mı, hangi hatlar, kabaca süre. Tablo `geo.py` ile tutarlı olmalı.

- [ ] **Step 5: Commit**

```bash
git add docs/kiralama-rehberi
git commit -m "docs: kiralama rehberi - sozlesme, gezme sorulari, beli karton, ulasim"
```

---

## Self-Review

**1. Spec coverage**

| Spec bölümü | Task |
|---|---|
| §4 Mimari | 13 |
| §5.1 CityExpert | 3 |
| §5.2 4zida | 4 |
| §5.3 halooglasi | 5 |
| §6 Veri modeli | 1, 10 |
| §7 Skorlama | 7 |
| §8 Dedupe | 8 |
| §9 Durum kalıcılığı | 10, 15 |
| §10 Telegram (iki mesaj) | 11 |
| §10 Buton mekanizması | 12 |
| §10 Gürültü kontrolü / ilk koşu sessiz | 13 |
| §11.1 Şablonlar + Türkçe çeviri | 9 |
| §11.2 Beli karton yaklaşımı | 9 (yasak testi), 16 (döküman) |
| §11.3 Döküman paketi | 16 |
| §12 Test stratejisi | 3, 4, 5, 14 |
| §12 Sağlık kontrolü | 13 |
| §13 Dağıtım | 15 |

Boşluk yok.

**2. Placeholder taraması**

Task 16 madde madde içerik tarifi veriyor, tam metin değil - bu bilinçli: dört döküman düzyazı ve her biri birkaç sayfa; plan içine gömmek planı okunmaz yapar. Her maddede ne yazılacağı ve kısıtlar açık.

**3. Tip tutarlılığı**

- `Listing.city` Task 4'te **en sona varsayılanlı** eklendi; Task 1'deki testler bozulmuyor.
- `Evaluation` alanları Task 7'de tanımlandı, Task 10/11/13'te aynı isimlerle kullanılıyor (`score`, `commute_minutes`, `is_stretch`, `flags`, `passed`).
- `ListingGroup.all_urls` Task 8'de tanımlı, Task 10 ve 11'de kullanılıyor.
- `VALID_STATUSES` Task 10'da tanımlı, Task 12'de import ediliyor.
- `notify` modülü Task 13'te `Notifier` protokolünü karşılıyor (`send_listing`, `send_text`) - imzalar eşleşiyor.
