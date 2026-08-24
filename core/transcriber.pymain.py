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


class AudioTranscriber:
    def __init__(
        self,
        model_path: str | Path,
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        """
        Inisialisasi WhisperModel dari path direktori lokal.
        
        :param model_path: Path direktori lokal ke model faster-whisper yang di-bundle.
        :param device: Device komputasi ("cpu" atau "cuda").
        :param compute_type: Tipe kuantisasi ("int8", "float16", "float32").
        """
        self.model_path = Path(model_path).resolve()
        self.device = device
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None
        self._load_model()

    def _load_model(self) -> None:
        """Memuat model secara offline dari path lokal tanpa internet access."""
        if not self.model_path.exists() or not self.model_path.is_dir():
            raise ModelLoadError(
                f"Direktori model tidak ditemukan di: {self.model_path}. "
                "Pastikan model telah didownload dan ditaruh di folder lokal tersebut."
            )
        
        try:
            # Load model dari path lokal absolut (menghindari auto-download HuggingFace)
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

        :param audio_path: Path ke file audio (mp3/wav/dll).
        :param language: Kode bahasa opsional (misal: "id", "en"). Jika None, auto-detect.
        :param progress_callback: Fungsi callback opsional menerima estimasi persentase (0.0 - 100.0).
        :param is_cancelled: Fungsi callback opsional yang mengembalikan bool untuk abort/cancel proses dari QThread.
        :return: List of dicts persis sesuai Bagian 4 dokumen konteks.
        """
        if self.model is None:
            raise ModelLoadError("Model belum berhasil diinisialisasi.")

        resolved_audio_path = Path(audio_path).resolve()

        # Validasi file audio
        if not resolved_audio_path.exists() or not resolved_audio_path.is_file():
            raise AudioTranscriptionError(f"File audio tidak ditemukan di: {resolved_audio_path}")

        if resolved_audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise AudioTranscriptionError(
                f"Format file '{resolved_audio_path.suffix}' tidak didukung. "
                f"Gunakan salah satu dari: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )

        try:
            # word_timestamps diaktifkan untuk akurasi sinkronisasi
            segments_generator, info = self.model.transcribe(
                str(resolved_audio_path),
                language=language,
                word_timestamps=True,
                vad_filter=True
            )

            total_duration = info.duration if info.duration > 0 else 1.0
            formatted_segments: List[Dict[str, Any]] = []
            segment_id = 1

            for segment in segments_generator:
                # Cek apakah ada sinyal pembatalan dari thread UI
                if is_cancelled and is_cancelled():
                    break

                text_cleaned = segment.text.strip()
                if text_cleaned:
                    # Format output persis sesuai Bagian 4 PROJECT_CONTEXT.md
                    formatted_segments.append({
                        "id": segment_id,
                        "start": round(float(segment.start), 3),
                        "end": round(float(segment.end), 3),
                        "text": text_cleaned
                    })
                    segment_id += 1

                # Update progress callback berdasarkan durasi audio yang telah diproses
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

    print(f"Loading model dari: {args.model_dir} ...")
    try:
        transcriber = AudioTranscriber(model_path=args.model_dir)
        print("Model berhasil dimuat.")
        print(f"Memproses file audio: {args.audio} ...")
        
        results = transcriber.transcribe(
            audio_path=args.audio,
            language=args.lang,
            progress_callback=print_progress
        )
        
        print("\n\nHasil Transkripsi (Format Sesuai Struktur Data Bagian 4):")
        print(json.dumps(results, indent=4, ensure_ascii=False))

    except Exception as err:
        print(f"\n[ERROR]: {err}", file=sys.stderr)
        sys.exit(1)
