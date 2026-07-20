$ErrorActionPreference = "Stop"

python -m pip install -r requirements-dev.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name id14-volume-control `
    --paths src `
    src/id14_tray.py

Write-Host "Built dist/id14-volume-control.exe"
