# PROJECT CONTEXT — Lyrics Maker

## 1. RINGKASAN PROYEK

Aplikasi desktop **offline** untuk menghasilkan **video lirik dengan latar
green screen**, dari input berupa file audio. Alur inti:

```
Audio (mp3/wav) 
   → [Whisper] Speech-to-text otomatis (dengan timestamp)
   → [Editor Manual] User perbaiki teks & timing yang kurang presisi
   → [Render Engine] Generate frame teks + transisi (fade/slide) di atas background hijau
   → [FFmpeg] Encode ke file video MP4 (green screen + lirik bertransisi)
```

Output akhirnya adalah file `.mp4` berlatar hijau solid (chroma key ready)
dengan teks lirik yang muncul/hilang bertransisi sesuai timing di audio,
siap dipakai di software editing lain (misal untuk di-composite di atas
video lain via green screen).

---

## 2. TARGET PENGGUNA & PLATFORM

- **Target OS akhir**: Windows 10/11 dan Linux (Ubuntu/Debian-based)
- **Environment development**: Ubuntu (developer coding di sini)
- **Distribusi**: Aplikasi desktop standalone (bukan web app), dibundel
  jadi installer/executable per OS
- **Mode kerja**: 100% offline setelah instalasi — tidak boleh ada
  dependency yang wajib fetch dari internet saat runtime (termasuk
  model Whisper harus sudah ter-bundle atau ter-cache lokal)
- **Prioritas**: aplikasi ringan (runtime performance), UI sederhana,
  tidak perlu fitur berlebihan di luar scope

---

## 3. TECH STACK (WAJIB DIIKUTI — JANGAN GANTI TANPA DISKUSI)

| Layer | Pilihan | Catatan |
|---|---|---|
| Bahasa | Python 3.11 | Jangan pakai 3.12+ untuk saat ini (kompatibilitas lib ML) |
| Speech-to-text | `faster-whisper` | BUKAN openai-whisper asli — versi ini lebih ringan & cepat (CTranslate2 backend) |
| GUI Framework | PyQt6 | Native, ringan, cross-platform. Jangan sarankan Electron/web-based |
| Audio playback | `QMediaPlayer` (bawaan PyQt6) | Jangan tambah library audio player lain kecuali benar-benar perlu |
| Waveform visual | `librosa` (analisis) + `pyqtgraph` (render) | |
| Render teks ke frame | `Pillow` (PIL) | |
| Compositing/transisi | Custom logic Python (interpolasi manual per frame) | Bukan pakai library video-editing berat (moviepy dihindari kecuali diperlukan — terlalu berat & lambat) |
| Encode video final | `FFmpeg` (binary eksternal, dipanggil via `subprocess`) | Tidak lewat pip; harus di-bundle terpisah per OS |
| Packaging | `PyInstaller` | Build terpisah di tiap OS (tidak bisa cross-compile) |
| CI/CD build | GitHub Actions (`ubuntu-latest` + `windows-latest`) | Untuk otomatis build dua platform dari 1 repo |
| Format data project | JSON (`.lyricproj`) | Simpan path audio, segments lirik, style, dsb |
| Encoding file | UTF-8 eksplisit di semua read/write | Hindari masalah encoding Windows |

**Jangan menyarankan penggantian stack di atas** kecuali ada masalah teknis
serius yang saya laporkan secara eksplisit.

---

## 3B. STRATEGI MODEL WHISPER (KEPUTUSAN FINAL — Pilihan A: Bundle Model)

Model Whisper (file weights, bukan library-nya) **wajib di-bundle langsung
ke dalam installer/executable**, bukan didownload otomatis saat runtime.
Ini wajib supaya requirement "100% offline" di Bagian 2 benar-benar
terpenuhi, termasuk saat instalasi pertama kali.

**Alasan**: `faster-whisper` secara default akan auto-download model dari
internet saat pertama dipakai (tersimpan di cache HuggingFace). Ini
melanggar syarat offline kalau tidak ditangani.

**Cara implementasi:**

1. Model didownload **sekali oleh developer** (bukan oleh user), lalu
   disimpan permanen di dalam repo/project di folder:
   ```
   assets/models/faster-whisper-<size>/
   ```
2. Kode **wajib** load model dari path lokal ini, **jangan** pakai nama
   model biasa (yang akan trigger auto-download):
   ```python
   # BENAR — path lokal, tidak akan fetch internet
   model = WhisperModel(
       "assets/models/faster-whisper-base",
       device="cpu",
       compute_type="int8"
   )

   # SALAH — ini akan coba auto-download dari HuggingFace
   model = WhisperModel("base", device="cpu")
   ```
3. Saat build dengan PyInstaller, folder `assets/models/` wajib
   di-include lewat opsi `--add-data`, sama seperti folder `assets/fonts/`.
4. Karena file model ikut disimpan di repo/artifact, proses build di
   GitHub Actions (baik `ubuntu-latest` maupun `windows-latest`) akan
   otomatis menyertakan model yang sama — **tidak perlu di-download
   ulang** saat build di mesin Windows.

**Konsekuensi yang disadari & diterima:**
- Ukuran installer akan lebih besar (model `base` ≈150MB, `small` ≈500MB,
  ditambah dependencies lain)
- Ini trade-off yang disengaja demi memenuhi requirement offline —
  **jangan disarankan untuk diubah ke auto-download** kecuali saya
  eksplisit minta ubah requirement offline-nya.

**Ukuran model default**: base (~150MB) — sudah diputuskan.

**Catatan strategi penyimpanan file besar (update)**: Model Whisper dan
FFmpeg binary (`bin/ffmpeg_linux/ffmpeg`, `bin/ffmpeg_windows/ffmpeg.exe`)
**TIDAK disimpan di Git** (baik cara biasa maupun Git LFS) karena
ukurannya besar dan bisa kena limit GitHub. Sebagai gantinya:

- File-file ini masuk `.gitignore`
- Saat proses build CI (`build.yml`), ada step khusus yang men-download
  model Whisper (lewat `faster_whisper.download_model()`) dan FFmpeg
  binary (dari sumber static build) SEBELUM `pyinstaller` dijalankan
- Developer tetap perlu punya file-file ini secara lokal untuk testing
  `python main.py` sehari-hari (didownload manual sekali, lihat
  README di `assets/models/` dan `bin/`)

**Ini TIDAK mengubah keputusan "Pilihan A: Bundle Model" di atas** —
aplikasi hasil jadi (.exe/binary akhir dari PyInstaller) tetap berisi
model di dalamnya dan tetap 100% offline saat dipakai user. Yang
berubah hanya cara file besar ini disimpan/didapat SELAMA proses
development & build, bukan di aplikasi hasil akhir.

---

## 4. STRUKTUR DATA INTI

Struktur ini dipakai konsisten di seluruh aplikasi (transcription, editor,
render, project save/load). **Jangan ubah nama field tanpa update semua
bagian yang memakainya.**

```python
# Satu "segment" lirik
segment = {
    "id": 1,                    # int, urutan unik
    "start": 0.24,               # float, detik
    "end": 2.51,                 # float, detik
    "text": "Lirik baris ini",   # string
}

# Struktur project file (.lyricproj, JSON)
project = {
    "version": "1.0",
    "audio_path": "relative/or/absolute/path.mp3",
    "segments": [ ... ],          # list of segment dict di atas
    "style": {
        "font_path": "assets/fonts/Poppins-Bold.ttf",
        "font_size": 64,
        "text_color": "#FFFFFF",
        "position": "center",      # center | bottom | top
        "transition_type": "fade", # fade | slide_up | slide_left (dst, sesuai yang sudah diimplementasi)
        "transition_duration": 0.3 # detik
    },
    "video_settings": {
        "resolution": [1920, 1080],
        "fps": 30,
        "green_color": "#00FF00"
    }
}
```

---

## 5. ATURAN CODING WAJIB

1. **Path handling**: selalu pakai `pathlib.Path`, jangan hardcode
   path gaya Linux (`/tmp/...`) atau Windows (`C:\...`). Gunakan
   `tempfile.gettempdir()` untuk temp file.
2. **FFmpeg binary**: pilih binary sesuai OS saat runtime:
   ```python
   import platform
   ffmpeg_bin = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
   ```
3. **Font**: jangan bergantung pada font sistem (beda antar OS). Semua
   font harus di-bundle di folder `assets/fonts/`.
4. **File I/O**: selalu eksplisit `encoding="utf-8"`.
5. **Tidak ada network call wajib** di runtime utama — semua proses
   (transcription, render, export) harus bisa jalan tanpa internet.
6. **Modular**: pisahkan logic ke modul berbeda (lihat struktur folder
   di bawah), jangan taruh semua di satu file besar.
7. **Threading**: proses berat (transcription, render, encode) WAJIB
   dijalankan di thread terpisah dari UI thread (pakai `QThread`),
   supaya UI tidak freeze.

---

## 6. STRUKTUR FOLDER PROYEK

```
lyric-green-screen/
├── main.py                      # entry point aplikasi
├── requirements.txt
├── assets/
│   ├── fonts/                   # font yang di-bundle (Poppins, Inter, dll)
│   └── models/                  # model faster-whisper (di-bundle, LIHAT BAGIAN 3B)
│       └── faster-whisper-<size>/
├── core/
│   ├── transcriber.py           # wrapper faster-whisper
│   ├── project_io.py            # save/load .lyricproj (JSON)
│   ├── renderer.py              # render frame teks + transisi (Pillow)
│   └── exporter.py              # panggil FFmpeg untuk encode video
├── ui/
│   ├── main_window.py           # window utama
│   ├── editor_widget.py         # tabel/list editor segmen lirik
│   ├── waveform_widget.py       # visualisasi waveform + timeline
│   └── preview_widget.py        # live preview green screen
├── bin/
│   ├── ffmpeg_linux/
│   └── ffmpeg_windows/
├── .gitignore                   # exclude model & ffmpeg binary dari Git (lihat Bagian 3B)
├── .github/
│   └── workflows/
│       └── build.yml            # CI build Windows + Linux (download model+ffmpeg saat CI)
└── PROJECT_CONTEXT.md           # file ini
```

---

## 7. STATUS PROGRES

> **PENTING: Update bagian ini setiap sesi selesai.** Tandai `[x]` untuk
> yang sudah selesai, tambahkan catatan kalau ada keputusan/perubahan
> penting yang perlu diingat AI di sesi berikutnya.

- [x] Setup environment & struktur folder awal
- [x] Modul `transcriber.py` — integrasi faster-whisper, output list of segments
- [x] Modul `project_io.py` — save/load `.lyricproj`
- [x] UI dasar `main_window.py` — layout dengan area preview, waveform, tabel editor
- [x] `editor_widget.py` — tabel editable untuk segmen lirik (edit teks, start/end, split/merge)
- [x] `waveform_widget.py` — render waveform dari audio
- [x] `preview_widget.py` — live preview green screen dengan teks + transisi
- [x] Sinkronisasi playback audio ↔ highlight segmen aktif ↔ preview
- [x] Modul `renderer.py` — render frame per frame (transisi fade; slide_up sudah ada strukturnya, belum full diuji)
- [x] Modul `exporter.py` — pipeline render frames → FFmpeg → MP4
- [ ] Bundling font & FFmpeg binary — README sudah dibuat, TAPI belum benar-benar mengisi file font/model/ffmpeg (masih placeholder)
- [x] Setup PyInstaller config (Linux) — `lyric_app.spec` sudah dibuat
- [ ] Setup GitHub Actions build (Windows + Linux) — `build.yml` sudah dibuat & sudah diupdate untuk download model+ffmpeg saat CI, TAPI belum pernah benar-benar dijalankan/ditest karena project belum di-push ke GitHub
- [ ] Testing manual di Windows
- [ ] Polish UI / styling tambahan (opsional, di luar MVP)

**Catatan sesi terakhir**: Semua modul inti (transcriber, project_io,
text_frame [shared render logic], renderer, exporter, editor_widget,
waveform_widget, preview_widget, main_window) sudah ditulis lengkap dan
sudah lolos testing otomatis (syntax check, unit test tiap modul,
integrasi MainWindow, render-frame-ke-video end-to-end via FFmpeg) di
lingkungan testing terpisah. **Belum pernah dijalankan langsung oleh
saya sendiri di Ubuntu asli** — perlu saya coba `python main.py` untuk
verifikasi tampilan GUI sungguhan. Model Whisper asli, font, dan ffmpeg
binary belum ditaruh di folder assets/bin (masih kosong + README
panduan). Project juga baru saja di-`git init` secara lokal (belum
pernah push ke GitHub, jadi CI build.yml belum pernah benar-benar jalan
dan belum tervalidasi 100% bekerja).

Ada modul tambahan di luar rencana awal yang ikut dibuat: `core/text_frame.py`
— berisi logic shared untuk render frame teks+transisi, dipakai bersama
oleh `preview_widget.py` (live preview) dan `renderer.py` (export),
supaya hasil preview dan hasil video final selalu identik (menghindari
duplikasi logic transisi di dua tempat berbeda).

---

## 8. HAL YANG PERLU DITANYAKAN KE SAYA DULU (jangan diasumsikan AI)

Kalau instruksi saya ambigu di area berikut, **tanyakan dulu**, jangan
langsung asumsi:

- Ukuran model Whisper mana yang dipakai default (`tiny`/`base`/`small`)
- Resolusi & FPS default output video
- Skema warna/style default teks (kalau saya belum spesifikasikan)
- Apakah suatu fitur masuk MVP (harus ada di versi pertama) atau
  nice-to-have (boleh ditunda)

---

## 9. DI LUAR SCOPE (JANGAN DITAMBAHKAN KECUALI DIMINTA)

- Tidak ada fitur cloud sync / akun user
- Tidak ada fitur multi-track audio / mixing
- Tidak ada AI lyric writing/generation (hanya transcription dari audio
  yang sudah ada, bukan membuat lirik baru)
- Tidak ada export selain MP4 (kecuali diminta eksplisit nanti)
