"""Periksa dan jalankan rencana unggah Moodle (`docs/MOODLE.json`).

Pembagian tugas yang dipegang modul ini: peran Moodle menyusun rencana — nama,
kalimat instruksi, pertanyaan feedback, bobot — dan modul ini memeriksanya lalu
mengeksekusinya. Tidak ada model yang dipanggil di sini, jadi unggahan yang
sama menghasilkan kursus yang sama.

    python moodle_unggah.py workspace/<proyek> --periksa
    python moodle_unggah.py workspace/<proyek> --unggah
"""
import json
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import moodle
import rencana

BERKAS_RENCANA = "MOODLE.json"
BERKAS_HASIL = "MOODLE_HASIL.json"

# Berkas materi yang diunggah, sesuai urutan tampil di folder Moodle.
BERKAS_MATERI = ["HANDBOOK.docx", "SLIDE.pptx", "LATIHAN.docx",
                 "KUNCI.docx", "PRAKTIK.docx"]
TIPE_FEEDBACK = {"multichoice", "textarea", "numeric"}


class RencanaError(ValueError):
    """Rencana tidak bisa dieksekusi. Lebih baik berhenti daripada membangun
    kursus setengah jadi yang harus dibereskan manual."""


# ---------------------------------------------------------------------------
# Komposisi nyata proyek
# ---------------------------------------------------------------------------
def komposisi(ws: Path) -> dict:
    """Apa yang BENAR-BENAR ada di proyek, untuk peran Moodle dan validator.

    Diambil dari berkas, bukan dari blueprint saja: blueprint menyatakan niat,
    sedangkan yang bisa diunggah hanyalah yang sudah jadi.
    """
    pertemuan = rencana.daftar_pertemuan(ws, laporkan=None)
    out = []
    for p in pertemuan:
        f = ws / "materi" / f"pertemuan-{p['no']:02d}"
        ada = [n for n in BERKAS_MATERI if (f / n).is_file()]
        out.append({
            "no": p["no"],
            "judul": p["judul"],
            "jenis": sorted(p["jenis"]),
            "berkas": ada,
            "quiz": (f / "QUIZ_AIKEN.txt").is_file(),
            "praktik": "praktik" in p["jenis"] and (f / "PRAKTIK.md").is_file(),
            "bahan": (f / "bahan").is_dir(),
            "lab": (f / "lab").is_dir(),
            "point": len(p["point"]),
            "siap": bool(ada),
        })
    return {
        "proyek": ws.name,
        "pertemuan": out,
        "jumlah_pertemuan": len(out),
        "pertemuan_siap": [x["no"] for x in out if x["siap"]],
        "pertemuan_kosong": [x["no"] for x in out if not x["siap"]],
    }


# ---------------------------------------------------------------------------
# Validasi rencana
# ---------------------------------------------------------------------------
def periksa(rencana_: dict, komp: dict) -> list[str]:
    """Masalah pada rencana, satu baris masing-masing. Kosong = boleh dijalankan."""
    m: list[str] = []
    if not isinstance(rencana_, dict):
        return ["rencana bukan objek JSON"]

    k = rencana_.get("kursus") or {}
    for kunci in ("fullname", "shortname"):
        if not str(k.get(kunci) or "").strip():
            m.append(f"kursus.{kunci} kosong")
    sn = str(k.get("shortname") or "")
    if sn and not re.fullmatch(r"[A-Z0-9-]{1,40}", sn):
        m.append(f"kursus.shortname '{sn[:50]}' harus huruf besar/angka/strip, maks 40")

    # Pertemuan harus cocok satu-satu dengan yang ada di proyek.
    siap = [x["no"] for x in komp["pertemuan"] if x["siap"]]
    ada = [x.get("no") for x in (rencana_.get("pertemuan") or [])]
    if sorted(n for n in ada if isinstance(n, int)) != sorted(siap):
        m.append(f"nomor pertemuan di rencana {ada} tidak sama dengan yang "
                 f"materinya siap {siap}")

    per_no = {x["no"]: x for x in komp["pertemuan"]}
    for p in (rencana_.get("pertemuan") or []):
        no = p.get("no")
        info = per_no.get(no)
        awalan = f"pertemuan {no}"
        if not info:
            continue
        if not str((p.get("folder_materi") or {}).get("nama") or "").strip():
            m.append(f"{awalan}: folder_materi.nama kosong")
        if info["quiz"] and not str((p.get("quiz") or {}).get("nama") or "").strip():
            m.append(f"{awalan}: ada QUIZ_AIKEN.txt tetapi quiz.nama kosong")
        if p.get("praktik") and not info["praktik"]:
            m.append(f"{awalan}: rencana memuat praktik, tetapi pertemuan ini "
                     f"tidak berjenis praktik atau tidak punya PRAKTIK.md")
        if info["praktik"] and not str((p.get("praktik") or {}).get("instruksi") or "").strip():
            m.append(f"{awalan}: praktik.instruksi kosong")
        for i, q in enumerate((p.get("feedback") or {}).get("pertanyaan") or [], 1):
            tipe = q.get("tipe")
            if tipe not in TIPE_FEEDBACK:
                m.append(f"{awalan}: pertanyaan {i} bertipe '{tipe}', "
                         f"harus salah satu dari {sorted(TIPE_FEEDBACK)}")
            if tipe == "multichoice" and len(q.get("pilihan") or []) < 2:
                m.append(f"{awalan}: pertanyaan {i} multichoice tanpa minimal dua pilihan")
            if not str(q.get("teks") or "").strip():
                m.append(f"{awalan}: pertanyaan {i} tanpa teks")

    # Penilaian
    nilai = rencana_.get("penilaian") or {}
    bobot = nilai.get("bobot") or {}
    kunci = ("quiz", "praktik", "proyek", "kehadiran")
    hilang = [x for x in kunci if x not in bobot]
    if hilang:
        m.append(f"penilaian.bobot kekurangan kunci: {', '.join(hilang)}")
    else:
        try:
            angka = {x: float(bobot[x]) for x in kunci}
        except (TypeError, ValueError):
            m.append("penilaian.bobot memuat nilai yang bukan angka")
            angka = {}
        if angka:
            total = round(sum(angka.values()), 3)
            if total != 100:
                m.append(f"penilaian.bobot berjumlah {total}, harus tepat 100")
            if any(v < 0 for v in angka.values()):
                m.append("penilaian.bobot memuat angka negatif")
            if not rencana_.get("proyek_akhir") and angka.get("proyek", 0) > 0:
                m.append("tidak ada proyek_akhir, tetapi bobot proyek bukan 0")
            ada_praktik = any(x["praktik"] for x in komp["pertemuan"])
            if not ada_praktik and angka.get("praktik", 0) > 0:
                m.append("tidak ada pertemuan berpraktik, tetapi bobot praktik bukan 0")
    try:
        lulus = float(nilai.get("nilai_lulus", 0))
        if not 50 <= lulus <= 100:
            m.append(f"penilaian.nilai_lulus {lulus} di luar 50-100")
    except (TypeError, ValueError):
        m.append("penilaian.nilai_lulus bukan angka")

    pa = rencana_.get("proyek_akhir")
    if pa and pa.get("pertemuan") not in siap:
        m.append(f"proyek_akhir.pertemuan {pa.get('pertemuan')} bukan pertemuan "
                 f"yang materinya siap")
    return m


def bobot_hitungan(komp: dict) -> dict:
    """Bobot cadangan kalau peran Moodle tidak bisa dipanggil.

    Aturannya sederhana dan bisa dijelaskan: kehadiran 10% karena ia syarat dan
    bukan ukuran kemampuan, sisanya dibagi menurut jumlah butir dengan praktik
    dihitung tiga kali quiz dan proyek enam kali — mencerminkan berapa banyak
    yang dituntut dari peserta, bukan selera.
    """
    n_quiz = sum(1 for x in komp["pertemuan"] if x["siap"] and x["quiz"])
    n_praktik = sum(1 for x in komp["pertemuan"] if x["siap"] and x["praktik"])
    ada_proyek = n_praktik > 0
    butir = {"quiz": n_quiz * 1, "praktik": n_praktik * 3,
             "proyek": 6 if ada_proyek else 0}
    total = sum(butir.values())
    if total == 0:
        return {"quiz": 0, "praktik": 0, "proyek": 0, "kehadiran": 100}
    bobot = {k: round(v / total * 90) for k, v in butir.items()}
    bobot["kehadiran"] = 100 - sum(bobot.values())
    return bobot


# ---------------------------------------------------------------------------
# Eksekusi
# ---------------------------------------------------------------------------
def _zip_bahan(folder: Path) -> bytes:
    """Folder bahan/ dikemas jadi satu .zip supaya peserta mengunduh sekali."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file() and "node_modules" not in f.parts:
                z.write(f, f.relative_to(folder).as_posix())
    return buf.getvalue()


def unggah(ws: Path, rencana_: dict, kategori_id: int, template_id: int,
           lapor=print) -> dict:
    """Bangun kursus di Moodle dari rencana. Mengembalikan ringkasan hasil."""
    komp = komposisi(ws)
    masalah = periksa(rencana_, komp)
    if masalah:
        raise RencanaError("rencana tidak lolos pemeriksaan:\n- "
                           + "\n- ".join(masalah))

    k = moodle.Klien()
    k.mulai()
    kurang = k.periksa_kesiapan()
    if kurang:
        raise RencanaError("Moodle kekurangan fungsi berikut, pasang plugin dulu:\n- "
                           + "\n- ".join(kurang))
    situs = k.wajib("core_webservice_get_site_info", {}, "baca info situs")
    uid = int(situs["userid"])

    kursus = rencana_["kursus"]
    lapor(f">>> Membuat kursus '{kursus['fullname']}'")
    hasil = k.wajib("core_course_create_courses", {"courses": [{
        "fullname": kursus["fullname"], "shortname": kursus["shortname"],
        "categoryid": kategori_id, "format": "topics",
        "numsections": max(komp["jumlah_pertemuan"], 1),
        "summary": kursus.get("summary", ""), "summaryformat": 1,
    }]}, "buat kursus")
    kid = int(hasil[0]["id"])
    lapor(f"    kursus id={kid}")

    if template_id:
        lapor(f">>> Menyalin template {template_id}")
        k.wajib("core_course_import_course",
                {"importfrom": template_id, "importto": kid}, "salin template")
        _bersihkan_announcements_ganda(k, kid, lapor)

    dibuat = {"pertemuan": [], "kursus_id": kid}
    for p in rencana_["pertemuan"]:
        no = p["no"]
        f = ws / "materi" / f"pertemuan-{no:02d}"
        sec = no                      # section 0 = General, jadi hari N = section N
        lapor(f">>> Pertemuan {no} (section {sec})")
        catat = {"no": no}

        _pastikan_section(k, kid, sec, p.get("section") or f"Day {no}", lapor)
        catat["materi"] = _unggah_materi(k, kid, sec, f, p, uid, lapor)
        if p.get("quiz") and (f / "QUIZ_AIKEN.txt").is_file():
            catat["quiz"] = _buat_quiz(k, kid, sec, f, p, uid, lapor)
        if p.get("praktik"):
            catat["praktik"] = _buat_assignment(
                k, kid, sec, p["praktik"]["nama"], p["praktik"]["instruksi"], lapor)
        if p.get("feedback"):
            catat["feedback"] = _buat_feedback(k, kid, sec, p["feedback"], lapor)
        dibuat["pertemuan"].append(catat)

    pa = rencana_.get("proyek_akhir")
    if pa:
        lapor(f">>> Proyek akhir di section {pa['pertemuan']}")
        dibuat["proyek_akhir"] = _buat_assignment(
            k, kid, int(pa["pertemuan"]), pa["nama"], pa.get("instruksi", ""), lapor)

    ab = rencana_.get("absensi") or {}
    lapor(">>> Absensi")
    dibuat["absensi"] = _buat_absensi(k, kid, ab, komp, lapor)

    lapor(">>> Gradebook")
    dibuat["penilaian"] = _atur_nilai(k, kid, rencana_["penilaian"], lapor)

    (ws / "docs" / BERKAS_HASIL).write_text(
        json.dumps(dibuat, ensure_ascii=False, indent=1), encoding="utf-8")
    lapor(f">>> Selesai. Ringkasan di docs/{BERKAS_HASIL}")
    return dibuat


def _bersihkan_announcements_ganda(k, kid, lapor):
    """Salinan template membawa forum Announcements-nya sendiri, sehingga kursus
    baru punya dua. Yang kedua disembunyikan, bukan dihapus — menghapus modul
    lewat API berisiko salah sasaran, menyembunyikan tidak."""
    isi, galat = k.panggil("core_course_get_contents", {"courseid": kid})
    if galat:
        return
    forum = [m for s in (isi or []) for m in (s.get("modules") or [])
             if m.get("modname") == "forum" and m.get("name") == "Announcements"]
    for m in forum[1:]:
        k.panggil("local_moodlia_update_module",
                  {"course_id": kid, "module_id": m["id"], "visible": False})
        lapor(f"    forum Announcements ganda disembunyikan (cmid {m['id']})")


def _pastikan_section(k, kid, nomor, judul, lapor):
    isi, galat = k.panggil("core_course_get_contents", {"courseid": kid})
    punya = {int(s.get("section", -1)) for s in (isi or [])}
    if nomor not in punya:
        k.wajib("local_moodlia_create_section",
                {"course_id": kid, "name": judul}, f"buat section {nomor}")
        lapor(f"    section {nomor} dibuat")
    else:
        k.panggil("local_moodlia_update_section",
                  {"course_id": kid, "section_number": nomor, "name": judul})


def _unggah_materi(k, kid, sec, f, p, uid, lapor):
    fm = p["folder_materi"]
    berkas = [(n, (f / n).read_bytes()) for n in BERKAS_MATERI if (f / n).is_file()]
    if (f / "bahan").is_dir():
        berkas.append((f"bahan-hari-{p['no']}.zip", _zip_bahan(f / "bahan")))
    if not berkas:
        lapor("    tidak ada berkas materi — dilewati")
        return None
    mod = k.wajib("local_moodlia_create_module", {
        "course_id": kid, "section_number": sec, "module_type": "folder",
        "name": fm["nama"],
        "options": json.dumps({"intro": fm.get("intro", "")}),
    }, f"buat folder materi pertemuan {p['no']}")
    cmid = int(mod["module_id"])
    for nama, isi in berkas:
        item = moodle.unggah_berkas(k, uid, nama, isi)
        k.wajib("local_moodlia_upload_folder_file", {
            "course_id": kid, "module_id": cmid, "filename": nama,
            "draft_item_id": item}, f"masukkan {nama} ke folder")
        lapor(f"    {nama} ({len(isi) // 1024} KB)")
    return {"cmid": cmid, "berkas": [n for n, _ in berkas]}


def _buat_quiz(k, kid, sec, f, p, uid, lapor):
    """Quiz dengan bank soal privatnya sendiri.

    Soal dibuat langsung, bukan lewat impor XML. Alasannya terbukti di
    pengujian: kalau kursus sudah punya bank soal bawaan dari template, plugin
    importer mengabaikan jalur kategori di XML dan menumpuk seluruh soal di satu
    kategori bawaan — quiz hari 1 lalu menarik soal hari 4. Bank privat per quiz
    menghilangkan percampuran itu sepenuhnya.
    """
    import aiken

    soal = aiken.urai_aiken((f / "QUIZ_AIKEN.txt").read_text(encoding="utf-8"))
    mod = k.wajib("local_moodlia_create_module", {
        "course_id": kid, "section_number": sec, "module_type": "quiz",
        "name": p["quiz"]["nama"],
        "options": json.dumps({"intro": p["quiz"].get("intro", "")}),
    }, "buat quiz")
    cmid = int(mod["module_id"])

    kat = k.wajib("local_moodlia_create_question_category", {
        "course_id": kid, "name": f"Soal Hari {p['no']}",
        "bank_scope": "quiz_private", "quiz_module_id": cmid,
    }, f"buat kategori soal hari {p['no']}")
    cid, ctx = kat["category_id"], kat["context_id"]

    dibuat = []
    for i, s in enumerate(soal, 1):
        # fraction adalah PECAHAN: 1 untuk jawaban benar, 0 untuk sisanya.
        # Angka 100 ditolak Moodle dengan invalidparameter.
        opsi = {"single": True, "shuffleanswers": True,
                "answers": [{"text": teks,
                             "fraction": 1 if huruf == s["jawaban"] else 0}
                            for huruf, teks in s["pilihan"]]}
        hasil, galat = k.panggil("local_moodlia_create_question", {
            "category_id": cid, "context_id": ctx,
            "question_type": "multichoice",
            "name": f"{i:02d}. {s['soal'][:70]}",
            "question_text": "<p>" + s["soal"] + "</p>",
            "options": json.dumps(opsi)})
        if galat:
            lapor(f"    soal {i} gagal: {galat}")
        else:
            dibuat.append(hasil["question_id"])

    # Ditautkan satu per satu, bukan diacak: peserta mendapat kesepuluh soal
    # dalam urutan yang sama seperti di QUIZ_AIKEN.txt, dan trainer bisa
    # mencocokkannya dengan berkas sumbernya.
    tertaut = 0
    for slot, qid in enumerate(dibuat, 1):
        _, galat = k.panggil("local_moodlia_add_question_to_quiz", {
            "quiz_module_id": cmid, "question_id": qid, "slot": slot})
        if galat:
            lapor(f"    soal slot {slot} gagal ditautkan: {galat}")
        else:
            tertaut += 1
    lapor(f"    quiz '{p['quiz']['nama']}' + {tertaut} dari {len(soal)} soal")
    return {"cmid": cmid, "soal": tertaut, "kategori": cid}


def _buat_assignment(k, kid, sec, nama, instruksi, lapor):
    mod = k.wajib("local_moodlia_create_module", {
        "course_id": kid, "section_number": sec, "module_type": "assign",
        "name": nama, "options": json.dumps({"intro": instruksi}),
    }, f"buat tugas '{nama}'")
    lapor(f"    tugas '{nama}'")
    return {"cmid": int(mod["module_id"]), "nama": nama}


def _buat_feedback(k, kid, sec, fb, lapor):
    mod = k.wajib("local_moodlia_create_module", {
        "course_id": kid, "section_number": sec, "module_type": "feedback",
        "name": fb["nama"],
    }, f"buat feedback '{fb['nama']}'")
    cmid = int(mod["module_id"])
    dibuat = 0
    for i, q in enumerate(fb.get("pertanyaan") or [], 1):
        # Bentuk `definition` berbeda tiap tipe; ini yang diterima MoodlIA.
        if q["tipe"] == "multichoice":
            definisi = {"subtype": "r", "choices": list(q["pilihan"])}
        elif q["tipe"] == "numeric":
            definisi = {}
        else:
            definisi = {"width": 60, "height": 5}
        _, galat = k.panggil("local_moodlia_create_feedback_item", {
            "course_id": kid, "module_id": cmid, "type": q["tipe"],
            "name": q["teks"], "definition": json.dumps(definisi),
            "position": i, "required": False})
        if galat:
            lapor(f"    pertanyaan {i} gagal: {galat}")
        else:
            dibuat += 1
    lapor(f"    feedback '{fb['nama']}' + {dibuat} pertanyaan")
    return {"cmid": cmid, "pertanyaan": dibuat}


def _buat_absensi(k, kid, ab, komp, lapor):
    hasil = k.wajib("mod_attendance_add_attendance", {
        "courseid": kid, "name": ab.get("nama") or "Absensi Pelatihan",
        "intro": ab.get("intro", "")}, "buat absensi")
    lapor(f"    absensi id={hasil.get('attendanceid')} "
          f"(sesi diisi trainer di Moodle)")
    return {"attendance_id": hasil.get("attendanceid"), "sesi": 0}


def _atur_nilai(k, kid, penilaian, lapor):
    """Kategori nilai dibuat, lalu grade item activity dipindahkan ke dalamnya.

    Grade item terbentuk sendiri saat activity dibuat, jadi urutannya harus
    setelah semua activity ada — bukan sebelumnya.
    """
    bobot = penilaian["bobot"]
    item, galat = k.panggil("local_moodlia_get_grade_items", {"course_id": kid})
    daftar = item if isinstance(item, list) else ((item or {}).get("items") or [])

    # Modul mana masuk kategori mana.
    peta = {"quiz": ("quiz",), "praktik": ("assign",), "kehadiran": ("attendance",)}
    kategori = {}
    for nama_kat in ("quiz", "praktik", "proyek", "kehadiran"):
        if float(bobot.get(nama_kat, 0)) <= 0:
            continue
        label = {"quiz": "Quiz", "praktik": "Praktik",
                 "proyek": "Proyek Akhir", "kehadiran": "Kehadiran"}[nama_kat]
        hasil, galat = k.panggil("local_moodlia_create_grade_category",
                                 {"course_id": kid, "name": label})
        if galat:
            lapor(f"    kategori {label} gagal: {galat}")
            continue
        kategori[nama_kat] = (hasil or {}).get("category_id") or (hasil or {}).get("id")
        lapor(f"    kategori {label} ({bobot[nama_kat]}%)")

    for g in daftar:
        modul = g.get("item_module")
        nama = str(g.get("name") or "")
        tujuan = None
        if modul == "assign" and "Proyek" in nama:
            tujuan = "proyek"
        else:
            for kat, mods in peta.items():
                if modul in mods:
                    tujuan = kat
                    break
        if not tujuan or tujuan not in kategori:
            continue
        iid = g.get("item_id") or g.get("id")
        k.panggil("local_moodlia_update_grade_item", {
            "course_id": kid, "item_id": iid,
            "category_id": kategori[tujuan], "weight": float(bobot[tujuan])})

    k.panggil("local_moodlia_set_course_grade_pass",
              {"course_id": kid, "grade_pass_percent": float(penilaian["nilai_lulus"])})
    lapor(f"    nilai lulus {penilaian['nilai_lulus']}%")
    return {"kategori": kategori, "bobot": bobot,
            "nilai_lulus": penilaian["nilai_lulus"]}


def _cli():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    ws = Path(sys.argv[1])
    komp = komposisi(ws)
    print(f"proyek     : {komp['proyek']}")
    print(f"pertemuan  : {komp['jumlah_pertemuan']} "
          f"(siap: {komp['pertemuan_siap']}, kosong: {komp['pertemuan_kosong']})")
    p = ws / "docs" / BERKAS_RENCANA
    if not p.exists():
        print(f"\nBelum ada docs/{BERKAS_RENCANA}. Susun dulu lewat peran Moodle:")
        print(f"   python academy.py --project {ws.name} --moodle rencana")
        sys.exit(1)
    r = json.loads(p.read_text(encoding="utf-8"))
    masalah = periksa(r, komp)
    print(f"\nrencana    : {len(masalah)} masalah")
    for m in masalah:
        print("   -", m)
    if "--unggah" in sys.argv and not masalah:
        kat = int(os.getenv("MOODLE_KATEGORI", "0") or 0)
        tpl = int(os.getenv("MOODLE_TEMPLATE", "0") or 0)
        unggah(ws, r, kat, tpl)


if __name__ == "__main__":
    import os
    _cli()
