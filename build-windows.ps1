# Build the double-click Windows app. Run this in PowerShell on a Windows PC.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
    $candidates = @(
        @("py", "-3.15"),
        @("py", "-3.14"),
        @("py", "-3.13"),
        @("py", "-3.12"),
        @("py", "-3"),
        @("python3"),
        @("python")
    )
    foreach ($parts in $candidates) {
        $exe = $parts[0]
        $pyArgs = @()
        if ($parts.Count -gt 1) {
            $pyArgs = $parts[1..($parts.Count - 1)]
        }
        try {
            $null = & $exe @pyArgs --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{ Exe = $exe; Args = $pyArgs }
            }
        } catch {
            continue
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Error @"
Python was not found on PATH.

Fix:
1. In a new PowerShell run:  py -3.15 --version
2. If that works, run the build with:
     py -3.15 -m pip install --upgrade pip
     py -3.15 -m pip install -r requirements.txt -r requirements-build.txt
     py -3.15 -m PyInstaller --noconfirm --clean windows.spec
3. Settings > Apps > Advanced app settings > App execution aliases
   Turn OFF the "python.exe" and "python3.exe" Microsoft Store stubs.
"@
}

$py = $python.Exe
$pyArgs = $python.Args
Write-Host "Using: $py $($pyArgs -join ' ')"
& $py @pyArgs --version

& $py @pyArgs -m pip install --upgrade pip
& $py @pyArgs -m pip install -r requirements.txt -r requirements-build.txt

if (-not $env:TESSERACT_HOME) {
    $default = "C:\Program Files\Tesseract-OCR"
    if (Test-Path $default) {
        $env:TESSERACT_HOME = $default
    }
}

if (-not $env:TESSERACT_HOME) {
    Write-Error "Install Tesseract OCR for Windows, then re-run. Expected folder: C:\Program Files\Tesseract-OCR"
}

& $py @pyArgs -m PyInstaller --noconfirm --clean windows.spec

Write-Host ""
Write-Host "Build folder: $PSScriptRoot\dist\TaxDocInventory"
Write-Host "Zip that folder and send it. Recipients unzip, then double-click TaxDocInventory.exe."
