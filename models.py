from datetime import date, datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func

# ==============================================================================
# INISIALISASI FLASK-SQLALCHEMY
# ==============================================================================
db = SQLAlchemy()


# ==============================================================================
# MODEL MAHASISWA (SQLAlchemy 2.x Declarative Mapping)
# ==============================================================================
class Mahasiswa(db.Model):
    """Model data Mahasiswa dengan standar SQLAlchemy 2.x Mapped & mapped_column."""

    __tablename__ = "mahasiswa"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    nim: Mapped[str] = mapped_column(db.String(14), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(db.String(100), nullable=False)
    prodi: Mapped[str] = mapped_column(db.String(100), nullable=False)
    ipk: Mapped[float] = mapped_column(db.Float, nullable=False)
    kehadiran: Mapped[int] = mapped_column(db.Integer, nullable=False)
    email: Mapped[str | None] = mapped_column(db.String(120), nullable=True)

    # Relasi One-to-Many ke Model Catatan:
    # - back_populates="mahasiswa": akses dua arah (mahasiswa.catatan <-> catatan.mahasiswa)
    # - cascade="all, delete-orphan": catatan otomatis terhapus jika mahasiswa pemilik dihapus
    catatan: Mapped[list["Catatan"]] = db.relationship(
        "Catatan",
        back_populates="mahasiswa",
        cascade="all, delete-orphan",
    )
    rencana_intervensi: Mapped[list["RencanaIntervensi"]] = db.relationship(
        "RencanaIntervensi",
        back_populates="mahasiswa",
        cascade="all, delete-orphan",
    )

    @property
    def is_berisiko(self) -> bool:
        """Indikator Early Warning System (IPK < 2.50 atau Kehadiran < 75%)."""
        return self.ipk < 2.50 or self.kehadiran < 75

    def __repr__(self) -> str:
        return f"<Mahasiswa nim='{self.nim}' nama='{self.nama}'>"


# ==============================================================================
# MODEL CATATAN (SQLAlchemy 2.x Declarative Mapping)
# ==============================================================================
class Catatan(db.Model):
    """Model Catatan perkembangan / konseling akademik mahasiswa."""

    __tablename__ = "catatan"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)

    # Foreign Key mengacu ke kolom 'id' di tabel 'mahasiswa'
    mahasiswa_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("mahasiswa.id"),
        nullable=False,
    )

    jenis: Mapped[str] = mapped_column(db.String(50), nullable=False)
    isi: Mapped[str] = mapped_column(db.Text, nullable=False)

    # Nilai default saat ini (Python-side timezone-aware UTC & DB-side func.now())
    dibuat: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relasi Many-to-One kembali ke Model Mahasiswa
    mahasiswa: Mapped["Mahasiswa"] = db.relationship(
        "Mahasiswa",
        back_populates="catatan",
    )

    def __repr__(self) -> str:
        return f"<Catatan id={self.id} jenis='{self.jenis}' mahasiswa_id={self.mahasiswa_id}>"


class RencanaIntervensi(db.Model):
    """Model rencana tindakan dan tindak lanjut untuk mahasiswa."""

    __tablename__ = "rencana_intervensi"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    mahasiswa_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("mahasiswa.id"),
        nullable=False,
    )
    judul: Mapped[str] = mapped_column(db.String(120), nullable=False)
    deskripsi: Mapped[str] = mapped_column(db.Text, nullable=False)
    penanggung_jawab: Mapped[str] = mapped_column(db.String(100), nullable=False)
    tenggat: Mapped[date] = mapped_column(db.Date, nullable=False)
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default="Belum dimulai",
    )
    dibuat: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    mahasiswa: Mapped["Mahasiswa"] = db.relationship(
        "Mahasiswa",
        back_populates="rencana_intervensi",
    )

    @property
    def is_terlambat(self) -> bool:
        return self.status != "Selesai" and self.tenggat < date.today()

    def __repr__(self) -> str:
        return f"<RencanaIntervensi id={self.id} judul='{self.judul}' status='{self.status}'>"
