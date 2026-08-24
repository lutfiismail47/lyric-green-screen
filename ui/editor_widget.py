from typing import List, Dict, Any, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDoubleSpinBox,
    QHeaderView,
    QAbstractItemView,
    QMessageBox
)


def format_seconds_to_mmss(seconds: float) -> str:
    """Format detik float ke format string mm:ss.zzz untuk tooltip/display."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:06.3f}"


class SegmentTimeSpinBox(QDoubleSpinBox):
    """Spinbox kustom untuk input waktu dalam satuan detik dengan presisi milidetik."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(3)
        self.setSingleStep(0.1)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class LyricsEditorWidget(QWidget):
    """
    Widget Editor Segmen Lirik.
    
    Signals:
        data_changed: Dipancarkan saat ada perubahan data segmen (edit, tambah, hapus, split, merge).
        segment_selected(dict): Dipancarkan saat sebuah baris dipilih, mengirimkan data segment dict terkait.
    """
    data_changed = pyqtSignal()
    segment_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_signals = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 1. Action Buttons Toolbar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_add = QPushButton("➕ Tambah Baris")
        self.btn_delete = QPushButton("🗑 Hapus")
        self.btn_split = QPushButton("✂️ Split Segmen")
        self.btn_merge = QPushButton("🔗 Merge Segmen")

        self.btn_add.clicked.connect(self._on_add_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_split.clicked.connect(self._on_split_clicked)
        self.btn_merge.clicked.connect(self._on_merge_clicked)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_split)
        btn_layout.addWidget(self.btn_merge)
        btn_layout.addStretch()

        # 2. QTableWidget
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["#", "Start (s)", "End (s)", "Teks Lirik"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 110)

        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addLayout(btn_layout)
        layout.addWidget(self.table)

    def load_segments(self, segments: List[Dict[str, Any]]) -> None:
        """Memuat list of segment dict (format Bagian 4) ke dalam tabel."""
        self._block_signals = True
        self.table.setRowCount(0)

        for segment in segments:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._populate_row(row, segment["id"], segment["start"], segment["end"], segment["text"])

        self._block_signals = False

    def export_segments(self) -> List[Dict[str, Any]]:
        """Mengekspor isi tabel kembali menjadi list of segment dict (format Bagian 4)."""
        segments: List[Dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            # ID
            id_item = self.table.item(row, 0)
            seg_id = int(id_item.text()) if id_item else (row + 1)

            # Start Time
            spin_start = self.table.cellWidget(row, 1)
            start_val = spin_start.value() if isinstance(spin_start, QDoubleSpinBox) else 0.0

            # End Time
            spin_end = self.table.cellWidget(row, 2)
            end_val = spin_end.value() if isinstance(spin_end, QDoubleSpinBox) else 0.0

            # Text
            text_item = self.table.item(row, 3)
            text_val = text_item.text().strip() if text_item else ""

            segments.append({
                "id": seg_id,
                "start": round(start_val, 3),
                "end": round(end_val, 3),
                "text": text_val
            })
        return segments

    def _populate_row(self, row: int, seg_id: int, start: float, end: float, text: str):
        # Kolom 0: ID (Read-only)
        id_item = QTableWidgetItem(str(seg_id))
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, id_item)

        # Kolom 1: Start Time (SpinBox)
        spin_start = SegmentTimeSpinBox(self.table)
        spin_start.setValue(start)
        spin_start.setToolTip(f"Format: {format_seconds_to_mmss(start)}")
        spin_start.valueChanged.connect(lambda val, r=row: self._on_time_changed(r, 1, val))
        self.table.setCellWidget(row, 1, spin_start)

        # Kolom 2: End Time (SpinBox)
        spin_end = SegmentTimeSpinBox(self.table)
        spin_end.setValue(end)
        spin_end.setToolTip(f"Format: {format_seconds_to_mmss(end)}")
        spin_end.valueChanged.connect(lambda val, r=row: self._on_time_changed(r, 2, val))
        self.table.setCellWidget(row, 2, spin_end)

        # Kolom 3: Teks Lirik (Editable Item)
        text_item = QTableWidgetItem(text)
        self.table.setItem(row, 3, text_item)

    def _reindex_ids(self):
        """Memperbarui ID berurutan setelah penambahan/penghapusan/split/merge."""
        self._block_signals = True
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setText(str(row + 1))
        self._block_signals = False

    def _on_time_changed(self, row: int, col: int, val: float):
        if self._block_signals:
            return
        widget = self.table.cellWidget(row, col)
        if isinstance(widget, QDoubleSpinBox):
            widget.setToolTip(f"Format: {format_seconds_to_mmss(val)}")
        self._emit_data_changed()

    def _on_cell_changed(self, row: int, column: int):
        if self._block_signals:
            return
        if column == 3:  # Kolom teks
            self._emit_data_changed()

    def _on_selection_changed(self):
        selected_rows = self._get_selected_row_indices()
        if len(selected_rows) == 1:
            row = selected_rows[0]
            segments = self.export_segments()
            if 0 <= row < len(segments):
                self.segment_selected.emit(segments[row])

    def _emit_data_changed(self):
        if not self._block_signals:
            self.data_changed.emit()

    def _get_selected_row_indices(self) -> List[int]:
        selected_indexes = self.table.selectionModel().selectedRows()
        return sorted(list(set(idx.row() for idx in selected_indexes)))

    # --- Actions: Add, Delete, Split, Merge ---

    def _on_add_clicked(self):
        segments = self.export_segments()
        last_end = segments[-1]["end"] if segments else 0.0
        new_start = last_end
        new_end = last_end + 2.0

        row = self.table.rowCount()
        self._block_signals = True
        self.table.insertRow(row)
        self._populate_row(row, row + 1, new_start, new_end, "Teks baru")
        self._block_signals = False

        self._emit_data_changed()
        self.table.selectRow(row)

    def _on_delete_clicked(self):
        selected_rows = self._get_selected_row_indices()
        if not selected_rows:
            return

        self._block_signals = True
        for row in reversed(selected_rows):
            self.table.removeRow(row)
        self._reindex_ids()
        self._block_signals = False

        self._emit_data_changed()

    def _on_split_clicked(self):
        selected_rows = self._get_selected_row_indices()
        if len(selected_rows) != 1:
            QMessageBox.information(self, "Split Segmen", "Pilih tepat satu baris untuk di-split.")
            return

        row = selected_rows[0]
        segments = self.export_segments()
        target = segments[row]

        duration = target["end"] - target["start"]
        mid_time = round(target["start"] + (duration / 2.0), 3)

        words = target["text"].split()
        if len(words) > 1:
            mid_idx = len(words) // 2
            text_1 = " ".join(words[:mid_idx])
            text_2 = " ".join(words[mid_idx:])
        else:
            text_1 = target["text"]
            text_2 = "..."

        seg1 = {"id": target["id"], "start": target["start"], "end": mid_time, "text": text_1}
        seg2 = {"id": target["id"] + 1, "start": mid_time, "end": target["end"], "text": text_2}

        segments = segments[:row] + [seg1, seg2] + segments[row + 1:]
        for idx, s in enumerate(segments):
            s["id"] = idx + 1

        self.load_segments(segments)
        self._emit_data_changed()
        self.table.selectRow(row)

    def _on_merge_clicked(self):
        selected_rows = self._get_selected_row_indices()
        if len(selected_rows) != 2 or abs(selected_rows[0] - selected_rows[1]) != 1:
            QMessageBox.information(
                self, "Merge Segmen", "Pilih tepat dua baris yang bersebelahan/berurutan untuk digabungkan."
            )
            return

        r1, r2 = selected_rows[0], selected_rows[1]
        segments = self.export_segments()
        first, second = segments[r1], segments[r2]

        merged_seg = {
            "id": first["id"],
            "start": first["start"],
            "end": second["end"],
            "text": f"{first['text']} {second['text']}".strip()
        }

        segments = segments[:r1] + [merged_seg] + segments[r2 + 1:]
        for idx, s in enumerate(segments):
            s["id"] = idx + 1

        self.load_segments(segments)
        self._emit_data_changed()
        self.table.selectRow(r1)