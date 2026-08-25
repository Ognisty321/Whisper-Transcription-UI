[CmdletBinding()]
param(
    [string]$BuildScript = 'tools\build_extended_candidate.ps1'
)
$ErrorActionPreference='Stop'
$p = $BuildScript
$text = Get-Content $p -Raw
$text = $text.Replace("'auditok==0.5.2'", "'auditok==0.2.0'")

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
& `$exe --xxl-runtime-info *>&1 | Tee-Object -FilePath (Join-Path `$report 'packaged-runtime-info.json')
`$runtimeRc=`$LASTEXITCODE
if (`$runtimeRc -ne 0) { throw "Packaged runtime diagnostic failed: `$runtimeRc" }
`$runtimeInfo=Get-Content (Join-Path `$report 'packaged-runtime-info.json') -Raw | ConvertFrom-Json
if (`$runtimeInfo.python -notmatch '^3\.10\.21') { throw "Packaged Python is not 3.10.21: `$(`$runtimeInfo.python)" }
if (`$runtimeInfo.python_magic -ne '6f0d0d0a') { throw "Packaged bytecode magic mismatch: `$(`$runtimeInfo.python_magic)" }
if (`$runtimeInfo.openssl -notmatch 'OpenSSL 1\.1\.1w') { throw "Packaged OpenSSL is not 1.1.1w: `$(`$runtimeInfo.openssl)" }

Status 'Running CLI smoke tests.'
"@
if (-not $text.Contains($runtimeNeedle)) { throw 'runtime verification insertion point not found' }
$text = $text.Replace($runtimeNeedle, $runtimeInsert.TrimEnd())

Set-Content $p $text -Encoding utf8
Write-Host "Prepared $p for Auditok 0.2.0 + full CPython 3.10.21 overlay."
