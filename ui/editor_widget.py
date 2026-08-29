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

    def _reindex_segments(self):
        """Menata ulang nomor ID setiap segmen dari 1 sampai N secara berurutan."""
        for idx, seg in enumerate(self.segments):
            seg["id"] = idx + 1

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
            if column == 1:  # Kolom Start (s)
                new_start = max(0.0, float(val))
                old_start = float(self.segments[row].get("start", 0.0))
                delta = new_start - old_start

                if abs(delta) > 1e-4:
                    # Geser start & end baris saat ini
                    self.segments[row]["start"] = new_start
                    self.segments[row]["end"] = max(new_start, round(float(self.segments[row].get("end", 0.0)) + delta, 2))

                    # Ripple: geser semua baris di bawahnya (maju atau mundur)
                    for r in range(row + 1, len(self.segments)):
                        s_r = round(max(0.0, float(self.segments[r].get("start", 0.0)) + delta), 2)
                        e_r = round(max(s_r, float(self.segments[r].get("end", 0.0)) + delta), 2)
                        self.segments[r]["start"] = s_r
                        self.segments[r]["end"] = e_r

                    self._refresh_table()

            elif column == 2:  # Kolom End (s)
                new_end = max(0.0, float(val))
                old_end = float(self.segments[row].get("end", 0.0))
                delta = new_end - old_end

                if abs(delta) > 1e-4:
                    # Update end baris saat ini
                    self.segments[row]["end"] = max(float(self.segments[row].get("start", 0.0)), new_end)

                    # Ripple: geser semua baris di bawahnya
                    for r in range(row + 1, len(self.segments)):
                        s_r = round(max(0.0, float(self.segments[r].get("start", 0.0)) + delta), 2)
                        e_r = round(max(s_r, float(self.segments[r].get("end", 0.0)) + delta), 2)
                        self.segments[r]["start"] = s_r
                        self.segments[r]["end"] = e_r

                    self._refresh_table()

            elif column == 3:  # Kolom Teks Lirik
                self.segments[row]["text"] = val

        except ValueError:
            # Jika user memasukkan format bukan angka, kembalikan tampilan tabel ke nilai lama
            self._refresh_table()
            return

        self.data_changed.emit()

    def _on_row_selected(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())))
        if selected_rows and selected_rows[0] < len(self.segments):
            self.segment_selected.emit(self.segments[selected_rows[0]])

    def _add_row(self):
        """Menyisipkan baris lirik baru tepat di bawah baris yang sedang dipilih."""
        selected_row = self.table.currentRow()

        # 1. Tentukan posisi penyisipan dan timing awal-akhir
        if 0 <= selected_row < len(self.segments):
            insert_idx = selected_row + 1
            curr_seg = self.segments[selected_row]
            new_start = round(float(curr_seg.get("end", 0.0)), 2)

            if insert_idx < len(self.segments):
                next_start = float(self.segments[insert_idx].get("start", new_start + 2.0))
                new_end = round(max(new_start + 0.5, min(new_start + 2.0, next_start)), 2)
            else:
                new_end = round(new_start + 2.0, 2)
        else:
            insert_idx = len(self.segments)
            if self.segments:
                last_end = float(self.segments[-1].get("end", 0.0))
                new_start = round(last_end, 2)
                new_end = round(last_end + 2.0, 2)
            else:
                new_start = 0.0
                new_end = 2.0

        new_segment = {
            "id": insert_idx + 1,
            "start": new_start,
            "end": new_end,
            "text": "Teks lirik baru"
        }

        # 2. Sisipkan ke data segmen dan perbarui penomoran ID
        self.segments.insert(insert_idx, new_segment)
        self._reindex_segments()

        # 3. Refresh tabel dan sorot baris yang baru dibuat
        self._refresh_table()
        self.table.selectRow(insert_idx)

        self.data_changed.emit()

    def _delete_selected_rows(self):
        selected_rows = sorted(list(set(item.row() for item in self.table.selectedItems())), reverse=True)
        if not selected_rows:
            return
        for r in selected_rows:
            if r < len(self.segments):
                self.segments.pop(r)
        
        self._reindex_segments()
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

        self._reindex_segments()
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

        self._reindex_segments()
        self._refresh_table()
        self.data_changed.emit()