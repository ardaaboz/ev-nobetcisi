from datetime import datetime, timezone

from watcher import notify
from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.outreach import Draft
from watcher.score import Evaluation


def _listing(**kwargs) -> Listing:
    base = dict(
        source="4zida", source_id="1", url="https://x/1", title="Dvosoban stan",
        price_eur=450, m2=38, rooms=2.0, furnished=True, lat=None, lng=None,
        address=None, municipality="Vracar", published_at=datetime.now(timezone.utc),
        image_url=None, description="", is_agency=True, city="Beograd",
    )
    base.update(kwargs)
    return Listing(**base)


def _group(**kwargs) -> ListingGroup:
    return ListingGroup(primary=_listing(**kwargs))


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


def test_card_omits_stretch_marker_at_target_price():
    card = notify.format_card(_group(price_eur=400), Evaluation(passed=True, score=80))
    assert "esnek" not in card.lower()


def test_card_lists_all_urls_when_duplicated():
    group = _group()
    group.duplicates.append(_listing(source="halooglasi", source_id="2", url="https://y/2"))
    card = notify.format_card(group, Evaluation(passed=True, score=70))
    assert "https://x/1" in card
    assert "https://y/2" in card


def test_card_shows_flags():
    card = notify.format_card(
        _group(), Evaluation(passed=True, score=70, flags=["balkon", "dogrudan-ev-sahibi"])
    )
    assert "balkon" in card
    assert "dogrudan-ev-sahibi" in card


def test_card_escapes_html_in_free_text():
    card = notify.format_card(_group(municipality="A & B"), Evaluation(passed=True, score=70))
    assert "&amp;" in card


def test_card_handles_missing_commute():
    card = notify.format_card(_group(), Evaluation(passed=True, score=70, commute_minutes=None))
    assert "450" in card


def test_draft_message_wraps_serbian_in_pre_block():
    """Sirpca metin <pre> icinde olmali - Telegram tek dokunusla kopyalama koyuyor."""
    message = notify.format_draft(Draft(serbian="Postovanje, zanima me stan.", turkish="Merhaba."))
    assert message.startswith("<pre>")
    assert "Postovanje, zanima me stan." in message
    assert message.index("</pre>") < message.index("Merhaba.")


def test_draft_message_escapes_html_in_serbian():
    message = notify.format_draft(Draft(serbian="a < b & c", turkish="x"))
    assert "&lt;" in message
    assert "&amp;" in message


def test_keyboard_encodes_fingerprint():
    keyboard = notify._keyboard("abc123")
    payloads = [b["callback_data"] for b in keyboard["inline_keyboard"][0]]
    assert "contacted:abc123" in payloads
    assert "rejected:abc123" in payloads


def test_send_listing_posts_two_separate_messages(monkeypatch):
    """Kart ve taslak ayri mesaj olmali - ayni balonda kopyalama bozulur."""
    sent = []
    monkeypatch.setattr(notify, "_post", lambda method, payload: sent.append((method, payload)))
    notify.send_listing(
        _group(), Evaluation(passed=True, score=70), Draft(serbian="sr", turkish="tr")
    )
    assert len(sent) == 2
    assert "reply_markup" in sent[0][1]      # kartta butonlar var
    assert "reply_markup" not in sent[1][1]  # taslakta yok
    assert "<pre>" in sent[1][1]["text"]
