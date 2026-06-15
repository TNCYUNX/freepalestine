@echo off
:: Scriptin bulundugu asil klasoru kilitliyoruz
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo.
echo ======================================================
echo   VERITAS SMS BOT: IZOLE FIZIKSEL YEDEKLEME
echo ======================================================
echo.

:: 1. TARIH VE SAATI AL
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'dd.MM.yyyy - HH.mm'"`) do set cur_dt=%%i

:: 2. YEDEK ACIKLAMASI SOR
set /p yedek_ismi="Yedek aciklamasi ne olsun?: "
if "!yedek_ismi!"=="" set yedek_ismi=Guncelleme

:: Klasor Adi ve Commit Mesaji
set folder_name=veritas_bot - !cur_dt!
set commit_msg=!yedek_ismi! - !cur_dt!

:: Mevcut bot klasorunun tam yolunu hafizaya aliyoruz
set "PROJECT_DIR=%~dp0"
if "!PROJECT_DIR:~-1!"=="\" set "PROJECT_DIR=!PROJECT_DIR:~0,-1!"

:: 3. BAGIMSIZ VE IZOLE GIT ODASI OLUSTUR
set "TEMP_GIT_DIR=%TEMP%\VeritasGitBackup"
if exist "!TEMP_GIT_DIR!" rd /s /q "!TEMP_GIT_DIR!"
mkdir "!TEMP_GIT_DIR!"
cd /d "!TEMP_GIT_DIR!"

echo [*] Bagimsiz Git ortami hazirlaniyor...
git init
git config --local user.email "admin@veritassms.com"
git config --local user.name "Veritas Admin"
git remote add origin https://github.com/TNCYUNX/freepalestine.git

:: KRITIK YAMA: Bilgisayardaki dal ismini (master) zorla (main) yapiyoruz
git branch -M main

echo [*] GitHub ile senkronizasyon yapiliyor (Pull)...
git pull origin main --rebase --autostash >nul 2>&1

echo.
echo [*] Sadece bot dosyalari kopyalaniyor: [!folder_name!]
mkdir "!folder_name!"
:: Sadece bot klasorundeki dosyalari bu izole odaya aliyoruz
xcopy /s /e /q /y /i "!PROJECT_DIR!\*.*" "!folder_name!\"

:: 4. YUKLEME VE PUSH
echo [*] Degisiklikler sahneye aliniyor...
git add "!folder_name!"

echo [*] Kayit olusturuluyor: !commit_msg!
git commit -m "!commit_msg!"

echo [*] GitHub'a gonderiliyor (Push)...
git push -u origin main

:: 5. TEMIZLIK (Izole odayi imha et)
cd /d "!PROJECT_DIR!"
rd /s /q "!TEMP_GIT_DIR!"

if %errorlevel% equ 0 (
    echo.
    echo ======================================================
    echo   [+] YEDEKLEME BASARILI!
    echo   [-] Klasor: !folder_name!
    echo ======================================================
) else (
    echo.
    echo [!] Bir hata olustu. GitHub yetkinizi kontrol edin.
)

echo.
pause