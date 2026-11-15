# T033 gap A: synthesize WAV fixtures from fixtures.json with Windows SAPI (offline).
# Output: scripts/stt_pin/fixtures/*.wav, 16 kHz, 16-bit, mono.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $here "fixtures"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$manifest = Get-Content (Join-Path $here "fixtures.json") -Raw | ConvertFrom-Json
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
foreach ($clip in $manifest.clips) {
    $path = Join-Path $outDir $clip.file
    $synth.SetOutputToWaveFile($path, $fmt)
    $synth.Speak($clip.reference)
    $synth.SetOutputToNull()
    Write-Output ("wrote {0} ({1} bytes)" -f $clip.file, (Get-Item $path).Length)
}
$synth.Dispose()
