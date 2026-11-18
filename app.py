import os
import csv
import io
from datetime import date, timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    abort,
    flash,
    Response,
)
from models import db, Mahasiswa, Catatan, RencanaIntervensi
from forms import (
    MahasiswaForm,
    MahasiswaEditForm,
    CatatanForm,
    RencanaIntervensiForm,
    UbahStatusRencanaForm,
)

app = Flask(__name__)

# Konfigurasi Keamanan dan Database SQLite
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "si-peringatan-dini-rahasia-super-aman-2026"
)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///siews.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inisialisasi Database
db.init_app(app)

# Otomatis buat tabel skema yang belum ada di database saat aplikasi dijalankan
with app.app_context():
    db.create_all()


# ==============================================================================
# CUSTOM JINJA FILTERS
# ==============================================================================
@app.template_filter("predikat")
def filter_predikat(nilai_ipk) -> str:
    """Filter Jinja untuk mengonversi angka IPK menjadi predikat akademik."""
    try:
        ipk = float(nilai_ipk)
        if ipk >= 3.51:
            return "Dengan Pujian (Cumlaude)"
        elif ipk >= 3.00:
            return "Sangat Memuaskan"
        elif ipk >= 2.50:
            return "Memuaskan"
        elif ipk >= 2.00:
            return "Cukup"
        else:
            return "Kurang / Butuh Bimbingan"
    except (ValueError, TypeError):
        return "-"


@app.template_filter("persen")
def filter_persen(nilai) -> str:
    """Filter Jinja untuk memformat persentase kehadiran dengan 1 desimal."""
    try:
        val = float(nilai)
        if 0.0 <= val <= 1.0:
            val *= 100
        return f"{val:.1f}%"
    except (ValueError, TypeError):
        return "-"


# ==============================================================================
# ROUTING & CONTROLLERS (SQLAlchemy 2.x Query Style)
# ==============================================================================

# Rute 1: Rute Dasar (/) - Menampilkan total mahasiswa & mahasiswa berisiko
@app.route("/")
def index():
    # Hitung total mahasiswa menggunakan db.func.count
    total_mahasiswa = (
        db.session.scalar(db.select(db.func.count(Mahasiswa.id))) or 0
    )

    # Query mahasiswa berisiko: IPK < 2.50 ATAU Kehadiran < 75%
    stmt_berisiko = (
        db.select(Mahasiswa)
        .where(db.or_(Mahasiswa.ipk < 2.50, Mahasiswa.kehadiran < 75))
        .order_by(Mahasiswa.ipk.asc())
    )
    mahasiswa_berisiko = db.session.execute(stmt_berisiko).scalars().all()
    total_berisiko = len(mahasiswa_berisiko)

    stmt_rencana_aktif = (
        db.select(RencanaIntervensi)
        .where(RencanaIntervensi.status != "Selesai")
        .order_by(RencanaIntervensi.tenggat.asc())
        .limit(10)
    )
    rencana_aktif = db.session.execute(stmt_rencana_aktif).scalars().all()
    total_rencana_terlambat = db.session.scalar(
        db.select(db.func.count(RencanaIntervensi.id)).where(
            RencanaIntervensi.status != "Selesai",
            RencanaIntervensi.tenggat < date.today(),
        )
    ) or 0

    # Ambil daftar prodi unik dari database
    stmt_prodi = db.select(Mahasiswa.prodi).distinct().order_by(Mahasiswa.prodi)
    daftar_prodi = db.session.execute(stmt_prodi).scalars().all()

    return render_template(
        "index.html",
        total_mahasiswa=total_mahasiswa,
        total_berisiko=total_berisiko,
        mahasiswa_berisiko=mahasiswa_berisiko,
        daftar_prodi=daftar_prodi,
        rencana_aktif=rencana_aktif,
        total_rencana_terlambat=total_rencana_terlambat,
        batas_dekat=date.today() + timedelta(days=7),
    )


# Rute halaman anggota tim
@app.route("/tim")
def anggota_tim():
    return render_template("tim.html")


# Rute 2: Query String (/mahasiswa?prodi=...)
@app.route("/mahasiswa")
def daftar_mahasiswa():
    prodi_filter = request.args.get("prodi", "").strip()

    stmt = db.select(Mahasiswa)
    if prodi_filter:
        stmt = stmt.where(Mahasiswa.prodi.ilike(f"%{prodi_filter}%"))
    stmt = stmt.order_by(Mahasiswa.nim.asc())

    daftar = db.session.execute(stmt).scalars().all()

    stmt_prodi = db.select(Mahasiswa.prodi).distinct().order_by(Mahasiswa.prodi)
    daftar_prodi = db.session.execute(stmt_prodi).scalars().all()

    return render_template(
        "mahasiswa.html",
        daftar_mahasiswa=daftar,
        prodi_aktif=prodi_filter,
        daftar_prodi=daftar_prodi,
    )


# Rute 3: Tambah Mahasiswa Baru (/mahasiswa/tambah - GET & POST)
@app.route("/mahasiswa/tambah", methods=["GET", "POST"])
def tambah_mahasiswa():
    form = MahasiswaForm()

    if form.validate_on_submit():
        mahasiswa = Mahasiswa(
            nim=form.nim.data.strip(),
            nama=form.nama.data.strip(),
            prodi=form.prodi.data,
            ipk=form.ipk.data,
            kehadiran=form.kehadiran.data,
            email=form.email.data.strip() if form.email.data else None,
        )
        db.session.add(mahasiswa)
        db.session.commit()
        flash(
            f"Mahasiswa {mahasiswa.nama} ({mahasiswa.nim}) berhasil ditambahkan ke sistem!",
            "success",
        )
        return redirect(url_for("detail_mahasiswa", nim=mahasiswa.nim))

    # Jika pengiriman POST gagal validasi, kembalikan dengan status kode 422
    if request.method == "POST":
        return render_template("tambah.html", form=form), 422

    return render_template("tambah.html", form=form)


# Rute Edit Mahasiswa (/mahasiswa/<nim>/edit - GET & POST)
@app.route("/mahasiswa/<nim>/edit", methods=["GET", "POST"])
def edit_mahasiswa(nim):
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))
    if not mahasiswa:
        abort(404)

    form = MahasiswaEditForm(obj=mahasiswa)

    if form.validate_on_submit():
        mahasiswa.nama = form.nama.data.strip()
        mahasiswa.prodi = form.prodi.data
        mahasiswa.ipk = form.ipk.data
        mahasiswa.kehadiran = form.kehadiran.data
        mahasiswa.email = form.email.data.strip() if form.email.data else None

        db.session.commit()
        flash(
            f"Data mahasiswa {mahasiswa.nama} ({mahasiswa.nim}) berhasil diperbarui!",
            "success",
        )
        return redirect(url_for("detail_mahasiswa", nim=mahasiswa.nim))

    # Pastikan field NIM tetap terisi sesuai mahasiswa saat validasi gagal
    form.nim.data = mahasiswa.nim

    if request.method == "POST":
        return render_template("edit.html", form=form, mahasiswa=mahasiswa), 422

    return render_template("edit.html", form=form, mahasiswa=mahasiswa)


# Rute 4: Detail Mahasiswa & Tambah Catatan (/mahasiswa/<nim> - GET & POST)
@app.route("/mahasiswa/<nim>", methods=["GET", "POST"])
def detail_mahasiswa(nim):
    # Query mahasiswa berdasarkan NIM gaya SQLAlchemy 2.x
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        abort(404)

    form = CatatanForm()
    rencana_form = RencanaIntervensiForm()
    status_rencana_forms = {
        rencana.id: UbahStatusRencanaForm(data={"status": rencana.status})
        for rencana in mahasiswa.rencana_intervensi
    }

    # Penanganan penambahan catatan konseling
    if form.validate_on_submit():
        catatan = Catatan(
            mahasiswa_id=mahasiswa.id,
            jenis=form.jenis.data,
            isi=form.isi.data.strip(),
        )
        db.session.add(catatan)
        db.session.commit()
        flash("Catatan konseling baru berhasil disimpan!", "success")
        return redirect(url_for("detail_mahasiswa", nim=mahasiswa.nim))

    return render_template(
        "detail.html",
        mahasiswa=mahasiswa,
        form=form,
        rencana_form=rencana_form,
        status_rencana_forms=status_rencana_forms,
        is_berisiko=mahasiswa.is_berisiko,
    )


@app.route("/mahasiswa/<nim>/rencana", methods=["POST"])
def tambah_rencana_intervensi(nim):
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        abort(404)

    form = RencanaIntervensiForm()
    if form.validate_on_submit():
        rencana = RencanaIntervensi(
            mahasiswa_id=mahasiswa.id,
            judul=form.judul.data.strip(),
            deskripsi=form.deskripsi.data.strip(),
            penanggung_jawab=form.penanggung_jawab.data.strip(),
            tenggat=form.tenggat.data,
        )
        db.session.add(rencana)
        db.session.commit()
        flash("Rencana tindak lanjut berhasil ditambahkan.", "success")
        return redirect(url_for("detail_mahasiswa", nim=mahasiswa.nim))

    status_rencana_forms = {
        rencana.id: UbahStatusRencanaForm(data={"status": rencana.status})
        for rencana in mahasiswa.rencana_intervensi
    }
    return (
        render_template(
            "detail.html",
            mahasiswa=mahasiswa,
            form=CatatanForm(),
            rencana_form=form,
            status_rencana_forms=status_rencana_forms,
            is_berisiko=mahasiswa.is_berisiko,
        ),
        422,
    )


@app.route("/rencana/<int:rencana_id>/status", methods=["POST"])
def ubah_status_rencana(rencana_id):
    rencana = db.session.get(RencanaIntervensi, rencana_id)
    if not rencana:
        abort(404)

    form = UbahStatusRencanaForm()
    if form.validate_on_submit():
        rencana.status = form.status.data
        db.session.commit()
        flash("Status rencana tindak lanjut berhasil diperbarui.", "success")
    else:
        flash("Status rencana tidak valid dan tidak diperbarui.", "danger")

    return redirect(url_for("detail_mahasiswa", nim=rencana.mahasiswa.nim))


# Rute 5: Hapus Mahasiswa (/mahasiswa/<nim>/hapus - POST Only)
@app.route("/mahasiswa/<nim>/hapus", methods=["POST"])
def hapus_mahasiswa(nim):
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        abort(404)

    nama_mhs = mahasiswa.nama
    nim_mhs = mahasiswa.nim

    # Catatan terkait akan otomatis terhapus berkat cascade='all, delete-orphan'
    db.session.delete(mahasiswa)
    db.session.commit()
    flash(
        f"Data mahasiswa {nama_mhs} ({nim_mhs}) beserta catatan terkait telah berhasil dihapus.",
        "warning",
    )
    return redirect(url_for("daftar_mahasiswa"))


# Rute 6: Form Pencarian (/cari) dengan Pola PRG
@app.route("/cari", methods=["GET", "POST"])
def cari():
    if request.method == "POST":
        tipe_pencarian = request.form.get("tipe", "prodi")
        kata_kunci = request.form.get("keyword", "").strip()

        if tipe_pencarian == "nim" and kata_kunci:
            return redirect(url_for("detail_mahasiswa", nim=kata_kunci))
        else:
            return redirect(url_for("daftar_mahasiswa", prodi=kata_kunci))

    stmt_prodi = db.select(Mahasiswa.prodi).distinct().order_by(Mahasiswa.prodi)
    daftar_prodi = db.session.execute(stmt_prodi).scalars().all()
    return render_template("cari.html", daftar_prodi=daftar_prodi)


# Rute 7: Ekspor Data Mahasiswa ke CSV (/ekspor/mahasiswa - GET)
@app.route("/ekspor/mahasiswa")
def ekspor_mahasiswa():
    status_filter = request.args.get("status", "semua").lower()
    prodi_filter = request.args.get("prodi", "").strip()

    stmt = db.select(Mahasiswa)
    if status_filter == "berisiko":
        stmt = stmt.where(db.or_(Mahasiswa.ipk < 2.50, Mahasiswa.kehadiran < 75))
    elif status_filter == "aman":
        stmt = stmt.where(db.and_(Mahasiswa.ipk >= 2.50, Mahasiswa.kehadiran >= 75))

    if prodi_filter:
        stmt = stmt.where(Mahasiswa.prodi.ilike(f"%{prodi_filter}%"))

    stmt = stmt.order_by(Mahasiswa.nim.asc())
    daftar = db.session.execute(stmt).scalars().all()

    output = io.StringIO()
    # Menuliskan UTF-8 BOM agar Excel Windows membuka karakter dengan benar
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL)

    # Header CSV
    writer.writerow([
        "NIM",
        "Nama Lengkap",
        "Program Studi",
        "IPK",
        "Predikat",
        "Kehadiran (%)",
        "Status EWS",
        "Email",
        "Jumlah Catatan",
        "Jumlah Rencana Aktif",
    ])

    for m in daftar:
        status_ews = "BERISIKO" if m.is_berisiko else "AMAN"
        rencana_aktif = len([r for r in m.rencana_intervensi if r.status != "Selesai"])
        writer.writerow([
            m.nim,
            m.nama,
            m.prodi,
            f"{m.ipk:.2f}",
            filter_predikat(m.ipk),
            f"{m.kehadiran}%",
            status_ews,
            m.email or "-",
            len(m.catatan),
            rencana_aktif,
        ])

    csv_data = output.getvalue()
    output.close()

    nama_file = (
        "laporan_mahasiswa_berisiko.csv"
        if status_filter == "berisiko"
        else "laporan_mahasiswa_siews.csv"
    )

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nama_file}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


# Rute 8: Endpoint JSON (/api/mahasiswa/<nim>)
@app.route("/api/mahasiswa/<nim>")
def api_mahasiswa(nim):
    mahasiswa = db.session.scalar(db.select(Mahasiswa).filter_by(nim=nim))

    if not mahasiswa:
        return (
            jsonify(
                {
                    "status": "error",
                    "kode": 404,
                    "pesan": f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.",
                }
            ),
            404,
        )

    daftar_catatan = [
        {
            "id": c.id,
            "jenis": c.jenis,
            "isi": c.isi,
            "dibuat": c.dibuat.isoformat() if c.dibuat else None,
        }
        for c in mahasiswa.catatan
    ]

    return jsonify(
        {
            "status": "success",
            "kode": 200,
            "data": {
                "id": mahasiswa.id,
                "nim": mahasiswa.nim,
                "nama": mahasiswa.nama,
                "prodi": mahasiswa.prodi,
                "ipk": mahasiswa.ipk,
                "predikat": filter_predikat(mahasiswa.ipk),
                "kehadiran": filter_persen(mahasiswa.kehadiran),
                "email": mahasiswa.email,
                "is_berisiko": mahasiswa.is_berisiko,
                "total_catatan": len(daftar_catatan),
                "catatan": daftar_catatan,
            },
        }
    )


# ==============================================================================
# PENANGANAN ERROR 404
# ==============================================================================
@app.errorhandler(404)
def penanganan_404(error):
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "status": "error",
                    "kode": 404,
                    "pesan": "Endpoint atau data API tidak ditemukan.",
                }
            ),
            404,
        )
    return render_template("404.html", error=error), 404


# ==============================================================================
# CLI COMMAND: FLASK SEED
# ==============================================================================
@app.cli.command("seed")
def seed():
    """CLI Command untuk reset tabel dan mengisi 5 data dummy mahasiswa & catatan."""
    db.drop_all()
    db.create_all()

    data_dummy = [
        Mahasiswa(
            nim="A11.2023.00001",
            nama="Ahmad Fauzi",
            prodi="SI",
            ipk=3.75,
            kehadiran=92,
            email="ahmad.fauzi@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00002",
            nama="Budi Santoso",
            prodi="TI",
            ipk=2.35,
            kehadiran=68,
            email="budi.santoso@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00003",
            nama="Citra Lestari",
            prodi="SI",
            ipk=3.85,
            kehadiran=96,
            email="citra.lestari@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00004",
            nama="Dewi Anggraini",
            prodi="MI",
            ipk=2.10,
            kehadiran=55,
            email="dewi.anggraini@kampus.ac.id",
        ),
        Mahasiswa(
            nim="A11.2023.00005",
            nama="Eko Prasetyo",
            prodi="TI",
            ipk=3.15,
            kehadiran=81,
            email="eko.prasetyo@kampus.ac.id",
        ),
    ]

    db.session.add_all(data_dummy)
    db.session.flush()  # Dapatkan ID mahasiswa sebelum membuat catatan

    # Catatan konseling dummy untuk mendemonstrasikan relasi One-to-Many
    catatan_budi = Catatan(
        mahasiswa_id=data_dummy[1].id,
        jenis="Akademik",
        isi="Diberikan peringatan dini akademik terkait kehadiran 68% dan IPK 2.35. Dijadwalkan bimbingan intensif pekan depan.",
    )
    catatan_dewi = Catatan(
        mahasiswa_id=data_dummy[3].id,
        jenis="Pribadi",
        isi="Mahasiswa mengalami kendala transportasi sehingga sering terlambat kuliah. Direkomendasikan bantuan asrama.",
    )

    # Rencana intervensi dummy untuk mendemonstrasikan tabel tindak lanjut aktif
    rencana_budi = RencanaIntervensi(
        mahasiswa_id=data_dummy[1].id,
        judul="Konseling Presensi & Remedial Nilai",
        deskripsi="Pemberian bimbingan belajar tambahan dan pemantauan presensi mingguan.",
        penanggung_jawab="Dosen Pembimbing Akademik",
        tenggat=date.today() + timedelta(days=5),
        status="Berjalan",
    )
    rencana_dewi = RencanaIntervensi(
        mahasiswa_id=data_dummy[3].id,
        judul="Advokasi Pengajuan Fasilitas Asrama",
        deskripsi="Koordinasi dengan bagian kemahasiswaan untuk membantu kendala transportasi tempat tinggal.",
        penanggung_jawab="Tim Konseling Mahasiswa",
        tenggat=date.today() + timedelta(days=10),
        status="Belum dimulai",
    )

    db.session.add_all([catatan_budi, catatan_dewi, rencana_budi, rencana_dewi])
    db.session.commit()

    print("SUCCESS: Database SQLite berhasil di-reset dan diisi 5 data dummy mahasiswa!")


@app.cli.command("init-db")
def init_db():
    """Membuat tabel yang belum ada tanpa menghapus atau mengubah data."""
    db.create_all()
    print("SUCCESS: Tabel database yang belum ada berhasil dibuat.")


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    app.run(debug=True)
