from typing import List, Dict, Any, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView
)


class LyricsEditorWidget(QWidget):
    data_changed = pyqtSignal()
    segment_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

        self.btn_add = QPushButton("Insert Row")
        self.btn_delete = QPushButton("Remove")
        self.btn_split = QPushButton("Split")
        self.btn_merge = QPushButton("Merge")
        
        self.btn_upper = QPushButton("UPPERCASE")
        self.btn_lower = QPushButton("lowercase")
        self.btn_title = QPushButton("Title Case")

        self.btn_add.clicked.connect(self._add_row)
        self.btn_delete.clicked.connect(self._delete_selected_rows)
        self.btn_split.clicked.connect(self._split_selected_row)
        self.btn_merge.clicked.connect(self._merge_selected_rows)
        
        self.btn_upper.clicked.connect(lambda: self._convert_case("upper"))
        self.btn_lower.clicked.connect(lambda: self._convert_case("lower"))
        self.btn_title.clicked.connect(lambda: self._convert_case("title"))

        toolbar_layout.addWidget(self.btn_add)
        toolbar_layout.addWidget(self.btn_delete)
        toolbar_layout.addWidget(self.btn_split)
        toolbar_layout.addWidget(self.btn_merge)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(self.btn_upper)
        toolbar_layout.addWidget(self.btn_lower)
        toolbar_layout.addWidget(self.btn_title)
        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Start (s)", "End (s)", "Lyrics"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.itemSelectionChanged.connect(self._on_row_selected)

        layout.addWidget(self.table)

    def load_segments(self, segments: List[Dict[str, Any]]):
        self.segments = sorted(segments, key=lambda s: float(s.get("start", 0.0)))
        self._refresh_table()

    def export_segments(self) -> List[Dict[str, Any]]:
        return self.segments

    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for row_idx, seg in enumerate(self.segments):
            self.table.insertRow(row_idx)

            id_item = QTableWidgetItem(str(seg.get("id", row_idx + 1)))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            start_item = QTableWidgetItem(f"{float(seg.get('start', 0.0)):.2f}")
            end_item = QTableWidgetItem(f"{float(seg.get('end', 0.0)):.2f}")
            text_item = QTableWidgetItem(str(seg.get("text", "")))

            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, start_item)
            self.table.setItem(row_idx, 2, end_item)
            self.table.setItem(row_idx, 3, text_item)

        self.table.blockSignals(False)

    def _convert_case(self, case_type: str):
        """Mengubah format huruf teks lirik untuk SEMUA segmen secara global."""
        if not self.segments:
            return

        for seg in self.segments:
            txt = seg.get("text", "")
            if case_type == "upper":
                seg["text"] = txt.upper()
            elif case_type == "lower":
                seg["text"] = txt.lower()
            elif case_type == "title":
                seg["text"] = txt.title()

        self._refresh_table()
        self.data_changed.emit()

    def _on_cell_changed(self, row: int, column: int):
        if row >= len(self.segments):
            return

        item = self.table.item(row, column)
        if not item:
            return

        val = item.text().strip()
        try:
            if column == 1:
                self.segments[row]["start"] = max(0.0, float(val))
            elif column == 2:
                self.segments[row]["end"] = max(0.0, float(val))
            elif column == 3:
                self.segments[row]["text"] = val
        except ValueError:
            pass

        self.data_changed.emit()

    def _on_row_selected(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())))
        if selected_rows and selected_rows[0] < len(self.segments):
            self.segment_selected.emit(self.segments[selected_rows[0]])

    def _add_row(self):
        new_id = len(self.segments) + 1
        last_end = self.segments[-1]["end"] if self.segments else 0.0
        new_seg = {
            "id": new_id,
            "start": round(last_end, 2),
            "end": round(last_end + 2.0, 2),
            "text": "Teks lirik baru"
        }
        self.segments.append(new_seg)
        self._refresh_table()
        self.data_changed.emit()

    def _delete_selected_rows(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())), reverse=True)
        if not selected_rows:
            return
        for r in selected_rows:
            if r < len(self.segments):
                self.segments.pop(r)
        
        for i, s in enumerate(self.segments):
            s["id"] = i + 1

        self._refresh_table()
        self.data_changed.emit()

    def _split_selected_row(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())))
        if not selected_rows:
            return
        row = selected_rows[0]
        seg = self.segments[row]

        words = seg.get("text", "").split()
        if len(words) < 2:
            return

        mid = len(words) // 2
        text1 = " ".join(words[:mid])
        text2 = " ".join(words[mid:])

        mid_time = round((seg["start"] + seg["end"]) / 2.0, 2)

        seg1 = {"id": seg["id"], "start": seg["start"], "end": mid_time, "text": text1}
        seg2 = {"id": seg["id"] + 1, "start": mid_time, "end": seg["end"], "text": text2}

        self.segments.pop(row)
        self.segments.insert(row, seg2)
        self.segments.insert(row, seg1)

        for i, s in enumerate(self.segments):
            s["id"] = i + 1

        self._refresh_table()
        self.data_changed.emit()

    def _merge_selected_rows(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())))
        if len(selected_rows) < 2:
            return

        first_idx = selected_rows[0]
        last_idx = selected_rows[-1]

        merged_text = " ".join([self.segments[i]["text"] for i in selected_rows])
        merged_start = self.segments[first_idx]["start"]
        merged_end = self.segments[last_idx]["end"]

        new_seg = {
            "id": self.segments[first_idx]["id"],
            "start": merged_start,
            "end": merged_end,
            "text": merged_text
        }

        for i in reversed(selected_rows):
            self.segments.pop(i)

        self.segments.insert(first_idx, new_seg)

        for i, s in enumerate(self.segments):
            s["id"] = i + 1

        self._refresh_table()
        self.data_changed.emit()