# Build Hive Planner portable Windows distribution (PyInstaller onedir).
param(
    [string]$PythonExe = ""
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

Write-Host "Running PyInstaller..."
Run-Py @("-m", "PyInstaller", "packaging/hive_planner_portable.spec", "--noconfirm", "--clean")

$Dist = Join-Path $RepoRoot "dist\HivePlannerPortable"
if (-not (Test-Path $Dist)) {
    throw "Build output not found: $Dist"
}

Copy-Item -Force (Join-Path $RepoRoot "packaging\PORTABLE_README.md") (Join-Path $Dist "README-PORTABLE.md")

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

Write-Host ""
Write-Host "Portable build ready:"
Write-Host "  $Dist"
Write-Host ""
Write-Host "Zip that folder to distribute. Run HivePlanner.exe or HivePlanner-cli.bat."
