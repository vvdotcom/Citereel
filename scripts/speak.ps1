param([Parameter(Mandatory=$true)][string]$TextPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$voiceEngine = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voiceEngine.Rate = 0
    $voiceEngine.SetOutputToWaveFile($OutputPath)
    $voiceEngine.Speak([System.IO.File]::ReadAllText($TextPath))
} finally { $voiceEngine.Dispose() }
