# Yerel nobetci kosusu (Windows / PowerShell)
#
# Neden var: halooglasi veri merkezi IP'lerini engelliyor, bu yuzden GitHub
# Actions'tan cekilemiyor. Normal bir internet baglantisindan ise sorunsuz
# geliyor. Bu betik ucuncu kaynagi da kapsayan bir kosu yapar.
#
# Durum veritabanini repo uzerinden paylasir: once ceker, sonra kosar, sonra
# geri gonderir. Boylece Actions ile ayni ilanlari iki kez bildirmez.
#
# Kullanim:
#   .\scripts\yerel-kosu.ps1
#
# Zamanlanmis gorev olarak kurmak icin (her 10 dakikada bir):
#   scripts/README.md dosyasina bak.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "[1/4] Uzaktaki durum cekiliyor..."
git pull --rebase --autostash --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warning "git pull basarisiz. Cakisma olabilir, elle bakman gerekiyor."
    exit 1
}

Write-Host "[2/4] Nobetci calisiyor..."
python run.py
$runExit = $LASTEXITCODE

Write-Host "[3/4] Durum kaydediliyor..."
git add state/
git diff --staged --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "      durum degismedi"
} else {
    git commit --quiet -m "durum guncellendi (yerel kosu) [skip ci]"
    Write-Host "[4/4] Gonderiliyor..."
    for ($i = 1; $i -le 3; $i++) {
        git push --quiet
        if ($LASTEXITCODE -eq 0) { break }
        Write-Host "      push carpisti, yeniden deneniyor ($i)"
        git pull --rebase --autostash --quiet
    }
}

if ($runExit -ne 0) {
    Write-Warning "run.py $runExit koduyla cikti."
    exit $runExit
}
Write-Host "Bitti."
