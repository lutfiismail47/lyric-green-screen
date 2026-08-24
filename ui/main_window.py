from pathlib import Path
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, QUrl, QTimer
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
    QMessageBox
)
from ui.editor_widget import LyricsEditorWidget
from ui.waveform_widget import WaveformWidget
from ui.preview_widget import PreviewWidget
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QProgressDialog
from core.transcriber import AudioTranscriber
from PyQt6.QtWidgets import QProgressDialog, QFileDialog, QMessageBox
from core.renderer import FrameRenderer
from core.exporter import VideoExportWorker


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
        self.setWindowTitle("Lyric Green Screen Generator")
        self.resize(1000, 800)
        self.setMinimumSize(800, 600)

        self.current_audio_path: Optional[str] = None
        self._is_user_seeking: bool = False

        # Inisialisasi Audio Player bawaan PyQt6
        self._init_player()

        # Inisialisasi Menu, Toolbar, dan Layout UI
        self._init_menu_and_toolbar()
        self._init_ui()

        # Hubungkan semua signals antar widget
        self._connect_signals()

        # Timer loop rendering (30 FPS ≈ 33ms) untuk sinkronisasi preview yang efisien & halus
        self.render_timer = QTimer(self)
        self.render_timer.setInterval(33)
        self.render_timer.timeout.connect(self._on_render_tick)

    def _init_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

    def _init_menu_and_toolbar(self):
        menubar = self.menuBar()
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)

        file_menu = menubar.addMenu("&File")

        self.action_new = QAction("New Project", self)
        self.action_open = QAction("Open Project", self)
        self.action_save = QAction("Save Project", self)
        self.action_import_audio = QAction("Import Audio", self)
        self.action_export_video = QAction("Export Video", self)
        self.action_exit = QAction("Exit", self)
        self.action_exit.triggered.connect(self.close)

        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addAction(self.action_save)
        file_menu.addSeparator()
        file_menu.addAction(self.action_import_audio)
        file_menu.addAction(self.action_export_video)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        toolbar.addAction(self.action_new)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_save)
        toolbar.addSeparator()
        toolbar.addAction(self.action_import_audio)
        toolbar.addAction(self.action_export_video)

        self.action_import_audio.triggered.connect(self._on_import_audio_dialog)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Top Area: Preview + Playback Controls
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

        # 2. Middle Area: Waveform Widget
        self.waveform_area = WaveformWidget(self)

        # 3. Bottom Area: Lyrics Editor Widget
        self.editor_area = LyricsEditorWidget(self)

        splitter.addWidget(top_container)
        splitter.addWidget(self.waveform_area)
        splitter.addWidget(self.editor_area)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 4)

        main_layout.addWidget(splitter)

    def _connect_signals(self):
        # 1. Playback Button Controls
        self.btn_play.clicked.connect(self._play_audio)
        self.btn_pause.clicked.connect(self._pause_audio)
        self.btn_stop.clicked.connect(self._stop_audio)

        # 2. Player State Tracking
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        # 3. Waveform Click -> Audio Player Seek (ms)
        self.waveform_area.seek_requested.connect(self._seek_to_time)

        # 4. Editor Row Click -> Audio Player Seek ke waktu start segment
        self.editor_area.segment_selected.connect(self._on_segment_selected_in_editor)

        # 5. Editor Data Changes -> Update Marker di Waveform & Refresh Preview
        self.editor_area.data_changed.connect(self._on_editor_data_changed)

        # 6. Hubungkan tombol/menu export (TARUH DI SINI)
        self.action_export_video.triggered.connect(self._on_export_video_dialog)

    # --- Audio Playback Logic ---

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

    # --- Synchronized Loop Tick ---

    def _on_render_tick(self):
        """Loop eksekusi per ~33ms saat audio play untuk update waveform, tabel, dan preview."""
        current_sec = self.player.position() / 1000.0
        self._sync_ui_state(current_sec)

    def _sync_ui_state(self, current_sec: float):
        # 1. Update posisi garis playhead di waveform
        self.waveform_area.set_playback_position(current_sec)

        # 2. Cari segmen lirik yang aktif berdasarkan waktu
        segments = self.editor_area.export_segments()
        active_segment: Optional[Dict[str, Any]] = None
        active_index: Optional[int] = None

        for idx, seg in enumerate(segments):
            if seg["start"] <= current_sec <= seg["end"]:
                active_segment = seg
                active_index = idx
                break

        # 3. Highlight baris aktif di tabel editor (tanpa trigger re-seek)
        if active_index is not None:
            self.editor_area.table.blockSignals(True)
            self.editor_area.table.selectRow(active_index)
            self.editor_area.table.blockSignals(False)

        # 4. Render teks & transisi di PreviewWidget
        self.preview_area.update_state(current_sec, active_segment)

    # --- Event Handlers Antar Widget ---

    def _on_segment_selected_in_editor(self, segment: Dict[str, Any]):
        """Seek audio player saat user mengklik baris tertentu di tabel."""
        start_time = segment.get("start", 0.0)
        self._seek_to_time(start_time)

    def _on_editor_data_changed(self):
        """Sinkronisasi marker batas di waveform saat ada edit teks/waktu/split/merge."""
        segments = self.editor_area.export_segments()
        self.waveform_area.update_segments(segments)
        
        # Refresh preview tampilan terkini
        current_sec = self.player.position() / 1000.0
        self._sync_ui_state(current_sec)

    def _on_import_audio_dialog(self):
        """Dialog import audio untuk memuat waveform & source audio player."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Audio",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.ogg *.flac *.aac)"
        )
        if file_path:
            self.load_audio_file(file_path)

    def load_audio_file(self, audio_path: str):
        """Memuat audio dan langsung mentranskripsi lirik secara otomatis."""
        path = Path(audio_path).resolve()
        if not path.exists():
            QMessageBox.critical(self, "Error", f"File audio tidak ditemukan: {path}")
            return

        self._stop_audio()
        self.current_audio_path = str(path)

        # 1. Set source ke player & load visual waveform
        self.player.setSource(QUrl.fromLocalFile(self.current_audio_path))
        self.waveform_area.load_audio(self.current_audio_path)

        # 2. Siapkan Progress Dialog
        self.transcribe_dialog = QProgressDialog("Mendeteksi lirik dari audio...", "Batal", 0, 100, self)
        self.transcribe_dialog.setWindowTitle("Speech-to-Text Otomatis")
        self.transcribe_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.transcribe_dialog.setMinimumDuration(0)
        self.transcribe_dialog.setValue(0)

        # 3. Jalankan Transkripsi di Background Thread
        self.transcribe_worker = TranscriptionWorker(self.current_audio_path)
        
        self.transcribe_worker.progress_changed.connect(
            lambda val: self.transcribe_dialog.setValue(int(val))
        )
        self.transcribe_dialog.canceled.connect(self.transcribe_worker.cancel)

        self.transcribe_worker.finished.connect(self._on_transcription_finished)
        self.transcribe_worker.error.connect(self._on_transcription_error)

        self.transcribe_worker.start()

    def _on_transcription_finished(self, segments: list):
        """Dipanggil saat Whisper selesai mengekstrak lirik dan timestamp."""
        self.transcribe_dialog.close()
        # Otomatis isi tabel editor dan marker waveform
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
        """Membuka dialog penyimpanan file dan memulai proses export video."""
        if not self.current_audio_path:
            QMessageBox.warning(self, "Peringatan", "Silakan import file audio terlebih dahulu.")
            return

        segments = self.editor_area.export_segments()
        if not segments:
            QMessageBox.warning(self, "Peringatan", "Tidak ada segmen lirik untuk diekspor.")
            return

        # 1. Buka dialog save file MP4
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Video Green Screen",
            "output_lyrics.mp4",
            "Video Files (*.mp4)"
        )
        if not output_path:
            return

        # 2. Hitung total durasi video berdasarkan player/segmen terakhir
        total_duration = self.player.duration() / 1000.0
        if total_duration <= 0 and segments:
            total_duration = segments[-1]["end"] + 1.0

        # 3. Siapkan Konfigurasi Renderer
        style = self.preview_area.style
        video_settings = self.preview_area.video_settings
        renderer = FrameRenderer(style, video_settings, segments)

        # 4. Siapkan Progress Dialog
        self.export_dialog = QProgressDialog("Menyiapkan render video...", "Batal", 0, 100, self)
        self.export_dialog.setWindowTitle("Export Video Green Screen")
        self.export_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.export_dialog.setMinimumDuration(0)
        self.export_dialog.setValue(0)

        # 5. Jalankan Worker Thread
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