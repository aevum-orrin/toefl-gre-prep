"""Speech transcription for speaking practice. Wraps faster-whisper (local, offline, free) —
chosen over openai-whisper because it needs no PyTorch and is much faster on CPU (laptop or
login node), while still bundling model download + audio decoding.

Notes:
- Recording happens in the *browser* (getUserMedia / MediaRecorder); the app uploads the clip.
- The model is downloaded from HuggingFace on first use and cached under ~/.cache.
- Import is lazy so `import prep_core` stays cheap where audio is never transcribed.
- For heavy/batch use on the cluster, run on a compute node (Slurm), not a login node.
"""
from __future__ import annotations

import re


class Transcriber:
    def __init__(self, model_name: str = "tiny.en", compute_type: str = "int8"):
        self.model_name = model_name      # tiny.en fast/rough; bump to base.en/small.en for accuracy
        self.compute_type = compute_type
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # optional dep: pip install prep-core[audio]
            self._model = WhisperModel(self.model_name, device="cpu", compute_type=self.compute_type)
        return self._model

    def transcribe(self, audio_path: str) -> dict:
        """Return {'text', 'language', 'segments'} for the given audio file (webm/ogg/wav/...)."""
        segments, info = self._load().transcribe(str(audio_path))
        segs = list(segments)
        text = " ".join(s.text.strip() for s in segs).strip()
        return {
            "text": text,
            "language": info.language,
            "segments": [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs],
        }


def word_accuracy(reference: str, hypothesis: str) -> float:
    """Fraction of reference words hit, for Listen-and-Repeat scoring (order-insensitive, crude)."""
    norm = lambda s: re.findall(r"[a-z']+", s.lower())
    ref, hyp = norm(reference), norm(hypothesis)
    if not ref:
        return 0.0
    hyp_pool = list(hyp)
    hits = 0
    for w in ref:
        if w in hyp_pool:
            hyp_pool.remove(w)
            hits += 1
    return round(hits / len(ref), 3)
