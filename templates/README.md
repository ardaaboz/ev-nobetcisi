# Mesaj Şablonları

Bu dosyalar doğrudan düzenlenebilir. Kod değiştirmeye gerek yok, kaydet ve bitti.

| Dosya | Ne zaman kullanılır |
|---|---|
| `ev_sahibi.sr.txt` / `.tr.txt` | İlan doğrudan ev sahibinden (`vlasnik`) |
| `emlakci.sr.txt` / `.tr.txt` | İlan emlakçıdan |

`.sr` Sırpça (gönderilen metin), `.tr` Türkçe (ne gönderdiğini bilmen için).
İkisini birlikte güncelle, yoksa çeviri metinle uyuşmaz.

Metin her ilanda aynıdır ve bildirimlerle gönderilmez; gruba bir kez
sabitlenir. Bu yüzden ilana özel bilgi (fiyat, semt) içermemeli.

## Kullanılabilecek yer tutucular

| Yer tutucu | Ne gelir | Örnek |
|---|---|---|
| `{student}` | Öğrenci kelimesi, cinsiyete göre | `Studentkinja` / `Student` |
| `{uredan_c}` | "düzenli", cümle başı büyük harf | `Uredna` / `Uredan` |
| `{miran}` | "sessiz" | `mirna` / `miran` |

Cinsiyet `.env` içindeki `USER_GENDER` ile belirlenir (`f` veya `m`).

Yer tutucu kullanmak zorunda değilsin, düz metin de yazabilirsin. Ama
yazdığın bir yer tutucu listede yoksa sistem hata verir ve o ilan için
bildirim gitmez.

## Yazarken dikkat

**Doğru olmayan bir şey yazma.** Sigara içmiyorum, peşin ödeyebilirim gibi
ifadeler ev sahibiyle yüz yüze gelince ters teper. Şu an şablonlarda
bilinçli olarak yok.

**Vergi ve beli karton (prijava boravišta) buraya girmemeli.** İlk mesajın
işi randevu almak. İdari konular ev gezildikten sonra açılır
(bkz. `docs/kiralama-rehberi/beli-karton-notu.md`). Bu kural teste bağlı:
o kelimelerden biri şablona girerse `pytest` kırılır.

**Kısa tut.** Uzun ve savunmacı metin yanlış sinyal verir. Test 90 kelimede
sınır koyuyor.

**Sırpçayı sade tut.** Yüz yüze görüşmede tutturamayacağın bir seviyede
yazmak tutarsızlık yaratır.

## Değişiklikten sonra kontrol

```bash
python -m pytest tests/test_outreach.py -q
```

```bash
python scripts/sabit-mesaj.py --goster
```

Yeni metni gruba gönderip sabitlemek için `--goster` olmadan çalıştır.
