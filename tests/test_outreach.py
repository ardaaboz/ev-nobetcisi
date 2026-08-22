from datetime import datetime, timezone

import pytest

from watcher.dedupe import ListingGroup
from watcher.models import Listing
from watcher.outreach import TEMPLATE_DIR, Draft, TemplateError, draft

# Spec 11.2: vergi ve beli karton (prijava boravista) ILK MESAJDA GECMEZ.
# Gerekce: ev sahibine "beyan etmedigini biliyorum" mesaji verir ve ilk
# temasta siradan gorunme hedefinin tersine calisir.
FORBIDDEN_TOPICS = [
    "porez", "poresk", "prijav", "beli karton", "beli-karton",
    "boravist", "boravišt", "vergi", "beyan", "euprava",
]

# Dogru olmayan iddialar. Arkadas sigara iciyor ve pesin odeme durumu belirsiz;
# yuz yuze gorusmede aciga cikacak bir iddia ilanı kazanmaktan pahaliya patlar.
FORBIDDEN_CLAIMS = [
    "ne pušim", "ne pusim", "nepušač", "sigara icmiyorum", "sigara kullanmıyorum",
    "unapred za", "mogu i unapred", "peşin", "pesin", "avans",
]


def _group(is_agency=True, price=450, muni="Vracar") -> ListingGroup:
    return ListingGroup(primary=Listing(
        source="t", source_id="1", url="u", title="Dvosoban stan", price_eur=price,
        m2=38, rooms=2.0, furnished=True, lat=None, lng=None, address=None,
        municipality=muni, published_at=datetime.now(timezone.utc), image_url=None,
        description="", is_agency=is_agency, city="Beograd",
    ))


def _all_text(is_agency, gender) -> str:
    result = draft(_group(is_agency=is_agency), gender=gender)
    return (result.serbian + " " + result.turkish).lower()


# --- temel davranis ---

def test_draft_has_both_languages():
    result = draft(_group())
    assert result.serbian.strip()
    assert result.turkish.strip()


def test_draft_mentions_medical_faculty():
    assert "medicin" in draft(_group()).serbian.lower()


def test_draft_includes_price_and_neighbourhood():
    result = draft(_group(price=430, muni="Vracar"))
    assert "430" in result.serbian
    assert "Vracar" in result.serbian


def test_agency_and_owner_drafts_differ():
    assert draft(_group(is_agency=True)).serbian != draft(_group(is_agency=False)).serbian


def test_draft_is_short():
    """Uzun ve savunmaci metin yanlis sinyal verir."""
    assert len(draft(_group()).serbian.split()) < 90


# --- kisitlar ---

@pytest.mark.parametrize("is_agency", [True, False])
@pytest.mark.parametrize("gender", ["m", "f"])
def test_never_mentions_tax_or_registration(is_agency, gender):
    blob = _all_text(is_agency, gender)
    for word in FORBIDDEN_TOPICS:
        assert word not in blob, f"yasakli konu bulundu: {word}"


@pytest.mark.parametrize("is_agency", [True, False])
@pytest.mark.parametrize("gender", ["m", "f"])
def test_never_makes_untrue_claims(is_agency, gender):
    """Sigara icmiyorum / pesin odeyebilirim iddialari olmamali."""
    blob = _all_text(is_agency, gender)
    for phrase in FORBIDDEN_CLAIMS:
        assert phrase not in blob, f"dogrulanmamis iddia bulundu: {phrase}"


@pytest.mark.parametrize("is_agency", [True, False])
@pytest.mark.parametrize("gender", ["m", "f"])
def test_no_em_dash(is_agency, gender):
    """Uzun tire yapay zeka ciktisi izlenimi veriyor."""
    blob = _all_text(is_agency, gender)
    assert "—" not in blob
    assert "–" not in blob


def test_template_files_contain_no_em_dash():
    for path in TEMPLATE_DIR.glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        assert "—" not in text, f"{path.name} uzun tire iceriyor"
        assert "–" not in text, f"{path.name} uzun tire iceriyor"


# --- cinsiyet cekimi ---

def test_masculine_and_feminine_forms_differ():
    assert draft(_group(), gender="m").serbian != draft(_group(), gender="f").serbian


def test_feminine_form_uses_feminine_adjectives():
    feminine = draft(_group(), gender="f").serbian.lower()
    assert "uredna" in feminine
    assert "studentkinja" in feminine


def test_masculine_form_uses_masculine_adjectives():
    masculine = draft(_group(), gender="m").serbian.lower()
    assert "uredan" in masculine
    assert "studentkinja" not in masculine


def test_default_gender_comes_from_config():
    """Kullanici kadin - varsayilan disi form olmali."""
    from watcher import config
    assert config.USER_GENDER == "f"
    assert draft(_group()).serbian == draft(_group(), gender="f").serbian


# --- duzenlenebilirlik ---

def test_templates_are_loaded_from_files_not_code():
    """Kullanici kod acmadan mesaji degistirebilmeli."""
    for name in ("emlakci.sr.txt", "emlakci.tr.txt",
                 "ev_sahibi.sr.txt", "ev_sahibi.tr.txt"):
        assert (TEMPLATE_DIR / name).is_file(), f"eksik sablon: {name}"


def test_edited_template_is_reflected_in_output(tmp_path, monkeypatch):
    """Dosyayi degistirince cikti degismeli - kod yeniden kurulmasin."""
    monkeypatch.setattr("watcher.outreach.TEMPLATE_DIR", tmp_path)
    (tmp_path / "emlakci.sr.txt").write_text("Zdravo, {muni} {price}", encoding="utf-8")
    (tmp_path / "emlakci.tr.txt").write_text("Selam", encoding="utf-8")
    result = draft(_group(price=399, muni="Zvezdara"))
    assert result.serbian == "Zdravo, Zvezdara 399"


def test_unknown_placeholder_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr("watcher.outreach.TEMPLATE_DIR", tmp_path)
    (tmp_path / "emlakci.sr.txt").write_text("Zdravo {uydurma}", encoding="utf-8")
    (tmp_path / "emlakci.tr.txt").write_text("Selam", encoding="utf-8")
    with pytest.raises(TemplateError) as excinfo:
        draft(_group())
    assert "uydurma" in str(excinfo.value)


def test_missing_template_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr("watcher.outreach.TEMPLATE_DIR", tmp_path)
    with pytest.raises(TemplateError):
        draft(_group())
