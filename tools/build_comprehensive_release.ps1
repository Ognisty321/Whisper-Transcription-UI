[CmdletBinding()]
param(
    [string]$OriginalUrl = 'https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_windows.7z',
    [Int64]$OriginalSize = 1424256246,
    [string]$OriginalSha256 = '237DEE23939CDABFC96EF859FC5E584B842C3A5557E0D2CA744E1F87C14C5844',
    [string]$ArchiveName = 'Faster-Whisper-XXL_r245.4_Modernized2_RTX50_CUDA128_Windows_x64.zip',
    [string]$GitSha = $env:GITHUB_SHA,
    [switch]$SkipHosting
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HUB_ENABLE_HF_TRANSFER = '0'
$env:PYTHONNOUSERSITE = '1'

$workspace = (Get-Location).Path
$work = Join-Path $workspace 'modern2-work'
$report = Join-Path $workspace 'modern2-report'
Remove-Item $work, $report -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $work, $report | Out-Null

function Assert-NativeSuccess {
    param([string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

function Write-Status {
    param([string]$Message)
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    "[$stamp] $Message" | Tee-Object -FilePath (Join-Path $report 'build-status.txt') -Append
}

function Get-DirectorySize {
    param([string]$Path)
    return (Get-ChildItem $Path -Recurse -File | Measure-Object Length -Sum).Sum
}

$tests = [ordered]@{}
function Invoke-XxlTest {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$OutputDirectory = '',
        [switch]$RequireOutput
    )
    $log = Join-Path $report ("test-" + $Name + '.txt')
    if ($OutputDirectory) {
        Remove-Item $OutputDirectory -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    }
    $started = Get-Date
    Push-Location $script:bundleRoot
    try {
        & $script:exe @Arguments *>&1 | Tee-Object -FilePath $log
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 3)
    $outputFiles = @()
    if ($OutputDirectory -and (Test-Path $OutputDirectory)) {
        $outputFiles = @(Get-ChildItem $OutputDirectory -Recurse -File | Where-Object Length -gt 0 | ForEach-Object {
            [ordered]@{ name = $_.Name; relative_path = $_.FullName.Substring($OutputDirectory.Length).TrimStart('\'); size = $_.Length }
        })
    }
    $tests[$Name] = [ordered]@{
        exit_code = $exitCode
        elapsed_seconds = $elapsed
        arguments = $Arguments
        log = [System.IO.Path]::GetFileName($log)
        nonempty_output_files = $outputFiles
    }
    if ($exitCode -ne 0) { throw "XXL test '$Name' failed with exit code $exitCode" }
    if ($RequireOutput -and $outputFiles.Count -eq 0) { throw "XXL test '$Name' produced no non-empty output file" }
}

Write-Status 'Downloading and verifying the original r245.4 archive.'
$originalArchive = Join-Path $work 'original.7z'
& curl.exe --location --fail --retry 5 --retry-all-errors --retry-delay 5 --output $originalArchive $OriginalUrl
Assert-NativeSuccess 'Original archive download'
$actualSize = (Get-Item $originalArchive).Length
$actualHash = (Get-FileHash $originalArchive -Algorithm SHA256).Hash
@{ url = $OriginalUrl; size_bytes = $actualSize; sha256 = $actualHash } |
    ConvertTo-Json | Set-Content (Join-Path $report 'original-archive.json') -Encoding utf8
if ($actualSize -ne $OriginalSize) { throw "Unexpected original archive size: $actualSize" }
if ($actualHash -ne $OriginalSha256) { throw "Unexpected original archive SHA256: $actualHash" }

$extractDir = Join-Path $work 'extracted'
& 7z.exe x $originalArchive "-o$extractDir" -y | Tee-Object -FilePath (Join-Path $report '7z-extract.txt')
Assert-NativeSuccess 'Original archive extraction'
Remove-Item $originalArchive -Force
$script:bundleRoot = (Get-ChildItem $extractDir -Directory | Where-Object Name -eq 'Faster-Whisper-XXL' | Select-Object -First 1).FullName
if (-not $script:bundleRoot) { throw 'Faster-Whisper-XXL bundle root was not found.' }
$contents = Join-Path $script:bundleRoot '_xxl_data'
$script:exe = Join-Path $script:bundleRoot 'faster-whisper-xxl.exe'
if (-not (Test-Path $contents -PathType Container)) { throw "Missing contents directory: $contents" }
if (-not (Test-Path $script:exe -PathType Leaf)) { throw "Missing executable: $script:exe" }
"bundle_root=$script:bundleRoot" | Set-Content (Join-Path $report 'bundle-root.txt')

Write-Status 'Externalizing the original PyInstaller archive and applying the r245.4 code fix.'
& python -m pip install --disable-pip-version-check --no-input pyinstaller==6.12.0 packaging
Assert-NativeSuccess 'Bootstrap PyInstaller installation'
$scriptsDir = Join-Path $contents 'xxl_original_scripts'
$externalManifest = Join-Path $contents 'xxl_externalization_manifest.json'
& python tools\externalize_pyz.py $script:exe $contents --scripts-dir $scriptsDir --manifest $externalManifest `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'externalize.txt')
Assert-NativeSuccess 'Original bytecode externalization'
$mainMarshal = Join-Path $scriptsDir '__main__.marshal'
$mainPatchReport = Join-Path $report 'main-bytecode-patches.json'
& python tools\patch_xxl_main_bytecode.py $mainMarshal --report $mainPatchReport `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'main-bytecode-patch.txt')
Assert-NativeSuccess 'r245.4 main bytecode patch'
Copy-Item $externalManifest (Join-Path $report 'xxl_externalization_manifest.json')

Write-Status 'Building CPython 3.10.21 with OpenSSL 3.5.7.'
$cpythonRoot = Join-Path $work 'cpython'
& git clone --depth 1 --branch v3.10.21 https://github.com/python/cpython.git $cpythonRoot `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'cpython-clone.txt')
Assert-NativeSuccess 'CPython clone'
$opensslExternal = Join-Path $cpythonRoot 'externals\openssl-bin-3.5'
& git clone --depth 1 --branch openssl-bin-3.5 https://github.com/python/cpython-bin-deps.git $opensslExternal `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'openssl-clone.txt')
Assert-NativeSuccess 'OpenSSL 3.5 binary dependency clone'
$pythonProps = Join-Path $cpythonRoot 'PCbuild\python.props'
$props = Get-Content $pythonProps -Raw
$props = $props.Replace('openssl-bin-1.1.1w\$(ArchName)\', 'openssl-bin-3.5\$(ArchName)\')
Set-Content $pythonProps $props -Encoding utf8
$opensslProps = Join-Path $cpythonRoot 'PCbuild\openssl.props'
$sslProps = Get-Content $opensslProps -Raw
$sslProps = $sslProps.Replace('<_DLLSuffix>-1_1</_DLLSuffix>', '<_DLLSuffix>-3</_DLLSuffix>')
Set-Content $opensslProps $sslProps -Encoding utf8
Push-Location $cpythonRoot
try {
    & .\PCbuild\build.bat -p x64 -c Release *>&1 | Tee-Object -FilePath (Join-Path $report 'cpython-build.txt')
    $cpythonBuildExit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($cpythonBuildExit -ne 0) { throw "CPython build failed with exit code $cpythonBuildExit" }
$amd64 = Join-Path $cpythonRoot 'PCbuild\amd64'
$builtPython = Join-Path $amd64 'python.exe'
if (-not (Test-Path $builtPython -PathType Leaf)) { throw "Built CPython executable missing: $builtPython" }
& $builtPython tools\probe_tls_runtime.py | Set-Content (Join-Path $report 'python-runtime-before-packaging.json')
Assert-NativeSuccess 'Built CPython TLS probe'
$pythonRuntime = Get-Content (Join-Path $report 'python-runtime-before-packaging.json') -Raw | ConvertFrom-Json
if (-not $pythonRuntime.python.StartsWith('3.10.21')) { throw "Unexpected built Python: $($pythonRuntime.python)" }
if (-not $pythonRuntime.openssl.StartsWith('OpenSSL 3.5.7')) { throw "Unexpected built OpenSSL: $($pythonRuntime.openssl)" }
if ($pythonRuntime.https_status -ne 200) { throw "Built CPython HTTPS probe failed: $($pythonRuntime.https_status)" }
Push-Location $cpythonRoot
try {
    & $builtPython -m ensurepip --upgrade *>&1 | Tee-Object -FilePath (Join-Path $report 'ensurepip.txt')
    Assert-NativeSuccess 'ensurepip'
    & $builtPython -m pip install --disable-pip-version-check --no-input --upgrade pip pyinstaller==6.22.1 `
        *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-build-tools.txt')
    Assert-NativeSuccess 'Modern build tools installation'
} finally {
    Pop-Location
}

Write-Status 'Resolving and installing the comprehensive compatible Windows runtime.'
$stage = Join-Path $work 'runtime-stage'
New-Item -ItemType Directory -Force -Path $stage | Out-Null
& $builtPython -m pip install --disable-pip-version-check --no-input --no-cache-dir --upgrade --ignore-installed `
    --target $stage --only-binary=:all: --no-binary=antlr4-python3-runtime,docopt `
    --extra-index-url https://download.pytorch.org/whl/cu128 `
    --report (Join-Path $report 'pip-install-report.json') `
    -r requirements\xxl-modern-win-py310.txt `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-runtime-install.txt')
Assert-NativeSuccess 'Comprehensive runtime installation'
& $builtPython tools\summarize_pip_report.py (Join-Path $report 'pip-install-report.json') (Join-Path $report 'selected-distributions.tsv')
Assert-NativeSuccess 'Installed distribution summary'
& $builtPython tools\overlay_python_target.py $stage $contents --report (Join-Path $report 'runtime-overlay.json') `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'runtime-overlay.txt')
Assert-NativeSuccess 'Runtime overlay'
Remove-Item $stage -Recurse -Force

Write-Status 'Installing Silero VAD v6 from the faster-whisper 1.2.1 tag.'
$fasterWhisperSource = Join-Path $work 'faster-whisper-1.2.1'
& git clone --depth 1 --branch v1.2.1 https://github.com/SYSTRAN/faster-whisper.git $fasterWhisperSource `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'faster-whisper-source.txt')
Assert-NativeSuccess 'faster-whisper v1.2.1 clone'
$vadAssetSource = Join-Path $fasterWhisperSource 'faster_whisper\assets\silero_vad_v6.onnx'
$vadAssetDestination = Join-Path $contents 'faster_whisper\assets\silero_vad_v6.onnx'
if (-not (Test-Path $vadAssetSource -PathType Leaf)) { throw "Silero VAD v6 asset missing: $vadAssetSource" }
New-Item -ItemType Directory -Force -Path (Split-Path $vadAssetDestination) | Out-Null
Copy-Item $vadAssetSource $vadAssetDestination -Force
@{ source_tag = 'v1.2.1'; size = (Get-Item $vadAssetDestination).Length; sha256 = (Get-FileHash $vadAssetDestination -Algorithm SHA256).Hash } |
    ConvertTo-Json | Set-Content (Join-Path $report 'silero-vad-v6.json') -Encoding utf8
Remove-Item $fasterWhisperSource -Recurse -Force

Write-Status 'Updating FFmpeg and ffprobe to the current stable Windows essentials build.'
$ffmpegZip = Join-Path $work 'ffmpeg-release-essentials.zip'
$ffmpegChecksum = Join-Path $report 'ffmpeg-release-essentials.zip.sha256'
& curl.exe --location --fail --retry 5 --retry-all-errors --output $ffmpegZip 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
Assert-NativeSuccess 'FFmpeg download'
& curl.exe --location --fail --retry 5 --retry-all-errors --output $ffmpegChecksum 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256'
Assert-NativeSuccess 'FFmpeg checksum download'
$expectedFfmpegHash = ((Get-Content $ffmpegChecksum -Raw).Trim() -split '\s+')[0].ToUpperInvariant()
$actualFfmpegHash = (Get-FileHash $ffmpegZip -Algorithm SHA256).Hash
if ($actualFfmpegHash -ne $expectedFfmpegHash) { throw "FFmpeg SHA256 mismatch: $actualFfmpegHash != $expectedFfmpegHash" }
$ffmpegExtract = Join-Path $work 'ffmpeg-extracted'
& 7z.exe x $ffmpegZip "-o$ffmpegExtract" -y | Tee-Object -FilePath (Join-Path $report 'ffmpeg-extract.txt')
Assert-NativeSuccess 'FFmpeg extraction'
$ffmpegSource = (Get-ChildItem $ffmpegExtract -Recurse -File -Filter ffmpeg.exe | Select-Object -First 1).FullName
$ffprobeSource = (Get-ChildItem $ffmpegExtract -Recurse -File -Filter ffprobe.exe | Select-Object -First 1).FullName
if (-not $ffmpegSource -or -not $ffprobeSource) { throw 'FFmpeg archive did not contain ffmpeg.exe and ffprobe.exe.' }
Copy-Item $ffmpegSource (Join-Path $script:bundleRoot 'ffmpeg.exe') -Force
Copy-Item $ffprobeSource (Join-Path $script:bundleRoot 'ffprobe.exe') -Force
$ffmpegPackageRoot = Split-Path (Split-Path $ffmpegSource)
Get-ChildItem $ffmpegPackageRoot -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(LICENSE|README)' } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $script:bundleRoot ("FFMPEG-9.0-" + $_.Name)) -Force
}
& (Join-Path $script:bundleRoot 'ffmpeg.exe') -version | Select-Object -First 1 | Set-Content (Join-Path $report 'ffmpeg-version.txt')
Assert-NativeSuccess 'FFmpeg version probe'
if ((Get-Content (Join-Path $report 'ffmpeg-version.txt') -Raw) -notmatch 'ffmpeg version 9\.0') { throw 'Expected FFmpeg 9.0 was not installed.' }
Remove-Item $ffmpegZip, $ffmpegExtract -Recurse -Force

Write-Status 'Downloading and verifying SQLite 3.53.4 for Windows x64.'
$sqliteZip = Join-Path $work 'sqlite-dll-win-x64-3530400.zip'
& curl.exe --location --fail --retry 5 --retry-all-errors --output $sqliteZip 'https://www.sqlite.org/2026/sqlite-dll-win-x64-3530400.zip'
Assert-NativeSuccess 'SQLite download'
$sqliteSha3 = (& python -c "import hashlib,sys; h=hashlib.sha3_256(); f=open(sys.argv[1],'rb'); [h.update(c) for c in iter(lambda:f.read(1048576),b'')]; print(h.hexdigest())" $sqliteZip).Trim()
if ($sqliteSha3 -ne 'deddee963c810d1eeac3ce5e15c7c41da21a1c54d7a39cf54fbf577d2f50de3a') { throw "SQLite SHA3-256 mismatch: $sqliteSha3" }
$sqliteExtract = Join-Path $work 'sqlite-extracted'
& 7z.exe x $sqliteZip "-o$sqliteExtract" -y | Tee-Object -FilePath (Join-Path $report 'sqlite-extract.txt')
Assert-NativeSuccess 'SQLite extraction'
$sqliteSource = (Get-ChildItem $sqliteExtract -Recurse -File -Filter sqlite3.dll | Select-Object -First 1).FullName
if (-not $sqliteSource) { throw 'SQLite archive did not contain sqlite3.dll.' }
@{ source = 'sqlite-dll-win-x64-3530400.zip'; sha3_256 = $sqliteSha3; dll_sha256 = (Get-FileHash $sqliteSource -Algorithm SHA256).Hash } |
    ConvertTo-Json | Set-Content (Join-Path $report 'sqlite-runtime.json') -Encoding utf8

Write-Status 'Rebuilding the launcher with CPython 3.10.21 and PyInstaller 6.22.1.'
$launcherDist = Join-Path $work 'launcher-dist'
$launcherBuild = Join-Path $work 'launcher-build'
$launcherSpec = Join-Path $work 'launcher-spec'
$launcherScript = Join-Path $workspace 'tools\xxl_launcher.py'
Push-Location $cpythonRoot
try {
    & $builtPython -m PyInstaller --noconfirm --clean --onedir --console `
        --name faster-whisper-xxl --contents-directory _xxl_data `
        --distpath $launcherDist --workpath $launcherBuild --specpath $launcherSpec `
        $launcherScript *>&1 | Tee-Object -FilePath (Join-Path $report 'pyinstaller-build.txt')
    $launcherExit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($launcherExit -ne 0) { throw "Launcher rebuild failed with exit code $launcherExit" }
$launcherRoot = Join-Path $launcherDist 'faster-whisper-xxl'
Copy-Item (Join-Path $launcherRoot 'faster-whisper-xxl.exe') $script:exe -Force
Copy-Item (Join-Path $launcherRoot '_xxl_data\*') $contents -Recurse -Force
Remove-Item $launcherDist, $launcherBuild, $launcherSpec -Recurse -Force

Write-Status 'Overlaying the CPython 3.10.21 standard library and native modules.'
$stdlib = Join-Path $cpythonRoot 'Lib'
$stdlibExclusions = @('site-packages','test','ensurepip','idlelib','tkinter','__pycache__')
Get-ChildItem $stdlib -Force | Where-Object { $stdlibExclusions -notcontains $_.Name } | ForEach-Object {
    $target = Join-Path $contents $_.Name
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }
    Copy-Item $_.FullName $target -Recurse -Force
}
Get-ChildItem $amd64 -File | Where-Object {
    $_.Extension -in @('.dll','.pyd') -and $_.Name -notmatch '^(_tkinter|tcl|tk)'
} | ForEach-Object { Copy-Item $_.FullName (Join-Path $contents $_.Name) -Force }
Remove-Item (Join-Path $contents 'libssl-1_1.dll'), (Join-Path $contents 'libcrypto-1_1.dll') -Force -ErrorAction SilentlyContinue
Copy-Item $sqliteSource (Join-Path $contents 'sqlite3.dll') -Force
Copy-Item $sqliteSource (Join-Path $amd64 'sqlite3.dll') -Force
Remove-Item $sqliteZip, $sqliteExtract -Recurse -Force

Write-Status 'Checking all target dependency constraints and runtime imports.'
$dependencyReport = Join-Path $report 'target-dependencies.json'
& $builtPython tools\check_target_dependencies.py $contents --output $dependencyReport `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'target-dependencies.txt')
Assert-NativeSuccess 'Target dependency consistency check'
$runtimeReport = Join-Path $report 'runtime-verification.json'
$oldPath = $env:PATH
$oldPythonPath = $env:PYTHONPATH
$env:PATH = "$script:bundleRoot;$contents;$(Join-Path $contents 'ctranslate2');$(Join-Path $contents 'torch\lib');$(Join-Path $contents 'onnxruntime\capi');$oldPath"
$env:PYTHONPATH = $contents
try {
    & $builtPython tools\verify_comprehensive_runtime.py $script:bundleRoot --patch-report $mainPatchReport --output $runtimeReport `
        --expected-openssl 'OpenSSL 3.5.7' --expected-sqlite '3.53.4' --expected-ffmpeg 'ffmpeg version 9.0' `
        *>&1 | Tee-Object -FilePath (Join-Path $report 'runtime-verification.txt')
    $runtimeExit = $LASTEXITCODE
} finally {
    $env:PATH = $oldPath
    $env:PYTHONPATH = $oldPythonPath
}
if ($runtimeExit -ne 0) { throw "Comprehensive runtime verification failed: $runtimeExit" }

Write-Status 'Running packaged CLI and runtime diagnostics.'
Invoke-XxlTest -Name 'help' -Arguments @('--help')
Invoke-XxlTest -Name 'version' -Arguments @('--version')
Invoke-XxlTest -Name 'checkcuda' -Arguments @('--checkcuda')
$runtimeInfoConsole = Join-Path $report 'packaged-runtime-info-console.txt'
Push-Location $script:bundleRoot
try {
    & $script:exe --runtime-info *>&1 | Tee-Object -FilePath $runtimeInfoConsole
    $runtimeInfoExit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($runtimeInfoExit -ne 0) { throw "Packaged --runtime-info failed: $runtimeInfoExit" }
$runtimeInfoJson = Join-Path $report 'packaged-runtime-info.json'
& python tools\extract_json_object.py $runtimeInfoConsole $runtimeInfoJson | Out-Null
Assert-NativeSuccess 'Packaged runtime JSON extraction'
$packagedRuntime = Get-Content $runtimeInfoJson -Raw | ConvertFrom-Json
if (-not $packagedRuntime.python.StartsWith('3.10.21')) { throw "Packaged Python mismatch: $($packagedRuntime.python)" }
if (-not $packagedRuntime.openssl.StartsWith('OpenSSL 3.5.7')) { throw "Packaged OpenSSL mismatch: $($packagedRuntime.openssl)" }
if ($packagedRuntime.sqlite -ne '3.53.4') { throw "Packaged SQLite mismatch: $($packagedRuntime.sqlite)" }
if ($packagedRuntime.torch_compiled_arch_flags -notmatch 'sm_120') { throw 'Packaged runtime does not report sm_120.' }
$tests['runtime_info'] = [ordered]@{ exit_code = $runtimeInfoExit; json = 'packaged-runtime-info.json'; verified_python = $true; verified_openssl = $true; verified_sqlite = $true; verified_sm120 = $true }

Write-Status 'Generating spoken Windows test audio and current codec variants.'
$fixture = Join-Path $report 'spoken-test.wav'
try {
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToWaveFile($fixture, $format)
    $synth.Speak('This is a comprehensive Faster Whisper Windows compatibility test. The second sentence checks timestamps and subtitle writers.')
    $synth.Dispose()
} catch {
    & python tools\generate_test_wav.py $fixture
    Assert-NativeSuccess 'Fallback WAV generation'
}
if (-not (Test-Path $fixture -PathType Leaf) -or (Get-Item $fixture).Length -eq 0) { throw 'Test WAV fixture is missing or empty.' }
$modelDir = Join-Path $work 'models'
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
$common = @('--model','tiny.en','--model_dir',$modelDir,'--device','cpu','--compute_type','int8','--language','en','--verbose','false')

$baselineDir = Join-Path $report 'output-baseline-all'
Invoke-XxlTest -Name 'baseline_all_writers' -Arguments (@($fixture) + $common + @('--output_dir',$baselineDir,'--word_timestamps','true','--output_format','all')) -OutputDirectory $baselineDir -RequireOutput

$batchedDir = Join-Path $report 'output-batched'
Invoke-XxlTest -Name 'batched_inference' -Arguments (@($fixture) + $common + @('--batched','--batch_size','2','--vad_filter','true','--output_dir',$batchedDir,'--output_format','txt')) -OutputDirectory $batchedDir -RequireOutput

$auditokDir = Join-Path $report 'output-auditok'
Invoke-XxlTest -Name 'auditok_vad' -Arguments (@($fixture) + $common + @('--vad_filter','true','--vad_method','auditok','--output_dir',$auditokDir,'--output_format','txt')) -OutputDirectory $auditokDir -RequireOutput

$webrtcDir = Join-Path $report 'output-webrtc'
Invoke-XxlTest -Name 'webrtc_vad' -Arguments (@($fixture) + $common + @('--vad_filter','true','--vad_method','webrtc','--output_dir',$webrtcDir,'--output_format','txt')) -OutputDirectory $webrtcDir -RequireOutput

$mp3 = Join-Path $report 'spoken-test.mp3'
$flac = Join-Path $report 'spoken-test.flac'
& (Join-Path $script:bundleRoot 'ffmpeg.exe') -y -hide_banner -loglevel error -i $fixture -codec:a libmp3lame -q:a 4 $mp3
Assert-NativeSuccess 'MP3 fixture conversion'
& (Join-Path $script:bundleRoot 'ffmpeg.exe') -y -hide_banner -loglevel error -i $fixture -codec:a flac $flac
Assert-NativeSuccess 'FLAC fixture conversion'
$mp3Dir = Join-Path $report 'output-mp3'
Invoke-XxlTest -Name 'pyav_mp3_decode' -Arguments (@($mp3) + $common + @('--output_dir',$mp3Dir,'--output_format','txt')) -OutputDirectory $mp3Dir -RequireOutput
$flacDir = Join-Path $report 'output-flac'
Invoke-XxlTest -Name 'pyav_flac_decode' -Arguments (@($flac) + $common + @('--output_dir',$flacDir,'--output_format','txt')) -OutputDirectory $flacDir -RequireOutput

Write-Status 'Testing actual diarization with the repaired --postfix path.'
$diarizeDir = Join-Path $report 'output-diarize-postfix'
Invoke-XxlTest -Name 'diarize_postfix_reverb' -Arguments (@($fixture) + $common + @('--diarize','reverb_v1','--diarize_device','cpu','--num_speakers','1','--postfix','--output_dir',$diarizeDir,'--output_format','txt','srt')) -OutputDirectory $diarizeDir -RequireOutput

Write-Status 'Testing the updated MDX/RoFormer dependency path.'
$mdxDir = Join-Path $report 'output-mdx'
Invoke-XxlTest -Name 'mdx_vocal_extract' -Arguments (@($fixture) + $common + @('--ff_vocal_extract','mdx_kim2','--voc_device','cpu','--mdx_chunk','5','--output_dir',$mdxDir,'--output_format','txt')) -OutputDirectory $mdxDir -RequireOutput

$testReport = Join-Path $report 'test-results.json'
$tests['physical_rtx_50_tested'] = $false
$tests['windows_runner'] = 'Windows Server 2022 x64'
$tests['notes'] = 'No physical NVIDIA GPU was available; CPU and packaged-runtime tests were exhaustive, while CUDA support was verified statically and by native imports.'
$tests | ConvertTo-Json -Depth 12 | Set-Content $testReport -Encoding utf8

Write-Status 'Adding release documentation, full file hashes and build metadata.'
& $builtPython tools\finalize_comprehensive_release.py $script:bundleRoot $runtimeReport $testReport `
    --report-dir $report --original-url $OriginalUrl --original-size $OriginalSize `
    --original-sha256 $OriginalSha256 --git-sha $GitSha `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'finalize-release.txt')
Assert-NativeSuccess 'Release finalization'

Write-Status 'Creating and testing the complete ZIP64 archive.'
$bundleFiles = Get-ChildItem $script:bundleRoot -Recurse -File
$bundleSize = ($bundleFiles | Measure-Object Length -Sum).Sum
"files=$($bundleFiles.Count)`nuncompressed_bytes=$bundleSize" | Set-Content (Join-Path $report 'bundle-footprint.txt')
$zipPath = Join-Path $work $ArchiveName
Push-Location $extractDir
try {
    & 7z.exe a -tzip -mx=5 -mmt=on $zipPath '.\Faster-Whisper-XXL' | Tee-Object -FilePath (Join-Path $report '7z-create.txt')
    $zipCreateExit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($zipCreateExit -ne 0) { throw "ZIP creation failed with exit code $zipCreateExit" }
& 7z.exe t $zipPath | Tee-Object -FilePath (Join-Path $report '7z-test.txt')
Assert-NativeSuccess 'ZIP integrity test'
$zipItem = Get-Item $zipPath
$zipHash = (Get-FileHash $zipPath -Algorithm SHA256).Hash
@{ filename = $zipItem.Name; size_bytes = $zipItem.Length; sha256 = $zipHash; files = $bundleFiles.Count; uncompressed_bytes = $bundleSize } |
    ConvertTo-Json | Set-Content (Join-Path $report 'archive-info.json') -Encoding utf8

if (-not $SkipHosting) {
    Write-Status 'Uploading the verified full archive to Buzzheavier and Gofile.'
    $hosting = [ordered]@{ filename = $ArchiveName; size_bytes = $zipItem.Length; sha256 = $zipHash; buzzheavier = $null; gofile = $null; errors = @() }
    try {
        $buzzResponse = Join-Path $report 'buzzheavier-response.json'
        & curl.exe --location --fail-with-body --retry 4 --retry-all-errors --connect-timeout 30 `
            --upload-file $zipPath --output $buzzResponse "https://w.buzzheavier.com/$ArchiveName" `
            2>&1 | Tee-Object -FilePath (Join-Path $report 'buzzheavier-curl.txt')
        Assert-NativeSuccess 'Buzzheavier upload'
        $buzzJson = Get-Content $buzzResponse -Raw | ConvertFrom-Json
        $buzzId = $buzzJson.data.id
        if (-not $buzzId) { throw 'Buzzheavier response did not contain data.id.' }
        $buzzUrl = "https://buzzheavier.com/$buzzId"
        & curl.exe --location --fail --retry 3 --retry-all-errors --max-time 120 `
            --output (Join-Path $report 'buzzheavier-page.html') $buzzUrl
        Assert-NativeSuccess 'Buzzheavier page verification'
        $hosting.buzzheavier = [ordered]@{ success = $true; url = $buzzUrl; id = $buzzId }
    } catch {
        $hosting.errors += "Buzzheavier: $($_.Exception.Message)"
        $hosting.buzzheavier = [ordered]@{ success = $false; error = $_.Exception.Message }
    }
    try {
        $gofileResponse = Join-Path $report 'gofile-response.json'
        & curl.exe --location --fail-with-body --retry 4 --retry-all-errors --connect-timeout 30 `
            --form "file=@$zipPath" --output $gofileResponse 'https://upload.gofile.io/uploadfile' `
            2>&1 | Tee-Object -FilePath (Join-Path $report 'gofile-curl.txt')
        Assert-NativeSuccess 'Gofile upload'
        $gofileJson = Get-Content $gofileResponse -Raw | ConvertFrom-Json
        if ($gofileJson.status -ne 'ok') { throw "Gofile returned status '$($gofileJson.status)'." }
        $gofileUrl = $gofileJson.data.downloadPage
        if (-not $gofileUrl) { $gofileUrl = $gofileJson.data.downloadPageUrl }
        if (-not $gofileUrl) { throw 'Gofile response did not contain a download page.' }
        & curl.exe --location --fail --retry 3 --retry-all-errors --max-time 120 `
            --output (Join-Path $report 'gofile-page.html') $gofileUrl
        Assert-NativeSuccess 'Gofile page verification'
        $hosting.gofile = [ordered]@{ success = $true; url = $gofileUrl; guestToken = $gofileJson.data.guestToken; parentFolder = $gofileJson.data.parentFolder }
    } catch {
        $hosting.errors += "Gofile: $($_.Exception.Message)"
        $hosting.gofile = [ordered]@{ success = $false; error = $_.Exception.Message }
    }
    $workingHosts = 0
    if ($hosting.buzzheavier.success) { $workingHosts++ }
    if ($hosting.gofile.success) { $workingHosts++ }
    $hosting.working_host_count = $workingHosts
    $hosting | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $report 'release-links.json') -Encoding utf8
    if ($workingHosts -eq 0) { throw 'Both hosting uploads or page verifications failed.' }
} else {
    @{ skipped = $true; reason = 'SkipHosting switch' } | ConvertTo-Json | Set-Content (Join-Path $report 'release-links.json') -Encoding utf8
}

Write-Status 'Comprehensive Modernized 2 build completed successfully.'
@{
    success = $true
    archive = $zipItem.Name
    size_bytes = $zipItem.Length
    sha256 = $zipHash
    report_dir = $report
    archive_path = $zipPath
} | ConvertTo-Json | Set-Content (Join-Path $report 'FINAL-SUCCESS.json') -Encoding utf8
Get-Content (Join-Path $report 'FINAL-SUCCESS.json')
