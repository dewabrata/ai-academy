"""Intake silabus: baca dari berkas .md/.txt/.docx/.pdf atau teks langsung,
normalkan menjadi satu teks polos, lalu siapkan ruang kerja proyek.

Dipanggil academy.py sebelum tahap pertama. Kalau silabusnya tidak terbaca,
pipeline berhenti di sini — bukan setelah biaya satu tahap keluar.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
WS = ROOT / "workspace"

EKSTENSI = {".md", ".txt", ".docx", ".pdf"}


class SilabusError(Exception):
    """Silabus tidak bisa dipakai. Pipeline harus berhenti sebelum tahap pertama."""


# ---------------------------------------------------------------------------
# Pembaca per format
# ---------------------------------------------------------------------------
def _baca_teks(path: Path) -> str:
    """Markdown/teks dibaca apa adanya. cp1252 ditoleransi untuk berkas lama."""
    data = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _baca_docx(path: Path) -> str:
    """Paragraf DAN isi tabel, dalam urutan kemunculannya di dokumen.

    Silabus pelatihan hampir selalu berupa tabel (pertemuan | topik | durasi).
    Iterasi `document.paragraphs` saja akan melewatkan seluruh isinya — jadi di
    sini bodi dokumen ditelusuri pada level XML untuk menjaga urutan.
    """
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as e:
        raise SilabusError(
            "Membaca .docx butuh python-docx. Jalankan: pip install -r requirements.txt"
        ) from e

    doc = Document(str(path))
    keluaran: list[str] = []
    for anak in doc.element.body.iterchildren():
        tag = anak.tag.split("}")[-1]
        if tag == "p":
            teks = Paragraph(anak, doc).text.strip()
            if teks:
                keluaran.append(teks)
        elif tag == "tbl":
            for baris in Table(anak, doc).rows:
                sel = [s.text.strip().replace("\n", " ") for s in baris.cells]
                if any(sel):
                    keluaran.append(" | ".join(sel))
    return "\n".join(keluaran)


def _baca_pdf(path: Path) -> str:
    """Teks tiap halaman berurutan, dengan penanda halaman.

    Penanda dipertahankan karena silabus PDF sering menaruh satu pertemuan per
    halaman; tanpa itu batas antarpertemuan hilang setelah digabung.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise SilabusError(
            "Membaca .pdf butuh pdfplumber. Jalankan: pip install -r requirements.txt"
        ) from e

    keluaran: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, hal in enumerate(pdf.pages, 1):
            teks = (hal.extract_text() or "").strip()
            if teks:
                keluaran.append(f"--- Halaman {i} ---\n{teks}")
    return "\n\n".join(keluaran)


PEMBACA = {".md": _baca_teks, ".txt": _baca_teks, ".docx": _baca_docx, ".pdf": _baca_pdf}


# ---------------------------------------------------------------------------
# Normalisasi
# ---------------------------------------------------------------------------
def normalkan(teks: str) -> str:
    """Rapikan spasi tanpa membuang struktur baris.

    Baris kosong berlebih dipangkas jadi satu; indentasi dibiarkan karena daftar
    bertingkat di silabus memakainya sebagai struktur.
    """
    teks = teks.replace("\r\n", "\n").replace("\r", "\n")
    teks = "".join(c for c in teks if c == "\n" or c == "\t" or ord(c) >= 32)
    teks = re.sub(r"[ \t]+\n", "\n", teks)
    teks = re.sub(r"\n{3,}", "\n\n", teks)
    return teks.strip()


def baca(sumber: str) -> tuple[str, Path | None]:
    """Baca silabus dari path berkas atau dari teks langsung.

    Mengembalikan (teks ternormalisasi, path berkas asli atau None).
    """
    kandidat = Path(sumber)
    # Teks langsung bisa panjang dan memuat newline; Path() pada string seperti
    # itu melempar di Windows, jadi pemeriksaan berkas dibungkus.
    try:
        adalah_berkas = kandidat.is_file()
    except OSError:
        adalah_berkas = False

    if not adalah_berkas:
        if kandidat.suffix.lower() in EKSTENSI and "\n" not in sumber:
            # Terlihat seperti path berkas tapi tidak ada — ini salah tulis path,
            # bukan silabus yang diketik langsung. Lebih baik bilang begitu.
            raise SilabusError(f"Berkas silabus tidak ditemukan: {sumber}")
        teks = normalkan(sumber)
        if not teks:
            raise SilabusError("Teks silabus kosong.")
        return teks, None

    ext = kandidat.suffix.lower()
    if ext not in EKSTENSI:
        raise SilabusError(
            f"Format '{ext or 'tanpa ekstensi'}' tidak didukung. "
            f"Yang didukung: {', '.join(sorted(EKSTENSI))}."
        )
    try:
        mentah = PEMBACA[ext](kandidat)
    except SilabusError:
        raise
    except Exception as e:
        raise SilabusError(f"Gagal membaca {kandidat.name}: {e}") from e

    teks = normalkan(mentah)
    if not teks:
        raise SilabusError(
            f"{kandidat.name} terbaca tetapi tidak ada teks di dalamnya. "
            "Kalau ini PDF hasil pindai, teksnya berupa gambar — konversi dulu "
            "(OCR) atau salin silabusnya ke .md/.docx."
        )
    return teks, kandidat


# ---------------------------------------------------------------------------
# Ruang kerja proyek
# ---------------------------------------------------------------------------
def slugify(teks: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", teks.lower()).strip("-")[:48] or "proyek"


def judul_silabus(teks: str) -> str:
    """Tebak judul dari baris tak-kosong pertama, dipakai sebagai nama proyek."""
    for baris in teks.splitlines():
        b = baris.strip().lstrip("#").strip()
        # Lewati penanda halaman PDF dan baris tabel yang jelas bukan judul.
        if b and not b.startswith("---") and "|" not in b:
            return b[:80]
    return "silabus"


def siapkan(teks: str, asli: Path | None, project: str | None) -> tuple[Path, str]:
    """Buat/lanjutkan direktori proyek dan simpan jejak sumber silabus.

    Mengembalikan (path ruang kerja, nama proyek). Proyek yang sudah ada TIDAK
    ditimpa: dokumen yang sudah dihasilkan tetap di tempatnya supaya pipeline
    bisa dilanjutkan.
    """
    nama = project or slugify(judul_silabus(teks))
    ws = WS / nama
    for sub in ("docs", "materi", "sumber"):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    (ws / "sumber" / "silabus.txt").write_text(teks, encoding="utf-8")
    if asli:
        salinan = ws / "sumber" / asli.name
        # Kalau sumbernya sudah berkas di dalam ruang kerja, jangan salin ke diri sendiri.
        if salinan.resolve() != asli.resolve():
            shutil.copy2(asli, salinan)
    return ws, nama


def ringkas(teks: str, baris: int = 25) -> str:
    """Potongan awal silabus untuk ditampilkan di gate pertama.

    Ini yang membuat ekstraksi PDF/DOCX yang berantakan tertangkap sebelum biaya
    produksi keluar: Bos melihat teks yang benar-benar dibaca peran, bukan
    berkas aslinya.
    """
    isi = teks.splitlines()
    potong = "\n".join(isi[:baris])
    if len(isi) > baris:
        potong += f"\n... (+{len(isi) - baris} baris lagi)"
    return potong
