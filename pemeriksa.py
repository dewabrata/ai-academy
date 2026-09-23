"""Pemeriksa materi deterministik — "unit test" untuk materi ajar.

Tidak memanggil model sama sekali, jadi murah, cepat, dan hasilnya sama setiap
kali dijalankan. Justru karena itu ia berguna membandingkan dua versi prompt:
selisih skor berasal dari materinya, bukan dari suasana hati grader.

Yang diperiksa adalah hal-hal yang BISA dicek tanpa memahami isi: paket
pertemuan lengkap sesuai jenis tugas, semua point lolos loop telaah, tidak ada
penanda [CEK-FAKTA yang tersisa, tiap capaian disebut dan diuji, lembar latihan
tidak bocor jawaban, quiz AIKEN bisa diimpor Moodle, alokasi waktu blueprint
pas, slide sesuai format, solusi lab jalan. Mutu isi (akurasi, keterbacaan)
tetap tugas Reviewer.

    python pemeriksa.py workspace/<proyek>
    python pemeriksa.py --bandingkan workspace/uji-baseline workspace/uji-v2
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import exporter
import opsi as opsi_mod
import rencana

LULUS, GAGAL, TAK_BERLAKU = "lulus", "gagal", "tidak berlaku"

KODE = r"P{n}-\d+"
PENANDA_JAWABAN = re.compile(
    r"^\s*(?:[-*>]\s*)?(?:\*\*|__)?(jawaban|kunci(?: jawaban)?|pembahasan|solusi)"
    r"(?:\*\*|__)?\s*:", re.I | re.M)
AWAL_SOAL = re.compile(r"^(?:\s{0,3}(?:\*\*|__)?(\d+)[.)](?:\*\*|__)?\s+"
                       r"|#{2,4}\s*(?:soal|butir|latihan)\s*(\d+))",
                       re.I | re.M)
MENIT = re.compile(r"(\d+)\s*[–—-]\s*(\d+)")
BATAS_WAKTU_LAB = 60
JUMLAH_QUIZ = 10


def _baca(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _hasil(nama: str, status: str, bukti: str = "", berkas: str = "") -> dict:
    return {"nama": nama, "status": status, "bukti": bukti, "berkas": berkas}


# ---------------------------------------------------------------------------
# Membaca rencana
# ---------------------------------------------------------------------------
def capaian_pertemuan(kurikulum: str, no: int) -> list[str]:
    """Kode capaian satu pertemuan, dalam urutan kemunculan pertamanya."""
    return list(dict.fromkeys(re.findall(rf"\b{KODE.format(n=no)}\b", kurikulum)))


def durasi_pertemuan(kurikulum: str, no: int) -> int | None:
    """Durasi (menit) dari baris tabel peta pertemuan yang kolom pertamanya `no`."""
    for baris in kurikulum.splitlines():
        sel = [s.strip() for s in baris.strip().strip("|").split("|")]
        if len(sel) >= 3 and sel[0] == str(no):
            for s in sel[1:]:
                m = re.search(r"(\d+)\s*menit", s, re.I)
                if m:
                    return int(m.group(1))
    return None


def bagian_blueprint(blueprint: str, no: int) -> str:
    m = re.search(rf"^##\s*Pertemuan\s+{no}\b.*$", blueprint, re.I | re.M)
    if not m:
        return ""
    sisa = blueprint[m.end():]
    akhir = re.search(r"^##\s+(?!#)", sisa, re.M)
    return sisa[:akhir.start()] if akhir else sisa


def total_menit(bagian: str) -> int | None:
    """Jumlah menit dari baris tabel alur sesi (`| 0–15 | ... |`)."""
    total, ada = 0, False
    for baris in bagian.splitlines():
        if not baris.lstrip().startswith("|"):
            continue
        sel0 = baris.strip().strip("|").split("|")[0].strip()
        m = MENIT.fullmatch(sel0.replace(" ", "")) or MENIT.fullmatch(sel0)
        if m:
            total += int(m.group(2)) - int(m.group(1))
            ada = True
    return total if ada else None


# ---------------------------------------------------------------------------
# Pemeriksaan satu pertemuan
# ---------------------------------------------------------------------------
def _pecah_soal(latihan: str) -> list[tuple[str, str]]:
    cocok = list(AWAL_SOAL.finditer(latihan))
    # Soal memakai bentuk penanda terkuat di berkas: judul "### Soal N", lalu
    # nomor tebal "**N.**", lalu "N.". Daftar bernomor yang lebih lemah di
    # dalamnya adalah langkah soal, bukan soal tersendiri.
    for cocok_bentuk in (lambda m: m.group(2), lambda m: m.group(0).lstrip()[:2] in ("**", "__")):
        pilihan = [m for m in cocok if cocok_bentuk(m)]
        if pilihan:
            cocok = pilihan
            break
    posisi = [(m.start(), m.group(1) or m.group(2)) for m in cocok]
    out = []
    for i, (awal, no) in enumerate(posisi):
        akhir = posisi[i + 1][0] if i + 1 < len(posisi) else len(latihan)
        out.append((no, latihan[awal:akhir]))
    return out


def _titik_masuk(solusi: Path) -> list[Path]:
    """Skrip yang dijalankan. Tanpa titik masuk bernama, semua skrip di puncak
    `solusi/` dijalankan — prompt lama tidak mewajibkan main.py (design D6)."""
    for nama in ("main.py", "solusi.py", "app.py", "run.py"):
        if (solusi / nama).is_file():
            return [solusi / nama]
    return sorted(solusi.glob("*.py"))


def periksa_aiken(teks: str) -> list[str]:
    """Masalah format AIKEN (Moodle). Kosong = valid.

    Satu soal = teks soal satu baris, pilihan `A. ...` berurutan mulai A, lalu
    `ANSWER: <huruf>`; antarsoal dipisah baris kosong. Teks soal yang lebih dari
    satu baris muncul sebagai "pilihan tidak berformat" — Moodle juga
    menolaknya.
    """
    blok = [b for b in re.split(r"\n\s*\n", teks.strip()) if b.strip()]
    masalah = []
    if len(blok) != JUMLAH_QUIZ:
        masalah.append(f"{len(blok)} soal, harus {JUMLAH_QUIZ}")
    for i, b in enumerate(blok, 1):
        baris = [x.strip() for x in b.strip().splitlines() if x.strip()]
        if len(baris) < 4:
            masalah.append(f"soal {i}: kurang dari 2 pilihan atau tanpa ANSWER")
            continue
        soal, pilihan, jawab = baris[0], baris[1:-1], baris[-1]
        if re.match(r"^(\*\*|#|\d+[.)]\s)", soal):
            masalah.append(f"soal {i}: teks soal memuat Markdown atau nomor")
        m = re.fullmatch(r"ANSWER:\s*([A-Z])", jawab)
        if not m:
            masalah.append(f"soal {i}: baris terakhir bukan 'ANSWER: <huruf>'")
            continue
        huruf = []
        for x in pilihan:
            mm = re.fullmatch(r"([A-Z])[.)]\s+\S.*", x)
            if not mm:
                masalah.append(f"soal {i}: baris bukan pilihan 'A. ...': {x[:40]!r}")
                break
            huruf.append(mm.group(1))
        else:
            if huruf != [chr(65 + j) for j in range(len(huruf))]:
                masalah.append(f"soal {i}: pilihan tidak berurutan mulai A")
            elif m.group(1) not in huruf:
                masalah.append(f"soal {i}: ANSWER {m.group(1)} tidak ada di pilihan")
    return masalah


def _status_point(ws: Path) -> dict:
    try:
        return json.loads((ws / "docs" / "PRODUKSI.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def periksa_pertemuan(ws: Path, p: dict) -> list[dict]:
    no = p["no"]
    f = ws / "materi" / f"pertemuan-{no:02d}"
    rel = f.relative_to(ws).as_posix()
    kurikulum = _baca(ws / "docs" / "KURIKULUM.md")
    blueprint = _baca(ws / "docs" / "BLUEPRINT.md")
    handbook, latihan = _baca(f / "HANDBOOK.md"), _baca(f / "LATIHAN.md")
    kode = capaian_pertemuan(kurikulum, no)
    lab = "lab-kode" in p["jenis"]
    o = opsi_mod.baca(ws)
    h: list[dict] = []

    # 1. Paket lengkap sesuai jenis tugas
    wajib = ["HANDBOOK.md", "LATIHAN.md", "KUNCI.md", "QUIZ_AIKEN.txt"]
    if o["slide"]:
        wajib.insert(1, "SLIDE.md")
    if "praktik" in p["jenis"]:
        wajib.append("PRAKTIK.md")
    hilang = [n for n in wajib if not (f / n).is_file()]
    if lab:
        hilang += [n for n in ("lab/solusi/", "lab/README.md") if not (f / n.rstrip("/")).exists()]
    h.append(_hasil("paket lengkap", GAGAL if hilang else LULUS,
                    "hilang: " + ", ".join(hilang) if hilang else f"{len(wajib) + 2 * lab} luaran", rel))

    # 2. Semua point ada dan lolos loop
    st = _status_point(ws)
    tak_ada = [pt["no"] for pt in p["point"] if not (f / "point" / f"point-{pt['no']:02d}.md").is_file()]
    stat = [st.get(f"{no:02d}.{pt['no']:02d}", {}).get("status", "belum") for pt in p["point"]]
    belum_siap = [str(pt["no"]) for pt, s in zip(p["point"], stat) if s != "siap"]
    if tak_ada:
        h.append(_hasil("point siap", GAGAL, "berkas point tidak ada: " + ", ".join(map(str, tak_ada)),
                        f"{rel}/point"))
    else:
        h.append(_hasil("point siap", GAGAL if belum_siap else LULUS,
                        (f"belum siap/eskalasi: point {', '.join(belum_siap)}" if belum_siap
                         else f"{len(p['point'])} point"), f"{rel}/point"))

    # 3. Klaim produk terverifikasi: penanda tidak tersisa di materi final
    sisa = sum(_baca(x).count("[CEK-FAKTA") for x in (f / "point").glob("point-[0-9][0-9].md"))
    h.append(_hasil("klaim terverifikasi", GAGAL if sisa else LULUS,
                    f"{sisa} penanda [CEK-FAKTA tersisa" if sisa else "", f"{rel}/point"))

    # 4. Capaian disebut di handbook
    if not kode:
        h.append(_hasil("capaian tertutup di handbook", TAK_BERLAKU,
                        f"tidak ada kode P{no}-* di KURIKULUM.md"))
    elif not handbook:
        h.append(_hasil("capaian tertutup di handbook", GAGAL, "HANDBOOK.md tidak ada", f"{rel}/HANDBOOK.md"))
    else:
        luput = [k for k in kode if k not in handbook]
        h.append(_hasil("capaian tertutup di handbook", GAGAL if luput else LULUS,
                        "tidak disebut: " + ", ".join(luput) if luput else f"{len(kode)} capaian",
                        f"{rel}/HANDBOOK.md"))

    # 5 & 6. Soal bertanda capaian, capaian teruji
    if not latihan:
        h.append(_hasil("soal bertanda capaian", GAGAL, "LATIHAN.md tidak ada", f"{rel}/LATIHAN.md"))
        h.append(_hasil("capaian teruji", GAGAL, "LATIHAN.md tidak ada", f"{rel}/LATIHAN.md"))
    else:
        soal = _pecah_soal(latihan)
        pola = re.compile(rf"\b{KODE.format(n=no)}\b")
        if not soal:
            h.append(_hasil("soal bertanda capaian", GAGAL,
                            "tidak menemukan butir soal bernomor", f"{rel}/LATIHAN.md"))
        else:
            tanpa = [n for n, isi in soal if not pola.search(isi)]
            h.append(_hasil("soal bertanda capaian", GAGAL if tanpa else LULUS,
                            f"soal tanpa tanda: {', '.join(tanpa)}" if tanpa else f"{len(soal)} soal",
                            f"{rel}/LATIHAN.md"))
        if kode:
            belum = [k for k in kode if k not in latihan]
            h.append(_hasil("capaian teruji", GAGAL if belum else LULUS,
                            "tidak diuji: " + ", ".join(belum) if belum else "",
                            f"{rel}/LATIHAN.md"))
        else:
            h.append(_hasil("capaian teruji", TAK_BERLAKU, "tidak ada kode capaian"))

    # 7. Latihan bebas jawaban
    if latihan:
        m = PENANDA_JAWABAN.search(latihan)
        h.append(_hasil("latihan bebas jawaban", GAGAL if m else LULUS,
                        f"baris: {m.group(0).strip()[:60]!r}" if m else "", f"{rel}/LATIHAN.md"))

    # 8. Quiz AIKEN valid untuk Moodle
    quiz = f / "QUIZ_AIKEN.txt"
    if quiz.is_file():
        masalah = periksa_aiken(_baca(quiz))
        h.append(_hasil("quiz AIKEN valid", GAGAL if masalah else LULUS,
                        "; ".join(masalah[:4]) if masalah else f"{JUMLAH_QUIZ} soal",
                        f"{rel}/QUIZ_AIKEN.txt"))
    else:
        h.append(_hasil("quiz AIKEN valid", GAGAL, "QUIZ_AIKEN.txt tidak ada", f"{rel}/QUIZ_AIKEN.txt"))

    # 9. Alokasi waktu blueprint
    durasi = durasi_pertemuan(kurikulum, no)
    total = total_menit(bagian_blueprint(blueprint, no))
    if durasi is None or total is None:
        h.append(_hasil("alokasi waktu", TAK_BERLAKU,
                        f"durasi={durasi}, total segmen={total} (tidak terurai)"))
    else:
        h.append(_hasil("alokasi waktu", LULUS if total == durasi else GAGAL,
                        f"segmen {total} menit, durasi {durasi} menit", "docs/BLUEPRINT.md"))

    # 10. Format dan kepadatan slide
    slide = f / "SLIDE.md"
    if not o["slide"]:
        h.append(_hasil("slide sesuai batas", TAK_BERLAKU, "slide dimatikan untuk proyek ini"))
    elif slide.is_file():
        _, slides = exporter.parse_slides(_baca(slide))
        temuan = exporter.periksa_kepadatan(slides, slide) if slides else ["tidak ada slide '## '"]
        h.append(_hasil("slide sesuai batas", GAGAL if temuan else LULUS,
                        f"{len(temuan)} pelanggaran: " + "; ".join(temuan[:3]) if temuan
                        else f"{len(slides)} slide", f"{rel}/SLIDE.md"))

    # 11. Solusi lab jalan
    if not lab:
        h.append(_hasil("lab jalan", TAK_BERLAKU, "jenis tugas tanpa lab kode"))
    else:
        solusi = f / "lab" / "solusi"
        skrip = _titik_masuk(solusi) if solusi.is_dir() else []
        if not skrip:
            h.append(_hasil("lab jalan", GAGAL,
                            "lab/solusi/ tidak ada" if not solusi.is_dir()
                            else "tidak ada berkas .py di lab/solusi/", f"{rel}/lab/solusi"))
        else:
            h.append(_jalankan_lab(solusi, skrip, rel))
    return h


def _jalankan_lab(solusi: Path, skrip: list[Path], rel: str) -> dict:
    lulus, gagal = [], []
    for masuk in skrip:
        # Lab yang membaca input() diberi masukan contoh; tanpa itu EOFError
        # akan tercatat sebagai kegagalan padahal kodenya benar.
        masukan = "10\n20\n30\n\n" * 5 if "input(" in _baca(masuk) else ""
        try:
            r = subprocess.run([sys.executable, masuk.name], cwd=str(solusi), input=masukan,
                               capture_output=True, text=True, timeout=BATAS_WAKTU_LAB,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0:
                lulus.append(masuk.name + (" (masukan contoh)" if masukan else ""))
            else:
                ekor = (r.stderr or r.stdout).strip().splitlines()[-2:]
                gagal.append(f"{masuk.name} exit {r.returncode}: {' | '.join(ekor)[:120]}")
        except subprocess.TimeoutExpired:
            gagal.append(f"{masuk.name} melebihi {BATAS_WAKTU_LAB} detik")
    bukti = "; ".join(gagal) if gagal else ", ".join(lulus) + " exit 0"
    return _hasil("lab jalan", GAGAL if gagal else LULUS, bukti, f"{rel}/lab/solusi")


def skor(hasil: list[dict]) -> float | None:
    berlaku = [x for x in hasil if x["status"] != TAK_BERLAKU]
    if not berlaku:
        return None
    return round(100 * sum(x["status"] == LULUS for x in berlaku) / len(berlaku), 1)


# ---------------------------------------------------------------------------
# Satu proyek
# ---------------------------------------------------------------------------
def periksa_proyek(ws: Path) -> dict:
    pertemuan = rencana.daftar_pertemuan(ws, laporkan=None)
    hasil = {}
    for p in pertemuan:
        if (ws / "materi" / f"pertemuan-{p['no']:02d}").is_dir():
            h = periksa_pertemuan(ws, p)
            hasil[p["no"]] = {"judul": p["judul"], "skor": skor(h), "hasil": h}
    nilai = [v["skor"] for v in hasil.values() if v["skor"] is not None]
    return {"proyek": ws.name, "pertemuan_blueprint": len(pertemuan),
            "pertemuan_diperiksa": len(hasil),
            "skor_rata": round(sum(nilai) / len(nilai), 1) if nilai else None,
            "pertemuan": hasil}


def tulis_laporan(ws: Path, data: dict) -> Path:
    docs = ws / "docs"
    (docs / "pemeriksaan.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    baris = ["# Pemeriksaan otomatis", "",
             f"Skor rata-rata: **{data['skor_rata']}%** — "
             f"{data['pertemuan_diperiksa']} dari {data['pertemuan_blueprint']} pertemuan diperiksa.",
             "", "Pemeriksaan deterministik tanpa model. Mutu isi tetap dinilai Reviewer.", ""]
    for no, v in sorted(data["pertemuan"].items(), key=lambda x: int(x[0])):
        baris += [f"## Pertemuan {no} — {v['judul']} · skor {v['skor']}%", "",
                  "| Pemeriksaan | Status | Bukti |", "|---|---|---|"]
        for x in v["hasil"]:
            tanda = {"lulus": "✓", "gagal": "✗"}.get(x["status"], "–")
            baris.append(f"| {x['nama']} | {tanda} {x['status']} | {x['bukti'].replace('|', '/')} |")
        baris.append("")
    out = docs / "PEMERIKSAAN.md"
    out.write_text("\n".join(baris), encoding="utf-8")
    return out


def baca_hasil(ws: Path) -> dict:
    """Hasil pemeriksaan terakhir dari docs/pemeriksaan.json (kunci pertemuan str)."""
    try:
        return json.loads((ws / "docs" / "pemeriksaan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def bandingkan(a: dict, b: dict) -> str:
    baris = [f"{'':34s}{a['proyek'][:18]:>18s}{b['proyek'][:18]:>18s}",
             f"{'skor rata-rata':34s}{str(a['skor_rata']):>18s}{str(b['skor_rata']):>18s}"]
    nama = []
    for d in (a, b):
        for v in d["pertemuan"].values():
            for x in v["hasil"]:
                if x["nama"] not in nama:
                    nama.append(x["nama"])

    def lulus(d, n):
        s = [x["status"] for v in d["pertemuan"].values() for x in v["hasil"] if x["nama"] == n]
        s = [x for x in s if x != TAK_BERLAKU]
        return f"{sum(x == LULUS for x in s)}/{len(s)}" if s else "-"

    for n in nama:
        baris.append(f"{n:34s}{lulus(a, n):>18s}{lulus(b, n):>18s}")
    return "\n".join(baris)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--bandingkan":
        print(bandingkan(periksa_proyek(Path(args[1])), periksa_proyek(Path(args[2]))))
    elif len(args) == 1:
        ws = Path(args[0])
        data = periksa_proyek(ws)
        print(f"{tulis_laporan(ws, data)} — skor rata-rata {data['skor_rata']}%")
    else:
        print(__doc__)
        sys.exit(2)
