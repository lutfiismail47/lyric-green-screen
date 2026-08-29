from pathlib import Path
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, QUrl, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QInputDialog
)
from ui.editor_widget import LyricsEditorWidget
from ui.waveform_widget import WaveformWidget
from ui.preview_widget import PreviewWidget
from core.transcriber import AudioTranscriber
from core.renderer import FrameRenderer
from core.exporter import VideoExportWorker
from core.project_io import save_project_file, load_project_file, ProjectIOError
from core.srt_io import export_to_srt, import_from_srt


class TranscriptionWorker(QThread):
    """Worker thread untuk speech-to-text otomatis tanpa membekukan UI."""
    progress_changed = pyqtSignal(float)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, audio_path: str, model_path: str = "assets/models/faster-whisper-base"):
        super().__init__()
        self.audio_path = audio_path
        self.model_path = model_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            transcriber = AudioTranscriber(model_path=self.model_path)
            segments = transcriber.transcribe(
                audio_path=self.audio_path,
                language="id",
                progress_callback=self.progress_changed.emit,
                is_cancelled=lambda: self._is_cancelled
            )
            if not self._is_cancelled:
                self.finished.emit(segments)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mimik | Turn Audio into Lyrics, Instantly")
        self.resize(1000, 800)
        self.setMinimumSize(800, 600)

        self.current_audio_path: Optional[str] = None
        self._is_user_seeking: bool = False
        self.current_project_path: Optional[str] = None

        self._init_player()
        self._init_menu_and_toolbar()
        self._init_ui()
        self._connect_signals()

        self.render_timer = QTimer(self)
        self.render_timer.setInterval(33)
        self.render_timer.timeout.connect(self._on_render_tick)

    def _init_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

    def _init_menu_and_toolbar(self):
        self.menuBar().setVisible(False)

        self.action_new = QAction("New Project", self)
        self.action_open = QAction("Open Project", self)
        self.action_save = QAction("Save Project", self)
        self.action_import_audio = QAction("Import Audio", self)
        self.action_import_srt = QAction("Import SRT", self)
        self.action_export_srt = QAction("Export SRT", self)
        self.action_export_video = QAction("Export Video", self)
        self.action_exit = QAction("Exit", self)
        self.action_exit.triggered.connect(self.close)

        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.action_new)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_save)
        toolbar.addSeparator()
        toolbar.addAction(self.action_import_audio)
        toolbar.addAction(self.action_import_srt)
        toolbar.addSeparator()
        toolbar.addAction(self.action_export_srt)
        toolbar.addAction(self.action_export_video)

        self.action_import_audio.triggered.connect(self._on_import_audio_dialog)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Vertical)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        self.preview_area = PreviewWidget(self)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        self.btn_play = QPushButton("▶ Play")
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_stop = QPushButton("⏹ Stop")

        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addStretch()

        top_layout.addWidget(self.preview_area)
        top_layout.addLayout(controls_layout)

        self.waveform_area = WaveformWidget(self)

        self.editor_area = LyricsEditorWidget(self)

        splitter.addWidget(top_container)
        splitter.addWidget(self.waveform_area)
        splitter.addWidget(self.editor_area)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 4)

        main_layout.addWidget(splitter)

    def _connect_signals(self):
        self.btn_play.clicked.connect(self._play_audio)
        self.btn_pause.clicked.connect(self._pause_audio)
        self.btn_stop.clicked.connect(self._stop_audio)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.waveform_area.seek_requested.connect(self._seek_to_time)
        self.editor_area.segment_selected.connect(self._on_segment_selected_in_editor)
        self.editor_area.data_changed.connect(self._on_editor_data_changed)
        self.action_export_video.triggered.connect(self._on_export_video_dialog)
        self.action_new.triggered.connect(self._on_new_project)
        self.action_save.triggered.connect(self._on_save_project)
        self.action_open.triggered.connect(self._on_open_project)
        self.action_import_srt.triggered.connect(self._on_import_srt_dialog)
        self.action_export_srt.triggered.connect(self._on_export_srt_dialog)

    # Audio Playback Logic

    def _play_audio(self):
        if not self.current_audio_path:
            return
        self.player.play()
        self.render_timer.start()

    def _pause_audio(self):
        self.player.pause()
        self.render_timer.stop()

    def _stop_audio(self):
        self.player.stop()
        self.render_timer.stop()
        self.waveform_area.set_playback_position(0.0)
        self.preview_area.update_state(0.0, None)

    def _seek_to_time(self, seconds: float):
        """Seek audio ke waktu spesifik (dalam detik)."""
        target_ms = int(seconds * 1000)
        self.player.setPosition(target_ms)
        self._sync_ui_state(seconds)

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            if not self.render_timer.isActive():
                self.render_timer.start()
        else:
            if self.render_timer.isActive():
                self.render_timer.stop()

    # Synchronized Loop Tick

    def _on_render_tick(self):
        """Loop eksekusi per ~33ms saat audio play untuk update waveform, tabel, dan preview."""
        current_sec = self.player.position() / 1000.0
        self._sync_ui_state(current_sec)

    def _sync_ui_state(self, current_sec: float):
        self.waveform_area.set_playback_position(current_sec)

        segments = self.editor_area.export_segments()
        active_segment: Optional[Dict[str, Any]] = None
        active_index: Optional[int] = None

        for idx, seg in enumerate(segments):
            if seg["start"] <= current_sec <= seg["end"]:
                active_segment = seg
                active_index = idx
                break

        if active_index is not None:
            self.editor_area.table.blockSignals(True)
            self.editor_area.table.selectRow(active_index)
            self.editor_area.table.blockSignals(False)

        self.preview_area.update_state(current_sec, active_segment)

    # Event Handlers Antar Widget

    def _on_segment_selected_in_editor(self, segment: Dict[str, Any]):
        start_time = segment.get("start", 0.0)
        self._seek_to_time(start_time)

    def _on_editor_data_changed(self):
        segments = self.editor_area.export_segments()
        self.waveform_area.update_segments(segments)
        
        current_sec = self.player.position() / 1000.0
        self._sync_ui_state(current_sec)

    def _on_import_audio_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Audio",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.ogg *.flac *.aac)"
        )
        if file_path:
            self.load_audio_file(file_path)

    def load_audio_file(self, audio_path: str):
        path = Path(audio_path).resolve()
        if not path.exists():
            QMessageBox.critical(self, "Error", f"File audio tidak ditemukan: {path}")
            return

        self._stop_audio()
        self.current_audio_path = str(path)

        self.player.setSource(QUrl.fromLocalFile(self.current_audio_path))
        self.waveform_area.load_audio(self.current_audio_path)

        self.transcribe_dialog = QProgressDialog("Mendeteksi lirik dari audio...", "Batal", 0, 100, self)
        self.transcribe_dialog.setWindowTitle("Speech-to-Text Otomatis")
        self.transcribe_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.transcribe_dialog.setMinimumDuration(0)
        self.transcribe_dialog.setValue(0)

        self.transcribe_worker = TranscriptionWorker(self.current_audio_path)
        
        self.transcribe_worker.progress_changed.connect(
            lambda val: self.transcribe_dialog.setValue(int(val))
        )
        self.transcribe_dialog.canceled.connect(self.transcribe_worker.cancel)

        self.transcribe_worker.finished.connect(self._on_transcription_finished)
        self.transcribe_worker.error.connect(self._on_transcription_error)

        self.transcribe_worker.start()

    def _on_transcription_finished(self, segments: list):
        self.transcribe_dialog.close()
        self.editor_area.load_segments(segments)
        self.waveform_area.update_segments(segments)
        QMessageBox.information(
            self,
            "Selesai",
            f"Berhasil mendeteksi {len(segments)} baris lirik otomatis!\n"
            "Anda bisa menyesuaikan teks atau timing jika diperlukan."
        )

    def _on_transcription_error(self, err_msg: str):
        self.transcribe_dialog.close()
        QMessageBox.warning(
            self,
            "Transkripsi Gagal",
            f"Gagal mendeteksi lirik otomatis:\n{err_msg}\n\n"
            "Anda tetap bisa menambahkan lirik secara manual melalui tabel editor."
        )

    def _on_export_video_dialog(self):
        if not self.current_audio_path:
            QMessageBox.warning(self, "Peringatan", "Silakan import file audio terlebih dahulu.")
            return

        segments = self.editor_area.export_segments()
        if not segments:
            QMessageBox.warning(self, "Peringatan", "Tidak ada segmen lirik untuk diekspor.")
            return

        resolutions = {
            "1080p (FHD - 1920x1080)": [1920, 1080],
            "720p (HD - 1280x720)": [1280, 720],
            "480p (SD - 854x480)": [854, 480],
        }
        res_items = list(resolutions.keys())
        
        selected_res_label, ok = QInputDialog.getItem(
            self,
            "Pilih Resolusi Video",
            "Resolusi Output:",
            res_items,
            current=0,
            editable=False
        )
        if not ok or not selected_res_label:
            return

        target_resolution = resolutions[selected_res_label]

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Video Green Screen",
            "Output_Lyrics.mp4",
            "Video Files (*.mp4)"
        )
        if not output_path:
            return

        total_duration = self.player.duration() / 1000.0
        if total_duration <= 0 and segments:
            total_duration = segments[-1]["end"] + 1.0

        base_style = dict(self.preview_area.style)
        video_settings = dict(self.preview_area.video_settings)
        video_settings["resolution"] = target_resolution

        scale_factor = target_resolution[1] / 1080.0
        base_style["font_size"] = max(12, int(base_style.get("font_size", 64) * scale_factor))

        renderer = FrameRenderer(base_style, video_settings, segments)

        self.export_dialog = QProgressDialog("Menyiapkan render video...", "Batal", 0, 100, self)
        self.export_dialog.setWindowTitle("Export Video Green Screen")
        self.export_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.export_dialog.setMinimumDuration(0)
        self.export_dialog.setValue(0)

        self.export_worker = VideoExportWorker(
            renderer=renderer,
            audio_path=self.current_audio_path,
            output_path=output_path,
            total_duration=total_duration,
            video_settings=video_settings
        )

        self.export_worker.progress_changed.connect(self._on_export_progress)
        self.export_dialog.canceled.connect(self.export_worker.cancel)
        self.export_worker.export_finished.connect(self._on_export_success)
        self.export_worker.export_failed.connect(self._on_export_error)

        self.export_worker.start()

    def _on_export_progress(self, message: str, percent: float):
        self.export_dialog.setLabelText(message)
        self.export_dialog.setValue(int(percent))

    def _on_export_success(self, output_file: str):
        self.export_dialog.close()
        QMessageBox.information(
            self,
            "Export Selesai",
            f"Video green screen berhasil dibuat!\nTersimpan di:\n{output_file}"
        )

    def _on_export_error(self, err_msg: str):
        self.export_dialog.close()
        QMessageBox.critical(
            self,
            "Export Gagal",
            f"Terjadi kesalahan saat memproses video:\n{err_msg}"
        )

    # Project Management Handlers

    def _on_new_project(self):
        """Mereset state kerja untuk memulai proyek baru."""
        if self.editor_area.export_segments() or self.current_audio_path:
            reply = QMessageBox.question(
                self,
                "Proyek Baru",
                "Apakah Anda yakin ingin membuat proyek baru? Perubahan yang belum disimpan akan hilang.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._stop_audio()
        self.current_audio_path = None
        self.current_project_path = None
        self.editor_area.load_segments([])
        self.waveform_area.load_audio("")
        self.preview_area.update_state(0.0, None)
        self.setWindowTitle("Mimik | Turn Audio into Lyrics, Instantly - Proyek Baru")

    def _on_save_project(self):
        """Menyimpan data audio, segmen lirik, style, dan video settings ke file .lyricproj."""
        if not self.current_audio_path and not self.editor_area.export_segments():
            QMessageBox.warning(self, "Peringatan", "Tidak ada data proyek untuk disimpan.")
            return

        if not self.current_project_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Simpan Proyek",
                "my_lyrics.lyricproj",
                "Lyric Project Files (*.lyricproj)"
            )
            if not file_path:
                return
            self.current_project_path = file_path

        project_data = {
            "version": "1.0",
            "audio_path": self.current_audio_path or "",
            "segments": self.editor_area.export_segments(),
            "style": self.preview_area.style,
            "video_settings": self.preview_area.video_settings
        }

        try:
            save_project_file(self.current_project_path, project_data)
            self.setWindowTitle(f"Mimik | Turn Audio into Lyrics, Instantly - {Path(self.current_project_path).name}")
            QMessageBox.information(self, "Tersimpan", "Proyek berhasil disimpan!")
        except ProjectIOError as err:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan proyek:\n{err}")

    def _on_open_project(self):
        """Membuka file .lyricproj dan memulihkan seluruh state aplikasi."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Buka Proyek",
            "",
            "Lyric Project Files (*.lyricproj)"
        )
        if not file_path:
            return

        try:
            project_data = load_project_file(file_path)
            self.current_project_path = file_path

            self.preview_area.set_config(
                style=project_data.get("style", {}),
                video_settings=project_data.get("video_settings", {})
            )

            audio_p = project_data.get("audio_path", "")
            if audio_p and Path(audio_p).exists():
                self._stop_audio()
                self.current_audio_path = str(Path(audio_p).resolve())
                self.player.setSource(QUrl.fromLocalFile(self.current_audio_path))
                self.waveform_area.load_audio(self.current_audio_path)
            else:
                self.current_audio_path = None
                self.waveform_area.load_audio("")

            segments = project_data.get("segments", [])
            self.editor_area.load_segments(segments)
            self.waveform_area.update_segments(segments)

            self._sync_ui_state(0.0)
            self.setWindowTitle(f"Mimik | Turn Audio into Lyrics, Instantly - {Path(file_path).name}")
            QMessageBox.information(self, "Berhasil", "Proyek berhasil dimuat!")

        except ProjectIOError as err:
            QMessageBox.critical(self, "Error", f"Gagal membuka proyek:\n{err}")

        # SRT Import / Export Handlers

    def _on_export_srt_dialog(self):
        """Mengekspor daftar transkrip teks saat ini menjadi file .srt."""
        segments = self.editor_area.export_segments()
        if not segments:
            QMessageBox.warning(self, "Peringatan", "Tidak ada transkrip teks untuk diekspor.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Ekspor Subtitle SRT",
            "captions.srt",
            "SubRip Subtitle Files (*.srt)"
        )
        if not file_path:
            return

        try:
            export_to_srt(segments, file_path)
            QMessageBox.information(
                self,
                "Ekspor Selesai",
                f"File SRT berhasil disimpan!\nTersimpan di:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal mengekspor file SRT:\n{e}")

    def _on_import_srt_dialog(self):
        """Mengimpor file .srt, menggantikan transkrip lama, dan langsung menyinkronkan UI."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Subtitle SRT",
            "",
            "SubRip Subtitle Files (*.srt)"
        )
        if not file_path:
            return

        try:
            new_segments = import_from_srt(file_path)
            if not new_segments:
                QMessageBox.warning(self, "Peringatan", "File SRT tidak memiliki data subtitle yang valid.")
                return

            if self.editor_area.export_segments():
                reply = QMessageBox.question(
                    self,
                    "Konfirmasi Ganti Transkrip",
                    "Mengimpor SRT akan mengganti semua baris transkrip yang ada saat ini.\nLanjutkan?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            self.editor_area.load_segments(new_segments)
            self.waveform_area.update_segments(new_segments)

            cur_sec = self.player.position() / 1000.0 if self.player else 0.0
            self._sync_ui_state(cur_sec)

            QMessageBox.information(
                self,
                "Import Selesai",
                f"Berhasil memuat {len(new_segments)} baris subtitle dari file SRT!\n"
                "Timestamp dan teks telah disinkronkan."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal membaca file SRT:\n{e}")