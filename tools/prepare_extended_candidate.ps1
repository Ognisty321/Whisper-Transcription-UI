[CmdletBinding()]
param(
    [string]$BuildScript = 'tools\build_extended_candidate.ps1'
)
$ErrorActionPreference='Stop'
$p = $BuildScript
$text = Get-Content $p -Raw

# Compatibility hold proven by integration test: XXL's custom vad5_auditok.py
# uses private AudioRegion._meta removed in newer Auditok.
$text = $text.Replace("'auditok==0.5.2'", "'auditok==0.2.0'")

# Explicitly modernize additional audio/MDX helpers that were present in the
# frozen bundle but were not all pulled as direct dependencies by pyannote.
$text = $text.Replace(
    "'einops==0.8.2','torch-audiomentations==0.12.0',",
    "'einops==0.8.2','asteroid-filterbanks==0.4.0','julius==0.2.8','torch-audiomentations==0.12.0','torch-pitch-shift==1.2.5','rotary-embedding-torch==0.9.1',"
)
$text = $text.Replace(
    "'av==17.1.0','librosa==0.11.0','soundfile==0.14.0','soxr==1.1.0','audioread==3.1.0','auditok==0.2.0',",
    "'av==17.1.0','librosa==0.11.0','soundfile==0.14.0','soxr==1.1.0','audioread==3.1.0','pydub==0.25.1','ffmpeg-python==0.2.0','webrtcvad-wheels==2.0.14','auditok==0.2.0',"
)

$needle = "Assert-Native 'stage apply'"
$insert = @"
Assert-Native 'stage apply'
& python tools\overlay_cpython_runtime.py (Join-Path `$workspace 'cpython31021') (Join-Path `$workspace 'cpython31021\PCbuild\amd64') `$contents --output (Join-Path `$report 'cpython-runtime-overlay.json') *>&1 | Tee-Object -FilePath (Join-Path `$report 'cpython-runtime-overlay.txt')
Assert-Native 'CPython 3.10.21 runtime overlay'
"@
if (-not $text.Contains($needle)) { throw 'stage apply insertion point not found' }
$text = $text.Replace($needle, $insert.TrimEnd())

$runtimeNeedle = "Status 'Running CLI smoke tests.'"
$runtimeInsert = @"
Status 'Verifying packaged CPython 3.10.21 runtime and security libraries.'
`$runtimeStdout=Join-Path `$report 'packaged-runtime-info.json'
`$runtimeStderr=Join-Path `$report 'packaged-runtime-info.stderr.txt'
& `$exe --xxl-runtime-info 2> `$runtimeStderr | Set-Content `$runtimeStdout -Encoding utf8
`$runtimeRc=`$LASTEXITCODE
if (`$runtimeRc -ne 0) { throw "Packaged runtime diagnostic failed: `$runtimeRc" }
`$runtimeInfo=Get-Content `$runtimeStdout -Raw | ConvertFrom-Json
if (`$runtimeInfo.python -notmatch '^3\.10\.21') { throw "Packaged Python is not 3.10.21: `$(`$runtimeInfo.python)" }
if (`$runtimeInfo.python_magic -ne '6f0d0d0a') { throw "Packaged bytecode magic mismatch: `$(`$runtimeInfo.python_magic)" }
if (`$runtimeInfo.openssl -notmatch 'OpenSSL 1\.1\.1w') { throw "Packaged OpenSSL is not 1.1.1w: `$(`$runtimeInfo.openssl)" }

Status 'Running CLI smoke tests.'
"@
if (-not $text.Contains($runtimeNeedle)) { throw 'runtime verification insertion point not found' }
$text = $text.Replace($runtimeNeedle, $runtimeInsert.TrimEnd())

Set-Content $p $text -Encoding utf8
Write-Host "Prepared $p for full compatible dependency set + CPython 3.10.21 overlay."
