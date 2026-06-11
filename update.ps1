# =============================================================================
#  update.ps1  -  Actualizacion diaria durante el Mundial 2026
# -----------------------------------------------------------------------------
#  Reingiere resultados nuevos, reestima el modelo y regenera las predicciones
#  de los partidos pendientes. Luego puedes recargar el dashboard para ver los
#  numeros actualizados. Se ejecuta siempre desde la carpeta del proyecto.
#
#  Uso:  .\update.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

Write-Host "Actualizando resultados y prediciones con: $py" -ForegroundColor Cyan
& $py (Join-Path $PSScriptRoot "update.py")

Write-Host "Listo. Abre o recarga el dashboard con .\dashboard.ps1" -ForegroundColor Green
