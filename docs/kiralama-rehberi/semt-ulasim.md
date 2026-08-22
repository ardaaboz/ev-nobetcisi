# Semt ve Ulaşım

Dr Subotića 8 (Tıp Fakültesi) referans alınarak kabaca kapıdan kapıya süreler.

> Bu tablo `src/watcher/geo.py` içindeki `PLACE_MINUTES` sözlüğünden üretildi - > sistemin sıralama yaparken kullandığı değerlerin **birebir aynısı**. Bir semt
> yanlış geliyorsa orayı düzelt, bu döküman yeniden üretilir.

**Süreler tahmindir.** Koordinat veren tek kaynak CityExpert; diğer ilanlarda
semt adından tahmin ediliyor. Ciddi bir ilan için Google Maps'te kontrol et.

## Öncelikli bölgeler (senin listendekiler)

| Opština | Süre | Not |
|---|---|---|
| Savski Venac | ~8 dk | Fakultenin bulundugu opstina. Cogu yer yurume mesafesinde. |
| Vracar | ~14 dk | Fakulteye en yakin ikinci bolge, yurunebilir. Sakin ve ogrenci icin ideal. |
| Stari Grad | ~18 dk | Merkez. Yurume + kisa toplu tasima. Gurultulu olabilir. |
| Vozdovac | ~22 dk | Genis opstina - kuzeyi yakin, guneyi uzak. Ilan hangi mahallede, bak. |
| Novi Beograd | ~30 dk | Nehrin karsisi. Otobus/tramvay ile ~30 dk. Bloklara gore degisir. |

## Tüm opštinalar

| Opština | Süre | Not |
|---|---|---|
| Savski Venac | ~8 dk | Fakultenin bulundugu opstina. Cogu yer yurume mesafesinde. |
| Vracar | ~14 dk | Fakulteye en yakin ikinci bolge, yurunebilir. Sakin ve ogrenci icin ideal. |
| Stari Grad | ~18 dk | Merkez. Yurume + kisa toplu tasima. Gurultulu olabilir. |
| Vozdovac | ~22 dk | Genis opstina - kuzeyi yakin, guneyi uzak. Ilan hangi mahallede, bak. |
| Palilula | ~26 dk | Merkez kismi yakin, Tuna'nin kuzeyi (Borca, Krnjaca) cok uzak. |
| Zvezdara | ~28 dk | Otobus gerekir. Ic mahalleleri makul, disi uzak. |
| Cukarica | ~28 dk | Otobus/tramvay. Banovo brdo makul, Zeleznik uzak. |
| Novi Beograd | ~30 dk | Nehrin karsisi. Otobus/tramvay ile ~30 dk. Bloklara gore degisir. |
| Rakovica | ~33 dk | Uzak. Sadece ev cok iyiyse degerlendir. |
| Zemun | ~40 dk | Cok uzak, gunluk gidis-gelis yorucu olur. |
| Surcin | ~55 dk | Cok uzak. Onerilmez. |
| Grocka | ~60 dk | Cok uzak. Onerilmez. |
| Obrenovac | ~65 dk | Sehir disi sayilir. Onerilmez. |
| Mladenovac | ~75 dk | Sehir disi sayilir. Onerilmez. |

## Mahalleler

Büyük opštinaların dış mahalleleri, opština ortalamasından belirgin şekilde uzak
olabiliyor. Sistem bu mahalleleri ayrıca tanır.

| Mahalle | Süre |
|---|---|
| Slavija | ~12 dk |
| Cvetni Trg | ~12 dk |
| Kalenic Pijaca | ~15 dk |
| Terazije | ~15 dk |
| Neimar | ~16 dk |
| Banjica | ~20 dk |
| Dorcol | ~22 dk |
| Kalemegdan | ~22 dk |
| Pasino Brdo | ~24 dk |
| Lekino Brdo | ~25 dk |
| Karaburma | ~26 dk |
| Kumodraska | ~26 dk |
| Medakovic | ~28 dk |
| Konjarnik | ~30 dk |
| Banovo Brdo | ~30 dk |
| Olimp | ~30 dk |
| Zarkovo | ~33 dk |
| Cerak | ~33 dk |
| Kumodraz | ~35 dk |
| Visnjica | ~35 dk |
| Mirijevo | ~38 dk |
| Bezanijska Kosa | ~38 dk |
| Blok 45 | ~40 dk |
| Krnjaca | ~40 dk |
| Zeleznik | ~40 dk |
| Resnik | ~45 dk |
| Altina | ~48 dk |
| Borca | ~50 dk |
| Kaludjerica | ~50 dk |
| Vinca | ~50 dk |
| Batajnica | ~55 dk |
| Ripanj | ~55 dk |

## Pratik notlar

- **35 dakikanın üstü günlük gidiş-geliş için yorucudur.** Tıp programının
  ders yoğunluğu düşünülürse, ucuz ama uzak bir ev uzun vadede pahalıya gelir.
- Novi Beograd blokları arasında büyük fark var - blok numarasına bak.
- Voždovac ve Palilula çok geniş; ilanın hangi mahallede olduğu opštinadan
  daha belirleyici.
- Gece geç saatte dönüş olacaksa otobüs hattının gece servisi olup olmadığını
  kontrol et.
