# Stage portable Tesseract OCR into vendor/tesseract (and optionally dist folder).
param(
    [string]$TargetDir = "",
    [string]$SourceExe = "",
    [switch]$ScanDDrive
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $TargetDir) {
    $TargetDir = Join-Path $RepoRoot "vendor\tesseract"
}

function Test-TesseractInstall {
    param([string]$ExePath)
    if (-not (Test-Path $ExePath)) { return $false }
    $root = Split-Path -Parent $ExePath
    $tessdata = Join-Path $root "tessdata"
    if (-not (Test-Path (Join-Path $tessdata "eng.traineddata"))) { return $false }
    return $true
}

function Find-TesseractExe {
    param([string]$Hint)
    if ($Hint -and (Test-TesseractInstall $Hint)) { return (Resolve-Path $Hint).Path }

    $envHint = $env:HIVE_TESSERACT_EXE
    if ($envHint -and (Test-TesseractInstall $envHint)) { return (Resolve-Path $envHint).Path }

    $candidates = @(
        "D:\Program Files\Tesseract-OCR\tesseract.exe",
        "D:\Tesseract-OCR\tesseract.exe",
        "D:\tools\Tesseract-OCR\tesseract.exe",
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    )
    foreach ($path in $candidates) {
        if (Test-TesseractInstall $path) { return $path }
    }

    $which = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($which -and (Test-TesseractInstall $which.Source)) { return $which.Source }

    if ($ScanDDrive -and (Test-Path "D:\")) {
        Write-Host "Scanning D: for tesseract.exe (may take a minute)..."
        $found = Get-ChildItem -Path "D:\" -Filter "tesseract.exe" -Recurse -ErrorAction SilentlyContinue |
            Where-Object { Test-TesseractInstall $_.FullName } |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }

    return $null
}

$exe = Find-TesseractExe -Hint $SourceExe
if (-not $exe) {
    Write-Warning "Tesseract not found. OCR will use system install at runtime if available."
    Write-Warning "Install to D:\Program Files\Tesseract-OCR or set HIVE_TESSERACT_EXE, then re-run."
    exit 0
}

$sourceRoot = Split-Path -Parent $exe
$tessdata = Join-Path $sourceRoot "tessdata"
Write-Host "Staging Tesseract from: $exe"
Write-Host "Target: $TargetDir"

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
Copy-Item -Force $exe (Join-Path $TargetDir "tesseract.exe")

$destTess = Join-Path $TargetDir "tessdata"
if (Test-Path $destTess) { Remove-Item -Recurse -Force $destTess }
Copy-Item -Recurse -Force $tessdata $destTess

# Copy common DLL dependencies next to tesseract.exe when present.
Get-ChildItem -Path $sourceRoot -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -Force $_.FullName (Join-Path $TargetDir $_.Name)
}

@"
Hive Planner bundled Tesseract OCR
==================================
Auto-staged from: $exe

Used for image-only PDF conversion during Load Sources ingest.
Override with HIVE_TESSERACT_EXE if needed.
"@ | Set-Content -Path (Join-Path $TargetDir "README.txt") -Encoding UTF8

Write-Host "Tesseract staged successfully."
