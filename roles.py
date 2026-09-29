"""Definisi sepuluh peran "karyawan AI" produksi materi ajar.

Tiap peran dipakai sebagai system_prompt + model pada satu query() tersendiri,
jadi konteks tiap peran bersih dan biaya per tahap bisa dibatasi.

roles.py diimpor SEBELUM academy.py memanggil load_dotenv(), jadi .env dimuat
di sini juga. Tanpa ini setelan MODEL_* di .env akan diabaikan diam-diam.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROMPTS = Path(__file__).parent / "prompts"

# Urutan kekuatan model, dipakai untuk menaikkan model saat sebuah tahap gagal.
ESKALASI = ["haiku", "sonnet", "opus"]

# Bawaan proyek ini opus untuk semua peran. Mutu materi ajar dinilai dari isinya,
# dan kekeliruan satu peran perencanaan terbawa ke seluruh pertemuan.
BAWAAN = "opus"


def model_for(peran: str) -> str:
    """Model untuk satu peran, bisa ditimpa lewat .env (mis. MODEL_WRITER=sonnet)."""
    return os.getenv(f"MODEL_{peran}", BAWAAN).strip() or BAWAAN


def naik_model(model: str) -> str | None:
    """Model satu tingkat di atas, atau None kalau sudah yang tertinggi."""
    if model not in ESKALASI:
        return None
    i = ESKALASI.index(model)
    return ESKALASI[i + 1] if i + 1 < len(ESKALASI) else None


def load(name: str) -> str:
    """Muat prompt peran, dengan standar materi ditempelkan di belakangnya.

    Standar ditulis sekali di prompts/_standar.md, bukan disalin ke tiap peran —
    jadi mengubah aturan bahasa atau batas kepadatan slide cukup di satu tempat.
    """
    teks = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return teks + "\n" + (PROMPTS / "_standar.md").read_text(encoding="utf-8")


# Daftar tool di sini adalah SELURUH tool yang tersedia bagi peran: academy.py
# mengisinya ke opsi SDK `tools=` (bukan hanya `allowed_tools`, yang sekadar
# menyetujui otomatis dan tetap membiarkan tool lain dipakai).
# Tool untuk peran yang hanya menulis dokumen.
DOC_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
# Tool untuk peran yang memverifikasi atau meriset fakta produk.
WEB_TOOLS = DOC_TOOLS + ["WebSearch", "WebFetch"]
# Tool untuk peran yang harus mengeksekusi kode: Tugas dan Aplikasi.
CODE_TOOLS = DOC_TOOLS + ["Bash"]

# Perintah shell yang selalu ditolak, di semua peran. Berlaku juga untuk Lab
# peran Tugas — satu-satunya peran yang punya Bash.
DENY_BASH = [
    "Bash(rm -rf *)",
    "Bash(sudo *)",
    "Bash(curl * | sh)",
    "Bash(curl * | bash)",
    "Bash(wget * | sh)",
    "Bash(wget * | bash)",
    "Bash(git push *)",
    # Materi ajar tidak perlu memasang paket ke lingkungan global; kalau lab
    # butuh dependensi, blueprint yang menyebutnya dan pengajar yang memasangnya.
    "Bash(pip install -g *)",
    "Bash(npm install -g *)",
    "Bash(npm i -g *)",
]

# ---- Delapan peran ---------------------------------------------------------
# Perencanaan
KURIKULUM = dict(model=model_for("KURIKULUM"), system_prompt=load("kurikulum"), tools=DOC_TOOLS)
BLUEPRINT = dict(model=model_for("BLUEPRINT"), system_prompt=load("blueprint"), tools=DOC_TOOLS)

# Loop per point: Writer -> Reviewer + Fact-Checker (paralel) -> revisi
WRITER = dict(model=model_for("WRITER"), system_prompt=load("writer"), tools=WEB_TOOLS)
REVIEWER = dict(model=model_for("REVIEWER"), system_prompt=load("reviewer"), tools=DOC_TOOLS)
FAKTA = dict(model=model_for("FAKTA"), system_prompt=load("fakta"), tools=WEB_TOOLS)

# Paket pertemuan, dibangun dari point final — jalan paralel
SLIDE = dict(model=model_for("SLIDE"), system_prompt=load("slide"), tools=DOC_TOOLS)
# Satu-satunya peran dengan Bash: solusi lab kode wajib benar-benar dieksekusi.
TUGAS = dict(model=model_for("TUGAS"), system_prompt=load("tugas"), tools=CODE_TOOLS)

# Berkas kerja yang dibuka peserta: kode awal dan kode benar, atau berkas data.
# Dipisah dari Tugas karena pekerjaannya berbeda jenis — membangun sesuatu yang
# harus JALAN — dan karena kegagalannya tidak boleh ikut menjatuhkan soal,
# kunci, dan quiz yang sudah benar.
APLIKASI = dict(model=model_for("APLIKASI"), system_prompt=load("aplikasi"),
                tools=CODE_TOOLS)

# Menyusun rencana unggah Moodle: nama, kalimat instruksi tugas, pertanyaan
# feedback, dan bobot penilaian. Tidak menyentuh LMS — luarannya satu berkas
# JSON yang dieksekusi moodle_unggah.py.
MOODLE = dict(model=model_for("MOODLE"), system_prompt=load("moodle"),
              tools=DOC_TOOLS)

# Penyeragaman bahasa di akhir
EDITOR = dict(model=model_for("EDITOR"), system_prompt=load("editor"), tools=DOC_TOOLS)

SEMUA = {
    "KURIKULUM": KURIKULUM,
    "BLUEPRINT": BLUEPRINT,
    "WRITER": WRITER,
    "REVIEWER": REVIEWER,
    "FAKTA": FAKTA,
    "SLIDE": SLIDE,
    "TUGAS": TUGAS,
    "APLIKASI": APLIKASI,
    "MOODLE": MOODLE,
    "EDITOR": EDITOR,
}

# Berkas mana diperbaiki peran mana saat putaran revisi. Yang menulis sebuah
# berkas adalah yang paling tahu cara memperbaikinya, jadi tidak ada peran
# "tukang tambal" terpisah.
PEMILIK_BERKAS = {
    "SLIDE.md": "SLIDE",
    "LATIHAN.md": "TUGAS",
    "KUNCI.md": "TUGAS",
    "PRAKTIK.md": "TUGAS",
    "QUIZ_AIKEN.txt": "TUGAS",
}


def pemilik(path: str) -> str:
    """Peran yang bertanggung jawab atas satu berkas materi.

    Berkas yang tidak dikenali — termasuk point/*.md dan HANDBOOK.md, yang
    merupakan gabungan point — diserahkan ke WRITER: ia satu-satunya peran yang
    boleh menyentuh prosa mana pun, dan lebih baik satu butir perbaikan salah
    alamat daripada terlewat.
    """
    p = path.replace("\\", "/")
    if "/lab/" in p or p.endswith("/lab"):
        return "TUGAS"
    for nama, peran in PEMILIK_BERKAS.items():
        if p.endswith(nama):
            return peran
    return "WRITER"
