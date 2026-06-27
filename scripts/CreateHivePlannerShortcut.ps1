# Creates a Windows shortcut with the Hive Planner icon.
# .bat files cannot embed icons; use HivePlanner.lnk (or a Desktop shortcut) instead.
param(
    [switch]$Desktop
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here "..")).Path
$icon = Join-Path $here "assets\HivePlanner.ico"
$target = Join-Path $here "HivePlanner.vbs"

if (-not (Test-Path $icon)) {
    Write-Error "Icon not found: $icon"
}
if (-not (Test-Path $target)) {
    Write-Error "Launcher not found: $target"
}

function New-HiveShortcut {
    param(
        [string]$LinkPath
    )
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($LinkPath)
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = $repo
    $shortcut.IconLocation = "$icon,0"
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Hive Planner - local planning control for Cursor"
    $shortcut.Save()
    Write-Host "Created: $LinkPath"
}

$localLink = Join-Path $here "HivePlanner.lnk"
New-HiveShortcut -LinkPath $localLink

if ($Desktop) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    New-HiveShortcut -LinkPath (Join-Path $desktop "Hive Planner.lnk")
}
