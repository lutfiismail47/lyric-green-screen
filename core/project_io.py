import json
from pathlib import Path
from typing import Dict, Any, Union


class ProjectFormatError(Exception):
    """Exception custom jika format project file tidak valid atau kehilangan field wajib."""
    pass


class ProjectIOError(Exception):
    """Exception custom untuk error saat membaca atau menyimpan file project."""
    pass


def create_default_project() -> Dict[str, Any]:
    """
    Membuat struktur project baru dengan nilai default yang sesuai
    dengan Bagian 4 dokumen PROJECT_CONTEXT.
    """
    return {
        "version": "1.0",
        "audio_path": "",
        "segments": [],
        "style": {
            "font_path": "assets/fonts/Poppins-Bold.ttf",
            "font_size": 64,
            "text_color": "#FFFFFF",
            "position": "center",
            "transition_type": "fade",
            "transition_duration": 0.3
        },
        "video_settings": {
            "resolution": [1920, 1080],
            "fps": 30,
            "green_color": "#00FF00"
        }
    }


def save_project(project_dict: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """
    Menyimpan dictionary project ke dalam file JSON (.lyricproj).
    
    :param project_dict: Data project yang akan disimpan.
    :param file_path: Path tujuan penyimpanan file.
    """
    path = Path(file_path).resolve()
    
    try:
        # Menulis menggunakan encoding UTF-8 secara eksplisit
        with path.open("w", encoding="utf-8") as f:
            json.dump(project_dict, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise ProjectIOError(f"Gagal menyimpan project ke {path}: {e}")


def load_project(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Membaca dan memvalidasi file project JSON (.lyricproj).
    
    :param file_path: Path file project yang akan dibaca.
    :return: Dictionary berisi data project yang sudah tervalidasi.
    """
    path = Path(file_path).resolve()
    
    if not path.exists() or not path.is_file():
        raise ProjectIOError(f"File project tidak ditemukan: {path}")
        
    try:
        # Membaca menggunakan encoding UTF-8 secara eksplisit
        with path.open("r", encoding="utf-8") as f:
            project_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ProjectFormatError(f"File {path.name} bukan format JSON yang valid: {e}")
    except Exception as e:
        raise ProjectIOError(f"Gagal membaca project dari {path}: {e}")

    # --- Validasi Struktur dan Field Wajib ---
    required_keys = ["version", "audio_path", "segments", "style", "video_settings"]
    for key in required_keys:
        if key not in project_data:
            raise ProjectFormatError(f"Field wajib '{key}' tidak ditemukan di dalam file project.")
            
    if not isinstance(project_data.get("segments"), list):
        raise ProjectFormatError("Field 'segments' harus berupa sebuah list (array).")
        
    if not isinstance(project_data.get("style"), dict):
        raise ProjectFormatError("Field 'style' harus berupa sebuah dictionary (object).")
        
    if not isinstance(project_data.get("video_settings"), dict):
        raise ProjectFormatError("Field 'video_settings' harus berupa sebuah dictionary (object).")

    return project_data


if __name__ == "__main__":
    import tempfile
    
    # 1. Test Membuat Default Project
    print("--- 1. Testing Pembuatan Default Project ---")
    my_project = create_default_project()
    print("Project berhasil dibuat. Default values:")
    print(json.dumps(my_project, indent=4))
    
    # Gunakan temporary directory untuk I/O test yang aman
    temp_dir = Path(tempfile.gettempdir())
    test_file_path = temp_dir / "test_project.lyricproj"
    
    # 2. Test Simpan Project
    print(f"\n--- 2. Testing Save Project ke: {test_file_path} ---")
    
    # Modifikasi sedikit untuk membuktikan bisa di-save
    my_project["audio_path"] = "C:/Music/test_song.mp3"
    my_project["segments"].append({
        "id": 1, "start": 0.0, "end": 2.5, "text": "Testing lirik"
    })
    
    try:
        save_project(my_project, test_file_path)
        print("Save project sukses.")
    except Exception as e:
        print(f"Error saat menyimpan: {e}")

    # 3. Test Load Project
    print("\n--- 3. Testing Load Project ---")
    try:
        loaded_project = load_project(test_file_path)
        print("Load project sukses. Isi data audio_path:", loaded_project["audio_path"])
        print("Jumlah segmen lirik dimuat:", len(loaded_project["segments"]))
    except Exception as e:
        print(f"Error saat meload: {e}")
        
    # 4. Test Validasi Error (Simulasi data corrupt)
    print("\n--- 4. Testing Validasi Format ---")
    corrupt_file_path = temp_dir / "corrupt_project.lyricproj"
    try:
        # Simpan JSON yang field 'style'-nya hilang
        corrupt_data = {"version": "1.0", "audio_path": "", "segments": [], "video_settings": {}}
        with open(corrupt_file_path, "w", encoding="utf-8") as f:
            json.dump(corrupt_data, f)
            
        print("Mencoba me-load project yang corrupt...")
        load_project(corrupt_file_path)
        print("GAGAL: Seharusnya baris ini tidak pernah dieksekusi karena akan raise error!")
    except ProjectFormatError as e:
        print(f"BERHASIL menangkap error validasi: {e}")
    finally:
        # Bersihkan file testing
        if test_file_path.exists(): test_file_path.unlink()
        if corrupt_file_path.exists(): corrupt_file_path.unlink()