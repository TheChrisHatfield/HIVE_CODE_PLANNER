# Build Hive Planner portable Windows distribution (PyInstaller onedir).
param(
    [string]$PythonExe = "",
    [switch]$Sign,
    [string]$CertificatePath = "",
    [SecureString]$CertificatePassword
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not $PythonExe) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = "py"
        $PythonArgs = @("-3.11")
    } else {
        $PythonExe = "python"
        $PythonArgs = @()
    }
} else {
    $PythonArgs = @()
}

function Run-Py {
    param([string[]]$CmdArgs)
    & $PythonExe @PythonArgs @CmdArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installing build dependencies..."
Run-Py @("-m", "pip", "install", "-q", "-e", ".[dev,portable]")

Write-Host "Generating Windows version metadata..."
Run-Py @("packaging/gen_version_info.py")

Write-Host "Running PyInstaller (UPX off, Defender-friendly)..."
Run-Py @("-m", "PyInstaller", "packaging/hive_planner_portable.spec", "--noconfirm", "--clean")

$Dist = Join-Path $RepoRoot "dist\HivePlannerPortable"
if (-not (Test-Path $Dist)) {
    throw "Build output not found: $Dist"
}

$ExePath = Join-Path $Dist "HivePlanner.exe"
if (-not (Test-Path $ExePath)) {
    throw "HivePlanner.exe not found in $Dist"
}

if ($Sign) {
    if (-not $CertificatePath) {
        throw "Sign requires -CertificatePath to a .pfx Authenticode certificate"
    }
    $signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $signtool) {
        throw "signtool.exe not found. Install Windows SDK or Visual Studio Build Tools."
    }
    Write-Host "Signing HivePlanner.exe..."
    $signArgs = @(
        "sign",
        "/fd", "SHA256",
        "/tr", "http://timestamp.digicert.com",
        "/td", "SHA256",
        "/f", $CertificatePath,
        $ExePath
    )
    if ($CertificatePassword) {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($CertificatePassword)
        )
        $signArgs = @("sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256", "/f", $CertificatePath, "/p", $plain, $ExePath)
    }
    & $signtool.Source $signArgs
    if ($LASTEXITCODE -ne 0) { throw "signtool sign failed" }
}

Copy-Item -Force (Join-Path $RepoRoot "packaging\PORTABLE_README.md") (Join-Path $Dist "README-PORTABLE.md")
Copy-Item -Force (Join-Path $RepoRoot "packaging\DEFENDER.md") (Join-Path $Dist "DEFENDER.md")

$CliBat = Join-Path $Dist "HivePlanner-cli.bat"
@'
@echo off
setlocal
"%~dp0HivePlanner.exe" --hive-cli %*
'@ | Set-Content -Path $CliBat -Encoding ASCII

$IconSrc = Join-Path $RepoRoot "scripts\assets\HivePlanner.ico"
if (Test-Path $IconSrc) {
    Copy-Item -Force $IconSrc (Join-Path $Dist "HivePlanner.ico")
}

$hashLines = @("# Hive Planner portable build - SHA256", "# Verify before running if Defender flagged the download", "")
Get-ChildItem -Path $Dist -File -Recurse | Sort-Object FullName | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash
    $rel = $_.FullName.Substring($Dist.Length + 1)
    $hashLines += "$hash  $rel"
}
$hashLines | Set-Content -Path (Join-Path $Dist "BUILD-SHA256.txt") -Encoding UTF8

Write-Host ""
Write-Host "Portable build ready:"
Write-Host "  $Dist"
Write-Host ""
Write-Host "Defender: UPX disabled + version metadata embedded. See DEFENDER.md in the dist folder."
if (-not $Sign) {
    Write-Host "Tip: Authenticode signing (-Sign -CertificatePath ...) reduces SmartScreen warnings."
}
Write-Host "Zip that folder to distribute. Run HivePlanner.exe or HivePlanner-cli.bat."
