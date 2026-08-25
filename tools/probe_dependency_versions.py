#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

PACKAGES = [
    ("faster-whisper-custom", "faster_whisper"),
    ("torch", "torch"), ("torchvision", "torchvision"), ("torchaudio", "torchaudio"),
    ("ctranslate2", "ctranslate2"), ("onnxruntime-gpu", "onnxruntime"),
    ("numpy", "numpy"), ("scipy", "scipy"), ("scikit-learn", "sklearn"),
    ("pandas", "pandas"), ("numba", "numba"), ("llvmlite", "llvmlite"),
    ("pyannote.audio", "pyannote.audio"), ("pyannote.core", "pyannote.core"),
    ("pyannote.database", "pyannote.database"), ("pyannote.metrics", "pyannote.metrics"),
    ("pyannote.pipeline", "pyannote.pipeline"),
    ("lightning", "lightning"), ("pytorch-lightning", "pytorch_lightning"),
    ("lightning-fabric", "lightning_fabric"), ("torchmetrics", "torchmetrics"),
    ("huggingface-hub", "huggingface_hub"), ("tokenizers", "tokenizers"),
    ("sentencepiece", "sentencepiece"), ("safetensors", "safetensors"),
    ("av", "av"), ("librosa", "librosa"), ("soundfile", "soundfile"),
    ("soxr", "soxr"), ("audioread", "audioread"), ("pydub", "pydub"),
    ("ffmpeg-python", "ffmpeg"), ("auditok", "auditok"), ("webrtcvad-wheels", "webrtcvad"),
    ("einops", "einops"), ("asteroid-filterbanks", "asteroid_filterbanks"),
    ("julius", "julius"), ("torch-audiomentations", "torch_audiomentations"),
    ("torch-pitch-shift", "torch_pitch_shift"), ("rotary-embedding-torch", "rotary_embedding_torch"),
    ("pytorch-metric-learning", "pytorch_metric_learning"),
    ("optuna", "optuna"), ("SQLAlchemy", "sqlalchemy"), ("alembic", "alembic"),
    ("omegaconf", "omegaconf"), ("beartype", "beartype"),
    ("networkx", "networkx"), ("sympy", "sympy"), ("Pillow", "PIL"),
    ("matplotlib", "matplotlib"), ("rich", "rich"), ("tqdm", "tqdm"),
    ("requests", "requests"), ("urllib3", "urllib3"), ("certifi", "certifi"),
    ("charset-normalizer", "charset_normalizer"), ("idna", "idna"),
    ("PyYAML", "yaml"), ("packaging", "packaging"), ("filelock", "filelock"),
    ("fsspec", "fsspec"), ("platformdirs", "platformdirs"), ("pooch", "pooch"),
    ("joblib", "joblib"), ("threadpoolctl", "threadpoolctl"),
    ("typing-extensions", "typing_extensions"), ("psutil", "psutil"),
    ("attrs", "attr"), ("cffi", "cffi"), ("pycparser", "pycparser"),
    ("protobuf", "google.protobuf"), ("tensorboardX", "tensorboardX"),
    ("aiohttp", "aiohttp"), ("yarl", "yarl"), ("multidict", "multidict"),
    ("frozenlist", "frozenlist"), ("aiosignal", "aiosignal"),
    ("pyreadline3", "pyreadline3"), ("colorama", "colorama"),
    ("semver", "semver"), ("tabulate", "tabulate"),
]

CHILD = r'''
import importlib, json, os, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve(); modname = sys.argv[2]
search = [root, root/'ctranslate2', root/'torch'/'lib', root/'onnxruntime'/'capi']
os.environ['PATH'] = os.pathsep.join([str(p) for p in search if p.is_dir()] + [os.environ.get('PATH','')])
handles=[]
if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
    for p in search:
        if p.is_dir():
            try: handles.append(os.add_dll_directory(str(p)))
            except OSError: pass
sys.path.insert(0, str(root))
try:
    m=importlib.import_module(modname)
    vals=[]
    for attr in ('__version__','VERSION','version'):
        try:
            v=getattr(m, attr)
            if isinstance(v, (str,int,float,tuple,list)):
                vals.append([attr, str(v)])
            elif hasattr(v,'__version__'):
                vals.append([attr+'.__version__', str(v.__version__)])
        except Exception: pass
    print(json.dumps({'ok':True,'module':modname,'file':str(getattr(m,'__file__',None)),'versions':vals}))
except BaseException as e:
    print(json.dumps({'ok':False,'module':modname,'error':type(e).__name__+': '+str(e)}))
'''

def probe_import(root: Path, module: str) -> dict:
    p = subprocess.run([sys.executable, '-c', CHILD, str(root), module], capture_output=True, text=True, timeout=90)
    lines=[x for x in p.stdout.splitlines() if x.strip()]
    try:
        data=json.loads(lines[-1]) if lines else {'ok':False,'error':'no JSON output'}
    except Exception:
        data={'ok':False,'error':'invalid JSON output','stdout':p.stdout[-4000:]}
    data['exit_code']=p.returncode
    if p.stderr.strip(): data['stderr_tail']=p.stderr[-4000:]
    return data

def pypi_latest(dist: str) -> dict:
    if dist == 'faster-whisper-custom':
        dist = 'faster-whisper'
    url=f'https://pypi.org/pypi/{dist}/json'
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            obj=json.load(r)
    except Exception as e:
        return {'error':type(e).__name__+': '+str(e)}
    latest=obj.get('info',{}).get('version')
    compatible=[]
    target=Version('3.10.11')
    for ver, files in obj.get('releases',{}).items():
        try: vv=Version(ver)
        except InvalidVersion: continue
        if vv.is_prerelease or vv.is_devrelease: continue
        ok=False
        for f in files or []:
            if f.get('yanked'): continue
            req=f.get('requires_python')
            try:
                if req and target not in SpecifierSet(req): continue
            except Exception: pass
            fn=f.get('filename','')
            if fn.endswith('.whl') and ('-py3-none-any.whl' in fn or '-cp310-' in fn or '-abi3-' in fn):
                ok=True; break
        if ok: compatible.append(vv)
    best=str(max(compatible)) if compatible else None
    return {'pypi_latest':latest,'latest_py310_binary_candidate':best,'requires_python_latest':obj.get('info',{}).get('requires_python')}

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('contents', type=Path); ap.add_argument('--output', type=Path, required=True); args=ap.parse_args()
    root=args.contents.resolve()
    out={'python':sys.version,'contents':str(root),'packages':{}}
    for dist, mod in PACKAGES:
        item={'distribution':dist,'import':mod}
        item['bundled']=probe_import(root,mod)
        item['index']=pypi_latest(dist)
        out['packages'][dist]=item
        print(dist, item['bundled'].get('versions'), item['index'].get('latest_py310_binary_candidate'), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
