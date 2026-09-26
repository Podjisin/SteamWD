# Build a standalone SteamWD.exe with PyInstaller.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$python = (Get-Command python -ErrorAction Stop).Source

Push-Location $root
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name SteamWD `
        --paths src `
        --collect-submodules keyring.backends `
        --copy-metadata keyring `
        src\steamwd\__main__.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    Write-Host "Built: $(Join-Path $root 'dist\SteamWD.exe')"
}
finally {
    Pop-Location
}
