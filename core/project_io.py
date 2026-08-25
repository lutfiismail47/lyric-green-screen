import json
from pathlib import Path
from typing import Dict, Any


class ProjectIOError(Exception):
    pass


def save_project_file(file_path: str | Path, project_data: Dict[str, Any]) -> None:
    """Menyimpan dictionary proyek ke file .lyricproj (JSON) dengan encoding UTF-8."""
    path = Path(file_path).resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise ProjectIOError(f"Gagal menyimpan project ke {path}: {e}")


def load_project_file(file_path: str | Path) -> Dict[str, Any]:
    """Membaca dan memvalidasi file .lyricproj (JSON)."""
    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        raise ProjectIOError(f"File project tidak ditemukan: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validasi struktur data minimal
        required_keys = ["version", "segments", "style", "video_settings"]
        for key in required_keys:
            if key not in data:
                raise ProjectIOError(f"Format project tidak valid: atribut '{key}' hilang.")

        return data
    except json.JSONDecodeError as e:
        raise ProjectIOError(f"Format JSON rusak pada file project: {e}")
    except Exception as e:
        if isinstance(e, ProjectIOError):
            raise e
        raise ProjectIOError(f"Gagal memuat project dari {path}: {e}")