import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable
from PIL import Image, ImageDraw, ImageFont, ImageColor
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QColorDialog,
    QGroupBox,
    QSpinBox
)


def resolve_asset_path(relative_path: str | Path) -> Path:
    rel_p = Path(relative_path)
    if getattr(sys, 'frozen', False):
        meipass_dir = Path(getattr(sys, '_MEIPASS', ''))
        if (meipass_dir / rel_p).exists():
            return meipass_dir / rel_p
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "_internal" / rel_p).exists():
            return exe_dir / "_internal" / rel_p
        if (exe_dir / rel_p).exists():
            return exe_dir / rel_p

    dev_path = Path.cwd() / rel_p
    if dev_path.exists():
        return dev_path

    base_file_path = Path(__file__).resolve().parent.parent / rel_p
    if base_file_path.exists():
        return base_file_path

    return rel_p.resolve()


# --- Transition Interpolators ---

def apply_fade_transition(
    progress_in: float,
    progress_out: float,
    base_alpha: int = 255,
    **kwargs
) -> Tuple[int, Tuple[int, int]]:
    alpha = base_alpha
    if progress_in < 1.0:
        alpha = int(base_alpha * max(0.0, min(1.0, progress_in)))
    elif progress_out < 1.0:
        alpha = int(base_alpha * max(0.0, min(1.0, progress_out)))
    return max(0, min(255, alpha)), (0, 0)


def apply_slide_up_transition(
    progress_in: float,
    progress_out: float,
    base_alpha: int = 255,
    slide_distance: int = 50,
    **kwargs
) -> Tuple[int, Tuple[int, int]]:
    dy = 0
    alpha = base_alpha
    if progress_in < 1.0:
        factor = max(0.0, min(1.0, progress_in))
        alpha = int(base_alpha * factor)
        dy = int(slide_distance * (1.0 - factor))
    elif progress_out < 1.0:
        factor = max(0.0, min(1.0, progress_out))
        alpha = int(base_alpha * factor)
        dy = -int(slide_distance * (1.0 - factor))
    return max(0, min(255, alpha)), (0, dy)


TRANSITION_REGISTRY: Dict[str, Callable[..., Tuple[int, Tuple[int, int]]]] = {
    "fade": apply_fade_transition,
    "slide_up": apply_slide_up_transition,
}


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    canvas_width: int,
    canvas_height: int,
    position_type: str,
    offset_xy: Tuple[int, int],
    text_color: Tuple[int, int, int, int],
    max_width_ratio: float = 0.85
):
    max_width = int(canvas_width * max_width_ratio)
    words = text.split()
    if not words:
        return

    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))

    font_size = getattr(font, "size", 64)
    line_spacing = int(font_size * 0.3)
    line_metrics = []
    total_height = 0

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        line_metrics.append({"line": line, "bbox": bbox, "width": lw, "height": lh})
        total_height += lh
        if i < len(lines) - 1:
            total_height += line_spacing

    dx, dy = offset_xy

    if position_type == "top":
        start_y = int(canvas_height * 0.15) + dy
    elif position_type == "bottom":
        start_y = int(canvas_height * 0.85) - total_height + dy
    else:
        start_y = (canvas_height - total_height) // 2 + dy

    current_y = start_y
    for metric in line_metrics:
        lw = metric["width"]
        lh = metric["height"]
        bbox = metric["bbox"]
        
        x = (canvas_width - lw) // 2 - bbox[0] + dx
        y = current_y - bbox[1]
        
        draw.text((x, y), metric["line"], font=font, fill=text_color)
        current_y += lh + line_spacing


class PreviewWidget(QWidget):
    style_changed = pyqtSignal(dict)
    video_settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.style: Dict[str, Any] = {
            "font_path": "assets/fonts/Poppins-Bold.ttf",
            "font_size": 64,
            "text_color": "#FFFFFF",
            "position": "center",
            "transition_type": "fade",
            "transition_duration": 0.3
        }
        self.video_settings: Dict[str, Any] = {
            "resolution": [1920, 1080],
            "fps": 30,
            "green_color": "#00FF00"
        }
        
        self.current_segment: Optional[Dict[str, Any]] = None
        self.current_time: float = 0.0
        self._cached_font = None
        self._cached_font_key = None

        self._init_ui()
        self._populate_available_fonts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Screen Viewport
        self.label_screen = QLabel(self)
        self.label_screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_screen.setMinimumSize(320, 180)
        self.label_screen.setStyleSheet("background-color: #000000; border-radius: 4px;")
        main_layout.addWidget(self.label_screen)

        # 2. Styling Toolbar
        control_box = QGroupBox("Style Settings", self)
        ctrl_layout = QHBoxLayout(control_box)
        ctrl_layout.setContentsMargins(8, 6, 8, 6)
        ctrl_layout.setSpacing(10)

        # Font Dropdown
        ctrl_layout.addWidget(QLabel("Font:"))
        self.combo_fonts = QComboBox(self)
        self.combo_fonts.currentIndexChanged.connect(self._on_font_selected)
        ctrl_layout.addWidget(self.combo_fonts)

        # SpinBox Ukuran Font
        ctrl_layout.addWidget(QLabel("Size:"))
        self.spin_font_size = QSpinBox(self)
        self.spin_font_size.setRange(20, 200)
        self.spin_font_size.setValue(int(self.style.get("font_size", 64)))
        self.spin_font_size.setSingleStep(2)
        self.spin_font_size.valueChanged.connect(self._on_font_size_changed)
        ctrl_layout.addWidget(self.spin_font_size)

        # Tombol Warna Teks
        ctrl_layout.addWidget(QLabel("Text Color:"))
        self.btn_color = QPushButton("Pick Color", self)
        self.btn_color.setStyleSheet(f"background-color: {self.style['text_color']}; color: #000000; font-weight: bold;")
        self.btn_color.clicked.connect(self._on_choose_color)
        ctrl_layout.addWidget(self.btn_color)

        # Tombol Warna Latar (Green Screen / Custom BG)
        ctrl_layout.addWidget(QLabel("Background:"))
        self.btn_bg_color = QPushButton("Pick Color", self)
        self.btn_bg_color.setStyleSheet(f"background-color: {self.video_settings['green_color']}; color: #000000; font-weight: bold;")
        self.btn_bg_color.clicked.connect(self._on_choose_bg_color)
        ctrl_layout.addWidget(self.btn_bg_color)

        ctrl_layout.addStretch()
        main_layout.addWidget(control_box)

        self.render_frame()

    def _populate_available_fonts(self):
        fonts_dir = resolve_asset_path("assets/fonts")
        self.combo_fonts.blockSignals(True)
        self.combo_fonts.clear()

        found_fonts = []
        if fonts_dir.exists() and fonts_dir.is_dir():
            found_fonts = sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")))

        current_path_name = Path(self.style.get("font_path", "")).name

        if found_fonts:
            for font_file in found_fonts:
                rel_path = f"assets/fonts/{font_file.name}"
                display_name = font_file.stem.replace("-", " ")
                self.combo_fonts.addItem(display_name, userData=rel_path)
                
                if font_file.name == current_path_name:
                    self.combo_fonts.setCurrentIndex(self.combo_fonts.count() - 1)
        else:
            self.combo_fonts.addItem("Default Font", userData="assets/fonts/Poppins-Bold.ttf")

        self.combo_fonts.blockSignals(False)

    def _on_font_selected(self, index: int):
        font_path = self.combo_fonts.itemData(index)
        if font_path:
            self.style["font_path"] = font_path
            self._cached_font = None
            self.render_frame()
            self.style_changed.emit(self.style)

    def _on_font_size_changed(self, val: int):
        self.style["font_size"] = val
        self._cached_font = None
        self.render_frame()
        self.style_changed.emit(self.style)

    def _on_choose_color(self):
        initial_color = QColor(self.style.get("text_color", "#FFFFFF"))
        color = QColorDialog.getColor(initial_color, self, "Pilih Warna Teks Lirik")
        
        if color.isValid():
            hex_color = color.name().upper()
            self.style["text_color"] = hex_color
            btn_txt_color = "#000000" if color.lightness() > 128 else "#FFFFFF"
            self.btn_color.setStyleSheet(
                f"background-color: {hex_color}; color: {btn_txt_color}; font-weight: bold;"
            )
            self.render_frame()
            self.style_changed.emit(self.style)

    def _on_choose_bg_color(self):
        initial_color = QColor(self.video_settings.get("green_color", "#00FF00"))
        color = QColorDialog.getColor(initial_color, self, "Pilih Warna Latar Belakang")
        
        if color.isValid():
            hex_color = color.name().upper()
            self.video_settings["green_color"] = hex_color
            btn_txt_color = "#000000" if color.lightness() > 128 else "#FFFFFF"
            self.btn_bg_color.setStyleSheet(
                f"background-color: {hex_color}; color: {btn_txt_color}; font-weight: bold;"
            )
            self.render_frame()
            self.video_settings_changed.emit(self.video_settings)

    def set_config(self, style: Dict[str, Any], video_settings: Dict[str, Any]):
        self.style.update(style)
        self.video_settings.update(video_settings)
        self._cached_font = None

        self.spin_font_size.blockSignals(True)
        self.spin_font_size.setValue(int(self.style.get("font_size", 64)))
        self.spin_font_size.blockSignals(False)

        # Sync tombol warna teks
        cur_color = self.style.get("text_color", "#FFFFFF")
        qcol = QColor(cur_color)
        btn_txt = "#000000" if qcol.lightness() > 128 else "#FFFFFF"
        self.btn_color.setStyleSheet(f"background-color: {cur_color}; color: {btn_txt}; font-weight: bold;")

        # Sync tombol warna latar
        cur_bg = self.video_settings.get("green_color", "#00FF00")
        qbg = QColor(cur_bg)
        bg_btn_txt = "#000000" if qbg.lightness() > 128 else "#FFFFFF"
        self.btn_bg_color.setStyleSheet(f"background-color: {cur_bg}; color: {bg_btn_txt}; font-weight: bold;")

        # Sync dropdown font
        cur_font_name = Path(self.style.get("font_path", "")).name
        for i in range(self.combo_fonts.count()):
            f_data = self.combo_fonts.itemData(i)
            if f_data and Path(f_data).name == cur_font_name:
                self.combo_fonts.setCurrentIndex(i)
                break

        self.render_frame()

    def update_state(self, current_time: float, active_segment: Optional[Dict[str, Any]]):
        self.current_time = current_time
        self.current_segment = active_segment
        self.render_frame()

    def _get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_path = self.style.get("font_path", "assets/fonts/Poppins-Bold.ttf")
        font_size = int(self.style.get("font_size", 64))
        key = (str(font_path), font_size)

        if self._cached_font is None or self._cached_font_key != key:
            resolved_font = resolve_asset_path(font_path)
            if resolved_font.exists() and resolved_font.is_file():
                try:
                    self._cached_font = ImageFont.truetype(str(resolved_font), font_size)
                except Exception:
                    self._cached_font = ImageFont.load_default()
            else:
                self._cached_font = ImageFont.load_default()
            self._cached_font_key = key

        return self._cached_font

    def render_frame(self):
        width, height = self.video_settings.get("resolution", [1920, 1080])
        bg_hex = self.video_settings.get("green_color", "#00FF00")
        
        bg_rgb = ImageColor.getrgb(bg_hex)
        canvas = Image.new("RGBA", (width, height), (*bg_rgb, 255))

        if self.current_segment and self.current_segment.get("text"):
            text = self.current_segment["text"]
            start_t = float(self.current_segment.get("start", 0.0))
            end_t = float(self.current_segment.get("end", 0.0))
            
            t_dur = max(0.01, float(self.style.get("transition_duration", 0.3)))
            
            progress_in = (self.current_time - start_t) / t_dur if self.current_time >= start_t else 0.0
            progress_out = (end_t - self.current_time) / t_dur if self.current_time <= end_t else 0.0

            trans_type = self.style.get("transition_type", "fade")
            transition_func = TRANSITION_REGISTRY.get(trans_type, apply_fade_transition)
            alpha, offset_xy = transition_func(progress_in, progress_out, base_alpha=255)

            if alpha <= 0 and start_t <= self.current_time <= end_t:
                alpha = 255

            if alpha > 0:
                font = self._get_font()
                txt_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(txt_layer)

                color_hex = self.style.get("text_color", "#FFFFFF")
                txt_rgb = ImageColor.getrgb(color_hex)
                pos_type = self.style.get("position", "center")

                draw_wrapped_text(
                    draw=draw,
                    text=text,
                    font=font,
                    canvas_width=width,
                    canvas_height=height,
                    position_type=pos_type,
                    offset_xy=offset_xy,
                    text_color=(*txt_rgb, alpha)
                )

                canvas = Image.alpha_composite(canvas, txt_layer)

        raw_data = canvas.tobytes("raw", "RGBA")
        qimage = QImage(raw_data, width, height, width * 4, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)

        scaled_pixmap = pixmap.scaled(
            self.label_screen.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.label_screen.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_frame()