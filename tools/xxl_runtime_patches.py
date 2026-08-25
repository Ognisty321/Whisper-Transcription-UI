#!/usr/bin/env python3
"""Compatibility-preserving runtime fixes for abandoned Faster-Whisper-XXL r245.4.

The bundled Faster-Whisper code is a heavily modified fork based on 1.1.1. A
wholesale replacement with upstream 1.2.1 removes XXL-only options and VAD/MDX
features. This module applies the small upstream fixes that are safe to
backport without replacing the custom transcriber.
"""

from __future__ import annotations

import bisect
import functools
import logging
import os
from functools import cached_property
from pathlib import Path
from typing import Iterable, Optional


PATCH_LEVEL = "xxl-modern2-20260825"


def _patch_tokenizer() -> None:
    from faster_whisper.tokenizer import Tokenizer

    if not hasattr(Tokenizer, "no_speech"):
        def no_speech(self) -> int:
            return self.tokenizer.token_to_id("<|nospeech|>") or self.tokenizer.token_to_id(
                "<|nocaptions|>"
            )

        descriptor = cached_property(no_speech)
        descriptor.__set_name__(Tokenizer, "no_speech")
        Tokenizer.no_speech = descriptor  # type: ignore[attr-defined]


def _patch_suppressed_tokens() -> None:
    import faster_whisper.transcribe as transcribe

    def get_suppressed_tokens(tokenizer, suppress_tokens):
        if suppress_tokens is None:
            suppress_tokens = []
        elif -1 in suppress_tokens:
            suppress_tokens = [token for token in suppress_tokens if token >= 0]
            suppress_tokens.extend(tokenizer.non_speech_tokens)
        elif len(suppress_tokens) == 0:
            suppress_tokens = []
        elif not isinstance(suppress_tokens, list):
            suppress_tokens = list(suppress_tokens)

        suppress_tokens.extend(
            [
                tokenizer.transcribe,
                tokenizer.translate,
                tokenizer.sot,
                tokenizer.sot_prev,
                tokenizer.sot_lm,
                tokenizer.no_speech,
            ]
        )
        return tuple(sorted(set(suppress_tokens)))

    transcribe.get_suppressed_tokens = get_suppressed_tokens


def _patch_timestamp_boundaries() -> None:
    import faster_whisper.transcribe as transcribe
    import faster_whisper.vad as vad

    def get_chunk_index(self, time: float, is_end: bool = False) -> int:
        sample = int(time * self.sampling_rate)
        if is_end and sample in self.chunk_end_sample:
            return self.chunk_end_sample.index(sample)
        return min(
            bisect.bisect(self.chunk_end_sample, sample),
            len(self.chunk_end_sample) - 1,
        )

    def get_original_time(
        self,
        time: float,
        chunk_index: Optional[int] = None,
        is_end: bool = False,
    ) -> float:
        if chunk_index is None:
            chunk_index = self.get_chunk_index(time, is_end)
        total_silence_before = self.total_silence_before[chunk_index]
        return round(total_silence_before + time, self.time_precision)

    vad.SpeechTimestampsMap.get_chunk_index = get_chunk_index
    vad.SpeechTimestampsMap.get_original_time = get_original_time
    transcribe.SpeechTimestampsMap = vad.SpeechTimestampsMap

    def restore_speech_timestamps(segments: Iterable, speech_chunks: list[dict], sampling_rate: int):
        timestamp_map = vad.SpeechTimestampsMap(speech_chunks, sampling_rate)
        for segment in segments:
            if segment.words:
                words = []
                for word in segment.words:
                    middle = (word.start + word.end) / 2
                    chunk_index = timestamp_map.get_chunk_index(middle)
                    word.start = timestamp_map.get_original_time(word.start, chunk_index)
                    word.end = timestamp_map.get_original_time(word.end, chunk_index)
                    words.append(word)
                segment.start = words[0].start
                segment.end = words[-1].end
                segment.words = words
            else:
                segment.start = timestamp_map.get_original_time(segment.start)
                segment.end = timestamp_map.get_original_time(segment.end, is_end=True)
            yield segment

    transcribe.restore_speech_timestamps = restore_speech_timestamps


def _patch_silero_vad_v6() -> None:
    import numpy as np
    import faster_whisper.vad as vad
    from faster_whisper.utils import get_assets_path

    class SileroVADModelV6Compat:
        """Silero VAD v6 with the v5 callable shape expected by XXL's code."""

        def __init__(self, path: str):
            import onnxruntime

            options = onnxruntime.SessionOptions()
            options.inter_op_num_threads = 1
            options.intra_op_num_threads = 1
            options.enable_cpu_mem_arena = False
            options.log_severity_level = 4
            self.session = onnxruntime.InferenceSession(
                path,
                providers=["CPUExecutionProvider"],
                sess_options=options,
            )

        def __call__(
            self,
            audio: np.ndarray,
            num_samples: int = 512,
            context_size_samples: int = 64,
        ) -> np.ndarray:
            source_was_2d = audio.ndim == 2
            if source_was_2d:
                if audio.shape[0] != 1:
                    raise AssertionError("Silero VAD v6 compatibility path supports batch size 1")
                audio = audio.reshape(-1)
            if audio.ndim != 1:
                raise AssertionError("Input should be a 1D array or a (1, samples) array")
            if audio.shape[0] % num_samples != 0:
                raise AssertionError("Input size should be a multiple of num_samples")

            h = np.zeros((1, 1, 128), dtype="float32")
            c = np.zeros((1, 1, 128), dtype="float32")
            batched_audio = audio.reshape(-1, num_samples)
            context = batched_audio[..., -context_size_samples:].copy()
            context[-1] = 0
            context = np.roll(context, 1, 0)
            batched_audio = np.concatenate([context, batched_audio], axis=1)

            outputs = []
            batch_size = 10000
            for offset in range(0, batched_audio.shape[0], batch_size):
                output, h, c = self.session.run(
                    None,
                    {
                        "input": batched_audio[offset : offset + batch_size],
                        "h": h,
                        "c": c,
                    },
                )
                outputs.append(output)
            result = np.concatenate(outputs, axis=0).reshape(-1)
            return result.reshape(1, -1) if source_was_2d else result

    @functools.lru_cache
    def get_vad_model():
        path = os.path.join(get_assets_path(), "silero_vad_v6.onnx")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Silero VAD v6 model is missing: {path}")
        return SileroVADModelV6Compat(path)

    vad.SileroVADModelV6Compat = SileroVADModelV6Compat
    vad.get_vad_model = get_vad_model


def _patch_model_downloads() -> None:
    import huggingface_hub
    import faster_whisper.transcribe as transcribe
    import faster_whisper.utils as utils

    utils._MODELS.setdefault(
        "distil-large-v3.5", "distil-whisper/distil-large-v3.5-ct2"
    )

    def download_model(
        size_or_id: str,
        output_dir: Optional[str] = None,
        local_files_only: bool = False,
        cache_dir: Optional[str] = None,
        revision: Optional[str] = None,
        use_auth_token=None,
    ) -> str:
        if size_or_id in utils._MODELS:
            repo_id = utils._MODELS[size_or_id]
        elif "/" in size_or_id:
            repo_id = size_or_id
        else:
            raise ValueError(
                f"Invalid model size '{size_or_id}', expected one of: "
                f"{', '.join(utils.available_models())}"
            )

        allow_patterns = [
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
        ]
        kwargs = {
            "local_files_only": local_files_only,
            "allow_patterns": allow_patterns,
        }
        if revision is not None:
            kwargs["revision"] = revision
        disabled_tqdm = getattr(utils, "disabled_tqdm", None)
        if disabled_tqdm is not None:
            kwargs["tqdm_class"] = disabled_tqdm
        if output_dir is not None:
            kwargs["local_dir"] = output_dir
        if cache_dir is not None:
            kwargs["cache_dir"] = cache_dir
        if use_auth_token is not None:
            kwargs["token"] = use_auth_token
        return huggingface_hub.snapshot_download(repo_id, **kwargs)

    utils.download_model = download_model
    transcribe.download_model = download_model


def apply_runtime_patches(contents: Path | None = None) -> dict[str, object]:
    """Apply all tested compatibility patches and return diagnostic metadata."""
    _patch_tokenizer()
    _patch_suppressed_tokens()
    _patch_timestamp_boundaries()
    _patch_silero_vad_v6()
    _patch_model_downloads()

    import faster_whisper
    import faster_whisper.vad as vad

    metadata = {
        "patch_level": PATCH_LEVEL,
        "faster_whisper_base_version": getattr(faster_whisper, "__version__", None),
        "silero_vad_model": "v6",
        "no_speech_suppression_backport": True,
        "timestamp_end_boundary_backport": True,
        "modern_huggingface_download_backport": True,
        "contents": str(contents) if contents is not None else None,
        "vad_model_function": repr(vad.get_vad_model),
    }
    logging.getLogger("faster_whisper").debug("Applied XXL runtime patches: %s", metadata)
    return metadata
