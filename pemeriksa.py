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
import csv
import json
import re
import shutil
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
BARIS_POINT_BP = re.compile(r"^(\d+)[.)]\s+\S")
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
# Butir "Di kelas" di blueprint: jatah menit + langkah yang dikerjakan di jam
# kelas. Hanya ini yang terikat waktu — panjang handbook tidak, karena handbook
# adalah bahan bacaan mandiri.
DI_KELAS = re.compile(r"^\s*[-*]\s*Di kelas\s*\((\d+)\s*menit\)\s*:?(.*)$", re.I)
MENIT_PER_LANGKAH = 2          # patokan kasar: ketik, tunggu keluaran, periksa


# ---------------------------------------------------------------------------
# Bentuk tulisan point
# ---------------------------------------------------------------------------
# Kontrak keterbacaan di prompts/writer.md. Diperiksa mesin karena keempatnya
# mekanis: tidak butuh penilaian, dan memperbaikinya tidak menghasilkan kalimat
# baru yang perlu ditelaah ulang.
#
# Ambangnya lebih longgar daripada target di prompt (60 kata) supaya yang
# ditahan hanya yang tidak bisa diperdebatkan. Pada materi pertemuan 1-3 yang
# ditulis sebelum kontrak ini ada, 90 kata menangkap 15% paragraf.
MAKS_KATA_PARAGRAF = 90

_AWAL_BUKAN_PARAGRAF = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\||\s{4,}\S)")
_RUJUK_BAGIAN_LAIN = re.compile(
    r"(?:di|pada|ke) pertemuan \d"
    r"|(?:di|pada) point \d"
    r"|dibahas (?:di|pada|lebih|nanti)"
    r"|dipelajari (?:di|pada|penuh|nanti)"
    r"|akan (?:kita )?(?:lihat|bahas|pelajari) (?:di|pada|nanti)"
    r"|bagian (?:berikutnya|sebelumnya)"
    r"|point (?:berikutnya|sebelumnya)", re.I)
# "**Hasil yang sebenarnya terjadi:** container pertama hidup..." - label tebal
# panjang di awal paragraf yang sebenarnya menggantikan judul.
_LABEL_TEBAL = re.compile(r"^\*\*([^*]{12,}?)\*\*\s*\S")
# "reverse proxy (reverse proxy - komponen yang...)"
_ISTILAH_ULANG = re.compile(r"\b([A-Za-z][\w-]*(?: [\w-]+){0,2}) \(\1\b", re.I)


def _paragraf(teks: str):
    """Paragraf teks biasa di luar blok kode, judul, daftar, tabel, dan kutipan."""
    dalam_kode = False
    kini: list[str] = []
    for baris in teks.splitlines():
        if baris.lstrip().startswith("```"):
            dalam_kode = not dalam_kode
            if kini:
                yield " ".join(kini)
                kini = []
            continue
        if dalam_kode:
            continue
        if not baris.strip() or _AWAL_BUKAN_PARAGRAF.match(baris):
            if kini:
                yield " ".join(kini)
                kini = []
            continue
        kini.append(baris.strip())
    if kini:
        yield " ".join(kini)


def bentuk_point(teks: str, kelas_ada: bool | None = None) -> list[str]:
    """Pelanggaran kontrak keterbacaan di satu point, satu baris per jenis.

    Daftar kosong berarti bentuknya sudah sesuai. Contoh disertakan supaya
    Writer bisa langsung mencari tempatnya, bukan menebak.
    """
    langgar: list[str] = []

    tanpa_bahasa = 0
    dalam = False
    for baris in teks.splitlines():
        if baris.lstrip().startswith("```"):
            if not dalam and not baris.strip().strip("`").strip():
                tanpa_bahasa += 1
            dalam = not dalam
    if tanpa_bahasa:
        langgar.append(f"{tanpa_bahasa} blok kode tanpa penanda bahasa — "
                       "beri bahasanya (bash/yaml/json/...), atau `text` untuk "
                       "keluaran perintah dan teks biasa")

    panjang = [par for par in _paragraf(teks) if len(par.split()) > MAKS_KATA_PARAGRAF]
    if panjang:
        langgar.append(f"{len(panjang)} paragraf melebihi {MAKS_KATA_PARAGRAF} kata — "
                       "pecah jadi satu gagasan per paragraf. Mulai dari: "
                       f'"{panjang[0][:80]}..."')

    rujuk = list(dict.fromkeys(m.group(0) for m in _RUJUK_BAGIAN_LAIN.finditer(teks)))
    if rujuk:
        langgar.append(f"{len(rujuk)} rujukan ke bagian lain — hapus, dan beri "
                       "definisi satu kalimat kalau istilahnya memang dibutuhkan "
                       "di sini: " + ", ".join(f'"{x}"' for x in rujuk[:5]))

    label = [par for par in _paragraf(teks) if _LABEL_TEBAL.match(par)]
    if label:
        contoh = _LABEL_TEBAL.match(label[0]).group(1)
        langgar.append(f"{len(label)} label tebal di awal paragraf — ganti judul "
                       f'`####` yang pendek. Mulai dari: "{contoh[:60]}"')

    ulang = _ISTILAH_ULANG.findall(teks)
    if ulang:
        langgar.append(f"{len(ulang)} definisi mengulang nama istilahnya sendiri — "
                       "tulis sebagai baris `> **Istilah** — arti` di bawah "
                       f'paragrafnya: "{ulang[0]}"')

    if kelas_ada is False:
        langgar.append("berkas .kelas.md belum ada — pindahkan jatah menit dan "
                       "pembagian kelas ke sana, keluarkan dari teks point")

    return langgar


def bentuk_berkas_point(point: Path) -> list[str]:
    """`bentuk_point` untuk satu berkas, sekalian memeriksa pasangan .kelas.md."""
    if not point.exists():
        return []
    kelas = point.with_suffix(".kelas.md")
    return bentuk_point(point.read_text(encoding="utf-8"), kelas.exists())



def in_class_point(bagian: str) -> list[dict]:
    """Daftar {point, menit, langkah} dari bagian '### Point' satu pertemuan."""
    hasil: list[dict] = []
    for baris in bagian.splitlines():
        m = BARIS_POINT_BP.match(baris)
        if m:
            hasil.append({"no": len(hasil) + 1, "menit": None, "langkah": 0})
            continue
        m = DI_KELAS.match(baris)
        if m and hasil:
            hasil[-1]["menit"] = int(m.group(1))
            hasil[-1]["langkah"] = len(re.findall(r"\(\d+\)", m.group(2)))
    return hasil


# Berkas yang ISINYA ditampilkan: nama berkas di antara backtick pada baris
# tepat sebelum blok kode. Hanya bentuk inilah yang dijanjikan kepada peserta
# sebagai berkas yang bisa dibuka; penyebutan biasa di tengah kalimat tidak.
_NAMA_BERKAS = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:js|mjs|cjs|ts|py|json|ya?ml|csv|sh|sql|md|txt|html|css))`")


def berkas_ditampilkan(teks: str) -> list[str]:
    """Nama berkas yang diikuti blok kode di baris berikutnya."""
    baris = teks.splitlines()
    hasil: list[str] = []
    for i, b in enumerate(baris):
        if not b.lstrip().startswith("```"):
            continue
        # Lihat ke atas, lewati baris kosong, sampai baris teks terdekat.
        j = i - 1
        while j >= 0 and not baris[j].strip():
            j -= 1
        if j < 0:
            continue
        nama = _NAMA_BERKAS.findall(baris[j])
        # Satu nama saja yang dianggap judul blok. Baris dengan beberapa nama
        # berkas adalah kalimat biasa, bukan penanda isi berkas.
        if len(nama) == 1 and len(baris[j].strip()) < 120:
            hasil.append(nama[0])
    return list(dict.fromkeys(hasil))


# Pemeriksaan sintaks berkas yang diserahkan ke peserta. Menjalankannya penuh
# butuh `npm install` — jaringan dan waktu — sementara sintaks bisa diperiksa
# tanpa keduanya, deterministik, dan sudah menangkap kerusakan yang nyata.
LEWATI_FOLDER = {"node_modules", ".git", "__pycache__", "dist", "venv", ".venv"}


def _sintaks_js(f: Path) -> str:
    cmd = PENERJEMAH.get(".js", [])
    if not _ada_penerjemah(cmd):
        return ""                       # node tidak terpasang: bukan cacat materi
    r = subprocess.run(cmd + ["--check", str(f)], capture_output=True, text=True,
                       timeout=30, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        return ""
    galat = (r.stderr or r.stdout).strip().splitlines()
    return next((b.strip() for b in galat if "Error" in b), galat[0] if galat else "gagal")


def periksa_sintaks(akar: Path) -> list[str]:
    """Berkas dengan sintaks rusak di bawah `akar`, satu baris per berkas."""
    rusak: list[str] = []
    if not akar.is_dir():
        return rusak
    for f in sorted(akar.rglob("*")):
        if not f.is_file() or LEWATI_FOLDER & set(f.parts):
            continue
        ext = f.suffix.lower()
        rel = f.relative_to(akar).as_posix()
        try:
            if ext in (".js", ".mjs", ".cjs"):
                pesan = _sintaks_js(f)
                if pesan:
                    rusak.append(f"{rel}: {pesan[:90]}")
            elif ext == ".py":
                # compile() memeriksa sintaks tanpa menulis berkas .pyc.
                compile(f.read_text(encoding="utf-8"), str(f), "exec")
            elif ext == ".json":
                json.loads(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            rusak.append(f"{rel}: baris {e.lineno} — {e.msg}")
        except ValueError as e:                       # JSON rusak
            rusak.append(f"{rel}: {e}")
        except (OSError, subprocess.SubprocessError) as e:
            rusak.append(f"{rel}: tidak terbaca ({e})")
    return rusak


def _kolom_csv_tidak_sama(csv_path: Path) -> str:
    """Keterangan singkat kalau jumlah kolom CSV tidak seragam, atau '' kalau rapi."""
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            contoh = fh.read(4096)
            fh.seek(0)
            try:
                dialek = csv.Sniffer().sniff(contoh, delimiters=",;\t|")
            except csv.Error:
                dialek = csv.excel
            baris = [b for b in csv.reader(fh, dialek) if any(x.strip() for x in b)]
    except (OSError, csv.Error) as e:
        return f"tidak terbaca ({e})"
    if not baris:
        return "kosong"
    lebar = len(baris[0])
    beda = [i for i, b in enumerate(baris[1:], 2) if len(b) != lebar]
    if beda:
        return (f"judul {lebar} kolom, tetapi baris "
                f"{', '.join(map(str, beda[:3]))} berbeda")
    return ""


def berkas_diserahkan(f: Path) -> set[str]:
    """Nama berkas yang benar-benar ada di bahan/ dan lab/ pertemuan ini."""
    out: set[str] = set()
    for sub in ("bahan", "lab"):
        akar = f / sub
        if not akar.is_dir():
            continue
        for x in akar.rglob("*"):
            if x.is_file():
                out.add(x.name)
                out.add(x.relative_to(akar).as_posix())
    return out


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


# Bahasa lab ditentukan silabus, bukan oleh pemeriksa. Sebelumnya pemeriksa
# hanya mengenal .py, sehingga lab Node.js yang benar dilaporkan GAGAL dengan
# alasan "tidak ada berkas .py" — cacat pemeriksanya, bukan cacat materinya.
PENERJEMAH: dict[str, list[str]] = {
    ".py": [sys.executable],
    ".js": ["node"],
    ".mjs": ["node"],
    ".cjs": ["node"],
}
NAMA_MASUK = ("main", "solusi", "app", "run", "index")


def _ada_penerjemah(cmd: list[str]) -> bool:
    return bool(cmd) and (Path(cmd[0]).exists() or shutil.which(cmd[0]) is not None)


def _titik_masuk(solusi: Path) -> list[Path]:
    """Skrip yang dijalankan. Tanpa titik masuk bernama, semua skrip di puncak
    `solusi/` dijalankan — prompt lama tidak mewajibkan main.py (design D6)."""
    kandidat = sorted(p for p in solusi.glob("*.*")
                      if p.is_file() and p.suffix.lower() in PENERJEMAH)
    # Penguji didahulukan. Solusi lab bisa memuat berkas yang memang tidak
    # berdiri sendiri — hook yang menunggu payload JSON di stdin, modul yang
    # hanya diimpor. Menjalankannya langsung pasti gagal dan tidak membuktikan
    # apa pun; yang membuktikan solusinya benar adalah pengujinya.
    penguji = [p for p in kandidat if p.stem.lower().startswith(("uji", "test"))]
    if penguji:
        return penguji
    for nama in NAMA_MASUK:
        pilih = [p for p in kandidat if p.stem.lower() == nama]
        if pilih:
            return pilih
    return kandidat


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

    # 8b. Bentuk tulisan tiap point terhadap kontrak keterbacaan.
    # Pelanggaran di sini seharusnya sudah dibereskan sebelum Reviewer dipanggil;
    # kalau masih muncul di paket, artinya perbaikan otomatisnya tidak berhasil.
    berkas_pt = sorted((f / "point").glob("point-[0-9][0-9].md"))
    if not berkas_pt:
        h.append(_hasil("bentuk tulisan", TAK_BERLAKU, "tidak ada berkas point"))
    else:
        rinci = [f"{bp.name}: {x}" for bp in berkas_pt
                 for x in bentuk_berkas_point(bp)]
        titik = len({x.split(":")[0] for x in rinci})
        h.append(_hasil("bentuk tulisan", GAGAL if rinci else LULUS,
                        (f"{len(rinci)} pelanggaran di {titik} point — "
                         + "; ".join(x[:110] for x in rinci[:3])) if rinci else "",
                        f"{rel}/point"))

    # 8c. Berkas kerja peserta sesuai deklarasi blueprint
    bahan = f / "bahan"
    diminta = (p.get("bahan") or "").strip()
    if not diminta:
        h.append(_hasil("bahan kerja", TAK_BERLAKU,
                        "blueprint tidak meminta berkas kerja untuk pertemuan ini"))
    else:
        kurang = []
        for nama in ("README.md", "awal", "jadi"):
            jalur = bahan / nama
            if not jalur.exists():
                kurang.append(f"bahan/{nama}")
            elif jalur.is_dir() and not any(x.is_file() for x in jalur.rglob("*")):
                kurang.append(f"bahan/{nama}/ kosong")
        # CSV yang jumlah kolomnya tidak sama menghasilkan spreadsheet yang
        # kolomnya melenceng, dan peserta menyalahkan dirinya sendiri.
        for csv_path in sorted(bahan.rglob("*.csv")):
            rusak = _kolom_csv_tidak_sama(csv_path)
            if rusak:
                kurang.append(f"{csv_path.name}: {rusak}")
        h.append(_hasil("bahan kerja", GAGAL if kurang else LULUS,
                        ("hilang: " + ", ".join(kurang)) if kurang
                        else f"{sum(1 for x in bahan.rglob('*') if x.is_file())} berkas",
                        f"{rel}/bahan"))

    # 8c-2. Sintaks berkas yang diserahkan ke peserta. bahan/awal dan lab/awal
    # dijanjikan bisa dijalankan walau TODO belum dikerjakan, dan bahan/jadi
    # dijanjikan sudah benar — tetapi sampai sekarang tidak ada yang memeriksanya.
    sumber = [x for x in (bahan, f / "lab" / "awal") if x.is_dir()]
    if not sumber:
        h.append(_hasil("sintaks berkas peserta", TAK_BERLAKU,
                        "tidak ada bahan/ maupun lab/awal/"))
    else:
        rusak = [x for akar in sumber for x in periksa_sintaks(akar)]
        jumlah = sum(1 for akar in sumber for x in akar.rglob("*")
                     if x.is_file() and not (LEWATI_FOLDER & set(x.parts))
                     and x.suffix.lower() in (".js", ".mjs", ".cjs", ".py", ".json"))
        h.append(_hasil("sintaks berkas peserta", GAGAL if rusak else LULUS,
                        ("; ".join(rusak[:3]) if rusak else f"{jumlah} berkas kode diperiksa"),
                        f"{rel}/bahan"))

    # 8d. Berkas yang ditampilkan isinya harus benar-benar diserahkan.
    # Tanpa ini materi bisa menceritakan aplikasi yang tidak pernah ada, dan
    # peserta membaca kode yang tidak bisa mereka buka.
    ada = berkas_diserahkan(f)
    disebut: dict[str, list[str]] = {}
    for bp in sorted((f / "point").glob("point-[0-9][0-9].md")):
        for nama in berkas_ditampilkan(_baca(bp)):
            if nama not in ada and Path(nama).name not in ada:
                disebut.setdefault(nama, []).append(bp.name)
    if not (f / "point").is_dir():
        h.append(_hasil("berkas dirujuk ada", TAK_BERLAKU, "tidak ada berkas point"))
    else:
        h.append(_hasil("berkas dirujuk ada", GAGAL if disebut else LULUS,
                        (f"{len(disebut)} berkas ditampilkan isinya tetapi tidak "
                         f"diserahkan: " + ", ".join(list(disebut)[:5])) if disebut else "",
                        f"{rel}/point"))

    # 9. Alokasi menit per point vs langkah yang dikerjakan di kelas
    bagian = bagian_blueprint(blueprint, no)
    daftar = in_class_point(rencana.subbagian(bagian, "Point")) if bagian else []
    if not daftar:
        h.append(_hasil("menit per point", TAK_BERLAKU,
                        "blueprint tidak memuat daftar point yang terurai"))
    else:
        tanpa = [str(x["no"]) for x in daftar if x["menit"] is None]
        padat = [f"point {x['no']}: {x['langkah']} langkah / {x['menit']} menit"
                 for x in daftar if x["menit"] is not None
                 and x["langkah"] > max(1, x["menit"] // MENIT_PER_LANGKAH)]
        if tanpa:
            h.append(_hasil("menit per point", GAGAL,
                            "tanpa butir 'Di kelas (N menit)': point " + ", ".join(tanpa),
                            "docs/BLUEPRINT.md"))
        else:
            h.append(_hasil("menit per point", GAGAL if padat else LULUS,
                            "; ".join(padat[:3]) if padat
                            else f"{len(daftar)} point, langkah in-class sepadan",
                            "docs/BLUEPRINT.md"))

    # 10. Alokasi waktu blueprint
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
        isi = [p for p in solusi.rglob("*") if p.is_file()] if solusi.is_dir() else []
        if skrip:
            h.append(_jalankan_lab(solusi, skrip, rel))
        elif not solusi.is_dir() or not isi:
            h.append(_hasil("lab jalan", GAGAL,
                            "lab/solusi/ tidak ada" if not solusi.is_dir()
                            else "lab/solusi/ kosong", f"{rel}/lab/solusi"))
        else:
            # Ada solusinya, hanya bahasanya di luar yang bisa dijalankan
            # pemeriksa. Itu keterbatasan alat, bukan materi yang cacat.
            jenis = sorted({p.suffix for p in isi if p.suffix}) or ["tanpa ekstensi"]
            h.append(_hasil("lab jalan", TAK_BERLAKU,
                            f"berkas {', '.join(jenis)} — pemeriksa hanya menjalankan "
                            f"{', '.join(sorted(PENERJEMAH))}", f"{rel}/lab/solusi"))
    return h


def _jalankan_lab(solusi: Path, skrip: list[Path], rel: str) -> dict:
    lulus, gagal, dilewati = [], [], []
    for masuk in skrip:
        cmd = PENERJEMAH.get(masuk.suffix.lower(), [])
        if not _ada_penerjemah(cmd):
            # Penerjemah tidak terpasang di mesin ini bukan berarti solusinya
            # salah. Melaporkannya sebagai GAGAL akan menuduh materi yang benar.
            dilewati.append(f"{masuk.name} ({cmd[0] if cmd else masuk.suffix} tidak terpasang)")
            continue
        # Lab yang membaca stdin diberi masukan contoh; tanpa itu EOFError akan
        # tercatat sebagai kegagalan padahal kodenya benar.
        sumber = _baca(masuk)
        masukan = "10\n20\n30\n\n" * 5 if ("input(" in sumber or "process.stdin" in sumber) else ""
        try:
            r = subprocess.run(cmd + [masuk.name], cwd=str(solusi), input=masukan,
                               capture_output=True, text=True, timeout=BATAS_WAKTU_LAB,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0:
                lulus.append(masuk.name + (" (masukan contoh)" if masukan else ""))
            else:
                ekor = (r.stderr or r.stdout).strip().splitlines()[-2:]
                gagal.append(f"{masuk.name} exit {r.returncode}: {' | '.join(ekor)[:120]}")
        except subprocess.TimeoutExpired:
            gagal.append(f"{masuk.name} melebihi {BATAS_WAKTU_LAB} detik")
    if gagal:
        return _hasil("lab jalan", GAGAL, "; ".join(gagal), f"{rel}/lab/solusi")
    if not lulus:
        return _hasil("lab jalan", TAK_BERLAKU, "; ".join(dilewati), f"{rel}/lab/solusi")
    bukti = ", ".join(lulus) + " exit 0"
    if dilewati:
        bukti += f" ({len(dilewati)} dilewati: {'; '.join(dilewati)})"
    return _hasil("lab jalan", LULUS, bukti, f"{rel}/lab/solusi")


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
