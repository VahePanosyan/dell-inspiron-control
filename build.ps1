$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m PyInstaller --noconfirm DellInspironControl.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
python package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed' }
