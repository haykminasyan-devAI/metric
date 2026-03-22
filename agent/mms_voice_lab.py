"""
Optional MMS voice lab (standalone).

This file does NOT modify the existing OpenAI STT/TTS pipeline in agent/main.py.
Use it only for local MMS experiments.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _require_runtime():
    try:
        import torch  # noqa: F401
        import soundfile as sf  # noqa: F401
        from transformers import AutoProcessor, AutoModelForCTC, VitsModel, VitsTokenizer  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing MMS dependencies. Install with:\n"
            "  pip install transformers soundfile torch\n"
        ) from exc


def transcribe_with_mms(audio_path: Path, lang: str = "hye") -> str:
    """
    MMS ASR using facebook/mms-1b-all + language adapter (e.g., hye for Armenian).
    """
    _require_runtime()
    import torch
    import soundfile as sf
    from transformers import AutoProcessor, AutoModelForCTC

    model_id = "facebook/mms-1b-all"

    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForCTC.from_pretrained(model_id)

    # Configure requested language adapter when available.
    if hasattr(processor, "tokenizer") and hasattr(processor.tokenizer, "set_target_lang"):
        processor.tokenizer.set_target_lang(lang)
    if hasattr(model, "load_adapter"):
        model.load_adapter(lang)

    audio, sampling_rate = sf.read(str(audio_path))
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    inputs = processor(audio, sampling_rate=sampling_rate, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    predicted_ids = torch.argmax(logits, dim=-1)
    text = processor.batch_decode(predicted_ids)[0]
    return text.strip()


def synthesize_with_mms(text: str, output_wav: Path, model_id: str = "facebook/mms-tts-hye") -> None:
    """
    MMS TTS for Armenian (hye).
    """
    _require_runtime()
    import torch
    import soundfile as sf
    from transformers import VitsModel, VitsTokenizer

    tokenizer = VitsTokenizer.from_pretrained(model_id)
    model = VitsModel.from_pretrained(model_id)

    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        output = model(**inputs).waveform

    waveform = output.squeeze().cpu().numpy()
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_wav), waveform, model.config.sampling_rate)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone MMS ASR/TTS lab")
    sub = parser.add_subparsers(dest="cmd", required=True)

    asr = sub.add_parser("asr", help="Transcribe audio with MMS ASR")
    asr.add_argument("--input", required=True, help="Path to input audio (wav preferred)")
    asr.add_argument("--lang", default="hye", help="MMS language code (default: hye)")

    tts = sub.add_parser("tts", help="Synthesize speech with MMS TTS")
    tts.add_argument("--text", required=True, help="Input text")
    tts.add_argument("--output", required=True, help="Output wav file path")
    tts.add_argument("--model", default="facebook/mms-tts-hye", help="TTS model id")

    args = parser.parse_args()

    if args.cmd == "asr":
        result = transcribe_with_mms(Path(args.input), lang=args.lang)
        print(result)
        return

    synthesize_with_mms(args.text, Path(args.output), model_id=args.model)
    print(f"Saved TTS audio to: {args.output}")


if __name__ == "__main__":
    main()

