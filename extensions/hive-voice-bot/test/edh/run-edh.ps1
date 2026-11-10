# Launches the extension in a real VS Code Extension Development Host and runs test/edh/smoke.js.
# Usage: powershell -File test/edh/run-edh.ps1 [-CodeExe "C:\path\to\Code.exe"]
# Writes the report to %TEMP%\hive-voice-bot-edh-report.json and prints it. Exit 0 only if every check passed.
param(
  [string]$CodeExe = "D:\PROGRAM_FILES\VISUAL_STUDIO\Microsoft VS Code\Code.exe",
  [int]$TimeoutSeconds = 120
)

$ext = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$report = Join-Path $env:TEMP "hive-voice-bot-edh-report.json"
Remove-Item $report -ErrorAction SilentlyContinue
$profile = Join-Path $env:TEMP "hive-edh-profile"

$args = @(
  "--extensionDevelopmentPath=$ext",
  "--extensionTestsPath=$(Join-Path $ext 'test\edh\smoke.js')",
  "--user-data-dir=$profile",
  "--disable-telemetry",
  "--skip-release-notes",
  "--new-window",
  (Join-Path $ext "test\edh\fixture")
)
$proc = Start-Process -FilePath $CodeExe -ArgumentList $args -PassThru

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while (-not (Test-Path $report) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
if (-not (Test-Path $report)) {
  Write-Error "No EDH report after $TimeoutSeconds s (host pid $($proc.Id))."
  exit 2
}
$json = Get-Content $report -Raw
$json
$passed = ($json | ConvertFrom-Json).passed
if ($passed) { exit 0 } else { exit 1 }
