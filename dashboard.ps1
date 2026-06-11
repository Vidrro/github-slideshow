# =============================================================================
#  dashboard.ps1  -  Lanza el dashboard del Mundial 2026
# -----------------------------------------------------------------------------
#  Abre el dashboard de Streamlit usando el entorno virtual del proyecto si
#  existe (.venv), o el Python del sistema en su defecto. Se ejecuta siempre
#  desde la carpeta del proyecto.
#
#  Uso:  .\dashboard.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

Write-Host "Lanzando dashboard con: $py (Ctrl+C para detener)" -ForegroundColor Cyan
& $py -m streamlit run (Join-Path $PSScriptRoot "dashboard.py")
