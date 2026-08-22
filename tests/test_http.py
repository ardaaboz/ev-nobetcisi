import httpx
import pytest

from watcher.http import SourceFetchError, get_json


def test_get_json_returns_parsed_body(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    assert get_json("https://example.test/x") == {"ok": True}


def test_get_json_raises_on_http_error(monkeypatch):
    """500 throttle kodu degil - hemen hata verir, beklemez."""
    def fake_request(self, method, url, **kwargs):
        return httpx.Response(500, text="down", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")


def test_get_json_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("watcher.http._RETRY_BACKOFF", 0)
    attempts = {"n": 0}

    def fake_request(self, method, url, **kwargs):
        attempts["n"] += 1
        raise httpx.ConnectTimeout("zaman asimi")

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")
    assert attempts["n"] == 3


def test_transient_transport_error_is_retried(monkeypatch):
    """Tek seferlik DNS/baglanti hatasi bir tarama turunu kaybettirmemeli."""
    monkeypatch.setattr("watcher.http._RETRY_BACKOFF", 0)
    attempts = {"n": 0}

    def fake_request(self, method, url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectError("gecici DNS hatasi")
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    assert get_json("https://example.test/x") == {"ok": True}
    assert attempts["n"] == 2


def test_get_json_raises_on_invalid_json(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return httpx.Response(200, text="<html>bu json degil", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")


def test_throttle_code_is_retried_then_succeeds(monkeypatch):
    """429/503 gecici yuk sinyali - bekleyip tekrar denemek dogru."""
    monkeypatch.setattr("watcher.http._THROTTLE_BACKOFF", 0)
    attempts = {"n": 0}

    def fake_request(self, method, url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, text="slow down", request=httpx.Request(method, url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    assert get_json("https://example.test/x") == {"ok": True}
    assert attempts["n"] == 2


def test_persistent_throttle_raises_after_retries(monkeypatch):
    monkeypatch.setattr("watcher.http._THROTTLE_BACKOFF", 0)
    attempts = {"n": 0}

    def fake_request(self, method, url, **kwargs):
        attempts["n"] += 1
        return httpx.Response(429, text="no", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")
    assert attempts["n"] == 3


def test_permanent_client_error_is_not_retried(monkeypatch):
    """404/403 gercek cevaptir - tekrar denemek anlamsiz.
    403 ozellikle: halooglasi'nin 403'u TLS parmak izi kaynakliydi, beklemek
    cozmuyordu; get_text_via_curl ile cozuldu."""
    monkeypatch.setattr("watcher.http._THROTTLE_BACKOFF", 0)
    attempts = {"n": 0}

    def fake_request(self, method, url, **kwargs):
        attempts["n"] += 1
        return httpx.Response(404, text="yok", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")
    assert attempts["n"] == 1


def test_403_is_not_retried(monkeypatch):
    """403 throttle listesinde degil - bosa 12 saniye beklemesin."""
    attempts = {"n": 0}

    def fake_request(self, method, url, **kwargs):
        attempts["n"] += 1
        return httpx.Response(403, text="no", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    with pytest.raises(SourceFetchError):
        get_json("https://example.test/x")
    assert attempts["n"] == 1


def test_get_text_via_curl_returns_body(monkeypatch):
    import subprocess
    from watcher.http import get_text_via_curl

    def fake_run(command, **kwargs):
        assert command[0] == "curl"
        assert "belgrade-rental-watcher/1.0 (personal use)" in command
        return subprocess.CompletedProcess(command, 0, stdout="<html>sayfa</html>" + chr(10) + "200", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert get_text_via_curl("https://example.test/x") == "<html>sayfa</html>"


def test_get_text_via_curl_raises_on_bad_status(monkeypatch):
    import subprocess
    from watcher.http import get_text_via_curl

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="engellendi" + chr(10) + "403", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SourceFetchError):
        get_text_via_curl("https://example.test/x")


def test_get_text_via_curl_raises_when_curl_missing(monkeypatch):
    import subprocess
    from watcher.http import get_text_via_curl

    def fake_run(command, **kwargs):
        raise FileNotFoundError("curl yok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SourceFetchError):
        get_text_via_curl("https://example.test/x")
