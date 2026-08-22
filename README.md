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
cron (5dk) → 3 kaynak (sirali, aralarinda 1sn)
           → normalize (tek Listing semasi)
           → sert filtre (butce, Belgrad, mobilya, bodrum/penceresiz/gunluk eleme)
           → skor (fakulteye sure, fiyat, semt, m2, balkon, aydinlik)
           → dedupe (once adres, yoksa baslik)
           → daha once gorulmemisleri ayikla
           → Telegram: ilan karti + ayri mesajda kopyalanabilir Sirpca taslak
           → state/listings.db repoya geri commit'lenir
```

## Kaynaklar

| Kaynak | Erişim | Not |
|---|---|---|
| CityExpert | JSON POST API | Tek koordinat veren kaynak; ulaşım süresi burada en isabetli |
| 4zida | JSON GET API | Tüm Sırbistan'ı döner, Belgrad filtresi istemci tarafında |
| halooglasi | `serverListData` blob + `ListHTML` parçası | En yüksek hacim. curl ile çekilir. **Actions'ta çalışmaz**, aşağıya bak |

Bir kaynağın şeması değişirse ilgili fixture testi kırılır. Fixture'ları yenilemek için
plandaki Task 3/4/5'teki `curl` komutlarını çalıştır.

## GitHub Actions

Repo secret'ları olarak `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` eklenmeli.
İsteğe bağlı repo variable: `USER_GENDER` (`f` varsayılan, Sırpça çekim için).

Workflow 5 dakikada bir çalışır. GitHub bu aralığı garanti etmez - yoğun saatlerde
10-15 dakikaya sarkabilir.

### halooglasi neden Actions'ta gelmiyor

halooglasi veri merkezi IP bloklarını engelliyor. 2026-08-21'de Actions'tan
ölçüldü: beş farklı curl varyantı (bizim UA, tarayıcı UA, ek başlıklar,
http1.1, tlsv1.2) ve sitenin ana sayfası dahil **hepsi 403** döndü. Çıkış IP'si
Azure. Aynı komutlar ev bağlantısından 200 dönüyor. Yani istemci tarafında
çözülecek bir şey değil, kasıtlı bir IP engeli.

Bu yüzden sistem iki katmanlı:

| Katman | Kaynaklar | Ne zaman |
|---|---|---|
| GitHub Actions | CityExpert + 4zida | 7/24, 5 dakikada bir |
| Yerel koşu | + halooglasi | Bilgisayar açıkken |

İkisi aynı `state/listings.db` dosyasını repo üzerinden paylaşır, mükerrer
bildirim olmaz. Kurulum: [`scripts/README.md`](scripts/README.md)

Not: VPS de büyük ihtimalle aynı engele takılır, veri merkezi IP'si olduğu için.

## Bilinen sınırlar

- **Ulaşım süreleri tahmindir.** Koordinat veren tek kaynak CityExpert; diğerlerinde
  semt/opština tablosundan tahmin ediliyor. Kesin süre için Google Maps'e bakılmalı.
- **halooglasi sadece yerel koşuda gelir.** Veri merkezi IP'leri engelli.
- **`nekretnine.rs` ve Facebook grupları kapsam dışı.** Cloudflare / oturum gerektiriyor.
- **halooglasi mobilya alanı vermiyor**; o ilanlar `masa-dogrulanmali` bayrağıyla gelir - yatak ve çalışma masası ilan metninden teyit edilmeli.
- **Otomatik mesaj gönderilmez.** Sistem taslağı hazırlar, göndermeye kullanıcı karar verir.
