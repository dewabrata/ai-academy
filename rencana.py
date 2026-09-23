"""Membaca rencana produksi dari docs/BLUEPRINT.md.

Dipakai academy.py (untuk memproduksi) dan pemeriksa.py (untuk memeriksa).
Sengaja tanpa dependensi SDK, supaya pemeriksa tetap bisa berjalan sendiri, dan
supaya keduanya membaca blueprint dengan cara yang persis sama.

Format yang dibaca ditetapkan prompts/blueprint.md:

    ## Pertemuan 1 — <judul>
    ### Point
    1. <judul point> — P1-1, P1-2
    ### Tugas
    Jenis: praktik | lab-kode | praktik+lab-kode
"""
import re
from pathlib import Path

JUDUL_PERTEMUAN = re.compile(r"^##\s*Pertemuan\s+(\d+)\s*[—\-–:]?\s*(.*)$", re.I | re.M)
# Hanya baris bernomor di kolom pertama: arah isi di bawah tiap point ditulis
# menjorok atau sebagai butir, jadi tidak ikut terbaca sebagai point.
BARIS_POINT = re.compile(r"^(\d+)[.)]\s+(.+?)\s*$")
CAPAIAN_EKOR = re.compile(r"\s+[—–-]+\s+((?:P\d+-\d+)(?:\s*[,;/]\s*P\d+-\d+)*)\s*$")


def subbagian(potong: str, judul: str) -> str:
    """Isi `### <judul>` di dalam satu bagian pertemuan."""
    m = re.search(rf"^###\s*{judul}\b.*$", potong, re.I | re.M)
    if not m:
        return ""
    sisa = potong[m.end():]
    akhir = re.search(r"^#{2,3}\s", sisa, re.M)
    return sisa[:akhir.start()] if akhir else sisa


def urai_point(teks: str) -> list[dict]:
    """Baris `1. <judul> — P1-1, P1-2` menjadi daftar point. Nomor point diambil
    dari urutan, bukan dari angka yang ditulis, supaya nomor yang melompat di
    blueprint tidak menghasilkan berkas point yang bolong."""
    hasil = []
    for baris in teks.splitlines():
        m = BARIS_POINT.match(baris)
        if not m:
            # Daftar point berakhir di baris teks pertama yang tidak menjorok
            # (mis. "**Arah isi tiap point:**"). Daftar bernomor sesudahnya
            # adalah uraian, bukan point — ditemukan di uji 22 Sep 2026.
            if hasil and baris.strip() and not baris[:1].isspace():
                break
            continue
        judul = re.sub(r"\*\*|__", "", m.group(2)).strip()
        capaian: list[str] = []
        c = CAPAIAN_EKOR.search(judul)
        if c:
            capaian = re.findall(r"P\d+-\d+", c.group(1))
            judul = judul[:c.start()].strip()
        hasil.append({"no": len(hasil) + 1, "judul": judul, "capaian": capaian})
    return hasil


def urai_jenis(teks: str) -> set[str]:
    m = re.search(r"^\W*Jenis\W*:\s*(.+)$", teks, re.I | re.M)
    nilai = (m.group(1) if m else "").lower()
    jenis = set()
    if "praktik" in nilai:
        jenis.add("praktik")
    if "lab" in nilai or "kode" in nilai:
        jenis.add("lab-kode")
    # Tanpa tanda yang terbaca: praktik. Lab kode yang tidak diminta lebih
    # merugikan (peserta non-IT disuruh menulis kode) daripada sebaliknya.
    return jenis or {"praktik"}


def daftar_pertemuan(ws: Path, laporkan=print) -> list[dict]:
    """Daftar pertemuan dari docs/BLUEPRINT.md: nomor, judul, point, jenis tugas.

    Blueprint adalah kontrak produksi, jadi daftar ini — bukan silabus dan bukan
    tebakan — yang menentukan apa yang diproduksi.
    """
    bp = ws / "docs" / "BLUEPRINT.md"
    if not bp.exists():
        return []
    isi = bp.read_text(encoding="utf-8")
    cocok = list(JUDUL_PERTEMUAN.finditer(isi))
    hasil, terlihat = [], set()
    for i, m in enumerate(cocok):
        no = int(m.group(1))
        if no in terlihat:
            # Nomor ganda akan menimpa folder yang sama; pertahankan yang pertama.
            if laporkan:
                laporkan(f">>> Blueprint memuat Pertemuan {no} lebih dari sekali — yang kedua dilewati.")
            continue
        terlihat.add(no)
        potong = isi[m.end():cocok[i + 1].start() if i + 1 < len(cocok) else len(isi)]
        hasil.append({"no": no, "judul": m.group(2).strip() or "(tanpa judul)",
                      "point": urai_point(subbagian(potong, "Point")),
                      "jenis": urai_jenis(subbagian(potong, "Tugas"))})
    return hasil
