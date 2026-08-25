[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$workspace=(Get-Location).Path
$work=Join-Path $workspace 'extended-work'
$report=Join-Path $workspace 'extended-report'
Remove-Item $work,$report -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $work,$report | Out-Null
function Assert-Native([string]$Op) { if ($LASTEXITCODE -ne 0) { throw "$Op failed with exit code $LASTEXITCODE" } }
function Status([string]$s) { "[$((Get-Date).ToUniversalTime().ToString('s'))Z] $s" | Tee-Object -FilePath (Join-Path $report 'status.txt') -Append }

$origUrl='https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_windows.7z'
$origHash='237DEE23939CDABFC96EF859FC5E584B842C3A5557E0D2CA744E1F87C14C5844'
Status 'Downloading and extracting original bundle.'
$arc=Join-Path $work 'original.7z'
& curl.exe -L --fail --retry 5 --retry-all-errors --output $arc $origUrl
Assert-Native 'original download'
if ((Get-FileHash $arc -Algorithm SHA256).Hash -ne $origHash) { throw 'Original SHA256 mismatch' }
$extract=Join-Path $work 'extracted'
& 7z.exe x $arc "-o$extract" -y | Tee-Object -FilePath (Join-Path $report '7z-extract.txt')
Assert-Native 'original extraction'
Remove-Item $arc -Force
$root=(Resolve-Path (Join-Path $extract 'Faster-Whisper-XXL')).Path
$contents=Join-Path $root '_xxl_data'; $exe=Join-Path $root 'faster-whisper-xxl.exe'
$root | Set-Content (Join-Path $report 'bundle-root.txt')

Status 'Installing current PyInstaller and externalizing original CPython 3.10 bytecode.'
& python -m pip install --disable-pip-version-check --no-input --upgrade 'pyinstaller==6.22.2' packaging *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-pyinstaller.txt')
Assert-Native 'PyInstaller install'
& python tools\externalize_pyz.py $exe $contents --scripts-dir (Join-Path $contents 'xxl_original_scripts') --manifest (Join-Path $contents 'xxl_externalization_manifest.json') *>&1 | Tee-Object -FilePath (Join-Path $report 'externalize.txt')
Assert-Native 'externalize'

Status 'Resolving a coherent modern dependency environment for CPython 3.10 / Windows x64.'
$stage=Join-Path $work 'modern-stage'
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$packages=@(
 'torch==2.11.0+cu128','torchvision==0.26.0+cu128','torchaudio==2.11.0+cu128',
 'ctranslate2==4.8.1','onnxruntime-gpu==1.23.2',
 'numpy==2.2.6','scipy==1.15.3','scikit-learn==1.7.2','pandas==2.3.3','numba==0.67.0','llvmlite==0.49.0',
 'pyannote.audio==3.4.0','pyannote.core==5.0.0','pyannote.database==5.1.0','pyannote.metrics==3.2.1','pyannote.pipeline==3.0.1',
 'lightning==2.6.5','pytorch-lightning==2.6.5','torchmetrics==1.9.0','pytorch-metric-learning==2.9.0',
 'huggingface-hub==1.28.0','tokenizers==0.23.1','sentencepiece==0.2.2',
 'av==17.1.0','librosa==0.11.0','soundfile==0.14.0','soxr==1.1.0','audioread==3.1.0','auditok==0.5.2',
 'einops==0.8.2','torch-audiomentations==0.12.0',
 'optuna==4.9.0','SQLAlchemy==2.0.52','alembic==1.19.1','omegaconf==2.3.1','beartype==0.22.9',
 'networkx==3.4.2','sympy==1.14.0','Pillow==12.3.0','matplotlib==3.10.9',
 'rich==15.0.0','tqdm==4.70.0','requests==2.34.2','urllib3==2.7.0','certifi==2026.7.22','charset-normalizer==3.5.1','idna==3.19',
 'PyYAML==6.0.3','packaging==26.3','filelock==3.32.4','fsspec==2026.7.0','platformdirs==4.11.4','pooch==1.9.0','joblib==1.5.3','threadpoolctl==3.6.0',
 'typing-extensions==4.16.0','psutil==7.2.2','attrs==26.1.0','cffi==2.1.1','pycparser==3.0','protobuf==7.36.0','tensorboardX==2.6.5',
 'aiohttp==3.14.3','yarl==1.24.5','multidict==6.7.1','frozenlist==1.8.0','aiosignal==1.4.0','pyreadline3==3.5.6','semver==3.0.4','tabulate==0.10.0'
)
& python -m pip install --disable-pip-version-check --no-input --no-cache-dir --upgrade `
  --target $stage --index-url 'https://pypi.org/simple' --extra-index-url 'https://download.pytorch.org/whl/cu128' `
  @packages *>&1 | Tee-Object -FilePath (Join-Path $report 'pip-modern.txt')
Assert-Native 'modern dependency resolution/install'
& python tools\apply_staged_packages.py $stage $contents --report (Join-Path $report 'stage-apply.json') *>&1 | Tee-Object -FilePath (Join-Path $report 'stage-apply.txt')
Assert-Native 'stage apply'

Status 'Updating standalone FFmpeg to maintained 9.0 Windows GPL build.'
$ffZip=Join-Path $work 'ffmpeg.zip'; $ffDir=Join-Path $work 'ffmpeg'
& curl.exe -L --fail --retry 5 --retry-all-errors --output $ffZip 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n9.0-latest-win64-gpl-9.0.zip'
Assert-Native 'FFmpeg download'
& 7z.exe x $ffZip "-o$ffDir" -y | Out-Null
Assert-Native 'FFmpeg extraction'
$newFfmpeg=Get-ChildItem $ffDir -Recurse -File -Filter ffmpeg.exe | Select-Object -First 1
if (-not $newFfmpeg) { throw 'Updated ffmpeg.exe not found' }
Copy-Item $newFfmpeg.FullName (Join-Path $root 'ffmpeg.exe') -Force
& (Join-Path $root 'ffmpeg.exe') -version *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'ffmpeg-version.txt')
if ((Get-Content (Join-Path $report 'ffmpeg-version.txt') -Raw) -notmatch 'ffmpeg version n?9\.0') { throw 'FFmpeg 9.0 verification failed' }

Status 'Rebuilding launcher with current PyInstaller and current CPython 3.10 patch runtime.'
$dist=Join-Path $work 'launcher-dist'; $build=Join-Path $work 'launcher-build'; $spec=Join-Path $work 'launcher-spec'
& python -m PyInstaller --noconfirm --clean --onedir --console --name faster-whisper-xxl --contents-directory _xxl_data --distpath $dist --workpath $build --specpath $spec tools\xxl_launcher.py *>&1 | Tee-Object -FilePath (Join-Path $report 'pyinstaller-build.txt')
Assert-Native 'launcher build'
$launchRoot=Join-Path $dist 'faster-whisper-xxl'
Copy-Item (Join-Path $launchRoot 'faster-whisper-xxl.exe') $exe -Force
Copy-Item (Join-Path $launchRoot '_xxl_data\*') $contents -Recurse -Force

Status 'Probing versions after modernization.'
& python tools\probe_dependency_versions.py $contents --output (Join-Path $report 'post-versions.json') *>&1 | Tee-Object -FilePath (Join-Path $report 'post-probe.txt')
Assert-Native 'post modernization probe'
& python tools\verify_modern_runtime.py $contents --output (Join-Path $report 'core-runtime.json') *>&1 | Tee-Object -FilePath (Join-Path $report 'core-runtime.txt')
Assert-Native 'core runtime verification'

Status 'Running CLI smoke tests.'
Push-Location $root
try {
 & $exe --help *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'help.txt'); $e1=$LASTEXITCODE
 & $exe --version *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'version.txt'); $e2=$LASTEXITCODE
 & $exe --checkcuda *>&1 | Out-String -Width 8192 | Set-Content (Join-Path $report 'checkcuda.txt'); $e3=$LASTEXITCODE
} finally { Pop-Location }
"help=$e1`nversion=$e2`ncheckcuda=$e3" | Set-Content (Join-Path $report 'cli-status.txt')
if ($e1 -ne 0 -or $e2 -ne 0 -or $e3 -ne 0) { throw 'CLI smoke failed' }

Status 'Running end-to-end transcription and feature-path tests.'
$modelDir=Join-Path $work 'models'; New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
$wav=Join-Path $report 'test.wav'; & python tools\generate_test_wav.py $wav; Assert-Native 'wav generation'
function Run-XxlTest([string]$Name,[string[]]$Extra,[switch]$RequireOutput) {
  $out=Join-Path $report ("out-"+$Name); New-Item -ItemType Directory -Force -Path $out | Out-Null
  $args=@($wav,'--model','tiny.en','--model_dir',$modelDir,'--device','cpu','--compute_type','int8','--output_dir',$out,'--output_format','txt','--verbose','false') + $Extra
  & $exe @args *>&1 | Tee-Object -FilePath (Join-Path $report ("test-"+$Name+".log"))
  $rc=$LASTEXITCODE; "$rc" | Set-Content (Join-Path $report ("test-"+$Name+".exit"))
  if ($rc -ne 0) { throw "XXL test $Name failed with exit $rc" }
  if ($RequireOutput) {
    $files=Get-ChildItem $out -File -ErrorAction SilentlyContinue
    if (-not $files) { throw "XXL test $Name produced no output" }
  }
}
Run-XxlTest 'baseline' @() -RequireOutput
Run-XxlTest 'silero-v5' @('--vad_filter','true','--vad_method','silero_v5')
Run-XxlTest 'webrtc-vad' @('--vad_filter','true','--vad_method','webrtc')
Run-XxlTest 'auditok-vad' @('--vad_filter','true','--vad_method','auditok')
Run-XxlTest 'pyannote-onnx-vad' @('--vad_filter','true','--vad_method','pyannote_onnx_v3','--vad_device','cpu')
Run-XxlTest 'pyannote-torch-vad' @('--vad_filter','true','--vad_method','pyannote_v3','--vad_device','cpu')
Run-XxlTest 'mdx-kim2' @('--ff_vocal_extract','mdx_kim2','--voc_device','cpu')

# Diarization-only path intentionally tested separately because it does not need transcription output.
$diarOut=Join-Path $report 'out-diarize'; New-Item -ItemType Directory -Force -Path $diarOut | Out-Null
& $exe $wav --diarize pyannote_v3.1 --diarize_device cpu --diarize_only --output_dir $diarOut --verbose false *>&1 | Tee-Object -FilePath (Join-Path $report 'test-diarize.log')
$diarRc=$LASTEXITCODE; "$diarRc" | Set-Content (Join-Path $report 'test-diarize.exit')
if ($diarRc -ne 0) { throw "Diarization test failed with exit $diarRc" }

Status 'Candidate modernization passed all configured integration tests.'
$files=Get-ChildItem $root -Recurse -File; $size=($files|Measure-Object Length -Sum).Sum
@{success=$true;python=(python --version 2>&1);files=$files.Count;uncompressed_bytes=$size;git_sha=$env:GITHUB_SHA} | ConvertTo-Json | Set-Content (Join-Path $report 'candidate-success.json') -Encoding utf8
