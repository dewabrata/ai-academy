"""AIKEN -> Moodle XML. Python murni, tanpa jaringan.

Moodle tidak membuka impor AIKEN ke web service, tetapi plugin importer menerima
Moodle XML. AIKEN hanya pilihan ganda satu jawaban, jadi pemetaannya langsung:
tiap soal menjadi <question type="multichoice"> dengan single=true, pilihan yang
benar fraction=100 dan sisanya fraction=0.
"""
import html
import re

# Nama soal di bank dipotong supaya daftar di Moodle tetap terbaca; teks
# lengkapnya tetap utuh di questiontext.
MAKS_NAMA = 80


class AikenError(ValueError):
    """Berkas AIKEN tidak bisa diurai. Lebih baik gagal daripada mengimpor
    soal yang pilihannya tertukar."""


def urai_aiken(teks: str) -> list[dict]:
    """Daftar {soal, pilihan: [(huruf, teks)], jawaban} dari berkas AIKEN."""
    blok = [b for b in re.split(r"\n\s*\n", teks.strip()) if b.strip()]
    if not blok:
        raise AikenError("berkas kosong")
    soal = []
    for i, b in enumerate(blok, 1):
        baris = [x.strip() for x in b.splitlines() if x.strip()]
        if len(baris) < 4:
            raise AikenError(f"soal {i}: kurang dari dua pilihan atau tanpa ANSWER")
        m = re.fullmatch(r"ANSWER:\s*([A-Z])", baris[-1])
        if not m:
            raise AikenError(f"soal {i}: baris terakhir bukan 'ANSWER: <huruf>'")
        jawab = m.group(1)
        pilihan = []
        for p in baris[1:-1]:
            mp = re.fullmatch(r"([A-Z])[.)]\s+(.*)", p)
            if not mp:
                raise AikenError(f"soal {i}: pilihan tidak berformat 'A. teks' -> {p[:40]!r}")
            pilihan.append((mp.group(1), mp.group(2)))
        huruf = [h for h, _ in pilihan]
        if huruf != [chr(ord("A") + n) for n in range(len(pilihan))]:
            raise AikenError(f"soal {i}: huruf pilihan tidak berurutan dari A -> {huruf}")
        if jawab not in huruf:
            raise AikenError(f"soal {i}: ANSWER '{jawab}' tidak ada di pilihan {huruf}")
        soal.append({"soal": baris[0], "pilihan": pilihan, "jawaban": jawab})
    return soal


def _cdata(teks: str) -> str:
    # "]]>" di dalam CDATA memutus bloknya; dipecah supaya tetap aman.
    return "<![CDATA[" + str(teks).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def ke_moodle_xml(teks: str, kategori: str = "") -> str:
    """Moodle XML dari isi berkas AIKEN. `kategori` kosong = kategori bawaan."""
    soal = urai_aiken(teks)
    keluar = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"]
    if kategori:
        keluar += ['  <question type="category">', "    <category>",
                   f"      <text>$course$/top/{html.escape(kategori)}</text>",
                   "    </category>", "  </question>"]
    for i, s in enumerate(soal, 1):
        nama = s["soal"][:MAKS_NAMA] + ("…" if len(s["soal"]) > MAKS_NAMA else "")
        keluar += [
            '  <question type="multichoice">',
            f"    <name><text>{html.escape(f'{i:02d}. {nama}')}</text></name>",
            f'    <questiontext format="html"><text>{_cdata("<p>" + html.escape(s["soal"]) + "</p>")}</text></questiontext>',
            "    <defaultgrade>1.0000000</defaultgrade>",
            "    <penalty>0.3333333</penalty>",
            "    <hidden>0</hidden>",
            "    <single>true</single>",
            "    <shuffleanswers>true</shuffleanswers>",
            "    <answernumbering>abc</answernumbering>",
        ]
        for huruf, isi in s["pilihan"]:
            nilai = "100" if huruf == s["jawaban"] else "0"
            keluar += [
                f'    <answer fraction="{nilai}" format="html">',
                f'      <text>{_cdata("<p>" + html.escape(isi) + "</p>")}</text>',
                '      <feedback format="html"><text></text></feedback>',
                "    </answer>",
            ]
        keluar.append("  </question>")
    keluar.append("</quiz>")
    return "\n".join(keluar) + "\n"
