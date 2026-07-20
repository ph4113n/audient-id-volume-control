$ErrorActionPreference = "Stop"

python -m pip install -r requirements-dev.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name audient-id-volume-control `
    --paths src `
    src/id14_tray.py

$archive = "dist/audient-id-volume-control-windows.zip"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

Compress-Archive `
    -Path "dist/audient-id-volume-control" `
    -DestinationPath $archive `
    -CompressionLevel Optimal

Write-Host "Built $archive"
