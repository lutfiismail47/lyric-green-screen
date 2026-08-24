import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable
from PIL import Image, ImageDraw, ImageFont, ImageColor
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


def resolve_asset_path(relative_path: str | Path) -> Path:
    """Mendeteksi lokasi asset baik di mode dev maupun PyInstaller bundle."""
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
    else:  # "center"
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


# --- Preview Widget ---

class PreviewWidget(QWidget):
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

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label_screen = QLabel(self)
        self.label_screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_screen.setMinimumSize(320, 180)
        self.label_screen.setStyleSheet("background-color: #000000; border-radius: 4px;")
        
        layout.addWidget(self.label_screen)
        self.render_frame()

    def set_config(self, style: Dict[str, Any], video_settings: Dict[str, Any]):
        self.style.update(style)
        self.video_settings.update(video_settings)
        self._cached_font = None
        self.render_frame()

    def update_state(self, current_time: float, active_segment: Optional[Dict[str, Any]]):
        self.current_time = current_time
        self.current_segment = active_segment
        self.render_frame()

    def _get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_path = self.style.get("font_path", "assets/fonts/Poppins-Bold.ttf")
        font_size = self.style.get("font_size", 64)
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
            
            # Hitung progress transisi
            progress_in = (self.current_time - start_t) / t_dur if self.current_time >= start_t else 0.0
            progress_out = (end_t - self.current_time) / t_dur if self.current_time <= end_t else 0.0

            trans_type = self.style.get("transition_type", "fade")
            transition_func = TRANSITION_REGISTRY.get(trans_type, apply_fade_transition)
            alpha, offset_xy = transition_func(progress_in, progress_out, base_alpha=255)

            # Jika preview sedang di-pause tepat di awal atau di tengah segmen
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