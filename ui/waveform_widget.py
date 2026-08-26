from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import librosa
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout


class AudioAnalysisWorker(QThread):
    """Worker thread untuk decode dan downsampling amplitude audio agar UI tidak freeze."""
    finished = pyqtSignal(np.ndarray, np.ndarray, float)
    error = pyqtSignal(str)

    def __init__(self, audio_path: str, target_points: int = 4000):
        super().__init__()
        self.audio_path = audio_path
        self.target_points = target_points

    def run(self):
        try:
            y, sr = librosa.load(self.audio_path, sr=22050, mono=True)
            duration = float(len(y) / sr)

            if len(y) == 0:
                self.error.emit("File audio kosong atau tidak memiliki data gelombang.")
                return

            chunk_size = max(1, len(y) // self.target_points)
            num_chunks = len(y) // chunk_size
            y_trimmed = y[: num_chunks * chunk_size]
            
            chunks = y_trimmed.reshape(num_chunks, chunk_size)
            envelope = np.max(np.abs(chunks), axis=1)

            time_axis = np.linspace(0, duration, len(envelope))

            self.finished.emit(time_axis, envelope, duration)
        except Exception as e:
            self.error.emit(str(e))


class WaveformWidget(QWidget):
    """
    Widget visualisasi waveform interaktif berbasis pyqtgraph.

    Signals:
        seek_requested(float): Dipancarkan saat user klik posisi waveform (mengirim detik tujuan).
    """
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration: float = 0.0
        self.segments: List[Dict[str, Any]] = []
        self._segment_lines: List[pg.InfiniteLine] = []
        self._segment_regions: List[pg.LinearRegionItem] = []
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget(self)
        self.plot_widget.setBackground("#181818")
        self.plot_widget.showGrid(x=True, y=False, alpha=0.3)
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.getPlotItem().hideAxis("left")
        
        bottom_axis = self.plot_widget.getPlotItem().getAxis("bottom")
        bottom_axis.setLabel("Waktu (detik)", color="#AAAAAA")

        self.curve_top = self.plot_widget.plot(pen=pg.mkPen(color="#4A90E2", width=1.2))
        self.curve_bottom = self.plot_widget.plot(pen=pg.mkPen(color="#4A90E2", width=1.2))

        self.playhead = pg.InfiniteLine(
            pos=0,
            angle=90,
            movable=False,
            pen=pg.mkPen(color="#FFD700", width=2, style=Qt.PenStyle.SolidLine)
        )
        self.plot_widget.addItem(self.playhead)

        self.plot_widget.scene().sigMouseClicked.connect(self._on_plot_clicked)

        layout.addWidget(self.plot_widget)

    def load_audio(self, audio_path: str | Path):
        """Menganalisis audio dan menggambar waveform di thread terpisah."""
        resolved_path = str(Path(audio_path).resolve())
        self.worker = AudioAnalysisWorker(resolved_path)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_finished(self, time_axis: np.ndarray, envelope: np.ndarray, duration: float):
        self.duration = duration

        self.curve_top.setData(time_axis, envelope)
        self.curve_bottom.setData(time_axis, -envelope)

        self.plot_widget.setXRange(0, duration, padding=0.01)
        self.plot_widget.setYRange(-1.1, 1.1, padding=0)
        self.set_playback_position(0.0)

        self._redraw_segments()

    def _on_analysis_error(self, err_msg: str):
        print(f"[WaveformWidget Error]: {err_msg}")

    def update_segments(self, segments: List[Dict[str, Any]]):
        """Memperbarui visualisasi marker batas segmen lirik di atas waveform."""
        self.segments = segments
        self._redraw_segments()

    def _redraw_segments(self):
        """Membersihkan dan menggambar ulang batas overlay segmen lirik."""
        for item in self._segment_lines:
            self.plot_widget.removeItem(item)
        self._segment_lines.clear()

        line_pen = pg.mkPen(color="#FF4081", width=1, style=Qt.PenStyle.DashLine)

        for seg in self.segments:
            start_t = seg.get("start", 0.0)
            end_t = seg.get("end", 0.0)

            line_start = pg.InfiniteLine(pos=start_t, angle=90, movable=False, pen=line_pen)
            line_end = pg.InfiniteLine(pos=end_t, angle=90, movable=False, pen=line_pen)

            self.plot_widget.addItem(line_start)
            self.plot_widget.addItem(line_end)

            self._segment_lines.extend([line_start, line_end])

    @pyqtSlot(float)
    def set_playback_position(self, seconds: float):
        """Mengupdate posisi garis playback (playhead) saat audio berjalan."""
        self.playhead.setValue(seconds)

    def _on_plot_clicked(self, event):
        """Deteksi klik user pada canvas plot untuk seeking waktu playback."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            if self.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.plot_widget.getPlotItem().vb.mapSceneToView(pos)
                target_time = max(0.0, min(self.duration, mouse_point.x()))
                self.set_playback_position(target_time)
                self.seek_requested.emit(round(target_time, 3))