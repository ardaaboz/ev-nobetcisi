# Betikler

| Betik | Ne yapar |
|---|---|
| `smoke.py` | Canlı duman testi. Üç kaynak ayakta mı, şemalar bozulmuş mu? |
| `yerel-kosu.ps1` | Yerel nöbetçi koşusu (Windows). halooglasi dahil üç kaynak. |

## Neden yerel koşu gerekiyor

halooglasi veri merkezi IP bloklarını engelliyor. GitHub Actions Azure'dan
çıktığı için o kaynak orada 403 alıyor. 2026-08-21'de ölçüldü: beş farklı
curl varyantı ve sitenin ana sayfası dahil hepsi 403. Aynı komutlar normal
bir ev bağlantısından 200 dönüyor.

Sonuç olarak sistem iki katmanlı çalışıyor:

| Katman | Kaynaklar | Ne zaman |
|---|---|---|
| GitHub Actions | CityExpert + 4zida | 7/24, 5 dakikada bir |
| Yerel koşu | + halooglasi | Bilgisayar açıkken |

İkisi de aynı `state/listings.db` dosyasını repo üzerinden paylaşır, bu yüzden
aynı ilan iki kez bildirilmez. Yerel koşu olmadan da sistem çalışır, sadece
halooglasi ilanları gelmez.

## Kurulum

Repoyu klonla ve bağımlılıkları kur:

```bash
git clone https://github.com/ardaaboz/belgrade-rental-watcher.git
```

```bash
python -m pip install -e .
```

`.env` dosyasını oluştur (`.env.example` dosyasını kopyala) ve Telegram
bilgilerini yaz. Bu dosya repoya gitmez.

Tek seferlik dene:

```powershell
.\scripts\yerel-kosu.ps1
```

## Zamanlanmış görev olarak kurmak

Her 10 dakikada bir otomatik çalışması için, PowerShell'i **yönetici olarak**
açıp aşağıdakini çalıştır. `PROJE_YOLU` kısmını kendi klasör yolunla değiştir:

```powershell
$proje = "PROJE_YOLU"
$eylem = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -File `"$proje\scripts\yerel-kosu.ps1`""
$tetik = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "EvNobetcisi" -Action $eylem -Trigger $tetik -Description "Belgrad ev nobetcisi yerel kosu"
```

Görevi kaldırmak için:

```powershell
Unregister-ScheduledTask -TaskName "EvNobetcisi" -Confirm:$false
```

Bu komut bilgisayarında zamanlanmış görev oluşturur. Ne yaptığını görmeden
çalıştırma; istersen önce betiği elle deneyip sonucu gör.
