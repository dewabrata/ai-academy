"""Sistem desain deck pelatihan: satu tempat yang menentukan rupa semua slide.

Dipisah dari `exporter.py` karena ini keputusan rupa, bukan keputusan isi.
`exporter.py` mengurai SLIDE.md dan memanggil `buat_deck()`; modul ini tidak
tahu apa-apa tentang Markdown.

Rupanya mengikuti deck acuan milik pemilik proyek (Gamma, palet hangat
terakota-emas, huruf Jost/Poppins/JetBrains Mono). Yang ditiru adalah bahasa
desainnya — palet, hierarki huruf, kartu bersudut tumpul, label eyebrow — bukan
gambar dan ikonnya: generator ini tidak punya sumber gambar, dan kotak gambar
yang tidak pernah terisi jauh lebih buruk daripada slide yang memang bertumpu
pada tipografi.

Keputusan yang dipegang di sini, supaya tidak tersebar:

* **16:9.** Bawaan python-pptx adalah 10x7.5 inci (4:3).
* **Tidak memakai layout bawaan Office.** Semua slide dibangun dari layout
  kosong dan bentuk yang ditaruh sendiri; placeholder bawaan membawa tema Office
  yang justru ingin ditinggalkan.
* **Tanpa garis aksen di bawah judul dan tanpa bilah warna di tepi slide.**
  Pemisahan dikerjakan oleh ruang kosong, warna latar, dan kartu.
* **Butir pendek jadi kartu, butir panjang tetap daftar.** Deck acuan hampir
  seluruhnya kartu, tetapi isinya ditulis khusus untuk itu. Butir panjang yang
  dipaksa masuk kartu akan mengecil sampai tidak terbaca.
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt


def _w(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# --- Palet (diambil dari deck acuan) --------------------------------------
LATAR = _w("FFFFF4")          # krem hangat, latar semua slide isi
GELAP = _w("282828")          # latar slide pembatas
TINTA = _w("282828")          # judul dan teks utama
TEKS2 = _w("4A4540")          # isi sekunder
REDUP = _w("6B625A")
FOOTER = _w("7A7068")
TERAKOTA = _w("B33F00")       # eyebrow, nomor besar
EMAS = _w("F2B906")
HIJAU = _w("1F6B35")
AMBER = _w("9A5A00")
TERANG = _w("FFFFF4")         # teks di atas latar gelap
TERANG2 = _w("E8E1D2")

KARTU_ISI = _w("FFFDF8")
KARTU_GARIS = _w("EFE6CC")
KARTU_HIJAU = _w("E3F6E6")
KARTU_HIJAU_TEKS = _w("1F3A26")
KARTU_EMAS = _w("FFF6DB")
KODE_BG = _w("282828")
KODE_FG = _w("FFFFF4")

# Warna label kartu, dipakai berputar supaya grid tidak monoton — persis cara
# deck acuan membedakan kartu yang bersebelahan.
PUTAR_LABEL = [TERAKOTA, HIJAU, AMBER, TINTA]

# --- Huruf ----------------------------------------------------------------
# Tidak ikut paket Office. Pemilik proyek memilih memakainya apa adanya, sama
# seperti deck acuannya; di komputer tanpa font ini PowerPoint mengganti sendiri.
HURUF_JUDUL = "Jost"
HURUF_ISI = "Poppins"
HURUF_KODE = "JetBrains Mono"

# --- Tata letak (inci) ----------------------------------------------------
LEBAR, TINGGI = 13.333, 7.5
TEPI = 0.89                   # margin kiri, mengikuti grid deck acuan
ISI_LEBAR = 11.9
ATAS_EYEBROW = 0.72
ATAS_JUDUL = 1.04
BADAN_BAWAH = 6.55
FOOTER_Y = 6.83
JARAK = 0.3

MAKS_KODE_PT, MIN_KODE_PT = 13.0, 8.0
# Butir sepanjang ini atau kurang masih enak dibaca di dalam kartu.
MAKS_HURUF_KARTU = 110
# Tinggi kartu terkecil yang masih memuat label nomor dan satu baris isi.
# Di bawah ini kotak teks di dalamnya menjadi negatif.
MIN_KARTU = 0.98
# Lebar rata-rata huruf, dalam em, untuk memperkirakan pembungkusan baris.
# Angka judul dikalibrasi dari render PowerPoint yang sebenarnya: 0.47 membuat
# judul 48 huruf diperkirakan 2 baris padahal tergambar 3, dan subjudulnya
# tertimpa. Lebih baik terlalu hati-hati - salah ke arah ini hanya menyisakan
# sedikit ruang, salah ke arah sebaliknya membuat teks bertabrakan.
EM_JUDUL = 0.55
EM_ISI = 0.49


# Ukuran terkecil yang masih sah. PowerPoint MENOLAK membuka berkas yang
# memuat bentuk berukuran nol atau negatif - sementara python-pptx menuliskannya
# tanpa keluhan dan validator XML meloloskannya. Pagar ini mengubah kesalahan
# hitung tata letak menjadi slide yang jelek, bukan berkas yang tidak bisa
# dibuka sama sekali.
MIN_UKURAN = 0.08


def _sah(v):
    return max(float(v), MIN_UKURAN)


def _kotak(slide, x, y, lebar, tinggi):
    k = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(_sah(lebar)), Inches(_sah(tinggi)))
    tf = k.text_frame
    tf.word_wrap = True
    # Padding bawaan textbox menggeser teks beberapa milimeter dari posisi yang
    # dihitung; dinolkan supaya teks benar-benar lurus dengan bentuk lain.
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def _tulis(tf, teks, *, ukuran, warna, huruf=HURUF_ISI, tebal=False,
           spasi_setelah=0, rata=PP_ALIGN.LEFT, baru=False):
    p = tf.add_paragraph() if baru else tf.paragraphs[0]
    p.alignment = rata
    p.space_after = Pt(spasi_setelah)
    r = p.add_run()
    r.text = teks
    r.font.size = Pt(ukuran)
    r.font.bold = tebal
    r.font.name = huruf
    r.font.color.rgb = warna
    return p


def _tanpa_bayangan(bentuk):
    """Matikan bayangan sungguhan, bukan hanya `shadow.inherit = False`.

    add_shape() menyertakan <p:style> yang menunjuk effectRef tema; selama
    rujukan itu ada, PowerPoint tetap menggambar bayangan meski daftar efeknya
    kosong — dan kartu jadi tampak berhalo abu-abu.
    """
    bentuk.shadow.inherit = False
    gaya = bentuk._element.find(qn("p:style"))
    if gaya is not None:
        rujukan = gaya.find(qn("a:effectRef"))
        if rujukan is not None:
            rujukan.set("idx", "0")


def _latar(slide, warna):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = warna


def _bentuk(slide, jenis, x, y, lebar, tinggi, isi, garis=None, tebal_garis=1.0,
            radius=None):
    b = slide.shapes.add_shape(jenis, Inches(x), Inches(y),
                               Inches(_sah(lebar)), Inches(_sah(tinggi)))
    b.fill.solid()
    b.fill.fore_color.rgb = isi
    if garis is None:
        b.line.fill.background()
    else:
        b.line.color.rgb = garis
        b.line.width = Pt(tebal_garis)
    _tanpa_bayangan(b)
    if radius is not None and len(b.adjustments):
        b.adjustments[0] = radius
    return b


def _butir_bulat(p, warna=TERAKOTA):
    """Ganti bulatan bawaan dengan titik beraksen.

    python-pptx tidak membuka pengaturan bullet, jadi elemennya ditulis
    langsung. Tanpa ini bulatannya hitam dan ikut tema Office.
    """
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(Emu(Inches(0.26))))
    pPr.set("indent", str(-Emu(Inches(0.26))))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for lama in pPr.findall(qn(tag)):
            pPr.remove(lama)
    el_warna = pPr.makeelement(qn("a:buClr"), {})
    el_warna.append(el_warna.makeelement(qn("a:srgbClr"), {"val": str(warna)}))
    el_huruf = pPr.makeelement(qn("a:buFont"), {"typeface": "Arial"})
    el_tanda = pPr.makeelement(qn("a:buChar"), {"char": "•"})
    for el in (el_warna, el_huruf, el_tanda):
        pPr.append(el)


# --- Komponen -------------------------------------------------------------
def _eyebrow(slide, teks, y=ATAS_EYEBROW, warna=TERAKOTA):
    """Label kecil huruf besar di atas judul. Motif paling khas deck acuan."""
    tf = _kotak(slide, TEPI, y, ISI_LEBAR, 0.26)
    _tulis(tf, teks.upper()[:70], ukuran=12, warna=warna, tebal=True)


def _footer(slide, kiri_teks, kanan_teks=""):
    tf = _kotak(slide, TEPI, FOOTER_Y, ISI_LEBAR * 0.7, 0.26)
    _tulis(tf, kiri_teks, ukuran=12, warna=FOOTER)
    if kanan_teks:
        tf2 = _kotak(slide, TEPI + ISI_LEBAR - 2.0, FOOTER_Y, 2.0, 0.26)
        _tulis(tf2, kanan_teks, ukuran=12, warna=FOOTER, rata=PP_ALIGN.RIGHT)


def _baris_teks(teks, lebar_in, ukuran, lebar_huruf=0.5):
    per_baris = max(int(lebar_in * 72.0 / (ukuran * lebar_huruf)), 8)
    return max(1, -(-len(teks) // per_baris))


def _ukuran_kode(blok, lebar_in):
    """Ukuran huruf terbesar yang membuat baris terpanjang tetap muat.

    Dihitung, bukan ditebak: satu baris kode yang meluber keluar kartu adalah
    cacat yang paling cepat terlihat di layar.
    """
    panjang = max((len(b) for b in blok), default=1) or 1
    pas = (lebar_in * 72.0) / (panjang * 0.58)
    return max(MIN_KODE_PT, min(MAKS_KODE_PT, pas))


def _tinggi_kode(blok, lebar_in):
    ukuran = _ukuran_kode(blok, lebar_in - 0.5)
    return len(blok) * (ukuran * 1.3) / 72.0 + 0.52


def _kartu_kode(slide, blok, x, y, lebar, tinggi):
    _bentuk(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, lebar, tinggi,
            KODE_BG, radius=0.08)
    sisip = 0.25
    tf = _kotak(slide, x + sisip, y + sisip * 0.85,
                lebar - sisip * 2, tinggi - sisip * 1.7)
    ukuran = _ukuran_kode(blok, lebar - sisip * 2)
    for i, baris in enumerate(blok):
        _tulis(tf, baris or " ", ukuran=ukuran, warna=KODE_FG,
               huruf=HURUF_KODE, baru=i > 0)


def _kartu_butir(slide, teks, x, y, lebar, tinggi, warna_label, nomor):
    """Satu kartu grid: nomor beraksen di atas, isi butir di bawahnya."""
    _bentuk(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, lebar, tinggi,
            KARTU_ISI, garis=KARTU_GARIS, tebal_garis=1.0, radius=0.095)
    sisip = 0.2
    tf = _kotak(slide, x + sisip, y + sisip, lebar - sisip * 2, 0.26)
    _tulis(tf, f"{nomor:02d}", ukuran=12, warna=warna_label,
           huruf=HURUF_JUDUL, tebal=True)
    tfb = _kotak(slide, x + sisip, y + sisip + 0.32,
                 lebar - sisip * 2, tinggi - sisip * 2 - 0.32)
    _tulis(tfb, teks, ukuran=12, warna=TEKS2)


def _boleh_jadi_kartu(butir, tersedia):
    """Kartu hanya kalau isinya cocok DAN ruangnya cukup.

    Deck acuan hampir seluruhnya kartu, tetapi kalimatnya ditulis khusus untuk
    itu. Butir panjang yang dipaksa masuk kartu mengecil sampai tidak terbaca.
    Dan slide yang juga memuat blok kode panjang sering hanya menyisakan ruang
    di bawah tinggi minimum kartu - di situ daftar yang hurufnya bisa mengecil
    adalah jawaban yang benar.
    """
    if not (2 <= len(butir) <= 6
            and all(len(b) <= MAKS_HURUF_KARTU for b in butir)):
        return False
    _, baris, _, tinggi, sela = _ukuran_grid(butir, tersedia)
    return baris * tinggi + (baris - 1) * sela <= tersedia + 0.01


def _ukuran_grid(butir, tersedia):
    """(kolom, baris, lebar, tinggi) satu grid kartu - tanpa menggambar."""
    n = len(butir)
    kolom = 2 if n in (2, 4) else 3
    baris = -(-n // kolom)
    sela = 0.22
    lebar = (ISI_LEBAR - sela * (kolom - 1)) / kolom
    maks_baris = max(_baris_teks(b, lebar - 0.4, 12, EM_ISI) for b in butir)
    muat = (tersedia - sela * (baris - 1)) / baris
    tinggi = max(MIN_KARTU, min(0.62 + maks_baris * 0.21, muat))
    return kolom, baris, lebar, tinggi, sela


def _tinggi_grid(butir, tersedia):
    _, baris, _, tinggi, sela = _ukuran_grid(butir, tersedia)
    return baris * tinggi + (baris - 1) * sela


def _tinggi_daftar(butir, tersedia):
    ukuran = _ukuran_daftar(butir, tersedia)
    return min(_tinggi_daftar_pada(butir, ukuran), tersedia)


def _tinggi_daftar_pada(butir, ukuran):
    return sum(_baris_teks(b, ISI_LEBAR, ukuran, EM_ISI) * ukuran * 1.26
               + ukuran * 0.6 for b in butir) / 72.0


def _ukuran_daftar(butir, tersedia):
    ukuran = 17 if len(butir) <= 4 else (15 if len(butir) <= 6 else 13)
    while ukuran > 11 and _tinggi_daftar_pada(butir, ukuran) > tersedia:
        ukuran -= 1
    return ukuran


def _grid_kartu(slide, butir, y, tersedia):
    """Gambar butir sebagai grid kartu. Mengembalikan tinggi yang terpakai."""
    # Tinggi kartu mengikuti butir terpanjang, supaya satu baris kartu rata.
    kolom, baris, lebar, tinggi, sela = _ukuran_grid(butir, tersedia)
    for i, b in enumerate(butir):
        kx = TEPI + (i % kolom) * (lebar + sela)
        ky = y + (i // kolom) * (tinggi + sela)
        _kartu_butir(slide, b, kx, ky, lebar, tinggi,
                     PUTAR_LABEL[i % len(PUTAR_LABEL)], i + 1)
    return baris * tinggi + (baris - 1) * sela


def _daftar_butir(slide, butir, y, tersedia):
    ukuran = _ukuran_daftar(butir, tersedia)
    tf = _kotak(slide, TEPI, y, ISI_LEBAR, max(tersedia, 0.6))
    for i, b in enumerate(butir):
        p = _tulis(tf, b, ukuran=ukuran, warna=TEKS2,
                   spasi_setelah=ukuran * 0.6, baru=i > 0)
        _butir_bulat(p)
    return min(_tinggi_daftar_pada(butir, ukuran), tersedia)


# --- Jenis slide ----------------------------------------------------------
def _sampul(prs, judul, subjudul, label):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _latar(slide, LATAR)
    # Panel kanan: blok warna penuh tinggi, penyeimbang judul yang rata kiri.
    _bentuk(slide, MSO_SHAPE.RECTANGLE, 9.0, 0.0, LEBAR - 9.0, TINGGI, GELAP)

    lebar_kiri = 7.58
    # Judul panjang pada 46pt menjadi tiga baris dan menabrak subjudul. Ukuran
    # diturunkan sampai muat dua baris, lalu subjudul ditaruh SESUDAH tinggi
    # judul yang sebenarnya - bukan di titik tetap.
    ukuran = 46
    while ukuran > 28 and _baris_teks(judul, lebar_kiri, ukuran, EM_JUDUL) > 2:
        ukuran -= 2
    baris = _baris_teks(judul, lebar_kiri, ukuran, EM_JUDUL)
    tinggi_judul = baris * ukuran * 1.18 / 72.0

    y = 2.99
    _eyebrow(slide, label, y=y - 0.48)
    tf = _kotak(slide, TEPI, y, lebar_kiri, tinggi_judul + 0.1)
    _tulis(tf, judul, ukuran=ukuran, warna=TINTA, huruf=HURUF_JUDUL, tebal=True)
    if subjudul:
        tf2 = _kotak(slide, TEPI, y + tinggi_judul + 0.46, lebar_kiri, 0.9)
        _tulis(tf2, subjudul, ukuran=16, warna=TEKS2)
    # Tanpa footer: isinya akan mengulang eyebrow kata demi kata.
    return slide


def _pembatas(prs, nomor, judul, total):
    """Slide tanpa butir dan tanpa kode diperlakukan sebagai pembatas bagian."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _latar(slide, GELAP)
    _eyebrow(slide, f"Bagian {nomor} dari {total}", y=2.42, warna=EMAS)
    tf = _kotak(slide, TEPI, 2.86, ISI_LEBAR - 1.4, 1.9)
    _tulis(tf, judul, ukuran=44, warna=TERANG, huruf=HURUF_JUDUL, tebal=True)
    tf2 = _kotak(slide, TEPI, FOOTER_Y, ISI_LEBAR, 0.26)
    _tulis(tf2, f"{nomor:02d}", ukuran=12, warna=TERANG2, huruf=HURUF_JUDUL, tebal=True)
    return slide


def _isi(prs, nomor, sl, total, konteks):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _latar(slide, LATAR)

    judul = sl["judul"] or "(tanpa judul)"
    # Eyebrow memakai judul DECK, bukan judul slide: memakai judul slide
    # membuatnya tercetak dua kali persis, satu di atas yang lain.
    _eyebrow(slide, konteks)

    baris_judul = _baris_teks(judul, ISI_LEBAR, 32, EM_JUDUL)
    tinggi_judul = baris_judul * 32 * 1.2 / 72.0
    tf = _kotak(slide, TEPI, ATAS_JUDUL, ISI_LEBAR, tinggi_judul + 0.1)
    _tulis(tf, judul, ukuran=32, warna=TINTA, huruf=HURUF_JUDUL, tebal=True)

    butir = sl["butir"]
    blok = [b for b in sl["kode"] if b]
    y = ATAS_JUDUL + tinggi_judul + 0.42
    tersedia = BADAN_BAWAH - y

    perlu_kode = 0.0
    if blok:
        # Kode mengambil tinggi yang ia butuhkan, butir memakai sisanya. Titik
        # tetap untuk kartu kode membuatnya menimpa daftar butir di tiap slide
        # yang punya keduanya.
        perlu_kode = sum(_tinggi_kode(b, ISI_LEBAR) for b in blok) + JARAK * len(blok)
        perlu_kode = min(perlu_kode, tersedia - (1.0 if butir else 0))

    # Isi yang pendek menumpuk di atas dan meninggalkan separuh slide kosong.
    # Tingginya dihitung lebih dulu, lalu seluruh blok digeser turun separuh
    # dari sisa ruang - slide jadi seimbang tanpa mengubah ukuran apa pun.
    tinggi_butir = 0.0
    if butir:
        ruang_butir = tersedia - perlu_kode - (JARAK if blok else 0)
        tinggi_butir = (_tinggi_grid(butir, ruang_butir) if _boleh_jadi_kartu(butir, ruang_butir)
                        else _tinggi_daftar(butir, ruang_butir))
    total_isi = tinggi_butir + perlu_kode + (JARAK if (butir and blok) else 0)
    y += max(0.0, (tersedia - total_isi) * 0.5)

    if butir:
        ruang = tersedia - perlu_kode - (JARAK if blok else 0)
        if _boleh_jadi_kartu(butir, ruang):
            terpakai = _grid_kartu(slide, butir, y, ruang)
        else:
            terpakai = _daftar_butir(slide, butir, y, ruang)
        y += terpakai + JARAK

    for b in blok:
        tinggi = min(_tinggi_kode(b, ISI_LEBAR), max(BADAN_BAWAH - y, 0.6))
        if tinggi < 0.5:
            break
        _kartu_kode(slide, b, TEPI, y, ISI_LEBAR, tinggi)
        y += tinggi + JARAK

    _footer(slide, f"Slide {nomor} dari {total}", f"{nomor:02d}")
    return slide


def buat_deck(judul: str, slides: list[dict], keluar: Path,
              subjudul: str = "Materi pelatihan") -> Path:
    """Tulis deck ber-desain ke `keluar`. `slides` dari exporter.parse_slides()."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(LEBAR), Inches(TINGGI)
    total = len(slides)

    _sampul(prs, judul, subjudul, "Materi pelatihan")
    for i, sl in enumerate(slides, 1):
        kosong = not sl["butir"] and not any(sl["kode"])
        s = (_pembatas(prs, i, sl["judul"] or "(tanpa judul)", total) if kosong
             else _isi(prs, i, sl, total, judul))
        if sl["catatan"]:
            s.notes_slide.notes_text_frame.text = "\n".join(sl["catatan"])

    keluar.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(keluar))
    return keluar
