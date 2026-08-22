# Belgrad Kiralık Ev Nöbetçisi - Tasarım Dökümanı

**Tarih:** 2026-08-21
**Durum:** Onaylandı, implementasyona hazır

## 1. Problem

Belgrad'da kiralık daire aramak üç ayrı darboğaz içeriyor:

**Hız.** Bütçe segmentindeki ilanlar saatler içinde kapanıyor. Siteleri saat başı elle kontrol etmek bu yarışı yapısal olarak kaybediyor; ilana ulaşıldığında çoğu zaman "verildi" cevabı geliyor.

**İletişim yükü.** Her ilan için sıfırdan mesaj yazmak hem zaman alıyor hem de ilan başına yüksek bir eşik yaratıyor. Hazır ve kalibre edilmiş bir taslak bu eşiği düşürür.

**Takip kaybı.** Çok sayıda emlakçı ve ev sahibiyle paralel yazışma var; kimin ne dediği, kime dönülmesi gerektiği kayboluyor.

## 2. Hedefler

- Yeni ilanı yayınlandıktan sonra **dakikalar içinde** kullanıcının telefonuna düşürmek
- Gereksiz ilanları ayıklayıp sadece gerçekten uyanları göstermek
- Aynı dairenin farklı emlakçılardaki kopyalarını tek ilana indirmek
- Her ilan için kopyalanmaya hazır, kalibre edilmiş Sırpça mesaj üretmek
- Temas durumunu takip etmek
- Sürekli elle site kontrol etme yükünü ortadan kaldırmak

**Hedef olmayan:** Ev bulmayı garanti etmek. Sistem hız ve sunum avantajı sağlar; kararı ev sahipleri verir.

## 3. Arama kriterleri

| Kriter | Değer |
|---|---|
| Bütçe | Hedef ~400 EUR; fakülteye yakınsa 500 EUR'ya kadar. Sistem kasten 550 EUR'ya kadar tarar ve 500 üstünü "esnek" etiketiyle gösterir - ilan fiyatları pazarlığa açık olduğu ve iyi bir ilanı kaçırmak fazladan ilan görmekten pahalı olduğu için. |
| Referans nokta | Tıp Fakültesi, **Dr Subotića 8, Savski Venac, Belgrad** - koordinat `44.7974, 20.4611` (Nominatim ile doğrulandı) |
| Tercih edilen semtler | Savski Venac, Vračar, Voždovac, Stari Grad |
| Kabul edilebilir | Novi Beograd (ev çok ucuz ve güzelse) |
| **Zorunlu** | Yatak; çalışma masası VEYA masa olarak kullanılabilecek yemek masası |
| **Zorunlu** | Pencere olmalı - penceresiz/bodrum kesinlikle elenir |
| Artı puan | Teras, balkon veya dışarıya direkt kapı |
| Artı puan | İyi havalandırma, aydınlık, ferah |

## 4. Mimari

GitHub Actions üzerinde 5 dakikada bir çalışan Python job'ı.

```
cron (5 dk)
  -> sources/*  (3 adaptör, paralel fetch)
  -> normalize  (tek Listing şemasına indirge)
  -> score      (sert filtre + yumuşak skor)
  -> dedupe     (siteler arası aynı daire tespiti)
  -> store      (daha önce bildirilmemişleri ayıkla)
  -> notify     (Telegram push + Sırpça taslak)
  -> store      (state'i repoya geri commit'le)
  -> callbacks  (getUpdates ile buton basışlarını topla, durum güncelle)
```

Her aşama saf ve bağımsız test edilebilir. Bir kaynak adaptörü bozulursa job düşmez, o kaynağı atlar ve uyarı loglar.

## 5. Veri kaynakları

Üçü de 2026-08-21 tarihinde canlı doğrulandı.

### 5.1 CityExpert

- `POST https://cityexpert.rs/api/Search/`, JSON gövde
- Gövde: `{"ptId":[1,2],"cityId":1,"rentOrSale":"r","currentPage":1,"resultsPerPage":N,"sort":"datedsc","minPrice":..,"maxPrice":..}`
- Dönen alanlar: `uniqueID`, `price`, `size`, `municipality`, `location` ("lat, lng"), `furnished`, `furnishingArray`, `firstPublished`, `coverPhoto`, `structure`, `floor`
- **Not:** `municipality` filtresi sunucu tarafında güvenilir çalışmıyor - semt filtresi istemci tarafında koordinat üzerinden yapılacak (zaten daha doğru).

### 5.2 4zida

- `GET https://api.4zida.rs/v6/search/apartments?for=rent&priceTo=..&sort=createdAtDesc`
- Dönen alanlar: `id`, `price`, `m2`, `placeNames[]`, `placeLevel1..3`, `furnished`, `roomCount`, `structureName`, `createdAt`, `urlPath`, `safeAddress`, `image`, `description100`, `agencyUrl` (varlığı emlakçı/sahibi ayrımını verir)
- Tüm Sırbistan'ı kapsıyor - Belgrad filtresi `placeNames` üzerinden istemci tarafında.

### 5.3 halooglasi

- `GET https://www.halooglasi.com/nekretnine/izdavanje-stanova/beograd?cena_d_to=..&cena_d_unit=4&sort=D`
- HTML içine gömülü `QuidditaEnvironment.serverListData` JSON blob'u parse edilir.
- **Önemli:** Blob'daki `Ads[]` girdilerinde alanların çoğu `null` (`Address`, `City`, `OtherFields`, `ImageURLs`, `ValidFrom` dahil). Sadece `Id`, `Title`, `RelativeUrl`, `AdvertiserId` dolu. Gerçek veri her ilanın `ListHTML` alanında, HTML-escape edilmiş bir parça olarak duruyor. Yani JSON'dan ilan listesi alınır, sonra her `ListHTML` parçası unescape edilip parse edilir.
- Parça temiz ve sabit CSS sınıflarına sahip:
  - `.central-feature` → fiyat (`400 €`)
  - `.publish-date` → yayın tarihi (`21.08.2026.`)
  - `.product-type` → `Vlasnik` (doğrudan ev sahibi) veya emlakçı adı - **emlakçı/sahibi ayrımı için birincil sinyal**
  - `.product-title` → başlık ve link
  - `.subtitle-places` → semt zinciri (`Beograd > Opština Voždovac > Lekino brdo > Gospodara Vučića`)
  - `.product-features` → m², oda sayısı, kat
  - `.text-description-list` → açıklama özeti
- **Uyarı:** Başlıklar güvenilmez (ör. "izdavanje Vracar" başlıklı ilan aslında Voždovac'ta). Konum için daima `.subtitle-places` kullanılır, başlık değil.
- **Uyarı:** URL'de `beograd` filtresi olsa da tanıtımlı (promoted) ilanlar başka şehirlerden sızabiliyor. Belgrad filtresi istemci tarafında tekrar uygulanır.
- En yüksek ilan hacmi bu kaynakta.

### 5.4 Kapsam dışı (faz 2)

- `nekretnine.rs` - 403 / bot koruması, Playwright gerektirir
- KupujemProdajem, Sasomange, Facebook grupları

**Nezaket kuralı:** Kaynak başına istekler sıralı ve gecikmeli, makul `User-Agent` ile, koşu başına sadece en yeni sayfalar çekilir. Bu kişisel ölçekte, düşük hacimli, herkese açık ilan okumasıdır.

## 6. Veri modeli

```python
@dataclass(frozen=True)
class Listing:
    source: str              # "cityexpert" | "4zida" | "halooglasi"
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
```

Durum kaydı (SQLite):

```
listings(fingerprint PK, source, source_id, url, price_eur, m2, municipality,
         published_at, first_seen_at, score, payload_json)

outreach(fingerprint PK, status, updated_at, note)
    status in {new, notified, contacted, replied, viewing, rejected, dead}
```

## 7. Skorlama

### Sert filtreler (elenir)

- `price_eur > 550`
- Belgrad dışı
- Açıklama/başlıkta: `podrum`, `suteren`, `bez prozora`, `nema prozor`
- Mobilyasız (`nenamešten`) - yatak/masa zorunluluğu karşılanamaz
- Kısa dönem/turistik kiralama işaretleri (`dnevno`, `na dan`)

### Yumuşak skor (0-100)

| Sinyal | Ağırlık |
|---|---|
| Fakülteye (Dr Subotića 8) tahmini ulaşım süresi | 35 |
| Fiyat (400 EUR ve altı en yüksek puan; 500-550 "esnek" etiketi) | 25 |
| Semt tercihi (Savski Venac / Vračar / Stari Grad / Voždovac > Novi Beograd > diğer) | 15 |
| Teras / balkon / dışarı kapısı (`terasa`, `balkon`, `lođa`) | 10 |
| Aydınlık ve ferahlık sinyalleri (`svetao`, `sunčan`, `prostran`) | 8 |
| m² (küçük stüdyolar cezalandırılmaz ama çok küçükler düşer) | 7 |

**Not:** Yatak/masa zorunluluğu ilan metninden her zaman kesin çıkarılamaz. Sistem `furnishingArray` ve açıklama anahtar kelimeleriyle *tahmin* eder; kesinlik gerektiren durumda bildirimde "masa doğrulanmalı" uyarısı çıkar. Yanlış negatif (iyi ilanı elemek) yanlış pozitiften (fazladan ilan göstermek) daha pahalı olduğu için eşik gevşek tutulur.

## 8. Dedupe

Belgrad'da aynı daire tipik olarak 3-5 emlakçıda birden listelenir. Bu, manuel aramada en çok vakit yiyen şeylerden biri.

Bileşik parmak izi: `(round(price/10), round(m2), municipality_normalized)` + başlık/adres üzerinde bulanık eşleşme (token set ratio, eşik ~85).

Eşleşme bulunursa tek bir ilan olarak gösterilir, tüm kaynak linkleri bir arada verilir - bu aslında bir avantaj: aynı daireye farklı emlakçıdan sormak, "verildi" cevabını doğrulamanın bilinen yolu.

## 9. Durum kalıcılığı

GitHub Actions'ta kalıcı disk yok. SQLite dosyası her koşu sonunda repoya commit'lenir (`state/listings.db`). Dosya küçük kalır (birkaç bin satır). Commit mesajı gürültü yapmasın diye tek satır ve `[skip ci]` etiketli.

## 10. Telegram bildirimi

Her yeni eşleşme için **iki mesaj** gönderilir. Ayrı olmalarının sebebi kopyalanabilirlik: taslak metnin ilan bilgileriyle aynı balonda olması, kopyalarken istenmeyen metin de alınmasına yol açar.

**Mesaj 1 - ilan kartı:**

```
450 EUR · 38 m² · Vračar
Fakülteye ~14 dk (yürüme)
Skor 82 · Mobilyalı · Balkon var
[ilan linki]
[Yazdım] [Elendi] [Favori]
```

**Mesaj 2 - hazır mesaj:**

Sırpça metin, HTML `<pre>` bloğu içinde gönderilir. Telegram istemcileri `<pre>` bloklarına tek dokunuşluk kopyalama düğmesi koyar; kopyalanan içerik sadece blok içidir. Bloğun **altında**, düz metin olarak Türkçe çevirisi yer alır - böylece çeviri kopyalamaya karışmaz.

```
<pre>Poštovani, zanima me stan koji ste oglasili...</pre>

TR: Merhaba, ilan verdiğiniz daireyle ilgileniyorum...
```

Türkçe çevirinin amacı kullanıcının ne gönderdiğini birebir bilmesi. Fallback olarak her istemcide uzun basıp kopyalama zaten çalışır.

**Buton mekanizması:** Actions cron'u webhook tutamaz. Her koşuda bot `getUpdates` ile son koşudan beri gelen callback'leri toplar (Telegram güncellemeleri 24 saat saklar). Durum güncellemesi 5 dk'ya kadar gecikmeli yansır - kabul edilebilir.

**Hedef sohbet:** Bir Telegram grubu. Böylece ilanlar birden fazla kişiye düşebilir ve eleme paylaşılabilir. Grup `chat_id` secret olarak saklanır.

**Gürültü kontrolü:** Koşu başına en fazla 8 bildirim; fazlası varsa özet mesaj. İlk koşuda geçmiş ilanlarla telefonu bombalamamak için ilk çalıştırma "sessiz mod"da sadece state doldurur, bildirim atmaz.

## 11. Sırpça iletişim paketi

### 11.1 Mesaj şablonları

**Dil:** Sırpça taslak her zaman Türkçe çevirisiyle birlikte verilir; kullanıcı ne gönderdiğini birebir bilmeli. Metin sade tutulur.

İlan tipine göre kişiselleşen ilk temas mesajları:

- Emlakçı vs. doğrudan ev sahibi (ton farkı)
- Fiyat ve semte göre ufak varyasyon
- Sabit çekirdek: Belgrad Üniversitesi Tıp Fakültesi öğrencisi, sessiz, sigara içmiyor, uzun dönem kiracı, düzenli ödeme, peşin ödeme esnekliği

Şablonlar kısa, sakin ve sıradan tutulur. Aşırı açıklama ve savunmacı ton yanlış sinyal verir. Sırpça seviyesi temel olduğu için metin de **abartılı resmi veya karmaşık olmamalı** - yüz yüze görüşmede aynı dili konuşamayacağı bir metin tutarsızlık yaratır.

**Gelen cevaplar kapsam dışı.** Kullanıcı ev sahiplerinden gelen cevapları kendi hallediyor; çeviri araçları zaten mevcut. Sistem sadece giden mesajı üretir.

### 11.2 Beli karton (prijava boravišta) yaklaşımı

Kullanıcı kararı: **vergi konusu hiçbir şekilde gündeme getirilmez.** Ev sahibinin mali durumuna dair hiçbir ima, hiçbir para teklifi yok. Gerekçe: bu, ev sahibine "beyan etmediğini biliyorum" mesajı verir ve ilk temasta sıradan görünme hedefinin tersine çalışır.

Bunun yerine:

- **İlk mesajda açılmaz.** İlk temas sade kalır.
- Konu, karşılıklı ilgi oluştuktan sonra - ev gezildikten sonra, sözleşme imzalanmadan önce - gündeme gelir. Erken açmak gereksiz eleme, hiç açmamak imza sonrası çıkmaz demek.
- Sadece ev sahibi sorarsa kullanılmak üzere, kaydın eUprava üzerinden 5 dakikalık rutin bir işlem olduğunu anlatan kısa ve kuru bir Sırpça not hazırlanır. Nötr, prosedürel, ikna edici olmaya çalışmayan bir metin.

### 11.3 Döküman paketi

- Kira sözleşmesi kontrol listesi (Sırpça-Türkçe): depozito koşulları, fesih ihbarı, faturaların kime ait olduğu, envanter tutanağı, artış maddesi
- Semt-ulaşım analizi: her semtten Dr Subotića 8'e gerçekçi ulaşım süreleri ve hatlar
- Ev gezerken sorulacak sorular listesi (küf, ısıtma tipi ve maliyeti, sıcak su, internet, gürültü, komşu profili)

## 12. Test stratejisi

TDD. Her aşama için:

- **Kaynak adaptörleri:** Kaydedilmiş gerçek JSON/HTML fixture'ları üzerinden test. Site şeması değişirse test kırılır - sessizce boş liste dönmez. Bu kritik: sessiz bozulma bu sistemdeki en tehlikeli hata modu.
- **normalize / score / dedupe:** Saf fonksiyonlar, doğrudan birim testi. Dedupe için gerçek dünyadan alınmış çapraz-listeleme örnekleri fixture olarak tutulur.
- **store:** Geçici SQLite üzerinde durum geçişi testleri.
- **notify:** Telegram API mock'lanır; mesaj biçimlendirmesi snapshot testi.
- **Canlı duman testi:** Tüm kaynakları gerçekten çağıran, CI'da değil elle çalıştırılan bir betik. Kaynağın hâlâ ayakta olduğunu doğrular.

**Sağlık kontrolü:** Bir kaynak arka arkaya 3 koşuda sıfır sonuç dönerse Telegram'a uyarı gider. Sessiz ölüm bu projede kabul edilemez.

## 13. Dağıtım

- GitHub Actions, `schedule: cron` 5 dakikada bir + `workflow_dispatch` (elle tetikleme)
- Secret'lar: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Private repo
- **Bilinen kısıt:** GitHub Actions cron 5 dakikayı garanti etmez; yoğun saatlerde 10-15 dk'ya sarkabilir. Saat başı manuel kontrole göre yine 6-12 kat hızlı. Yetersiz kalırsa ~4 EUR/ay VPS'e taşınır - kod taşınabilir yazılır, cron dışında Actions'a özgü bağımlılık olmayacak.

## 14. Riskler

| Risk | Etki | Azaltma |
|---|---|---|
| Site API'si sessizce değişir | Yüksek - ilan kaçar | Fixture testleri + sıfır-sonuç sağlık uyarısı |
| Actions cron gecikmesi | Orta | Kabul; gerekirse VPS'e taşı |
| Dedupe yanlış birleştirme | Orta - gerçek ilan gizlenir | Eşik yüksek tutulur; birleşenler kartta ayrı link olarak gösterilir |
| Bildirim gürültüsü | Orta - kullanıcı sistemi susturur | Koşu başına 8 tavan, skor eşiği, ilk koşu sessiz |
| Sistem ev bulmayı garanti etmez | - | Açıkça beyan edildi; kazanç hız ve sunumda |

## 15. Faz 2 (v1 ayakta ve iş görüyorsa)

- `nekretnine.rs` (Playwright ile)
- KupujemProdajem / Sasomange
- Facebook grup takibi
- Basit web paneli
- Görsel hash ile daha güçlü dedupe

## 16. Karara bağlanmış noktalar

- **Dil:** Kullanıcının Sırpçası temel seviye (anadil Türkçe, İngilizce de var). Mesajlar tam hazır kalıp olarak, Türkçe çevirisiyle birlikte verilir. Metin sade tutulur - konuşamayacağı seviyede bir Sırpça yazmak tutarsızlık yaratır.
- **Gelen cevaplar:** Kapsam dışı. Kullanıcı kendi hallediyor, çeviri sözlüğü eklenmeyecek.
- **Kopyalanabilirlik:** Taslak, ilan kartından ayrı bir mesajda ve `<pre>` bloğu içinde gönderilir (bkz. §10).
