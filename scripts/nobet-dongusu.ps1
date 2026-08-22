# Yerel nobet dongusu. Bilgisayar acikken surekli calisir.
#
# Neden var: halooglasi sunucu IP'lerini engelliyor, bu yuzden bulut isi o
# siteden ilan cekemiyor. Normal bir ev baglantisindan ise sorunsuz geliyor.
# Bu dongu, bilgisayar acik oldugu surece ucuncu kaynagi da kapsar.
#
# Her turda:
#   1. Uzaktaki durumu yereldekiyle BIRLESTIRIR (ezmez)
#   2. Tarar, henuz bildirilmemis olanlari gruba gonderir
#   3. Durumu uzaga gonderir
#   4. 5 dakika bekler
#
# Acilista otomatik baslamasi icin: scripts/gorev-kur.ps1
# Durdurmak icin pencereyi kapat ya da Ctrl+C.

param(
    # Tek tur calisip cikar. Kurulumu dogrulamak icin.
    [switch]$Tek
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"

$ARALIK = 300   # 5 dakika

function Yaz($mesaj) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $mesaj"
}

function Durumu-Gonder {
    git add state/
    git diff --staged --quiet
    if ($LASTEXITCODE -eq 0) { return }

    git commit --quiet -m "durum guncellendi (yerel) [skip ci]"
    for ($d = 1; $d -le 3; $d++) {
        git push --quiet 2>$null
        if ($LASTEXITCODE -eq 0) { return }
        Yaz "  push carpisti, yeniden deneniyor ($d)"
        git pull --quiet --rebase --autostash 2>$null
    }
    Yaz "  UYARI: durum gonderilemedi, sonraki turda tekrar denenecek"
}

Yaz "Nobet dongusu basladi. Bilgisayar acik oldugu surece calisacak."

$tur = 0
while ($true) {
    $tur++
    Yaz "tur $tur"

    # Buluttaki kayitlari al ki onun gonderdiklerini tekrar gondermeyelim.
    python scripts/uzak-durumu-al.py

    python run.py
    if ($LASTEXITCODE -ne 0) {
        Yaz "  UYARI: bu tur hata verdi, devam ediliyor"
    }

    Durumu-Gonder

    if ($Tek) {
        Yaz "tek tur modu, cikiliyor"
        break
    }
    Start-Sleep -Seconds $ARALIK
}
