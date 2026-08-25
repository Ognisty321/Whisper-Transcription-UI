[CmdletBinding()]
param(
    [string]$OriginalUrl = 'https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_windows.7z',
    [Int64]$OriginalSize = 1424256246,
    [string]$OriginalSha256 = '237DEE23939CDABFC96EF859FC5E584B842C3A5557E0D2CA744E1F87C14C5844',
    [string]$ArchiveName = 'Faster-Whisper-XXL_r245.4_RTX50_CUDA128_FIXED.zip',
    [string]$GitSha = $env:GITHUB_SHA
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$workspace = (Get-Location).Path
$work = Join-Path $workspace 'final-work'
$report = Join-Path $workspace 'final-report'

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

Write-Status 'Downloading and verifying the original r245.4 archive.'
$originalArchive = Join-Path $work 'original.7z'
& curl.exe --location --fail --retry 5 --retry-all-errors --retry-delay 5 --output $originalArchive $OriginalUrl
Assert-NativeSuccess 'Original archive download'
$actualSize = (Get-Item $originalArchive).Length
$actualHash = (Get-FileHash $originalArchive -Algorithm SHA256).Hash
@{
    url = $OriginalUrl
    size_bytes = $actualSize
    sha256 = $actualHash
} | ConvertTo-Json | Set-Content (Join-Path $report 'original-archive.json') -Encoding utf8
if ($actualSize -ne $OriginalSize) { throw "Unexpected original archive size: $actualSize" }
if ($actualHash -ne $OriginalSha256) { throw "Unexpected original archive SHA256: $actualHash" }

$extractDir = Join-Path $work 'extracted'
& 7z.exe x $originalArchive "-o$extractDir" -y | Tee-Object -FilePath (Join-Path $report '7z-extract.txt')
Assert-NativeSuccess 'Original archive extraction'
Remove-Item $originalArchive -Force
$bundleRoot = (Get-ChildItem $extractDir -Directory | Where-Object Name -eq 'Faster-Whisper-XXL' | Select-Object -First 1).FullName
if (-not $bundleRoot) { throw 'Faster-Whisper-XXL bundle root was not found after extraction.' }
$contents = Join-Path $bundleRoot '_xxl_data'
$exe = Join-Path $bundleRoot 'faster-whisper-xxl.exe'
if (-not (Test-Path $contents -PathType Container)) { throw "Missing contents directory: $contents" }
if (-not (Test-Path $exe -PathType Leaf)) { throw "Missing executable: $exe" }
"bundle_root=$bundleRoot" | Set-Content (Join-Path $report 'bundle-root.txt')

Write-Status 'Externalizing original PyInstaller bytecode.'
& python -m pip install --disable-pip-version-check --no-input pyinstaller==6.12.0 *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-pyinstaller.txt')
Assert-NativeSuccess 'PyInstaller installation'
& python tools\externalize_pyz.py $exe $contents `
    --scripts-dir (Join-Path $contents 'xxl_original_scripts') `
    --manifest (Join-Path $contents 'xxl_externalization_manifest.json') `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'externalize.txt')
Assert-NativeSuccess 'PyInstaller bytecode externalization'
Copy-Item (Join-Path $contents 'xxl_externalization_manifest.json') (Join-Path $report 'xxl_externalization_manifest.json')

Write-Status 'Installing the coherent CUDA 12.8 / RTX 50 runtime stack.'
$modern = Join-Path $work 'modern'
New-Item -ItemType Directory -Force -Path $modern | Out-Null
& python -m pip install --disable-pip-version-check --no-input --no-cache-dir --no-deps `
    --target $modern `
    --index-url https://download.pytorch.org/whl/cu128 `
    torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-pytorch.txt')
Assert-NativeSuccess 'PyTorch CUDA 12.8 stack installation'
& python -m pip install --disable-pip-version-check --no-input --no-cache-dir --no-deps `
    --target $modern `
    ctranslate2==4.8.1 onnxruntime-gpu==1.23.2 `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-runtime.txt')
Assert-NativeSuccess 'CTranslate2 and ONNX Runtime installation'

Get-ChildItem $modern -Force | Select-Object Name,@{n='Size';e={if ($_.PSIsContainer) {(Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum} else {$_.Length}}} | Sort-Object Name | Export-Csv (Join-Path $report 'modern-stage.csv') -NoTypeInformation -Encoding utf8

$replaceDirectories = @('torch','torchgen','functorch','torchvision','torchaudio','ctranslate2','onnxruntime')
foreach ($name in $replaceDirectories) {
    $path = Join-Path $contents $name
    if (Test-Path $path) { Remove-Item $path -Recurse -Force }
}
Get-ChildItem $contents -Directory | Where-Object {
    $_.Name -match '^(torch|torchvision|torchaudio|ctranslate2|onnxruntime_gpu)-.*\.dist-info$'
} | Remove-Item -Recurse -Force
Copy-Item (Join-Path $modern '*') $contents -Recurse -Force

Write-Status 'Rebuilding the PyInstaller launcher and merging it into the complete application directory.'
$launcherDist = Join-Path $work 'launcher-dist'
$launcherBuild = Join-Path $work 'launcher-build'
$launcherSpec = Join-Path $work 'launcher-spec'
& python -m PyInstaller --noconfirm --clean --onedir --console `
    --name faster-whisper-xxl `
    --contents-directory _xxl_data `
    --distpath $launcherDist `
    --workpath $launcherBuild `
    --specpath $launcherSpec `
    tools\xxl_launcher.py *>&1 | Tee-Object -FilePath (Join-Path $report 'pyinstaller-build.txt')
Assert-NativeSuccess 'Launcher rebuild'
$launcherRoot = Join-Path $launcherDist 'faster-whisper-xxl'
Copy-Item (Join-Path $launcherRoot 'faster-whisper-xxl.exe') $exe -Force
Copy-Item (Join-Path $launcherRoot '_xxl_data\*') $contents -Recurse -Force
(Get-FileHash $exe -Algorithm SHA256).Hash | Set-Content (Join-Path $report 'rebuilt-executable.sha256')

Write-Status 'Verifying exact runtime versions, Blackwell sm_120, providers, and critical DLLs.'
$runtimeReport = Join-Path $report 'runtime-versions.json'
& python tools\verify_modern_runtime.py $contents --output $runtimeReport *>&1 | Tee-Object -FilePath (Join-Path $report 'runtime-verification.txt')
Assert-NativeSuccess 'Modern runtime verification'

Write-Status 'Running rebuilt CLI smoke tests.'
Push-Location $bundleRoot
try {
    & $exe --help *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'help.txt')
    $helpExit = $LASTEXITCODE
    & $exe --version *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'version.txt')
    $versionExit = $LASTEXITCODE
    & $exe --checkcuda *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'checkcuda.txt')
    $cudaExit = $LASTEXITCODE
} finally {
    Pop-Location
}
"help_exit=$helpExit`nversion_exit=$versionExit`ncheckcuda_exit=$cudaExit" | Set-Content (Join-Path $report 'cli-smoke-status.txt')
if ($helpExit -ne 0 -or $versionExit -ne 0 -or $cudaExit -ne 0) {
    throw 'One or more rebuilt CLI smoke tests failed.'
}

Write-Status 'Running an end-to-end CPU transcription test with tiny.en.'
$inferenceDir = Join-Path $report 'inference'
$modelDir = Join-Path $work 'models'
New-Item -ItemType Directory -Force -Path $inferenceDir, $modelDir | Out-Null
$wav = Join-Path $report 'decoder-test.wav'
& python tools\generate_test_wav.py $wav
Assert-NativeSuccess 'WAV fixture generation'
& $exe $wav `
    --model tiny.en `
    --model_dir $modelDir `
    --device cpu `
    --compute_type int8 `
    --output_dir $inferenceDir `
    --output_format txt `
    --verbose false `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'inference-log.txt')
$inferenceExit = $LASTEXITCODE
"inference_exit=$inferenceExit" | Set-Content (Join-Path $report 'inference-status.txt')
if ($inferenceExit -ne 0) { throw "CPU inference failed with exit code $inferenceExit" }
$inferenceOutput = Join-Path $inferenceDir 'decoder-test.txt'
if (-not (Test-Path $inferenceOutput -PathType Leaf) -or (Get-Item $inferenceOutput).Length -eq 0) {
    throw 'CPU inference output is missing or empty.'
}

Write-Status 'Adding release notes, manifests, and internal checksums.'
& python tools\finalize_rtx50_release.py $bundleRoot $runtimeReport `
    --report-dir $report `
    --original-url $OriginalUrl `
    --original-size $OriginalSize `
    --original-sha256 $OriginalSha256 `
    --git-sha $GitSha `
    --inference-output $inferenceOutput `
    *>&1 | Tee-Object -FilePath (Join-Path $report 'finalize-release.txt')
Assert-NativeSuccess 'Release metadata finalization'

$bundleFiles = Get-ChildItem $bundleRoot -Recurse -File
$bundleSize = ($bundleFiles | Measure-Object Length -Sum).Sum
"files=$($bundleFiles.Count)`nuncompressed_bytes=$bundleSize" | Set-Content (Join-Path $report 'bundle-footprint.txt')

Write-Status 'Creating and integrity-testing the complete ZIP64 archive.'
$zipPath = Join-Path $work $ArchiveName
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
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
@{
    filename = $zipItem.Name
    size_bytes = $zipItem.Length
    sha256 = $zipHash
    files = $bundleFiles.Count
    uncompressed_bytes = $bundleSize
} | ConvertTo-Json | Set-Content (Join-Path $report 'archive-info.json') -Encoding utf8

Write-Status 'Uploading the full ZIP to Buzzheavier and Gofile.'
$hosting = [ordered]@{
    filename = $ArchiveName
    size_bytes = $zipItem.Length
    sha256 = $zipHash
    buzzheavier = $null
    gofile = $null
    errors = @()
}

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
        --dump-header (Join-Path $report 'buzzheavier-page-headers.txt') `
        --output (Join-Path $report 'buzzheavier-page.html') $buzzUrl
    Assert-NativeSuccess 'Buzzheavier download-page GET verification'
    $hosting.buzzheavier = [ordered]@{ success = $true; url = $buzzUrl; id = $buzzId }
    $buzzUrl | Set-Content (Join-Path $report 'buzzheavier-url.txt')
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
        --dump-header (Join-Path $report 'gofile-page-headers.txt') `
        --output (Join-Path $report 'gofile-page.html') $gofileUrl
    Assert-NativeSuccess 'Gofile download-page GET verification'
    $hosting.gofile = [ordered]@{ success = $true; url = $gofileUrl; guestToken = $gofileJson.data.guestToken; parentFolder = $gofileJson.data.parentFolder }
    $gofileUrl | Set-Content (Join-Path $report 'gofile-url.txt')
} catch {
    $hosting.errors += "Gofile: $($_.Exception.Message)"
    $hosting.gofile = [ordered]@{ success = $false; error = $_.Exception.Message }
}

$workingHosts = 0
if ($hosting.buzzheavier.success) { $workingHosts++ }
if ($hosting.gofile.success) { $workingHosts++ }
$hosting.working_host_count = $workingHosts
$hostingJson = $hosting | ConvertTo-Json -Depth 8
$hostingJson | Set-Content (Join-Path $report 'release-links.json') -Encoding utf8
$hostingJson | Write-Host
if ($workingHosts -eq 0) { throw 'Both final hosting uploads or download-page verifications failed.' }

Write-Status "Completed successfully with $workingHosts verified hosting link(s)."
Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{n='UsedGB';e={[math]::Round($_.Used/1GB,2)}},@{n='FreeGB';e={[math]::Round($_.Free/1GB,2)}} | Format-Table -AutoSize | Out-String | Set-Content (Join-Path $report 'disk.txt')
