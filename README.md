# 🎓 Sistem Informasi Peringatan Dini Akademik (SI-EWS)

Aplikasi web Sistem Informasi Peringatan Dini (*Early Warning System*) akademik mahasiswa berbasis **Python 3.11+**, **Flask**, **Flask-SQLAlchemy (SQLAlchemy 2.x)**, **Flask-WTF / WTForms**, dan **Jinja2**.

Aplikasi ini dirancang untuk mendeteksi secara dini mahasiswa yang membutuhkan bimbingan intensif berdasarkan parameter Indeks Prestasi Kumulatif (IPK < 2.50) dan tingkat presensi kehadiran (< 75%), serta menyediakan pencatatan konseling/bimbingan akademik secara terintegrasi.

---

## 📑 Daftar Isi
1. [Tech Stack & Arsitektur](#-tech-stack--arsitektur)
2. [Struktur Direktori Proyek](#-struktur-direktori-proyek)
3. [Rekapitulasi Fitur Utama](#-rekapitulasi-fitur-utama)
4. [Langkah demi Langkah Penerapan Lokal](#-langkah-demi-langkah-penerapan-lokal)
5. [Pengujian Otomatis (Automated Testing)](#-pengujian-otomatis-automated-testing)
6. [Panduan Deployment ke PythonAnywhere.com](#-panduan-deployment-ke-pythonanywherecom)
7. [Daftar Endpoint & Rute HTTP](#-daftar-endpoint--rute-http)

---

## 🛠 Tech Stack & Arsitektur

- **Backend**: Python 3.11+, Flask 3.x
- **Database & ORM**: SQLite, Flask-SQLAlchemy 3.x dengan standar penulisan **SQLAlchemy 2.x** (`Mapped`, `mapped_column`, `db.select`)
- **Formulir & Validasi**: Flask-WTF, WTForms, `email-validator` (dilengkapi proteksi CSRF otomatis)
- **Templating Engine**: Jinja2 (Custom Filters: `predikat`, `persen`, serta Reusable Macros `_makro.html`)
- **Frontend Styling**: Bootstrap 5.3, Bootstrap Icons (Responsif & Modern)
- **Arsitektur Pattern**:
  - **PRG Pattern (Post/Redirect/Get)** untuk mencegah submit form ganda (*double form submission*).
  - **Dual-Mode 404 Handler**: Merespons dengan template HTML untuk browser dan payload JSON untuk permintaan API.
  - **Cascade Delete-Orphan**: Menjamin keutuhan integritas data relasional *One-to-Many*.

---

## 📂 Struktur Direktori Proyek

```text
Applikasi_Web_SI/
├── app.py                     # Entry point aplikasi Flask, routing, controller & custom CLI
├── models.py                  # Definisi skema ORM (Mahasiswa, Catatan & RencanaIntervensi)
├── forms.py                   # Form WTForms dengan validasi sisi server
├── uji_app.py                 # Automated unit tests (in-memory SQLite & mock HTTP client)
├── requirements.txt           # Daftar pustaka dependensi produksi & pengujian
├── siews.db                   # Basis data SQLite lokal (dibuat otomatis saat seed/run)
├── README.md                  # Dokumentasi teknis dan rekapitulasi proyek
└── templates/                 # Berkas presentasi Jinja2
    ├── _makro.html            # Makro komponen formulir (label, input, error)
    ├── base.html              # Layout utama, tag <nav>, dan blok pesan Flash
    ├── index.html             # Dashboard statistik mahasiswa berisiko
    ├── mahasiswa.html         # Tabel data mahasiswa dengan filter ?prodi=
    ├── tambah.html            # Formulir tambah mahasiswa baru via makro Jinja
    ├── edit.html              # Formulir edit data mahasiswa (NIM read-only)
    ├── detail.html            # Profil mahasiswa, riwayat catatan & form hapus
    ├── cari.html              # Form pencarian mahasiswa dengan arsitektur PRG
    └── 404.html               # Halaman kustom penanganan error HTTP 404
```

---

## 🚀 Rekapitulasi Fitur Utama

### 1. Data Model & Relasi ORM (`models.py`)
- **Model `Mahasiswa`**: Kolom `id` (PK), `nim` (String 14, unique), `nama`, `prodi`, `ipk` (Float), `kehadiran` (Integer), `email` (String nullable).
- **Model `Catatan`**: Kolom `id` (PK), `mahasiswa_id` (FK), `jenis`, `isi`, `dibuat` (DateTime UTC default).
- **Relasi One-to-Many**: Dihubungkan dengan parameter `back_populates` di kedua sisi model untuk navigasi dua arah, serta `cascade="all, delete-orphan"` agar catatan otomatis terhapus saat mahasiswa dihapus.
- **Model `RencanaIntervensi`**: Menyimpan langkah tindak lanjut, penanggung jawab, tenggat, dan status (`Belum dimulai`, `Berjalan`, atau `Selesai`). Rencana yang melewati tenggat ditandai di dashboard dan profil mahasiswa.

### 2. Validasi Form Sisi Server (`forms.py`)
- **`MahasiswaForm`**:
  - `nim`: Validasi format baku `A11.2023.00001` via `Regexp(r'^[A-Z]\d{2}\.\d{4}\.\d{5}$')`.
  - `nama`: `Length(min=3, max=100)`.
  - `prodi`: Pilihan dibatasi hanya `SI`, `TI`, atau `MI` menggunakan validator `AnyOf`.
  - `ipk` & `kehadiran`: Menggunakan **`InputRequired`** (bukan `DataRequired`) agar nilai `0` dan `0.0` tetap sah secara matematis.
  - `validate_nim`: Validator kustom yang mengecek duplikasi ke database SQLite secara *real-time*.
- **`CatatanForm`**:
  - `jenis`: `SelectField` (Akademik, Keuangan, Pribadi).
  - `isi`: `TextAreaField` dengan panjang 10–500 karakter dan penyaring teks sampah menggunakan `NoneOf(values=['tes', 'test', '-'])`.

### 3. Custom Jinja Filters & Makro (`app.py` & `_makro.html`)
- `{{ ipk | predikat }}`: Mengubah skor angka menjadi predikat resmi (*Dengan Pujian / Sangat Memuaskan / Memuaskan / Cukup / Kurang*).
- `{{ kehadiran | persen }}`: Memformat angka rasio/persentase menjadi string berformat `XX.X%`.
- `_makro.html`: Komponen modular `render_field()` yang otomatis menyematkan kelas CSS Bootstrap `is-invalid` dan menampilkan pesan kesalahan validasi per kolom.

### 4. Custom CLI Seeder (`@app.cli.command("seed")`)
Perintah terminal khusus untuk me-reset tabel dan mengisi 5 data dummy mahasiswa beserta catatan konseling awal.

Untuk menambahkan tabel yang belum tersedia ke database yang sudah berisi data, jalankan `flask init-db`. Perintah ini hanya membuat tabel yang belum ada dan tidak menghapus data. Perintah `flask seed` tetap mereset seluruh tabel dan datanya.

---

## 💻 Langkah demi Langkah Penerapan Lokal

Ikuti instruksi berikut untuk menjalankan aplikasi di komputer lokal:

### Langkah 1: Siapkan Virtual Environment
Buka terminal pada folder proyek:
```bash
# Membuat environment Python
python -m venv venv

# Aktivasi Environment:
# Di Windows (Command Prompt / PowerShell):
.\venv\Scripts\activate
# Di Linux / macOS:
source venv/bin/activate
```

### Langkah 2: Instalasi Dependensi
Pastikan pip terbarui, lalu pasang dependensi:
```bash
pip install -r requirements.txt
```

### Langkah 3: Inisialisasi & Seed Database SQLite
Jalankan CLI command yang telah disediakan untuk membuat skema tabel dan mengisi data awal:
```bash
flask seed
```
*Output yang diharapkan:*
```text
SUCCESS: Database SQLite berhasil di-reset dan diisi 5 data dummy mahasiswa!
```

### Langkah 4: Jalankan Server Aplikasi
Jalankan aplikasi Flask dalam mode pengembangan (*development*):
```bash
python app.py
```
Aplikasi akan aktif dan dapat diakses di browser pada alamat:
👉 **`http://127.0.0.1:5000`**

---

## 🧪 Pengujian Otomatis (Automated Testing)

Pengujian menyeluruh telah disediakan di file [uji_app.py](file:///d:/Applikasi_Web_SI/uji_app.py).

Karakteristik pengujian:
- **Zero Side-Effect**: Berjalan di atas basis data memori `sqlite://`, tidak menyentuh maupun merusak database utama `siews.db`.
- **Bypass CSRF**: `WTF_CSRF_ENABLED = False` diaktifkan khusus selama pengujian agar simulasi POST form dapat diuji langsung.

Jalankan perintah berikut di terminal:
```bash
python uji_app.py
```

### Rangkuman Skenario Pengujian:
1. `test_post_mahasiswa_valid_status_302`: Pengiriman form valid -> memastikan status HTTP `302` (Redirect PRG) dan data tersimpan di SQLite.
2. `test_post_mahasiswa_semua_data_salah_status_422`: Pengiriman data salah -> memastikan status HTTP `422` dan seluruh pesan error validasi muncul di HTML.
3. `test_post_mahasiswa_nim_duplikat_tertolak_422`: Pengujian validator kustom `validate_nim` saat NIM kembar di-submit.
4. `test_relasi_mahasiswa_catatan_orm`: Memverifikasi keterhubungan data mahasiswa dan catatan melalui query relasi dua arah (`mahasiswa.catatan` & `catatan.mahasiswa`).
5. `test_get_rute_dasar_dan_filter_prodi`: Memastikan rute `/` dan filter `?prodi=` berfungsi normal.
6. `test_api_json_respons`: Memastikan endpoint `/api/mahasiswa/<nim>` menghasilkan format JSON yang valid.

---

## 🌐 Panduan Deployment ke PythonAnywhere.com

### 1. Upload Berkas
1. Masuk ke dashboard [PythonAnywhere.com](https://www.pythonanywhere.com/).
2. Buka **Consoles** -> **Bash**, lalu clone atau letakkan proyek Anda di direktori:
   ```bash
   /home/<username>/Applikasi_Web_SI
   ```

### 2. Setup Virtual Environment di PythonAnywhere
Di dalam Bash Console PythonAnywhere, jalankan:
```bash
cd /home/<username>/Applikasi_Web_SI
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask seed
```

### 3. Konfigurasi Tab "Web"
1. Buka tab **Web** di dashboard PythonAnywhere.
2. Klik **Add a new web app** -> pilih **Manual configuration** -> pilih versi **Python 3.11**.
3. Di bagian **Code**:
   - **Source code:** `/home/<username>/Applikasi_Web_SI`
   - **Working directory:** `/home/<username>/Applikasi_Web_SI`
4. Di bagian **Virtualenv**:
   - Masukkan path: `/home/<username>/Applikasi_Web_SI/venv`

### 4. Konfigurasi File WSGI
Klik link pada baris **WSGI configuration file** (biasanya `/var/www/<username>_pythonanywhere_com_wsgi.py`), lalu ganti seluruh isinya dengan:

```python
import os
import sys

# Ganti <username> dengan username akun PythonAnywhere Anda
username = "username"
project_home = f"/home/{username}/Applikasi_Web_SI"

if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["FLASK_ENV"] = "production"

# Import instance Flask sebagai application untuk WSGI server
from app import app as application
```

### 5. Reload Web App
Klik tombol hijau **Reload <username>.pythonanywhere.com** dan situs Anda telah aktif secara publik di `https://<username>.pythonanywhere.com`.

---

## 📌 Daftar Endpoint & Rute HTTP

| Metode | URL Endpoint | Deskripsi | Status Respons |
|---|---|---|---|
| `GET` | `/` | Dashboard ringkasan total mahasiswa dan mahasiswa berisiko | `200 OK` |
| `GET` | `/mahasiswa` | Tabel data mahasiswa (mendukung query string `?prodi=`) | `200 OK` |
| `GET` | `/mahasiswa/tambah` | Menampilkan form pendaftaran mahasiswa baru (`tambah.html`) | `200 OK` |
| `POST` | `/mahasiswa/tambah` | Menyimpan data mahasiswa (Redirect jika valid, 422 jika gagal) | `302` / `422` |
| `GET` | `/mahasiswa/<nim>/edit` | Menampilkan form pembaruan data mahasiswa (`edit.html`) | `200 OK` / `404` |
| `POST` | `/mahasiswa/<nim>/edit` | Menyimpan perubahan data mahasiswa (Redirect jika valid, 422 jika gagal) | `302` / `422` |
| `GET` | `/ekspor/mahasiswa` | Mengunduh berkas laporan CSV (filter `?status=berisiko` / `?status=semua`) | `200 OK` |
| `GET` | `/mahasiswa/<nim>` | Halaman detail profil, riwayat catatan & form tambah catatan | `200 OK` / `404` |
| `POST` | `/mahasiswa/<nim>` | Menyimpan catatan konseling baru milik mahasiswa terkait (PRG) | `302 Redirect` |
| `POST` | `/mahasiswa/<nim>/rencana` | Membuat rencana intervensi mahasiswa (PRG) | `302 Redirect` |
| `POST` | `/rencana/<id>/status` | Memperbarui status tindak lanjut (`Belum dimulai`, `Berjalan`, `Selesai`) | `302 Redirect` |
| `POST` | `/mahasiswa/<nim>/hapus` | Menghapus mahasiswa beserta seluruh catatan terkait (*cascade*) | `302 Redirect` |
| `GET` | `/cari` | Menampilkan antarmuka pencarian mahasiswa | `200 OK` |
| `POST` | `/cari` | Memproses pencarian dan mengalihkan ke rute GET tujuan (PRG) | `302 Redirect` |
| `GET` | `/api/mahasiswa/<nim>` | Mengembalikan respons data mahasiswa & daftar catatan format JSON | `200 OK` / `404` |
| `ANY` | *Rute Salah* | Penanganan error 404 (Browser: `404.html`, API: JSON error 404) | `404 Not Found` |

---
*Dikembangkan dengan standar arsitektur dan kualitas kode Senior Web Developer.*
