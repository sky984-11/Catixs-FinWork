$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  if (-not (Test-Path ".\node_modules")) {
    npm install
  }
  npm run dist
  Write-Host ""
  Write-Host "Build finished. Output:"
  Get-ChildItem ".\release" -File | Select-Object FullName, Length, LastWriteTime
}
finally {
  Pop-Location
}
