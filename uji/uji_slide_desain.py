"""Deck yang dihasilkan selalu bisa dibuka PowerPoint.

Dijalankan dari akar repo:  ./.venv/Scripts/python.exe uji/uji_slide_desain.py

Bentuk berukuran nol atau negatif membuat PowerPoint MENOLAK membuka berkasnya
sama sekali - sementara python-pptx menuliskannya tanpa keluhan dan validator
XML meloloskannya. Pernah terjadi: slide dengan 4 butir dan blok kode 9 baris
menyisakan ruang kartu 0,55 inci, dan kotak teks di dalam kartu jadi -0,168.
Uji ini memeriksa seluruh deck di workspace, bukan satu contoh.
"""
import glob
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from pptx import Presentation  # noqa: E402
from pptx.util import Emu      # noqa: E402

import exporter                # noqa: E402
import slide_desain            # noqa: E402

gagal = 0


def cek(nama, kondisi, info=""):
    global gagal
    print(("  ok   " if kondisi else "  GAGAL") + f" {nama}"
          + (f" - {info}" if info and not kondisi else ""))
    gagal += not kondisi


def bentuk_tidak_sah(path):
    """Bentuk berukuran <= 0, satu-satunya penyebab PowerPoint menolak berkas."""
    buruk = []
    p = Presentation(str(path))
    for i, s in enumerate(p.slides, 1):
        for sh in s.shapes:
            if sh.width is None or sh.height is None:
                continue
            if sh.width <= 0 or sh.height <= 0:
                buruk.append(f"slide {i}: {Emu(sh.width).inches:.3f}x"
                             f"{Emu(sh.height).inches:.3f}")
    return buruk


print("Kasus yang pernah menghasilkan bentuk negatif")
# 4 butir + blok kode panjang: ruang kartu tersisa di bawah tinggi minimum.
kode = ["baris kode yang cukup panjang supaya kartunya terdesak %d" % i
        for i in range(9)]
slides = [{
    "judul": "AC-3: dari Tautological ke Benar Diuji",
    "butir": ["Pola sama seperti AC-2 - sama-sama menuntut tidak dikirim",
              "Keluaran terminal identik: tetap 4 passed, 4 total",
              "Satu-satunya beda: baca isi assertion-nya sendiri",
              "Tautological test tak pernah jadi merah, apa pun yang terjadi"],
    "kode": [kode],
    "catatan": [],
}]
tmp = AKAR / "uji" / "_tmp_slide.pptx"
try:
    slide_desain.buat_deck("Deck uji", slides, tmp)
    buruk = bentuk_tidak_sah(tmp)
    cek("tidak ada bentuk berukuran <= 0", not buruk, buruk)

    print("\nSemua deck di workspace")
    sumber = sorted(glob.glob(str(AKAR / "workspace" / "*" / "materi" / "*" / "SLIDE.md")))
    if not sumber:
        print("  (tidak ada SLIDE.md di workspace - dilewati)")
    for md in sumber:
        s = Path(md)
        exporter.md_ke_pptx(s, tmp)
        buruk = bentuk_tidak_sah(tmp)
        label = f"{s.parts[-3]}/{s.parts[-2]}"
        cek(f"{label}", not buruk, buruk[:3])

    print("\nPagar ukuran")
    cek("MIN_UKURAN positif", slide_desain.MIN_UKURAN > 0)
    cek("_sah() menaikkan nilai negatif", slide_desain._sah(-5) >= slide_desain.MIN_UKURAN)
    cek("_sah() membiarkan nilai wajar", slide_desain._sah(2.5) == 2.5)
    # Ruang sempit harus jatuh ke daftar, bukan kartu yang digencet.
    cek("ruang sempit menolak kartu",
        not slide_desain._boleh_jadi_kartu(["a" * 40] * 4, 0.9))
    cek("ruang lega menerima kartu",
        slide_desain._boleh_jadi_kartu(["a" * 40] * 4, 3.0))
finally:
    tmp.unlink(missing_ok=True)

print("")
print("SEMUA LULUS" if not gagal else f"{gagal} GAGAL")
sys.exit(1 if gagal else 0)
