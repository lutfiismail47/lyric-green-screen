import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from PIL import ImageColor
from PyQt6.QtCore import QThread, pyqtSignal


class ExporterError(Exception):
    pass


def get_ffmpeg_binary_path() -> Path:
    is_windows = platform.system() == "Windows"
    binary_name = "ffmpeg.exe" if is_windows else "ffmpeg"
    folder_name = "ffmpeg_windows" if is_windows else "ffmpeg_linux"
    rel_path = Path("bin") / folder_name / binary_name

    # 1. Cek bundle PyInstaller
    if getattr(sys, 'frozen', False):
        base_path = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
        candidate = base_path / rel_path
        if candidate.exists() and os.access(candidate, os.X_OK | (os.R_OK if is_windows else 0)):
            return candidate

    # 2. Cek folder lokal proyek
    local_bin = Path.cwd() / rel_path
    if local_bin.exists() and os.access(local_bin, os.X_OK | (os.R_OK if is_windows else 0)):
        return local_bin.resolve()

    # 3. Fallback ke PATH sistem
    system_bin = shutil.which("ffmpeg")
    if system_bin:
        return Path(system_bin).resolve()

    raise ExporterError(
        f"Binary FFmpeg '{binary_name}' tidak ditemukan di bundle aplikasi maupun PATH sistem."
    )


class VideoExportWorker(QThread):
    """
    Worker ekspor video ultra-cepat: Merender langsung ke stdin FFmpeg (Zero Disk I/O).
    """
    progress_changed = pyqtSignal(str, float)
    export_finished = pyqtSignal(str)
    export_failed = pyqtSignal(str)

    def __init__(
        self,
        renderer,
        audio_path: str | Path,
        output_path: str | Path,
        total_duration: float,
        video_settings: Dict[str, Any]
    ):
        super().__init__()
        self.renderer = renderer
        self.audio_path = Path(audio_path).resolve()
        self.output_path = Path(output_path).resolve()
        self.total_duration = total_duration
        self.video_settings = video_settings
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        process = None
        try:
            ffmpeg_bin = get_ffmpeg_binary_path()
            if not self.audio_path.exists():
                raise ExporterError(f"File audio tidak ditemukan: {self.audio_path}")

            self.output_path.parent.mkdir(parents=True, exist_ok=True)

            width, height = self.video_settings.get("resolution", [1920, 1080])
            fps = self.video_settings.get("fps", 30)
            total_frames = int(self.total_duration * fps)

            if total_frames <= 0:
                raise ExporterError("Durasi video tidak valid atau kosong.")

            # Command FFmpeg menerima streaming rawvideo langsung lewat pipe stdin
            cmd = [
                str(ffmpeg_bin),
                "-y",
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-s", f"{width}x{height}",
                "-pix_fmt", "rgba",
                "-r", str(fps),
                "-i", "pipe:0",                   # Input video dari Python stdin
                "-i", str(self.audio_path),        # Input audio
                "-c:v", "libx264",
                "-preset", "veryfast",             # Encoding preset cepat & efisien
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(self.output_path)
            ]

            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )

            self.progress_changed.emit("Merender dan meng-encode video...", 0.0)

            # Stream setiap frame byte buffer langsung ke FFmpeg
            frame_count = 0
            for frame_img in self.renderer.generate_all_frames(
                self.total_duration,
                is_cancelled=lambda: self._is_cancelled
            ):
                if self._is_cancelled:
                    break

                # Konversi Image ke raw byte RGBA
                raw_bytes = frame_img.tobytes("raw", "RGBA")
                try:
                    process.stdin.write(raw_bytes)
                except (BrokenPipeError, IOError):
                    break

                frame_count += 1
                if frame_count % max(1, total_frames // 100) == 0:
                    percent = min(99.0, (frame_count / total_frames) * 100.0)
                    self.progress_changed.emit(f"Rendering ({percent:.1f}%)...", percent)

            # Tutup pipe stdin agar FFmpeg menyelesaikan finalisasi container MP4
            if process.stdin:
                process.stdin.close()

            stderr_output = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
            process.wait()

            if self._is_cancelled:
                if self.output_path.exists():
                    self.output_path.unlink()
                self.export_failed.emit("Export dibatalkan.")
                return

            if process.returncode != 0:
                raise ExporterError(f"FFmpeg error:\n{stderr_output}")

            self.progress_changed.emit("Selesai!", 100.0)
            self.export_finished.emit(str(self.output_path))

        except Exception as e:
            if self.output_path.exists() and self._is_cancelled:
                self.output_path.unlink()
            self.export_failed.emit(str(e))

        finally:
            if process and process.poll() is None:
                process.kill()

def get_bundle_dir() -> Path:
    """Mendapatkan path base proyek baik saat dev maupun bundle executable."""
    if getattr(sys, 'frozen', False):
        # Saat running dari PyInstaller binary
        return Path(sys._MEIPASS if hasattr(sys, '_MEIPASS') else getattr(sys, 'executable', '')).parent
    return Path(__file__).resolve().parent.parent