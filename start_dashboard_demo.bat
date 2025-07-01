@echo off
echo 🚀 Avvio Multi-Video Dashboard Demo
echo =====================================
echo.

echo 📦 Verifico dipendenze...
python -c "import http.server, socketserver, json, webbrowser, threading, time" 2>nul
if errorlevel 1 (
    echo ❌ Dipendenze mancanti
    pause
    exit /b 1
)
echo ✅ Dipendenze OK

echo.
echo 🌐 Avvio server HTTP su porta 8000...
echo 📱 Il browser si aprirà automaticamente
echo ⌨️  Premi Ctrl+C per fermare
echo.

python simple_http_server.py
pause
