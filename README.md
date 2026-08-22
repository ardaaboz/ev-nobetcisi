# Belgrad Ev Nöbetçisi

Belgrad'daki kiralık ilanları üç kaynaktan 5 dakikada bir tarar, filtreler,
tekilleştirir ve uygun olanları hazır Sırpça mesaj taslağıyla Telegram'a düşürür.

Amaç ev bulmayı garanti etmek değil - her ilanda ilk temas edenlerden biri olmayı
sağlamak ve sürekli elle site kontrol etme yükünü ortadan kaldırmak.

- **Mesaj şablonları (düzenlenebilir): [`templates/`](templates/)**
- Tasarım: [`docs/superpowers/specs/2026-08-21-belgrade-rental-watcher-design.md`](docs/superpowers/specs/2026-08-21-belgrade-rental-watcher-design.md)
- Plan: [`docs/superpowers/plans/2026-08-21-belgrade-rental-watcher.md`](docs/superpowers/plans/2026-08-21-belgrade-rental-watcher.md)
- Kiralama rehberi: [`docs/kiralama-rehberi/`](docs/kiralama-rehberi/)

## Mesajı değiştirmek

Gönderilen metin kodda değil, [`templates/`](templates/) altındaki düz metin
dosyalarında. Dosyayı aç, düzenle, kaydet. Kod değiştirmeye veya yeniden
kurmaya gerek yok.

| Dosya | Ne zaman |
|---|---|
| `ev_sahibi.sr.txt` / `.tr.txt` | İlan doğrudan ev sahibinden |
| `emlakci.sr.txt` / `.tr.txt` | İlan emlakçıdan |

Kullanılabilir yer tutucular ve yazım kuralları: [`templates/README.md`](templates/README.md)

Metin bildirimlerle birlikte gönderilmiyor: her ilanda aynı olduğu için sohbeti
şişiriyordu. Bunun yerine gruba bir kez sabitleniyor. Şablonu değiştirdikten
sonra yeni metni sabitlemek için:

```bash
python scripts/sabit-mesaj.py
```

Şablonlarda **doğrulanmamış hiçbir iddia yok** (sigara, peşin ödeme gibi) ve
vergi/beli karton konusu geçmiyor. İkisi de teste bağlı; şablona sızarsa
`pytest` kırılır.

## Kurulum

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
```

`.env` içine Telegram bot token'ını ve chat id'sini yaz.

## Kullanım

```bash
python -m pytest
```

```bash
python scripts/smoke.py
```

```bash
python run.py --dry-run
```

```bash
python run.py
```

`--dry-run` Telegram'a hiçbir şey göndermez, sonucu terminale basar.

## Nasıl çalışıyor

```
uzun sureli is (5,5 saat), icinde her 5 dakikada:
  3 kaynak (sirali, aralarinda 1sn)
           → normalize (tek Listing semasi)
           → sert filtre (butce, Belgrad, mobilya, bodrum/penceresiz/gunluk eleme)
           → skor (fakulteye sure, fiyat, semt, m2, balkon, aydinlik)
           → dedupe (once adres, yoksa baslik)
           → daha once gorulmemisleri ayikla
           → Telegram: ilan basina TEK kart (taslak gruba sabitlenir)
           → state/listings.db her ~30 dakikada repoya commit'lenir
```

Zamanlayici sadece isi baslatir; tarama sikligi isin kendi dongusune bagli.

## Kaynaklar

| Kaynak | Erişim | Not |
|---|---|---|
| CityExpert | JSON POST API | Tek koordinat veren kaynak; ulaşım süresi burada en isabetli |
| 4zida | JSON GET API | Tüm Sırbistan'ı döner, Belgrad filtresi istemci tarafında |
| halooglasi | `serverListData` blob + `ListHTML` parçası | En yüksek hacim. curl ile çekilir. **Actions'ta çalışmaz**, aşağıya bak |

Bir kaynağın şeması değişirse ilgili fixture testi kırılır. Fixture'ları yenilemek için
plandaki Task 3/4/5'teki `curl` komutlarını çalıştır.

## GitHub Actions

Repo **public**, bu yüzden GitHub-hosted runner dakikaları ücretsiz ve sınırsız.
Mimari buna dayanıyor.

### Neden uzun süreli iş

GitHub ücretsiz repolarda `schedule` tetikleyicisini düzenli çalıştırmıyor.
Ölçüldü (2026-08-22): `*/5` cron ile 70 dakikada **1** koşu tetiklendi, aynı
sürede elle atılan `workflow_dispatch`'lerin **hepsi** anında çalıştı.

Bu yüzden zamanlayıcıya sadece *işi başlatma* görevi verildi. İş bir kez
başladığında 5 saat 25 dakika boyunca kendi içinde döngü kurup **5 dakikada
bir** tarıyor. Zamanlanmış denemeler saatte iki kez geliyor; zaten çalışan bir
iş varsa yeni gelen 6 saniyede çıkıyor (`Zaten calisan bir kosu var mi` adımı).

Sonuç: taramanın sıklığı GitHub'ın zamanlayıcısına değil, kendi döngümüze bağlı.

### Ayarlar

Repo secret'ları: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
Repo variable: `USER_GENDER` (`f` varsayılan).

Secret değerleri public repoda da okunamaz; sadece isimleri listelenir.

## Bilinen sınırlar

- **Ulaşım süreleri tahmindir.** Koordinat veren tek kaynak CityExpert; diğerlerinde
  semt/opština tablosundan tahmin ediliyor. Kesin süre için Google Maps'e bakılmalı.
- **halooglasi sadece yerel koşuda gelir.** Site veri merkezi IP'lerini
  engelliyor, bu yüzden Actions'tan çekilemiyor. Ölçüldü: beş farklı curl
  varyantı ve sitenin ana sayfası dahil hepsi Actions'tan 403 döndü, aynı
  komutlar ev bağlantısından 200 dönüyor.
- **`nekretnine.rs` ve Facebook grupları kapsam dışı.** Cloudflare / oturum gerektiriyor.
- **halooglasi mobilya alanı vermiyor**; o ilanlar `masa-dogrulanmali` bayrağıyla gelir - yatak ve çalışma masası ilan metninden teyit edilmeli.
- **Otomatik mesaj gönderilmez.** Sistem taslağı hazırlar, göndermeye kullanıcı karar verir.
