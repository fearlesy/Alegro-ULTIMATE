# build.ps1 - PowerShell Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ALEGRO ULTIMATE EXE DERLEYICI" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Temizlik
Write-Host "[1/6] Eski dosyalar temizleniyor..." -ForegroundColor Gray
Remove-Item -Path "build", "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "AlegroUltimate.spec" -Force -ErrorAction SilentlyContinue

# 2. Dosya kontrolleri
Write-Host "[2/6] Dosya kontrolleri yapılıyor..." -ForegroundColor Gray
if (-not (Test-Path "AlegroM.py")) {
    Write-Host "HATA: AlegroM.py bulunamadı!" -ForegroundColor Red
    pause
    exit
}

if (Test-Path "icon.ico") {
    Write-Host "✓ icon.ico dosyası mevcut" -ForegroundColor Green
} else {
    Write-Host "UYARI: icon.ico bulunamadı! Varsayılan ikon kullanılacak." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}

# 3. Bağımlılık kontrolü
Write-Host "[3/6] Bağımlılıklar kontrol ediliyor..." -ForegroundColor Gray
try {
    Import-Module PySide6 -ErrorAction Stop
    Write-Host "✓ PySide6 yüklü" -ForegroundColor Green
} catch {
    Write-Host "✗ PySide6 YÜKLÜ DEĞİL" -ForegroundColor Red
    Write-Host "Lütfen çalıştırın: pip install PySide6" -ForegroundColor Yellow
}

try {
    Import-Module psutil -ErrorAction Stop
    Write-Host "✓ psutil yüklü" -ForegroundColor Green
} catch {
    Write-Host "✗ psutil YÜKLÜ DEĞİL" -ForegroundColor Red
    Write-Host "Lütfen çalıştırın: pip install psutil" -ForegroundColor Yellow
}

# 4. Derleme
Write-Host "[4/6] EXE derleniyor... (Bu 1-2 dakika sürebilir)" -ForegroundColor Gray
pyinstaller --onefile --windowed --icon=icon.ico --name="AlegroUltimate" --clean AlegroM.py

# 5. Kontrol
Write-Host "[5/6] Derleme tamamlandı. Kontrol ediliyor..." -ForegroundColor Gray
if (Test-Path "dist\AlegroUltimate.exe") {
    Write-Host "✓ BAŞARILI: EXE oluşturuldu!" -ForegroundColor Green
    Write-Host ""
    
    $exeInfo = Get-Item "dist\AlegroUltimate.exe"
    Write-Host "Dosya Bilgileri:" -ForegroundColor Cyan
    Write-Host "  Ad: $($exeInfo.Name)" -ForegroundColor White
    Write-Host "  Boyut: $([math]::Round($exeInfo.Length/1MB, 2)) MB" -ForegroundColor White
    Write-Host "  Oluşturulma: $($exeInfo.CreationTime)" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "! HATA: EXE oluşturulamadı!" -ForegroundColor Red
    pause
    exit
}

# 6. Talimatlar
Write-Host "[6/6] Test önerileri:" -ForegroundColor Gray
Write-Host ""
Write-Host "TEST 1: EXE'yi çalıştır" -ForegroundColor Cyan
Write-Host "  cd dist" -ForegroundColor White
Write-Host "  .\AlegroUltimate.exe" -ForegroundColor White
Write-Host ""
Write-Host "TEST 2: Yönetici olarak çalıştır" -ForegroundColor Cyan
Write-Host "  Sağ tık -> 'Yönetici olarak çalıştır'" -ForegroundColor White
Write-Host ""
Write-Host "EXE konumu:" -ForegroundColor Cyan
Write-Host "  $PWD\dist\AlegroUltimate.exe" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   DERLEME TAMAMLANDI!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
pause