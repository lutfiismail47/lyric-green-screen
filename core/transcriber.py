import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
from faster_whisper import WhisperModel

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}


class AudioTranscriptionError(Exception):
    """Exception custom untuk error pada proses transkripsi audio."""
    pass


class ModelLoadError(Exception):
    """Exception custom jika path model lokal tidak valid atau gagal dimuat."""
    pass


def resolve_asset_path(relative_path: str | Path) -> Path:
    """
    Mendapatkan path absolut valid saat berjalan di mode dev biasa
    maupun di dalam bundle frozen PyInstaller (_internal).
    """
    rel_p = Path(relative_path)

    if getattr(sys, 'frozen', False):
        # 1. Cek di sys._MEIPASS (PyInstaller onedir internal)
        meipass_dir = Path(getattr(sys, '_MEIPASS', ''))
        if (meipass_dir / rel_p).exists():
            return meipass_dir / rel_p

        # 2. Cek di folder _internal di samping binary executable
        exe_dir = Path(sys.executable).parent
        internal_dir = exe_dir / "_internal" / rel_p
        if internal_dir.exists():
            return internal_dir

        # 3. Cek langsung di direktori yang sama dengan executable
        if (exe_dir / rel_p).exists():
            return exe_dir / rel_p

    # 4. Mode Development (saat menjalankan via python main.py)
    dev_path = Path.cwd() / rel_p
    if dev_path.exists():
        return dev_path

    base_file_path = Path(__file__).resolve().parent.parent / rel_p
    if base_file_path.exists():
        return base_file_path

    return rel_p.resolve()


class AudioTranscriber:
    def __init__(
        self,
        model_path: str | Path = "assets/models/faster-whisper-base",
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        self.model_path = resolve_asset_path(model_path)
        self.device = device
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None
        self._load_model()

    def _load_model(self) -> None:
        """Memuat model secara offline dari path lokal tanpa fetch internet."""
        if not self.model_path.exists() or not self.model_path.is_dir():
            raise ModelLoadError(
                f"Direktori model tidak ditemukan di: {self.model_path}. "
                "Pastikan model telah didownload dan ditaruh di folder lokal tersebut."
            )
        
        try:
            self.model = WhisperModel(
                str(self.model_path),
                device=self.device,
                compute_type=self.compute_type
            )
        except Exception as e:
            raise ModelLoadError(f"Gagal memuat model faster-whisper dari {self.model_path}: {e}")

    def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Melakukan transkripsi file audio menjadi list of segment dictionaries.
        """
        if self.model is None:
            raise ModelLoadError("Model belum berhasil diinisialisasi.")

        resolved_audio_path = Path(audio_path).resolve()

        if not resolved_audio_path.exists() or not resolved_audio_path.is_file():
            raise AudioTranscriptionError(f"File audio tidak ditemukan di: {resolved_audio_path}")

        if resolved_audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise AudioTranscriptionError(
                f"Format file '{resolved_audio_path.suffix}' tidak didukung. "
                f"Gunakan salah satu dari: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )

        try:
            segments_generator, info = self.model.transcribe(
                str(resolved_audio_path),
                language=language,
                word_timestamps=True,
                vad_filter=False,
                no_speech_threshold=0.6,
                condition_on_previous_text=False,
                temperature=[0.0, 0.2, 0.4]
            )

            total_duration = info.duration if info.duration > 0 else 1.0
            formatted_segments: List[Dict[str, Any]] = []
            segment_id = 1

            for segment in segments_generator:
                if is_cancelled and is_cancelled():
                    break

                text_cleaned = segment.text.strip()
                if text_cleaned:
                    formatted_segments.append({
                        "id": segment_id,
                        "start": round(float(segment.start), 3),
                        "end": round(float(segment.end), 3),
                        "text": text_cleaned
                    })
                    segment_id += 1

                if progress_callback:
                    current_progress = min(100.0, (segment.end / total_duration) * 100.0)
                    progress_callback(round(current_progress, 1))

            if progress_callback and not (is_cancelled and is_cancelled()):
                progress_callback(100.0)

            return formatted_segments

        except Exception as e:
            if isinstance(e, AudioTranscriptionError):
                raise e
            raise AudioTranscriptionError(f"Terjadi kesalahan saat memproses audio: {e}")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Test CLI Transcriber Module")
    parser.add_argument("--audio", type=str, required=True, help="Path ke file audio untuk ditranskripsi")
    parser.add_argument(
        "--model-dir",
        type=str,
        default="assets/models/faster-whisper-base",
        help="Path lokal direktori model faster-whisper"
    )
    parser.add_argument("--lang", type=str, default=None, help="Kode bahasa opsional (misal: 'id', 'en')")
    
    args = parser.parse_args()

    def print_progress(percent: float):
        print(f"\rProgress: {percent:.1f}%", end="", flush=True)

    print(f"Loading model dari: {args.model_dir} ...", flush=True)
    try:
        transcriber = AudioTranscriber(model_path=args.model_dir)
        print("Model berhasil dimuat.", flush=True)
        print(f"Memproses file audio: {args.audio} ...", flush=True)
        
        results = transcriber.transcribe(
            audio_path=args.audio,
            language=args.lang,
            progress_callback=print_progress
        )
        
        print("\n\nHasil Transkripsi (Format Sesuai Struktur Data Bagian 4):", flush=True)
        print(json.dumps(results, indent=4, ensure_ascii=False))

    except Exception as err:
        print(f"\n[ERROR]: {err}", file=sys.stderr, flush=True)
        sys.exit(1)