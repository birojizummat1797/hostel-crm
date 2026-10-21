@echo off
chcp 65001 >nul
title Y.S.H. ERP - Fullstack v5.0 Server

:: 1. SHU YERGA SUPABASE POSTGRESQL LINKINGIZNI QO'YING (Qo'shtirnoqsiz):
set DATABASE_URL=postgresql://postgres.xxxx:parol@aws-0-eu-central-1.pooler.supabase.com:6543/postgres

echo =========================================================
echo   🏨 Y.S.H. ERP FULLSTACK PLATFORMA ISHGA TUSHMOQDA...
echo =========================================================
echo.
echo 💻 Kompyuterning o'zida kirish manzili:
echo    http://127.0.0.1:8000
echo.
echo 📱 Hostel Wi-Fi'ga ulangan TELEFONLARDAN kirish manzili:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    echo    http://%%a:8000  ^(Bo'sh joylarsiz yozing^)
)
echo =========================================================
echo ⚠️ Dastur ishlashi uchun ushbu qora oynani yopmang! (Pastga tushirib qo'ying)
echo.

:: Brauzerni avtomatik ochish
start http://127.0.0.1:8000

:: Serverni barcha qurilmalar uchun yoqish
python -m uvicorn fullstack_server:app --host 0.0.0.0 --reload --port 8000
pause