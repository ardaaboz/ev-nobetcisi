# Nobet dongusunu Windows acilisina baglar.
#
# Oturum acildiginda otomatik baslar, bilgisayar kapanana kadar calisir.
# Kullanici duzeyinde bir gorev, yonetici yetkisi gerekmiyor.
#
# Kurmak icin:   .\scripts\gorev-kur.ps1
# Kaldirmak icin: .\scripts\gorev-kur.ps1 -Kaldir

param(
    [switch]$Kaldir
)

$ErrorActionPreference = "Stop"
$GorevAdi = "EvNobetcisi"
$proje = Split-Path $PSScriptRoot -Parent

if ($Kaldir) {
    if (Get-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $GorevAdi -Confirm:$false
        Write-Host "Gorev kaldirildi."
    } else {
        Write-Host "Gorev zaten yok."
    }
    return
}

$eylem = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$proje\scripts\nobet-dongusu.ps1`"" `
    -WorkingDirectory $proje

# Oturum acilisindan 1 dakika sonra: ag baglantisinin oturmasini bekliyoruz.
$tetik = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$tetik.Delay = "PT1M"

$ayarlar = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)   # sinirsiz: bilgisayar kapanana kadar

if (Get-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $GorevAdi -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $GorevAdi `
    -Action $eylem `
    -Trigger $tetik `
    -Settings $ayarlar `
    -Description "Belgrad ev nobetcisi: bilgisayar acikken 5 dakikada bir tarar" | Out-Null

Write-Host "Gorev kuruldu: $GorevAdi"
Write-Host "  Oturum acildiktan 1 dakika sonra basliyor."
Write-Host "  Bilgisayar kapanana kadar 5 dakikada bir tariyor."
Write-Host ""
Write-Host "Hemen baslatmak icin:  Start-ScheduledTask -TaskName $GorevAdi"
Write-Host "Durumu gormek icin:    Get-ScheduledTask -TaskName $GorevAdi | Get-ScheduledTaskInfo"
Write-Host "Kaldirmak icin:        .\scripts\gorev-kur.ps1 -Kaldir"
