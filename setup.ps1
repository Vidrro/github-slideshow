# =============================================================================
#  setup.ps1  -  Arranque del predictor del Mundial 2026 (Dixon-Coles)
# -----------------------------------------------------------------------------
#  Instala dependencias en un entorno virtual aislado (.venv), ejecuta la
#  pipeline completa y lanza el dashboard. Se ejecuta SIEMPRE desde la carpeta
#  del proyecto (no importa desde dónde lo invoques), así que evita los errores
#  de "No such file or directory".
#
#  Uso (PowerShell, dentro de la carpeta del proyecto):
#      .\setup.ps1                 # instala + pipeline + dashboard
#      .\setup.ps1 -NoDashboard    # solo instala y corre la pipeline
#      .\setup.ps1 -SkipInstall    # salta la instalacion (deps ya presentes)
#
#  Si PowerShell bloquea el script por la politica de ejecucion, corre:
#      powershell -ExecutionPolicy Bypass -File .\setup.ps1
# =============================================================================
[CmdletBinding()]
param(
    [switch]$NoDashboard,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

# Trabajar siempre desde la carpeta de este script (la raiz del proyecto).
Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Mundial 2026 - Predictor Dixon-Coles" -ForegroundColor Cyan
Write-Host " Proyecto: $PSScriptRoot" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# --- 1. Comprobar Python -----------------------------------------------------
try {
    $pyVersion = & python --version 2>&1
} catch {
    Write-Host "ERROR: No se encontro 'python' en el PATH." -ForegroundColor Red
    Write-Host "Instala Python 3.10+ desde https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "y marca 'Add python.exe to PATH' durante la instalacion." -ForegroundColor Yellow
    exit 1
}
Write-Host "Python detectado: $pyVersion" -ForegroundColor Green

# --- 2. Entorno virtual aislado ---------------------------------------------
$venvPath = Join-Path $PSScriptRoot ".venv"
$venvPy   = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "Creando entorno virtual en .venv ..." -ForegroundColor Cyan
    & python -m venv $venvPath
}
Write-Host "Entorno virtual: $venvPy" -ForegroundColor Green

# --- 3. Dependencias ---------------------------------------------------------
if (-not $SkipInstall) {
    Write-Host "Actualizando pip e instalando dependencias..." -ForegroundColor Cyan
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
} else {
    Write-Host "Saltando instalacion de dependencias (-SkipInstall)." -ForegroundColor Yellow
}

# --- 4. Pipeline (ingesta -> features -> modelo -> prediccion -> backtest) ----
Write-Host "Ejecutando la pipeline completa..." -ForegroundColor Cyan
& $venvPy (Join-Path $PSScriptRoot "run_all.py")

# --- 5. Dashboard ------------------------------------------------------------
if (-not $NoDashboard) {
    Write-Host "Lanzando el dashboard (Ctrl+C para detener)..." -ForegroundColor Cyan
    & $venvPy -m streamlit run (Join-Path $PSScriptRoot "dashboard.py")
} else {
    Write-Host "Listo. Para abrir el dashboard luego:" -ForegroundColor Green
    Write-Host "    .\dashboard.ps1" -ForegroundColor Green
}
