@echo off
echo ==========================================
echo   Verificador de Tweets - Iniciando...
echo ==========================================
echo.

python --version
if errorlevel 1 (
    echo ERROR: Python no esta instalado.
    echo Descargalo en: https://www.python.org/downloads/
    echo Marca la casilla "Add Python to PATH" al instalar.
    pause
    exit
)

echo.
echo Instalando dependencias (puede tardar 1-2 minutos)...
pip install streamlit anthropic duckduckgo-search
if errorlevel 1 (
    echo.
    echo ERROR al instalar dependencias.
    pause
    exit
)

echo.
echo ==========================================
echo   Abriendo en el navegador...
echo   Para cerrar: Ctrl+C en esta ventana
echo ==========================================
echo.
python -m streamlit run app.py
pause
