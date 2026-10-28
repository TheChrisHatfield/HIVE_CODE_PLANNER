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

function Clear-PortableDist {
    # PyInstaller COLLECT deletes dist\HivePlannerPortable in place. On Windows that
    # fails with Access Denied when HivePlanner.exe (or another process) still holds
    # a DLL under _internal. Rename-aside clears the path name so COLLECT can proceed.
    param([Parameter(Mandatory = $true)][string]$DistPath)

    if (-not (Test-Path -LiteralPath $DistPath)) {
        return
    }

    $exePath = Join-Path $DistPath "HivePlanner.exe"
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq "HivePlanner.exe" -and
            $_.ExecutablePath -and
            ($_.ExecutablePath -ieq $exePath)
        } |
        ForEach-Object {
            Write-Host "Stopping running portable HivePlanner.exe (PID $($_.ProcessId))..."
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Milliseconds 400

    try {
        Remove-Item -LiteralPath $DistPath -Recurse -Force -ErrorAction Stop
        Write-Host "Cleared previous dist: $DistPath"
        return
    } catch {
        Write-Host "Could not delete previous dist (file in use). Renaming aside..."
    }

    $parent = Split-Path -Parent $DistPath
    $staleName = "HivePlannerPortable_stale_{0}" -f (Get-Date -Format "yyyyMMddHHmmss")
    $stalePath = Join-Path $parent $staleName
    try {
        Rename-Item -LiteralPath $DistPath -NewName $staleName -ErrorAction Stop
    } catch {
        throw @"
Cannot clear '$DistPath' for rebuild (Access Denied).
Close HivePlanner.exe if it is running, close Explorer windows on that folder, then retry.
If Cursor Computer Use is active, end that session or retry after it releases DLLs under _internal.
Original error: $($_.Exception.Message)
"@
    }
    Write-Host "Moved locked dist aside: $stalePath"
    Write-Host "(Delete that folder later when nothing is using it.)"
}

Write-Host "Installing build dependencies..."
Run-Py @("-m", "pip", "install", "-q", "-e", ".[dev,portable,pdf]")

Write-Host "Generating Windows version metadata..."
Run-Py @("packaging/gen_version_info.py")

# A prior portable Hive Planner launch can leave these pointing at an incomplete
# dist/_internal/_tcl_data path, which makes PyInstaller skip Tcl/Tk data.
Remove-Item Env:TCL_LIBRARY -ErrorAction SilentlyContinue
Remove-Item Env:TK_LIBRARY -ErrorAction SilentlyContinue

$Dist = Join-Path $RepoRoot "dist\HivePlannerPortable"
Write-Host "Preparing dist folder..."
Clear-PortableDist -DistPath $Dist

Write-Host "Running PyInstaller (UPX off, Defender-friendly)..."
Run-Py @("-m", "PyInstaller", "packaging/hive_planner_portable.spec", "--noconfirm", "--clean")
if (-not (Test-Path $Dist)) {
    throw "Build output not found: $Dist"
}

$ExePath = Join-Path $Dist "HivePlanner.exe"
if (-not (Test-Path $ExePath)) {
    throw "HivePlanner.exe not found in $Dist"
}

$TclData = Join-Path $Dist "_internal\_tcl_data"
$TkData = Join-Path $Dist "_internal\_tk_data"
if (-not (Test-Path (Join-Path $TclData "init.tcl"))) {
    throw "Tcl data missing after build: $TclData (init.tcl). Clear TCL_LIBRARY/TK_LIBRARY and rebuild."
}
if (-not (Test-Path (Join-Path $TkData "pkgIndex.tcl"))) {
    throw "Tk data missing after build: $TkData. Clear TCL_LIBRARY/TK_LIBRARY and rebuild."
}
Write-Host "Verified Tcl/Tk data dirs under _internal."

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

Write-Host "Staging portable Tesseract OCR (if installed)..."
$VendorTess = Join-Path $Dist "vendor\tesseract"
& (Join-Path $RepoRoot "scripts\stage_tesseract.ps1") -TargetDir $VendorTess -ScanDDrive

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
