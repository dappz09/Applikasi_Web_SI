import os
import unittest
from datetime import date, timedelta

# ==============================================================================
# KONFIGURASI PENGUJIAN ISOLASI (IN-MEMORY DATABASE & NONAKTIFKAN CSRF)
# ==============================================================================
# Konfigurasikan sqlite:// (in-memory) sebelum import agar tidak menyentuh siews.db
os.environ["DATABASE_URL"] = "sqlite://"

from app import app
from models import db, Mahasiswa, Catatan, RencanaIntervensi

# Set konfigurasi pengujian
app.config["TESTING"] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
app.config["WTF_CSRF_ENABLED"] = (
    False  # Nonaktifkan sementara CSRF untuk pengujian payload form
)


class TestSIPeringatanDini(unittest.TestCase):
    """Test suite otomatis menggunakan SQLite in-memory dan Flask test_client()."""

    def setUp(self):
        """Menyiapkan konteks aplikasi dan database in-memory bersih sebelum tiap tes."""
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        # Buat seluruh tabel skema di memory
        db.create_all()

        # Masukkan 1 data awal untuk pengujian referensi
        self.mhs_awal = Mahasiswa(
            nim="A11.2023.00001",
            nama="Ahmad Fauzi",
            prodi="SI",
            ipk=3.75,
            kehadiran=92,
            email="ahmad.fauzi@kampus.ac.id",
        )
        db.session.add(self.mhs_awal)
        db.session.commit()

    def tearDown(self):
        """Membersihkan sesi dan menghapus database in-memory setelah tiap tes selesai."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================================================
    # SKENARIO 1: Pengiriman Form MahasiswaForm dengan Data Valid (Status 302)
    # ==========================================================================
    def test_post_mahasiswa_valid_status_302(self):
        """Memastikan data form valid berhasil disimpan dan server merespons 302 Redirect."""
        payload = {
            "nim": "A11.2023.00002",
            "nama": "Budi Santoso",
            "prodi": "TI",
            "ipk": 2.35,
            "kehadiran": 68,
            "email": "budi.santoso@kampus.ac.id",
        }

        response = self.client.post("/mahasiswa/tambah", data=payload)

        # 1. Pastikan kembali status 302 (Redirect)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/mahasiswa/A11.2023.00002", response.headers["Location"])

        # 2. Verifikasi data berhasil tersimpan di database via ORM
        mhs = db.session.scalar(
            db.select(Mahasiswa).filter_by(nim="A11.2023.00002")
        )
        self.assertIsNotNone(mhs)
        self.assertEqual(mhs.nama, "Budi Santoso")
        self.assertEqual(mhs.prodi, "TI")
        self.assertEqual(mhs.ipk, 2.35)
        self.assertEqual(mhs.kehadiran, 68)

    # ==========================================================================
    # SKENARIO 2: Pengiriman Form dengan Data Salah Semua (Status 422 & Error Muncul)
    # ==========================================================================
    def test_post_mahasiswa_semua_data_salah_status_422(self):
        """Memastikan pengiriman seluruh data salah mengembalikan 422 dan pesan error validasi."""
        payload_salah = {
            "nim": "format_salah_123",  # Tidak sesuai regex A11.2023.00001
            "nama": "Al",  # Kurang dari panjang minimum (min=3)
            "prodi": "KEDOKTERAN",  # Bukan salah satu dari: SI, TI, MI
            "ipk": 5.5,  # Di luar rentang 0.00 - 4.00
            "kehadiran": 150,  # Di luar rentang 0 - 100
            "email": "bukan-format-email",  # Format email tidak valid
        }

        response = self.client.post("/mahasiswa/tambah", data=payload_salah)

        # 1. Pastikan kembali status 422 (Unprocessable Content)
        self.assertEqual(response.status_code, 422)

        html = response.get_data(as_text=True)

        # 2. Pastikan pesan error spesifik muncul di halaman HTML
        self.assertIn("Format NIM tidak valid", html)
        self.assertIn(
            "Nama harus memiliki panjang antara 3 hingga 100", html
        )
        self.assertIn("Program studi harus salah satu dari: SI, TI, atau MI", html)
        self.assertIn("IPK harus berada dalam rentang", html)
        self.assertIn("Kehadiran harus berada dalam rentang", html)
        self.assertIn("Format alamat email tidak valid", html)

    # ==========================================================================
    # SKENARIO 3: Pengiriman NIM yang Sudah Ada (Validasi Khusus validate_nim)
    # ==========================================================================
    def test_post_mahasiswa_nim_duplikat_tertolak_422(self):
        """Memastikan validator khusus validate_nim menolak NIM yang sudah terdaftar."""
        # NIM A11.2023.00001 sudah didaftarkan di setUp()
        payload_duplikat = {
            "nim": "A11.2023.00001",
            "nama": "Siswa Kembar",
            "prodi": "SI",
            "ipk": 3.20,
            "kehadiran": 85,
            "email": "siswa.kembar@kampus.ac.id",
        }

        response = self.client.post("/mahasiswa/tambah", data=payload_duplikat)

        # 1. Status kode harus 422
        self.assertEqual(response.status_code, 422)

        # 2. Pesan error dari metode khusus validate_nim muncul
        html = response.get_data(as_text=True)
        self.assertIn("sudah terdaftar dalam sistem", html)

    # ==========================================================================
    # SKENARIO 4: Uji Relasi ORM (Menambahkan Catatan & Memverifikasi Akses Dua Arah)
    # ==========================================================================
    def test_relasi_mahasiswa_catatan_orm(self):
        """Memastikan penambahan catatan konseling terhubung ke mahasiswa via relasi ORM."""
        payload_catatan = {
            "jenis": "Akademik",
            "isi": "Konseling perencanaan tugas akhir dan evaluasi performa akademik semester.",
        }

        # POST catatan baru ke endpoint detail mahasiswa A11.2023.00001
        response = self.client.post(
            "/mahasiswa/A11.2023.00001", data=payload_catatan
        )
        self.assertEqual(response.status_code, 302)

        # Verifikasi relasi lewat query ORM (Mahasiswa -> Catatan)
        mahasiswa = db.session.scalar(
            db.select(Mahasiswa).filter_by(nim="A11.2023.00001")
        )
        self.assertEqual(len(mahasiswa.catatan), 1)

        catatan = mahasiswa.catatan[0]
        self.assertEqual(catatan.jenis, "Akademik")
        self.assertEqual(
            catatan.isi,
            "Konseling perencanaan tugas akhir dan evaluasi performa akademik semester.",
        )

        # Verifikasi akses relasi dua arah (Catatan -> Mahasiswa via back_populates)
        self.assertEqual(catatan.mahasiswa.nim, "A11.2023.00001")
        self.assertEqual(catatan.mahasiswa.nama, "Ahmad Fauzi")

    # ==========================================================================
    # SKENARIO PENDUKUNG: Pengujian Rute Dasar, Filter Prodi, dan API JSON
    # ==========================================================================
    def test_get_rute_dasar_dan_filter_prodi(self):
        """Memastikan rute / dan /mahasiswa?prodi= berjalan normal."""
        resp_index = self.client.get("/")
        self.assertEqual(resp_index.status_code, 200)

        resp_prodi = self.client.get("/mahasiswa?prodi=SI")
        self.assertEqual(resp_prodi.status_code, 200)
        self.assertIn("Ahmad Fauzi", resp_prodi.get_data(as_text=True))

    def test_halaman_anggota_tim(self):
        """Memastikan halaman anggota tim dapat dibuka dan memuat nama serta NIM."""
        response = self.client.get("/tim")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Anggota Tim", html)
        self.assertIn("Adela Putri Aji", html)
        self.assertIn("24.01.55.0012", html)
        self.assertIn("Daffa Iqbal Maulana", html)
        self.assertIn("24.01.55.14", html)
        self.assertIn("Kaisya Audia Viera", html)
        self.assertIn("24.01.55.0015", html)

    def test_api_json_respons(self):
        """Memastikan API JSON mengembalikan data mahasiswa dan list catatan."""
        response = self.client.get("/api/mahasiswa/A11.2023.00001")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)

        data = response.get_json()["data"]
        self.assertEqual(data["nim"], "A11.2023.00001")
        self.assertEqual(data["predikat"], "Dengan Pujian (Cumlaude)")
        self.assertEqual(data["kehadiran"], "92.0%")

    def test_tambah_dan_perbarui_status_rencana_intervensi(self):
        """Memastikan rencana tersimpan dan statusnya dapat diperbarui."""
        payload = {
            "judul": "Bimbingan akademik",
            "deskripsi": "Jadwalkan sesi bimbingan dan evaluasi mata kuliah.",
            "penanggung_jawab": "Dosen Wali",
            "tenggat": (date.today() + timedelta(days=7)).isoformat(),
        }
        response = self.client.post(
            "/mahasiswa/A11.2023.00001/rencana",
            data=payload,
        )
        self.assertEqual(response.status_code, 302)

        rencana = db.session.scalar(db.select(RencanaIntervensi))
        self.assertIsNotNone(rencana)
        self.assertEqual(rencana.status, "Belum dimulai")
        self.assertEqual(rencana.mahasiswa.nim, "A11.2023.00001")

        detail = self.client.get("/mahasiswa/A11.2023.00001")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Bimbingan akademik", detail.get_data(as_text=True))

        response = self.client.post(
            f"/rencana/{rencana.id}/status",
            data={"status": "Selesai"},
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(rencana)
        self.assertEqual(rencana.status, "Selesai")

    def test_rencana_intervensi_tidak_menyimpan_data_tidak_valid(self):
        """Memastikan validasi rencana menampilkan error tanpa menyimpan data."""
        response = self.client.post(
            "/mahasiswa/A11.2023.00001/rencana",
            data={
                "judul": "AB",
                "deskripsi": "Pendek",
                "penanggung_jawab": "",
                "tenggat": "tanggal-salah",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn(
            "Judul rencana harus memiliki panjang",
            response.get_data(as_text=True),
        )
        self.assertEqual(db.session.scalar(db.select(RencanaIntervensi)), None)

    def test_dashboard_menampilkan_rencana_terlambat(self):
        """Memastikan tindak lanjut lewat tenggat ditandai di dashboard."""
        rencana = RencanaIntervensi(
            mahasiswa_id=self.mhs_awal.id,
            judul="Tindak lanjut presensi",
            deskripsi="Hubungi mahasiswa untuk menyusun perbaikan presensi.",
            penanggung_jawab="Dosen Wali",
            tenggat=date.today() - timedelta(days=1),
        )
        db.session.add(rencana)
        db.session.commit()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Tindak lanjut presensi", html)
        self.assertIn("Terlambat", html)

    # ==========================================================================
    # SKENARIO 9: Fitur Edit Mahasiswa (GET 200, POST 302, & POST 422)
    # ==========================================================================
    def test_get_edit_mahasiswa_sukses(self):
        """Memastikan rute GET /mahasiswa/<nim>/edit mengembalikan 200 dan form berisi data lama."""
        response = self.client.get(f"/mahasiswa/{self.mhs_awal.nim}/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn(self.mhs_awal.nim, html)
        self.assertIn(self.mhs_awal.nama, html)

    def test_post_edit_mahasiswa_valid_status_302(self):
        """Memastikan perubahan data mahasiswa berhasil disimpan dan redirect ke detail."""
        payload_edit = {
            "nama": "Ahmad Fauzi Updated",
            "prodi": "TI",
            "ipk": 2.20,  # Ubah menjadi nilai berisiko (< 2.50)
            "kehadiran": 70,  # Ubah menjadi nilai berisiko (< 75%)
            "email": "ahmad.baru@kampus.ac.id",
        }
        response = self.client.post(
            f"/mahasiswa/{self.mhs_awal.nim}/edit",
            data=payload_edit,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/mahasiswa/{self.mhs_awal.nim}", response.headers["Location"])

        # Verifikasi data terupdate di database
        db.session.refresh(self.mhs_awal)
        self.assertEqual(self.mhs_awal.nama, "Ahmad Fauzi Updated")
        self.assertEqual(self.mhs_awal.prodi, "TI")
        self.assertEqual(self.mhs_awal.ipk, 2.20)
        self.assertEqual(self.mhs_awal.kehadiran, 70)
        self.assertEqual(self.mhs_awal.email, "ahmad.baru@kampus.ac.id")
        self.assertTrue(self.mhs_awal.is_berisiko)

    def test_post_edit_mahasiswa_invalid_status_422(self):
        """Memastikan pengiriman data edit yang salah menghasilkan status 422."""
        payload_salah = {
            "nama": "",  # Wajib diisi
            "prodi": "INVALID",
            "ipk": 6.0,  # Di luar rentang
            "kehadiran": 200,
        }
        response = self.client.post(
            f"/mahasiswa/{self.mhs_awal.nim}/edit",
            data=payload_salah,
        )
        self.assertEqual(response.status_code, 422)
        html = response.get_data(as_text=True)
        self.assertIn("Nama lengkap wajib diisi.", html)

    # ==========================================================================
    # SKENARIO 10: Fitur Ekspor Data Mahasiswa ke CSV (/ekspor/mahasiswa)
    # ==========================================================================
    def test_ekspor_csv_mahasiswa(self):
        """Memastikan file CSV berhasil digenerate dengan header dan isi data mahasiswa."""
        # Tambah mahasiswa kedua berstatus berisiko
        mhs_berisiko = Mahasiswa(
            nim="A11.2023.00002",
            nama="Budi Santoso",
            prodi="TI",
            ipk=2.10,
            kehadiran=60,
            email="budi@kampus.ac.id",
        )
        db.session.add(mhs_berisiko)
        db.session.commit()

        # 1. Ekspor semua mahasiswa
        response = self.client.get("/ekspor/mahasiswa")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment; filename=", response.headers["Content-Disposition"])

        csv_text = response.get_data(as_text=True)
        self.assertIn("NIM,Nama Lengkap,Program Studi,IPK,Predikat,Kehadiran (%),Status EWS", csv_text)
        self.assertIn("Ahmad Fauzi", csv_text)
        self.assertIn("Budi Santoso", csv_text)

        # 2. Ekspor filter berisiko saja
        response_berisiko = self.client.get("/ekspor/mahasiswa?status=berisiko")
        self.assertEqual(response_berisiko.status_code, 200)
        csv_berisiko = response_berisiko.get_data(as_text=True)
        self.assertIn("Budi Santoso", csv_berisiko)
        self.assertNotIn("Ahmad Fauzi", csv_berisiko)  # Ahmad Fauzi IPK 3.75 & 92% presensi


if __name__ == "__main__":
    unittest.main(verbosity=2)
