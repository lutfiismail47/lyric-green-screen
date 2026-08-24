# PROMPT PLAYBOOK — Lyric Green Screen Generator

> **Cara pakai:**
> 1. Selalu mulai sesi BARU dengan **Prompt 0** dulu (tempel isi
>    `PROJECT_CONTEXT.md` juga di pesan yang sama).
> 2. Lanjutkan dengan prompt bernomor secara berurutan, **satu per
>    sesi/pesan**. Jangan loncat, karena tiap modul saling bergantung.
> 3. Setelah tiap prompt selesai dan kode sudah kamu cek jalan, update
>    bagian "STATUS PROGRES" di `PROJECT_CONTEXT.md`, lalu tempel ulang
>    versi terbaru sebelum lanjut ke prompt berikutnya.
> 4. Bagian yang bertanda `[ISI DULU]` wajib kamu lengkapi sebelum
>    disalin — jangan dikirim dengan placeholder kosong.

---

## PROMPT 0 — Kickoff & Konfirmasi Konteks

```
Saya sedang membangun aplikasi desktop bernama "Lyric Green Screen
Generator". Berikut adalah dokumen konteks lengkap proyek ini, yang
berisi tech stack, struktur data, aturan coding, dan struktur folder
yang WAJIB kamu ikuti selama membantu saya coding proyek ini:

[TEMPEL SELURUH ISI PROJECT_CONTEXT.md DI SINI]

Instruksi untuk kamu:
1. Baca dan pahami seluruh dokumen di atas.
2. Jangan menyarankan penggantian tech stack, struktur data, atau
   struktur folder yang sudah ditentukan di dokumen ini, kecuali saya
   secara eksplisit melaporkan ada masalah teknis.
3. Kalau instruksi saya di prompt berikutnya ambigu terkait poin-poin
   di Bagian 8 dokumen ini, tanyakan dulu ke saya sebelum menulis kode.
4. Setelah ini saya akan memberi instruksi satu modul per pesan. Fokus
   HANYA pada modul yang saya minta di tiap pesan — jangan tulis kode
   untuk modul lain meskipun terkait, cukup sebutkan dependensinya
   kalau relevan.
5. Konfirmasi bahwa kamu sudah paham dengan meringkas dalam 3-4 kalimat:
   apa aplikasi ini, tech stack utamanya, dan aturan yang paling penting
   untuk diikuti.

Jangan tulis kode apapun dulu di respons ini — cukup konfirmasi
pemahaman.
```

---

## PROMPT 1 — Setup Environment & Struktur Folder

```
Sekarang buatkan saya:
1. Struktur folder lengkap sesuai Bagian 6 di PROJECT_CONTEXT (buat
   sebagai daftar perintah `mkdir` dan `touch` untuk Ubuntu/bash, bukan
   deskripsi teks saja).
2. File `main.py` sebagai entry point KOSONG tapi valid — cukup buka
   PyQt6 QApplication dengan window kosong berjudul "Lyric Green Screen
   Generator", supaya saya bisa test environment jalan dengan benar.
3. Isi `requirements.txt` (gunakan yang sudah ada di Bagian 3 dokumen
   konteks).
4. Instruksi langkah demi langkah untuk saya setup virtual environment
   di Ubuntu (buat venv, install requirements, cara run main.py).

Jangan buat modul lain dulu (transcriber, editor, dll) — fokus hanya
setup dasar supaya saya bisa pastikan environment jalan dulu.
```

---

## PROMPT 2 — Modul `transcriber.py`

```
Sekarang buatkan modul core/transcriber.py sesuai spesifikasi di
PROJECT_CONTEXT (Bagian 3 dan 3B).

Requirement:
1. Fungsi/class untuk load model faster-whisper dari path LOKAL (folder
   assets/models/), BUKAN dari nama model yang trigger auto-download.
   Ikuti contoh kode "BENAR" di Bagian 3B.
2. Fungsi untuk transcribe file audio (terima path audio, return list
   of segment dict PERSIS sesuai struktur di Bagian 4 — field id, start,
   end, text).
3. Sertakan word-level timestamp jika tersedia dari faster-whisper,
   supaya nanti bisa dipakai untuk sinkronisasi yang presisi.
4. Tangani error dengan baik: file audio tidak ditemukan, folder model
   tidak ditemukan, format audio tidak didukung.
5. Proses transcribe HARUS didesain agar mudah dipanggil dari QThread
   terpisah nantinya (Bagian 5 poin 7) — misal lewat callback progress
   atau bisa di-interrupt.
6. Tulis sebagai kode yang bisa langsung saya test lewat command line
   sederhana (tambahkan `if __name__ == "__main__":` block untuk testing
   manual dengan 1 file audio).

Catatan: saya belum menentukan ukuran model default (tiny/base/small).
Untuk sekarang, buat parameter model_path fleksibel (bisa saya ganti-
ganti saat testing), jangan hardcode salah satu ukuran.
```

---

## PROMPT 3 — Modul `project_io.py`

```
Sekarang buatkan modul core/project_io.py sesuai struktur project file
(.lyricproj) di Bagian 4 PROJECT_CONTEXT.

Requirement:
1. Fungsi save_project(project_dict, file_path) — tulis ke JSON,
   encoding UTF-8 eksplisit (Bagian 5 poin 4), format rapi (indent).
2. Fungsi load_project(file_path) — baca JSON, return dict, validasi
   field wajib ada (version, audio_path, segments, style,
   video_settings). Kalau field hilang atau format tidak sesuai,
   raise error yang jelas — jangan silent fail.
3. Fungsi untuk membuat project baru dengan nilai default yang masuk
   akal, mengikuti struktur di Bagian 4 (audio_path kosong, segments
   kosong, style dan video_settings pakai default value yang sudah
   dicontohkan di dokumen).
4. Path handling wajib pakai pathlib.Path (Bagian 5 poin 1).
5. Sertakan blok testing manual sederhana di bagian bawah file.
```

---

## PROMPT 4 — UI Dasar `main_window.py`

```
Sekarang buatkan ui/main_window.py — layout utama aplikasi.

Requirement:
1. Layout mengikuti sketsa ini (bisa kamu sesuaikan detail teknis PyQt6-
   nya, tapi susunan area harus seperti ini):
   - Area atas: preview green screen (placeholder kotak hijau solid
     dulu, widget asli akan diisi nanti di prompt terpisah)
   - Kontrol audio player sederhana (tombol play/pause/stop) di dekat
     preview
   - Area tengah: waveform/timeline (placeholder kosong dulu)
   - Area bawah: tabel editor segmen lirik (placeholder QTableWidget
     kosong dengan kolom: #, Start, End, Teks)
   - Toolbar/menu: New Project, Open Project, Save Project, Import
     Audio, Export Video
2. HANYA buat kerangka layout dan widget placeholder — belum perlu
   logic asli (belum connect ke transcriber.py atau project_io.py).
   Saya akan sambungkan logic-nya di prompt berikutnya secara bertahap.
3. Gunakan struktur widget terpisah yang nantinya gampang diganti
   dengan widget asli dari ui/editor_widget.py, ui/waveform_widget.py,
   ui/preview_widget.py (sesuai Bagian 6) — jangan tulis semua logic
   langsung di main_window.py.
4. Pastikan main.py yang sudah dibuat di Prompt 1 diupdate untuk
   memanggil MainWindow ini, bukan window kosong lagi.
```

---

## PROMPT 5 — `editor_widget.py` (Tabel Editor Lirik)

```
Sekarang buatkan ui/editor_widget.py — widget tabel editor segmen
lirik yang lebih lengkap, menggantikan placeholder tabel di
main_window.py.

Requirement:
1. Terima list of segment dict (struktur Bagian 4) sebagai input, dan
   tampilkan di QTableWidget dengan kolom: #, Start (mm:ss.ms), End
   (mm:ss.ms), Teks (editable).
2. User bisa edit teks langsung di cell (double-click atau klik
   sekali sesuai konvensi QTableWidget).
3. User bisa edit start/end time secara manual (lewat cell editable
   atau spin box — pilih yang lebih natural untuk PyQt6).
4. Tombol/aksi untuk: Tambah baris baru, Hapus baris terpilih, Split
   segmen terpilih jadi dua, Merge dua segmen terpilih jadi satu.
5. Emit sinyal (PyQt signal) setiap kali data berubah, supaya
   main_window.py atau widget lain bisa dengar perubahan ini (misal
   untuk update preview).
6. Emit sinyal juga saat user klik/pilih baris tertentu, supaya nanti
   bisa dipakai untuk auto-scroll waveform ke posisi segmen tersebut.
7. Sediakan method untuk export data tabel kembali jadi list of
   segment dict (format sama seperti input), supaya bisa langsung
   dipakai project_io.py untuk save.

Jangan sambungkan ke audio player atau waveform dulu — itu di prompt
berikutnya.
```

---

## PROMPT 6 — `waveform_widget.py`

```
Sekarang buatkan ui/waveform_widget.py sesuai Bagian 3 dan 6
PROJECT_CONTEXT (pakai librosa untuk analisis, pyqtgraph untuk render).

Requirement:
1. Terima path file audio, tampilkan visualisasi waveform (amplitude
   over time).
2. Tampilkan indikator posisi playback saat ini (garis vertikal yang
   bergerak sesuai waktu berjalan).
3. User bisa klik di titik manapun pada waveform untuk seek ke posisi
   waktu tersebut (emit sinyal posisi waktu yang diklik).
4. Terima juga list segment (dari editor_widget.py) untuk digambar
   sebagai overlay/marker di atas waveform (menandai batas start/end
   tiap segmen lirik), supaya user bisa lihat korelasi visual antara
   audio dan segmen teks.
5. Method untuk update posisi playback dari luar (dipanggil saat audio
   sedang play, biar garis indikator ikut bergerak).
6. Proses load & analisis waveform untuk file audio yang panjang harus
   tetap responsif — pertimbangkan downsampling data amplitude supaya
   rendering tidak berat (Bagian 2: aplikasi harus ringan).
```

---

## PROMPT 7 — `preview_widget.py` (Live Preview Green Screen)

```
Sekarang buatkan ui/preview_widget.py — live preview green screen
dengan teks lirik dan transisi, menggantikan placeholder kotak hijau
di main_window.py.

Requirement:
1. Render background solid sesuai video_settings.green_color (Bagian
   4, default #00FF00).
2. Terima segment aktif saat ini + progress waktu relatif terhadap
   segment tersebut, lalu render teks sesuai style (font_path,
   font_size, text_color, position) dari struktur style Bagian 4.
3. Implementasikan transisi fade terlebih dahulu (transition_type:
   "fade") — teks fade-in di awal segment dan fade-out di akhir,
   berdasarkan transition_duration. Desain kodenya supaya nanti mudah
   ditambah jenis transisi lain (slide_up, slide_left) tanpa refactor
   besar — misal lewat fungsi terpisah per jenis transisi yang bisa
   di-swap.
4. Widget ini harus bisa update tampilannya secara real-time mengikuti
   posisi playback audio (akan disambungkan ke QMediaPlayer di prompt
   berikutnya).
5. Gunakan Pillow untuk render frame teks ke gambar, lalu tampilkan
   sebagai QPixmap/QLabel di PyQt6 (jelaskan pendekatan yang kamu
   pakai untuk convert PIL Image ke QPixmap).
```

---

## PROMPT 8 — Sinkronisasi Audio Playback + Editor + Preview + Waveform

```
Sekarang sambungkan semua widget yang sudah dibuat (editor_widget.py,
waveform_widget.py, preview_widget.py) di main_window.py, dengan alur
sinkronisasi berikut:

1. Saat audio diputar lewat QMediaPlayer, posisi playback saat ini
   dipakai untuk:
   - Update garis indikator posisi di waveform_widget
   - Tentukan segment mana yang sedang aktif (berdasarkan start/end
     tiap segment), lalu highlight baris terkait di editor_widget
     (tabel)
   - Kirim segment aktif + progress waktu relatif ke preview_widget
     untuk render teks dengan transisi yang sesuai
2. Saat user klik salah satu baris di editor_widget (tabel), audio
   player seek ke waktu start segment tersebut.
3. Saat user klik di waveform_widget, audio player seek ke waktu
   yang diklik.
4. Update loop ini harus efisien — jangan re-render preview di setiap
   pixel pergerakan kalau tidak perlu, gunakan interval update yang
   wajar (misal setiap beberapa puluh milidetik) supaya tetap ringan
   sesuai requirement Bagian 2.

Tunjukkan perubahan yang perlu dilakukan di main_window.py untuk
menghubungkan semua sinyal (signals) antar widget ini.
```

---

## PROMPT 9 — Modul `renderer.py` (Render Frame untuk Export)

```
Sekarang buatkan core/renderer.py — render engine untuk keperluan
EXPORT (bukan preview live, ini untuk generate semua frame video
final).

Requirement:
1. Terima: list segments, dict style, dict video_settings (struktur
   Bagian 4).
2. Generate satu frame gambar (Pillow Image) untuk timestamp tertentu
   — reuse logic transisi yang sama dengan preview_widget.py supaya
   hasil render final identik dengan yang terlihat di preview (jangan
   duplikasi logic transisi secara terpisah, pertimbangkan extract ke
   fungsi/module shared kalau perlu).
3. Fungsi untuk generate seluruh urutan frame dari durasi 0 sampai
   akhir audio, sesuai fps di video_settings.
4. Optimalkan untuk kecepatan render (Bagian 2: aplikasi harus ringan
   & performant) — jelaskan trade-off apa saja yang kamu pertimbangkan
   (misal render paralel per frame, caching, dsb).
5. Sediakan callback progress (persentase frame yang sudah selesai
   di-render), supaya bisa ditampilkan di UI progress bar nantinya.
6. Ingat Bagian 5 poin 7 — proses ini akan dipanggil dari QThread
   terpisah, desain API-nya supaya mendukung itu (bisa di-cancel
   di tengah jalan).
```

---

## PROMPT 10 — Modul `exporter.py` (FFmpeg Pipeline)

```
Sekarang buatkan core/exporter.py — pipeline final dari frames hasil
renderer.py menjadi file MP4, menggunakan FFmpeg lewat subprocess
(Bagian 3).

Requirement:
1. Terima folder/list frame gambar hasil renderer.py + path audio asli
   + video_settings (resolution, fps), lalu jalankan FFmpeg untuk
   menggabungkan jadi 1 file MP4 dengan audio.
2. Pilih binary ffmpeg sesuai OS saat runtime, ikuti contoh kode di
   Bagian 5 poin 2 PROJECT_CONTEXT persis (path ke bin/ffmpeg_linux/
   atau bin/ffmpeg_windows/ sesuai struktur folder Bagian 6).
3. Tangani proses FFmpeg secara asinkron/non-blocking (jalan di
   QThread terpisah, Bagian 5 poin 7), dengan callback progress kalau
   memungkinkan (parsing output FFmpeg untuk estimasi persentase).
4. Validasi sebelum proses: cek ffmpeg binary ada, cek folder frame
   tidak kosong, cek audio path valid.
5. Setelah proses selesai, cleanup file-file frame sementara (temporary
   files) — gunakan tempfile.gettempdir() sesuai Bagian 5 poin 1,
   jangan tinggalkan sampah di sistem user.
6. Sertakan blok testing manual sederhana untuk saya coba end-to-end
   dengan folder frame contoh.
```

---

## PROMPT 11 — Bundling Font & FFmpeg Binary

```
Sekarang bantu saya siapkan proses bundling font dan FFmpeg binary
sesuai Bagian 3B (khusus model) dan Bagian 6 (struktur folder)
PROJECT_CONTEXT.

Berikan:
1. Rekomendasi 1-2 font open-source (gratis untuk redistribusi
   komersial) yang cocok untuk teks lirik video, beserta link resmi
   downloadnya, untuk saya taruh di assets/fonts/.
2. Instruksi jelas cara mendapatkan ffmpeg binary static/portable
   untuk Linux dan Windows (bukan yang perlu instalasi terpisah oleh
   user), untuk saya taruh di bin/ffmpeg_linux/ dan bin/ffmpeg_windows/.
3. Instruksi cara saya extract folder model faster-whisper yang sudah
   ter-download di cache Ubuntu saya, untuk dipindah ke
   assets/models/faster-whisper-<size>/ (ikuti Bagian 3B).
4. Checklist verifikasi: bagaimana saya test bahwa aplikasi benar-benar
   tidak melakukan network call sama sekali saat runtime (misal cara
   test dengan mematikan koneksi internet lalu jalankan full alur audio
   → transcribe → edit → export).
```

---

## PROMPT 12 — Setup PyInstaller (Linux)

```
Sekarang buatkan konfigurasi PyInstaller untuk build aplikasi ini di
Ubuntu, sesuai struktur folder Bagian 6 PROJECT_CONTEXT.

Requirement:
1. File .spec PyInstaller (bukan hanya command line) supaya konfigurasi
   tersimpan dan konsisten dipakai ulang, termasuk cara reference-nya
   dari GitHub Actions nanti.
2. Pastikan folder assets/fonts/, assets/models/, dan bin/ffmpeg_linux/
   ikut ter-bundle (data files), sesuai Bagian 3B dan Bagian 5.
3. Jelaskan opsi --onefile vs --onedir, dan rekomendasikan mana yang
   lebih cocok mengingat ukuran model Whisper yang besar (pertimbangkan
   waktu startup aplikasi).
4. Sertakan instruksi command lengkap untuk saya jalankan build secara
   manual di Ubuntu dulu (sebelum otomasi CI), supaya saya bisa
   verifikasi hasil build jalan dengan benar.
```

---

## PROMPT 12B — Setup `.gitignore` (sebelum git init / sebelum push pertama)

```
Sebelum saya push project ini ke GitHub, buatkan saya file .gitignore
untuk root project ini.

Requirement:
1. WAJIB exclude file-file besar berikut (lihat PROJECT_CONTEXT Bagian
   3B — strategi terbaru, file ini didownload otomatis saat CI, BUKAN
   disimpan di Git):
   - assets/models/faster-whisper-<size>/ (ganti <size> sesuai model
     default di Bagian 3B)
   - bin/ffmpeg_linux/ffmpeg
   - bin/ffmpeg_windows/ffmpeg.exe
2. Tambahkan juga pattern standar Python (__pycache__/, *.pyc, venv/,
   .venv/, *.egg-info/) dan hasil build PyInstaller (build/, dist/).
3. Tambahkan pattern umum OS/editor (.DS_Store, Thumbs.db, .vscode/,
   .idea/) kalau relevan.
4. JANGAN exclude folder assets/fonts/ — font wajib ikut di-commit
   karena ukurannya kecil dan tidak didownload otomatis saat CI.

Setelah itu, tunjukkan ke saya command untuk verifikasi .gitignore
bekerja dengan benar SEBELUM saya commit pertama kali:
  git init
  git add .
  git status   # cek: pastikan file model & ffmpeg TIDAK muncul di sini
```

---

## PROMPT 13 — Update GitHub Actions Workflow (Build Windows + Linux)

```
Saya sudah punya starter file .github/workflows/build.yml (isi di
bawah). Sekarang update/lengkapi file ini berdasarkan konfigurasi
PyInstaller .spec yang sudah kita buat di prompt sebelumnya, supaya
CI build benar-benar menghasilkan installer/executable yang lengkap
dengan assets (font, model, ffmpeg binary) untuk kedua OS.

File build.yml saat ini:
[TEMPEL ISI build.yml DI SINI]

PENTING — perubahan strategi (baca dulu sebelum menulis kode):
Model Whisper (~150MB) dan FFmpeg binary TIDAK akan disimpan di Git
sama sekali (bukan cara biasa, dan BUKAN Git LFS juga) karena akan
kena limit ukuran file GitHub (100MB) dan bisa boros kuota LFS. File-
file ini sudah saya masukkan ke .gitignore. Sebagai gantinya, file-
file ini harus DIDOWNLOAD OTOMATIS di dalam workflow ini setiap kali
CI jalan, SEBELUM step build PyInstaller. Ini tidak melanggar
requirement "aplikasi offline" (Bagian 2 PROJECT_CONTEXT) karena yang
wajib offline itu APLIKASI HASIL JADI saat dipakai user, bukan proses
build developer — mesin GitHub Actions memang punya akses internet.

Requirement:
1. Gunakan file .spec, bukan command line PyInstaller manual, supaya
   konsisten dengan Prompt 12.
2. Tambahkan step untuk download model Whisper (ukuran sesuai Bagian
   3B) memakai fungsi `faster_whisper.download_model()`, simpan ke
   path yang sama persis dengan yang dibaca core/transcriber.py
   (assets/models/faster-whisper-<size>/).
3. Tambahkan step terpisah untuk download FFmpeg binary sesuai OS
   (pakai source static build untuk Linux dan Windows — kalau kamu
   tahu URL sumber yang reliable, pakai itu; kalau tidak yakin,
   tanyakan ke saya dulu link mana yang sebaiknya dipakai, jangan
   asal tebak URL), simpan ke bin/ffmpeg_linux/ffmpeg (Linux) dan
   bin/ffmpeg_windows/ffmpeg.exe (Windows).
4. Step download harus jalan SEBELUM step build PyInstaller, dan
   idealnya beri nama step yang jelas (misal "Download Whisper model",
   "Download FFmpeg").
5. Upload hasil build sebagai artifact terpisah untuk tiap OS, dengan
   nama yang jelas (misal lyric-app-windows, lyric-app-linux).
6. Sertakan catatan/komentar di file YAML untuk bagian yang mungkin
   perlu saya sesuaikan manual (misal versi Python, nama entry point,
   versi/link ffmpeg kalau nanti sumbernya berubah).

Jangan sarankan Git LFS untuk menyimpan model/ffmpeg di repo — itu
sudah diputuskan TIDAK dipakai, sesuai strategi di atas.
```

---

## PROMPT 14 — Checklist Testing Manual Sebelum Rilis

```
Aplikasi sudah selesai dibangun sesuai seluruh modul di
PROJECT_CONTEXT. Sekarang buatkan saya checklist testing manual yang
lengkap, mencakup:

1. Testing di Ubuntu (environment development saya) — alur end-to-end
   dari import audio sampai export video.
2. Testing di Windows — poin-poin yang PALING RAWAN berbeda perilaku
   dibanding Linux (rujuk ke potensi masalah yang disebutkan soal
   QMediaPlayer, path handling, font, ffmpeg binary).
3. Test khusus mode offline (mematikan koneksi internet lalu jalankan
   full alur aplikasi).
4. Test edge case: file audio sangat pendek, sangat panjang, format
   audio berbeda (mp3 vs wav), audio dengan bagian hening panjang,
   lirik dengan karakter non-ASCII/emoji.
5. Format checklist sebagai daftar checkbox markdown yang bisa saya
   simpan dan centang manual satu per satu.
```

---

## CATATAN PENGGUNAAN TAMBAHAN

- Kalau di tengah jalan Gemini memberi kode yang **melanggar aturan** di
  `PROJECT_CONTEXT.md` (misal pakai library lain, hardcode path, dsb),
  tegur langsung dengan menunjuk bagian dokumen yang dilanggar, contoh:
  > "Ini melanggar Bagian 5 poin 1 di PROJECT_CONTEXT — tolong perbaiki
  > pakai pathlib.Path."
- Setelah tiap prompt berhasil dan sudah kamu test, **selalu update**
  checklist "STATUS PROGRES" di `PROJECT_CONTEXT.md` sebelum lanjut ke
  prompt nomor berikutnya, supaya konteks tetap sinkron di sesi
  selanjutnya.
- Prompt-prompt ini didesain berurutan karena tiap modul bergantung pada
  struktur/hasil modul sebelumnya. Kalau kamu ingin lompat urutan,
  pastikan modul yang jadi dependensinya sudah selesai duluan.
