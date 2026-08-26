import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable, Generator
from PIL import Image, ImageDraw, ImageFont, ImageColor
from ui.preview_widget import (
    TRANSITION_REGISTRY,
    apply_fade_transition,
    apply_slide_up_transition,
    draw_wrapped_text,
    resolve_asset_path
)


class RenderCancelledException(Exception):
    pass


class FrameRenderer:
    def __init__(
        self,
        style: Dict[str, Any],
        video_settings: Dict[str, Any],
        segments: List[Dict[str, Any]]
    ):
        self.style = style
        self.video_settings = video_settings
        self.segments = sorted(segments, key=lambda s: s.get("start", 0.0))

        self.width, self.height = self.video_settings.get("resolution", [1920, 1080])
        self.fps = self.video_settings.get("fps", 30)
        self.green_color = self.video_settings.get("green_color", "#00FF00")

        self.font = self._load_font()
        self.base_canvas = self._create_base_canvas()
        self.base_canvas_bytes = self.base_canvas.tobytes("raw", "RGBA")

        self._segment_layers: Dict[int, Image.Image] = {}
        self._segment_steady_bytes: Dict[int, bytes] = {}
        self._pre_render_segments()

    def _load_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_path = self.style.get("font_path", "assets/fonts/Poppins-Bold.ttf")
        font_size = int(self.style.get("font_size", 64))

        resolved_font = resolve_asset_path(font_path)
        if resolved_font.exists() and resolved_font.is_file():
            try:
                return ImageFont.truetype(str(resolved_font), font_size)
            except Exception:
                pass

        system_fallbacks = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
        for sys_font in system_fallbacks:
            if Path(sys_font).exists():
                try:
                    return ImageFont.truetype(sys_font, font_size)
                except Exception:
                    continue

        try:
            return ImageFont.load_default(size=font_size)
        except TypeError:
            return ImageFont.load_default()

    def _create_base_canvas(self) -> Image.Image:
        bg_rgb = ImageColor.getrgb(self.green_color)
        return Image.new("RGBA", (self.width, self.height), (*bg_rgb, 255))

    def _pre_render_segments(self):
        color_hex = self.style.get("text_color", "#FFFFFF")
        txt_rgb = ImageColor.getrgb(color_hex)
        pos_type = self.style.get("position", "center")

        for seg in self.segments:
            seg_id = seg.get("id")
            text = seg.get("text", "").strip()
            if not text:
                continue

            txt_layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(txt_layer)

            draw_wrapped_text(
                draw=draw,
                text=text,
                font=self.font,
                canvas_width=self.width,
                canvas_height=self.height,
                position_type=pos_type,
                offset_xy=(0, 0),
                text_color=(*txt_rgb, 255)
            )
            self._segment_layers[seg_id] = txt_layer

            steady_frame = self.base_canvas.copy()
            steady_frame.paste(txt_layer, (0, 0), txt_layer)
            self._segment_steady_bytes[seg_id] = steady_frame.tobytes("raw", "RGBA")

    def generate_all_raw_bytes(
        self,
        total_duration: float,
        progress_callback: Optional[Callable[[float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> Generator[bytes, None, None]:
        """Streaming langsung raw bytes ke stdin FFmpeg tanpa overhead konversi ulang."""
        total_frames = int(total_duration * self.fps)
        if total_frames <= 0:
            return

        frame_duration = 1.0 / self.fps
        t_dur = max(0.01, float(self.style.get("transition_duration", 0.3)))
        trans_type = self.style.get("transition_type", "fade")
        transition_func = TRANSITION_REGISTRY.get(trans_type, apply_fade_transition)

        current_seg_idx = 0
        num_segments = len(self.segments)

        for frame_idx in range(total_frames):
            if is_cancelled and is_cancelled():
                raise RenderCancelledException("Render dibatalkan.")

            timestamp = frame_idx * frame_duration

            while current_seg_idx < num_segments and timestamp > self.segments[current_seg_idx]["end"]:
                current_seg_idx += 1

            active_seg = None
            if current_seg_idx < num_segments:
                cand = self.segments[current_seg_idx]
                if cand["start"] <= timestamp <= cand["end"]:
                    active_seg = cand

            if not active_seg:
                yield self.base_canvas_bytes
            else:
                seg_id = active_seg.get("id")
                start_t = active_seg["start"]
                end_t = active_seg["end"]

                progress_in = (timestamp - start_t) / t_dur if timestamp >= start_t else 0.0
                progress_out = (end_t - timestamp) / t_dur if timestamp <= end_t else 0.0
                alpha, _ = transition_func(progress_in, progress_out, base_alpha=255)

                if alpha <= 0:
                    yield self.base_canvas_bytes
                elif alpha >= 255:
                    yield self._segment_steady_bytes.get(seg_id, self.base_canvas_bytes)
                else:
                    cached_layer = self._segment_layers.get(seg_id)
                    if cached_layer:
                        frame = self.base_canvas.copy()
                        faded_layer = cached_layer.copy()
                        faded_layer.putalpha(faded_layer.getchannel("A").point(lambda a: int(a * (alpha / 255.0))))
                        frame.paste(faded_layer, (0, 0), faded_layer)
                        yield frame.tobytes("raw", "RGBA")
                    else:
                        yield self.base_canvas_bytes

            if progress_callback and (frame_idx % max(1, total_frames // 100) == 0):
                progress_callback((frame_idx + 1) / total_frames * 100.0)