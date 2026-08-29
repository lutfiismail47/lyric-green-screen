import re
from pathlib import Path
from typing import List, Dict, Any


def seconds_to_srt_time(seconds: float) -> str:
    """Mengonversi detik float (misal: 65.250) menjadi format waktu SRT (00:01:05,250)."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def srt_time_to_seconds(srt_time_str: str) -> float:
    """Mengonversi format waktu SRT (00:01:05,250 atau 00:01:05.250) menjadi detik float."""
    clean_str = srt_time_str.strip().replace(",", ".")
    parts = clean_str.split(":")
    if len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return round(hours * 3600 + minutes * 60 + seconds, 3)
    return 0.0


def export_to_srt(segments: List[Dict[str, Any]], output_path: str | Path) -> None:
    """Menyimpan list segmen lirik ke file teks subtitle .srt standar UTF-8."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for idx, seg in enumerate(segments, start=1):
        start_str = seconds_to_srt_time(float(seg.get("start", 0.0)))
        end_str = seconds_to_srt_time(float(seg.get("end", 0.0)))
        text = str(seg.get("text", "")).strip()

        lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")


def import_from_srt(file_path: str | Path) -> List[Dict[str, Any]]:
    """Membaca file .srt dan mengubahnya menjadi list of dicts yang siap dimuat editor."""
    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File SRT tidak ditemukan: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    segments: List[Dict[str, Any]] = []

    time_pattern = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})"
    )

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue

        time_match = None
        time_line_idx = -1
        for idx, line in enumerate(lines):
            match = time_pattern.search(line)
            if match:
                time_match = match
                time_line_idx = idx
                break

        if not time_match:
            continue

        start_sec = srt_time_to_seconds(time_match.group(1))
        end_sec = srt_time_to_seconds(time_match.group(2))

        text_lines = lines[time_line_idx + 1 :]
        text = " ".join(text_lines).strip()

        segments.append({
            "id": len(segments) + 1,
            "start": start_sec,
            "end": max(start_sec + 0.1, end_sec),
            "text": text
        })

    return sorted(segments, key=lambda s: float(s.get("start", 0.0)))