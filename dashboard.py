"""Panel kendali web AI Academy.

    python dashboard.py      ->  http://127.0.0.1:8770

Membuat proyek (unggah silabus + konteks klien + opsi), memantau kemajuan per
point, MENJAWAB GATE, membaca materi, dan menyunting setelan `.env`.

Terikat 127.0.0.1 secara bawaan dan itu disengaja: panel ini menjalankan
pipeline, dan peran Tugas di dalamnya punya akses Bash. Kalau DASHBOARD_HOST
diisi alamat non-lokal sementara DASHBOARD_PASS kosong, panel menolak jalan.
Cara paling aman mengakses dari jauh tetap tanpa membuka port:

    ssh -L 8770:127.0.0.1:8770 user@server
"""
import hmac
import io
import json
import os
import secrets
import sys
import time
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from dotenv import load_dotenv

import control
import opsi as opsi_mod
import setelan


def akun_claude() -> str:
    """Akun Claude Code yang dipakai pipeline (login `claude` di mesin ini)."""
    try:
        d = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    a = d.get("oauthAccount") or {}
    return " · ".join(x for x in (a.get("emailAddress"), a.get("organizationName")) if x)

load_dotenv()

ROOT = Path(__file__).parent
WS = ROOT / "workspace"
SAFE_NAME = control.SAFE_NAME

MIME = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".jsonl": "text/plain; charset=utf-8",
    ".log": "text/plain; charset=utf-8",
    ".py": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
TEKS = {".md", ".txt", ".json", ".jsonl", ".log", ".py", ".csv"}

# token sesi -> kedaluwarsa (epoch). Di memori: restart = login ulang, dan itu
# lebih aman daripada menyimpan token ke disk.
SESI: dict[str, float] = {}
GAGAL: dict[str, list] = {}          # alamat -> waktu percobaan gagal
MAKS_GAGAL, JEDA_GAGAL = 5, 300


# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------
def aman(project: str, rel: str) -> Path | None:
    """Path berkas di dalam ruang kerja satu proyek, atau None kalau keluar.

    Dicek setelah resolve(), bukan dengan memeriksa ".." di string: symlink dan
    penulisan path yang aneh bisa lolos pemeriksaan string tapi tidak lolos ini.
    """
    if not SAFE_NAME.match(project or ""):
        return None
    dasar = (WS / project).resolve()
    try:
        p = (dasar / rel).resolve()
    except OSError:
        return None
    if dasar not in p.parents and p != dasar:
        return None
    return p if p.is_file() else None


def ekor(path: Path, n: int = 400) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def events(project: str, n: int = 250) -> list[dict]:
    out = []
    for baris in ekor(WS / project / "docs" / "events.jsonl", n):
        try:
            out.append(json.loads(baris))
        except json.JSONDecodeError:
            continue
    return out


def status_point(project: str) -> list[dict]:
    """Status tiap point dari docs/PRODUKSI.json, urut nomor."""
    try:
        data = json.loads((WS / project / "docs" / "PRODUKSI.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for kode, v in sorted(data.items()):
        rw = v.get("riwayat") or []
        out.append({"kode": kode, "status": v.get("status", "proses"),
                    "putaran": len(rw),
                    "skor": (rw[-1].get("skor") if rw else None) or {}})
    return out


def pohon_materi(project: str) -> list[dict]:
    """Berkas yang bisa dibaca di dashboard, per pertemuan."""
    m = WS / project / "materi"
    if not SAFE_NAME.match(project or "") or not m.exists():
        return []
    out = []
    for f in sorted(m.glob("pertemuan-*")):
        if not f.is_dir():
            continue
        berkas = []
        for pola in ("point/point-*.md", "point/*.catatan.md", "review/*.md",
                     "*.md", "*.txt"):
            for x in sorted(f.glob(pola)):
                rel = x.relative_to(WS / project).as_posix()
                if rel not in [b["path"] for b in berkas]:
                    berkas.append({"nama": x.relative_to(f).as_posix(), "path": rel,
                                   "kb": max(1, x.stat().st_size // 1024)})
        out.append({"nama": f.name, "berkas": berkas})
    return out


# Berkas proses yang tidak perlu ikut ke tangan trainer/peserta.
LEWATI_ZIP = ("review/", ".catatan.md", "__pycache__/")


def _ikut_zip(rel: str, lengkap: bool) -> bool:
    if Path(rel).name.startswith("."):
        return False
    return lengkap or not any(x in rel for x in LEWATI_ZIP)


def buat_zip(project: str, pertemuan: str = "", lengkap: bool = False) -> tuple[bytes, str] | None:
    """Zip materi satu proyek (atau satu pertemuan) di memori.

    `lengkap` menyertakan juga catatan proses (review/, *.catatan.md). Bawaan
    hanya materi yang dipakai mengajar, karena itu yang biasanya dikirim ke
    klien.
    """
    if not SAFE_NAME.match(project or ""):
        return None
    dasar = (WS / project).resolve()
    if not dasar.is_dir():
        return None
    akar = dasar / "materi"
    if pertemuan:
        if not Path(pertemuan).name == pertemuan or not (akar / pertemuan).is_dir():
            return None
        akar = akar / pertemuan
    if not akar.is_dir():
        return None

    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as z:
        for f in sorted(akar.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(dasar).as_posix()
            if _ikut_zip(rel, lengkap):
                z.write(f, f"{project}/{rel}")
        for n in ("KURIKULUM.md", "BLUEPRINT.md", "GLOSARIUM.md", "PEMERIKSAAN.md"):
            d = dasar / "docs" / n
            if not pertemuan and d.is_file():
                z.write(d, f"{project}/docs/{n}")
    nama = f"{project}{'-' + pertemuan if pertemuan else ''}{'-lengkap' if lengkap else ''}.zip"
    return buf.getvalue(), nama


def gate_hidup(st: dict, r: dict | None) -> dict | None:
    """Gate yang benar-benar menunggu jawaban sekarang.

    Dua sisa yang harus disaring, keduanya muncul setelah proses mati mendadak:
    (1) pipeline-nya sudah tidak hidup, jadi tidak ada yang membaca jawaban;
    (2) pipeline hidup tetapi tahap yang berjalan DIMULAI SETELAH gate itu
    dibuka — artinya gate itu milik proses sebelumnya.
    """
    gate = st.get("gate")
    if not gate or not (r and not r.get("basi")):
        return None
    mulai_tahap = st.get("current_since") or 0
    if mulai_tahap and (gate.get("since") or 0) < mulai_tahap:
        return None
    return gate


def detail(project: str) -> dict:
    docs = WS / project / "docs"
    st = control._status(project)
    r = control.running(project)
    perencanaan = ["KURIKULUM.md", "GLOSARIUM.md", "BLUEPRINT.md", "KLIEN.md", "ACUAN_GAYA.md",
                   "TELAAH_BAHASA.md", "PEMERIKSAAN.md"]
    ev = events(project, 5000)
    return {
        "nama": project,
        "tahap": (docs / "STATE.txt").read_text(encoding="utf-8").strip()
                 if (docs / "STATE.txt").exists() else "baru",
        "berjalan": bool(r and not r.get("basi")),
        "pid": (r or {}).get("pid"),
        "kunci_basi": bool(r and r.get("basi")),
        "sekarang": st.get("current"),
        "gate": gate_hidup(st, r),
        "biaya": st.get("cost") or {},
        "kuota": st.get("quota") or {},
        "pertemuan_selesai": st.get("pertemuan_selesai"),
        "pertemuan_total": st.get("pertemuan_total"),
        "point_total": st.get("point_total"),
        "point_aktif": st.get("point"),
        "point_judul": st.get("point_judul"),
        "pertemuan_aktif": st.get("pertemuan"),
        "skor_pemeriksaan": st.get("skor_pemeriksaan"),
        "penolakan": sum(1 for e in ev if e.get("kind") == "tool_denied"),
        "point": status_point(project),
        "opsi": opsi_mod.baca(WS / project),
        "plafon": os.getenv("BUDGET_PROYEK", "") or "",
        "dokumen": [n for n in perencanaan if (docs / n).exists()],
        "materi": control.daftar_materi(project),
        "pohon": pohon_materi(project),
        "silabus": control.daftar_silabus(project),
        "events": ev[-80:],
        "log": ekor(docs / "pipeline.log", 200),
        "diagnosa": control.diagnosa(project),
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _moodle_pilihan() -> dict:
    """Kategori dan kursus di Moodle, untuk dipilih dari namanya.

    Diambil lewat endpoint tersendiri, bukan ikut memuat tab: daftar kursus bisa
    ratusan dan Moodle bisa lambat, sementara sisa tab tidak perlu menunggunya.
    """
    try:
        import moodle
        k = moodle.Klien()
        k.mulai()
    except Exception as e:
        return {"ok": False, "msg": f"Moodle tidak bisa dihubungi: {e}"}
    kat, galat = k.panggil("core_course_get_categories",
                           {"criteria": [], "addsubcategories": 0})
    if galat:
        return {"ok": False, "msg": f"Gagal membaca kategori: {galat}"}
    kur, galat = k.panggil("core_course_get_courses", {"options": {}})
    if galat:
        kur = []
    return {
        "ok": True,
        "kategori": sorted(
            [{"id": c["id"], "nama": c.get("name", ""),
              "jumlah": c.get("coursecount", 0)} for c in (kat or [])],
            key=lambda x: x["nama"].lower()),
        "kursus": sorted(
            [{"id": c["id"], "nama": c.get("fullname", ""),
              "kode": c.get("shortname", ""), "kategori": c.get("categoryid")}
             for c in (kur or []) if c.get("id") != 1],
            key=lambda x: x["nama"].lower()),
    }


def _kursus_masih_ada(kursus_id: int) -> bool | None:
    """True/False, atau None kalau Moodle tidak bisa dihubungi.

    None dibedakan dari False dengan sengaja: "tidak bisa diperiksa" bukan
    "sudah dihapus", dan tab menampilkannya berbeda.
    """
    try:
        import moodle
        k = moodle.Klien()
        k.mulai()
        hasil, galat = k.panggil("core_course_get_courses_by_field",
                                 {"field": "id", "value": int(kursus_id)})
        if galat:
            return None
        return bool(((hasil or {}).get("courses")) or [])
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "AIAcademy"

    def log_message(self, *a):
        pass          # akses log ke stdout hanya membuat terminal ramai

    # ---- sesi ----
    def _perlu_login(self) -> bool:
        return bool((os.getenv("DASHBOARD_PASS") or "").strip())

    def _sesi_ok(self) -> bool:
        if not self._perlu_login():
            return True
        for bagian in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = bagian.strip().partition("=")
            if k == "sesi" and SESI.get(v, 0) > time.time():
                return True
        return False

    def _alamat(self) -> str:
        return self.client_address[0] if self.client_address else "?"

    def _diblokir(self) -> bool:
        riwayat = [t for t in GAGAL.get(self._alamat(), []) if time.time() - t < JEDA_GAGAL]
        GAGAL[self._alamat()] = riwayat
        return len(riwayat) >= MAKS_GAGAL

    def _login(self, b: dict):
        if self._diblokir():
            return self._json({"ok": False, "msg": "Terlalu banyak percobaan. "
                                                   "Coba lagi beberapa menit lagi."}, 429)
        user = os.getenv("DASHBOARD_USER", "admin")
        sandi = os.getenv("DASHBOARD_PASS", "")
        cocok = (hmac.compare_digest(str(b.get("user", "")), user)
                 and hmac.compare_digest(str(b.get("sandi", "")), sandi))
        if not cocok:
            GAGAL.setdefault(self._alamat(), []).append(time.time())
            return self._json({"ok": False, "msg": "Nama pengguna atau kata sandi salah."}, 401)
        token = secrets.token_urlsafe(32)
        jam = float(os.getenv("DASHBOARD_SESI_JAM", 12) or 12)
        SESI[token] = time.time() + jam * 3600
        GAGAL.pop(self._alamat(), None)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie",
                         f"sesi={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={int(jam * 3600)}")
        isi = json.dumps({"ok": True, "msg": "Masuk."}).encode()
        self.send_header("Content-Length", str(len(isi)))
        self.end_headers()
        self.wfile.write(isi)

    # ---- balasan ----
    def _kirim(self, kode: int, tipe: str, isi: bytes):
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(isi)

    def _json(self, data, kode: int = 200):
        self._kirim(kode, "application/json; charset=utf-8",
                    json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        mentah = self.rfile.read(n)
        tipe = self.headers.get("Content-Type", "")
        if "application/json" in tipe:
            try:
                return json.loads(mentah.decode("utf-8"))
            except Exception:
                return {}
        if "multipart/form-data" in tipe:
            return self._multipart(mentah, tipe)
        return {k: v[0] for k, v in parse_qs(mentah.decode("utf-8", "replace")).items()}

    def _multipart(self, mentah: bytes, tipe: str) -> dict:
        pesan = BytesParser(policy=email_policy).parsebytes(
            b"Content-Type: " + tipe.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + mentah)
        keluar: dict = {}
        for bagian in pesan.iter_parts():
            nama = bagian.get_param("name", header="content-disposition")
            berkas = bagian.get_filename()
            isi = bagian.get_payload(decode=True) or b""
            if berkas:
                keluar.setdefault("_berkas", {})[nama or berkas] = (berkas, isi)
            elif nama:
                keluar[nama] = isi.decode("utf-8", "replace")
        return keluar

    # ---- GET ----
    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}

        if u.path == "/":
            halaman = HALAMAN if self._sesi_ok() else LOGIN
            return self._kirim(200, "text/html; charset=utf-8", halaman.encode("utf-8"))
        if not self._sesi_ok():
            return self._json({"error": "Belum masuk.", "login": True}, 401)

        if u.path == "/api/moodle-pilihan":
            return self._json(_moodle_pilihan())
        if u.path == "/api/moodle":
            return self._json(self._moodle_keadaan(q.get("project", "")))
        if u.path == "/api/proyek":
            return self._json({"proyek": control.daftar_proyek(),
                               "berjalan": control.running_any(),
                               "opsi_bawaan": opsi_mod.bawaan(),
                               "akun": akun_claude(),
                               "api_key": bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())})
        if u.path == "/api/detail":
            p = q.get("project", "")
            if not SAFE_NAME.match(p) or not (WS / p).exists():
                return self._json({"error": "Proyek tidak ditemukan."}, 404)
            return self._json(detail(p))
        if u.path == "/api/setelan":
            return self._json({"setelan": setelan.baca()})
        if u.path == "/api/arsip":
            return self._json({"arsip": control.daftar_arsip()})
        if u.path == "/api/isi":
            f = aman(q.get("project", ""), q.get("path", ""))
            if not f or f.suffix.lower() not in TEKS:
                return self._json({"error": "Berkas tidak bisa dibaca sebagai teks."}, 404)
            teks = f.read_text(encoding="utf-8", errors="replace")
            return self._json({"nama": f.name, "isi": teks[:400_000],
                               "terpotong": len(teks) > 400_000})
        if u.path == "/api/zip":
            hasil = buat_zip(q.get("project", ""), Path(q.get("pertemuan", "") or "").name,
                             q.get("lengkap") == "1")
            if not hasil:
                return self._json({"error": "Tidak ada materi untuk diunduh."}, 404)
            isi, nama = hasil
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(isi)))
            self.send_header("Content-Disposition", f'attachment; filename="{nama}"')
            self.end_headers()
            return self.wfile.write(isi)
        if u.path == "/api/berkas":
            f = aman(q.get("project", ""), q.get("path", ""))
            if not f:
                return self._json({"error": "Berkas tidak ditemukan."}, 404)
            tipe = MIME.get(f.suffix.lower(), "application/octet-stream")
            isi = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipe)
            self.send_header("Content-Length", str(len(isi)))
            if f.suffix.lower() not in TEKS:
                self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
            self.end_headers()
            return self.wfile.write(isi)
        return self._json({"error": "Tidak ada."}, 404)

    # ---- POST ----
    def do_POST(self):
        u = urlparse(self.path)
        b = self._body()

        if u.path == "/api/login":
            return self._login(b)
        if not self._sesi_ok():
            return self._json({"error": "Belum masuk.", "login": True}, 401)
        if u.path == "/api/logout":
            for bagian in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = bagian.strip().partition("=")
                if k == "sesi":
                    SESI.pop(v, None)
            return self._json({"ok": True, "msg": "Keluar."})

        p = (b.get("project") or "").strip()

        if u.path == "/api/proyek-baru":
            return self._json(*self._proyek_baru(b))
        if u.path == "/api/mulai":
            pilot = b.get("pilot")
            try:
                pilot = int(pilot) if str(pilot or "").strip() else None
            except ValueError:
                pilot = None
            ok, msg = control.start(p, (b.get("aksi") or "lanjut").strip(),
                                    b.get("teks") or "", pilot)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/slide":
            ok, msg = control.start(p, "slide", str(b.get("pertemuan") or "semua"))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/moodle-rencana":
            ok, msg = control.start(p, "moodle", str(b.get("ulang") or ""),
                                    env_tambahan={"BATCH": b.get("batch") or ""})
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/moodle-simpan":
            return self._json(*self._moodle_simpan(p, b))
        if u.path == "/api/moodle-unggah":
            return self._json(*self._moodle_unggah(p, b))
        if u.path == "/api/bahan":
            ok, msg = control.start(p, "bahan", str(b.get("pertemuan") or "semua"))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/terapkan-setelan":
            ok, msg = control.terapkan_setelan(p)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/bersihkan-kunci":
            ok, msg = control.bersihkan_kunci(p)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/stop":
            ok, msg = control.stop(p)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/gate":
            ok, msg = control.jawab_gate(p, b.get("jawaban") or "")
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/opsi":
            if not SAFE_NAME.match(p) or not (WS / p).exists():
                return self._json({"ok": False, "msg": "Proyek tidak ditemukan."}, 404)
            opsi_mod.tulis(WS / p, b.get("opsi") or {})
            return self._json({"ok": True, "msg": "Opsi proyek disimpan."})
        if u.path == "/api/arsipkan":
            ok, msg = control.arsipkan(p)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/pulihkan":
            ok, msg = control.pulihkan(b.get("nama", ""), b.get("baru", ""))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/hapus-arsip":
            ok, msg = control.hapus_arsip(b.get("nama", ""), b.get("konfirmasi", ""))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/ganti-nama":
            ok, msg = control.ganti_nama(p, b.get("baru", ""))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/duplikat":
            ok, msg = control.duplikat(p, b.get("baru", ""))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/unggah":
            hasil, gagal = [], []
            for nama_f, data in (b.get("_berkas") or {}).values():
                ok, msg = control.simpan_silabus(p, nama_f, data)
                (hasil if ok else gagal).append(msg)
            if not hasil and not gagal:
                return self._json({"ok": False, "msg": "Tidak ada berkas."}, 400)
            return self._json({"ok": not gagal, "msg": " ".join(gagal or hasil)},
                              200 if not gagal else 400)
        if u.path == "/api/hapus-silabus":
            ok, msg = control.hapus_silabus(p, b.get("nama", ""))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/unggah-klien":
            berkas = list((b.get("_berkas") or {}).values())
            if not berkas:
                return self._json({"ok": False, "msg": "Tidak ada berkas."}, 400)
            ok, msg = control.simpan_klien(p, berkas[0][1])
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/hapus-klien":
            ok, msg = control.hapus_klien(p)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/setelan":
            ok, msg = setelan.tulis(b.get("setelan") or {})
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        if u.path == "/api/uji-telegram":
            ok, msg = setelan.uji_telegram(b.get("token", ""), b.get("chat", ""))
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 400)
        return self._json({"error": "Tidak ada."}, 404)

    # ---- buat proyek ----
    # ---- Moodle ---------------------------------------------------------
    def _moodle_keadaan(self, project: str) -> dict:
        """Komposisi proyek, rencana yang sudah ada, dan kesiapan setelan."""
        import moodle_unggah
        if not SAFE_NAME.match(project or "") or not (WS / project).exists():
            return {"ok": False, "msg": "Proyek tidak ditemukan."}
        ws = WS / project
        out = {"ok": True, "project": project}
        try:
            out["komposisi"] = moodle_unggah.komposisi(ws)
        except Exception as e:
            return {"ok": False, "msg": f"Blueprint belum bisa dibaca: {e}"}
        p = ws / "docs" / moodle_unggah.BERKAS_RENCANA
        if p.is_file():
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
                out["rencana"] = r
                out["masalah"] = moodle_unggah.periksa(r, out["komposisi"])
            except ValueError as e:
                out["masalah"] = [f"{p.name} bukan JSON yang sah: {e}"]
        h = ws / "docs" / moodle_unggah.BERKAS_HASIL
        if h.is_file():
            try:
                out["hasil"] = json.loads(h.read_text(encoding="utf-8"))
            except ValueError:
                pass
        # Kursus bisa sudah dihapus orang di Moodle, sementara berkas hasilnya
        # tertinggal. Tanpa pemeriksaan ini tab menyatakan "sudah diunggah"
        # sambil menunjuk kursus yang tidak ada.
        if out.get("hasil", {}).get("kursus_id"):
            out["hasil"]["masih_ada"] = _kursus_masih_ada(out["hasil"]["kursus_id"])
        out["bobot_hitungan"] = moodle_unggah.bobot_hitungan(out["komposisi"])
        out["setelan"] = {
            "url": bool((os.getenv("MOODLE_MCP_URL") or "").strip()),
            "token": bool((os.getenv("MOODLE_TOKEN") or "").strip()),
            "kategori": (os.getenv("MOODLE_KATEGORI") or "").strip(),
            "template": (os.getenv("MOODLE_TEMPLATE") or "").strip(),
        }
        return out

    def _moodle_simpan(self, project: str, b: dict) -> tuple[dict, int]:
        """Simpan suntingan rencana dari dashboard, setelah diperiksa."""
        import moodle_unggah
        if not SAFE_NAME.match(project or "") or not (WS / project).exists():
            return {"ok": False, "msg": "Proyek tidak ditemukan."}, 404
        ws = WS / project
        rencana_ = b.get("rencana")
        if not isinstance(rencana_, dict):
            return {"ok": False, "msg": "Rencana kosong."}, 400
        masalah = moodle_unggah.periksa(rencana_, moodle_unggah.komposisi(ws))
        if masalah:
            return {"ok": False, "msg": "Rencana belum lolos pemeriksaan.",
                    "masalah": masalah}, 400
        (ws / "docs" / moodle_unggah.BERKAS_RENCANA).write_text(
            json.dumps(rencana_, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "msg": "Rencana disimpan."}, 200

    def _moodle_unggah(self, project: str, b: dict) -> tuple[dict, int]:
        """Jalankan unggahan. Deterministik, tanpa memanggil model."""
        import moodle
        import moodle_unggah
        if not SAFE_NAME.match(project or "") or not (WS / project).exists():
            return {"ok": False, "msg": "Proyek tidak ditemukan."}, 404
        ws = WS / project
        p = ws / "docs" / moodle_unggah.BERKAS_RENCANA
        if not p.is_file():
            return {"ok": False, "msg": "Belum ada rencana. Susun dulu."}, 400
        try:
            rencana_ = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            return {"ok": False, "msg": f"Rencana bukan JSON yang sah: {e}"}, 400
        # Kolom yang ADA tetapi kosong berarti "belum dipilih", bukan "pakai
        # bawaan". Membedakan keduanya penting: kalau kosong jatuh ke .env,
        # menekan Unggah tanpa memilih kategori tetap membuat kursus, di tempat
        # yang tidak diniatkan.
        def _id(kunci: str, env: str) -> int:
            if kunci in b:
                nilai = str(b.get(kunci) or "").strip()
            else:
                nilai = (os.getenv(env) or "").strip()
            return int(nilai) if nilai else 0

        try:
            kategori = _id("kategori", "MOODLE_KATEGORI")
            template = _id("template", "MOODLE_TEMPLATE")
        except ValueError:
            return {"ok": False, "msg": "Id kategori/template harus angka."}, 400
        if not kategori:
            return {"ok": False, "msg": "Kategori Moodle belum dipilih."}, 400
        # Id diperiksa ke Moodle lebih dulu. Kategori yang tidak ada membuat
        # core_course_create_courses gagal di tengah, setelah rencana dianggap
        # sah — lebih baik ditolak sebelum apa pun dibuat.
        pilihan = _moodle_pilihan()
        if pilihan.get("ok"):
            if kategori not in {x["id"] for x in pilihan["kategori"]}:
                return {"ok": False, "msg": f"Kategori id {kategori} tidak ada "
                                            f"di Moodle."}, 400
            if template and template not in {x["id"] for x in pilihan["kursus"]}:
                return {"ok": False, "msg": f"Kursus template id {template} "
                                            f"tidak ada di Moodle."}, 400
            # Shortname unik se-Moodle, bukan per kategori. Proyek kedua yang
            # kebetulan menghasilkan kode sama membuat create_courses gagal
            # dengan 'shortnametaken' — di sini pesannya masih bisa menyebut
            # kursus mana yang memakainya.
            sn = str((rencana_.get("kursus") or {}).get("shortname") or "").strip()
            bentrok = next((x for x in pilihan["kursus"]
                            if x["kode"].strip().upper() == sn.upper()), None)
            if bentrok:
                return {"ok": False, "msg":
                        f"Kode kursus '{sn}' sudah dipakai oleh "
                        f"'{bentrok['nama']}' (id {bentrok['id']}). "
                        f"Ganti Kode kursus di atas — kode harus unik "
                        f"se-Moodle, bukan hanya dalam kategori."}, 400
        catatan = []
        try:
            hasil = moodle_unggah.unggah(ws, rencana_, kategori, template,
                                         lapor=catatan.append)
        except (moodle_unggah.RencanaError, moodle.MoodleError) as e:
            return {"ok": False, "msg": str(e), "log": catatan}, 400
        return {"ok": True, "msg": f"Kursus {hasil['kursus_id']} dibuat di Moodle.",
                "hasil": hasil, "log": catatan}, 200

    def _proyek_baru(self, b: dict) -> tuple[dict, int]:
        nama = (b.get("nama") or "").strip()
        if not SAFE_NAME.match(nama):
            return {"ok": False, "msg": "Nama proyek hanya boleh huruf, angka, - dan _."}, 400
        if (WS / nama / "docs" / "STATE.txt").exists():
            return {"ok": False, "msg": f"Proyek '{nama}' sudah pernah dijalankan. "
                                        f"Pakai nama lain."}, 400
        ok, msg = control.siapkan_proyek(nama)
        if not ok:
            return {"ok": False, "msg": msg}, 400

        berkas = b.get("_berkas") or {}
        sumber = ""
        if "silabus" in berkas:
            nama_f, data = berkas["silabus"]
            ok, msg = control.simpan_silabus(nama, nama_f, data)
            if not ok:
                return {"ok": False, "msg": msg}, 400
            sumber = str((WS / nama / "sumber" / Path(nama_f).name))
        elif (b.get("teks") or "").strip():
            teks = b["teks"].strip()
            f = WS / nama / "sumber" / "silabus-tempel.md"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(teks, encoding="utf-8")
            sumber = str(f)
        else:
            return {"ok": False, "msg": "Silabus belum diisi: unggah berkas atau tempel teks."}, 400

        if "klien" in berkas:
            ok, msg = control.simpan_klien(nama, berkas["klien"][1])
            if not ok:
                return {"ok": False, "msg": msg}, 400

        opsi = {
            "slide": str(b.get("slide", "1")) not in ("0", "false"),
            "ekspor_docx": str(b.get("ekspor_docx", "1")) not in ("0", "false"),
            "ekspor_pptx": str(b.get("ekspor_pptx", "1")) not in ("0", "false"),
            "point_halaman": b.get("point_halaman") or "",
            "point_maks_putaran": b.get("point_maks_putaran") or 0,
            "model": b.get("model") or "",
        }
        pilot = b.get("pilot")
        try:
            pilot = int(pilot) if str(pilot or "").strip() else None
        except ValueError:
            pilot = None

        env_tambahan = None
        if str(b.get("mutu_maksimal", "")) in ("1", "true", "on"):
            # Plafon dimatikan untuk PROSES ini saja, bukan diubah di .env:
            # proyek lain tetap punya rem.
            env_tambahan = {k: "0" for k in (
                "BUDGET_KURIKULUM", "BUDGET_BLUEPRINT", "BUDGET_POINT_WRITER",
                "BUDGET_POINT_REVIEW", "BUDGET_POINT_FAKTA", "BUDGET_SLIDE",
                "BUDGET_TUGAS", "BUDGET_PAKET_REVIEW", "BUDGET_EDITOR", "BUDGET_PROYEK")}
            env_tambahan.update(QUOTA_WAIT="auto", QUOTA_WAIT_MAX_HOURS="200")

        ok, msg = control.start(nama, "baru", sumber, pilot, opsi_proyek=opsi,
                                env_tambahan=env_tambahan)
        return ({"ok": ok, "msg": msg, "project": nama}, 200 if ok else 400)


# ---------------------------------------------------------------------------
GAYA = r"""
:root{--bg:#f6f7f9;--kartu:#fff;--garis:#e3e6ea;--fg:#1c2024;--dim:#6b7280;
--acc:#2563eb;--acc2:#eff4ff;--ok:#15803d;--okbg:#ecfdf3;--warn:#b45309;
--warnbg:#fff7ed;--bad:#b91c1c;--badbg:#fef2f2;--r:10px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--acc)}
button{font:inherit;border:1px solid var(--garis);background:#fff;color:var(--fg);
padding:8px 14px;border-radius:8px;cursor:pointer}
button:hover{background:#f3f4f6}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff}
button.pri:hover{filter:brightness(1.07)}
button.bad{background:#fff;border-color:#f1b0b0;color:var(--bad)}
input,select,textarea{font:inherit;padding:8px 10px;border:1px solid var(--garis);
border-radius:8px;background:#fff;color:var(--fg);width:100%}
textarea{min-height:90px;resize:vertical}
label{display:block;font-size:12px;color:var(--dim);margin:0 0 4px}
header{background:#fff;border-bottom:1px solid var(--garis);padding:10px 18px;
display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:5}
header h1{font-size:15px;margin:0;font-weight:650;letter-spacing:.2px}
.tumbuh{flex:1}
nav{display:flex;gap:4px;padding:0 18px;background:#fff;border-bottom:1px solid var(--garis);
overflow-x:auto}
nav button{border:0;border-bottom:2px solid transparent;border-radius:0;padding:10px 12px;
color:var(--dim);background:none}
nav button.on{color:var(--acc);border-bottom-color:var(--acc);font-weight:600}
main{padding:16px 18px 40px;max-width:1180px;margin:0 auto}
.kartu{background:var(--kartu);border:1px solid var(--garis);border-radius:var(--r);
padding:16px;margin-bottom:14px}
.kartu h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);
margin:0 0 12px;font-weight:600}
.grid{display:grid;gap:14px}
.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}
@media(max-width:900px){.g2,.g3{grid-template-columns:1fr}main{padding:12px}}
.pil{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;
font-size:12px;background:#f3f4f6;color:var(--dim)}
.pil.ok{background:var(--okbg);color:var(--ok)}
.pil.warn{background:var(--warnbg);color:var(--warn)}
.pil.bad{background:var(--badbg);color:var(--bad)}
.pil.acc{background:var(--acc2);color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--dim);font-weight:600;font-size:12px;padding:6px 8px;
border-bottom:1px solid var(--garis)}
td{padding:7px 8px;border-bottom:1px solid #f1f3f5;vertical-align:top}
.angka{font-size:26px;font-weight:650;letter-spacing:-.4px}
.kecil{font-size:12px;color:var(--dim)}
.drop{border:2px dashed #c9d2de;border-radius:var(--r);padding:26px;text-align:center;
color:var(--dim);background:#fbfcfe;cursor:pointer}
.drop.over{border-color:var(--acc);background:var(--acc2);color:var(--acc)}
.drop.terisi{border-style:solid;border-color:#86c99a;background:var(--okbg);color:var(--ok)}
.berkas{display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap}
.langkah{display:flex;gap:8px;align-items:center;margin-bottom:10px;font-size:12px;color:var(--dim)}
.langkah b{color:var(--fg)}
button[disabled]{opacity:.5;cursor:not-allowed}
.sumber{border:1px solid var(--garis);border-radius:8px;padding:10px;margin-top:10px;
display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.sumber.ada{border-color:#86c99a;background:var(--okbg)}
pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;
max-height:460px;font-size:12px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.log{background:#0f172a;color:#cbd5e1;border-radius:8px;padding:10px;max-height:260px;
overflow:auto;font:12px/1.5 ui-monospace,Consolas,monospace}
.baris{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.sisi{display:grid;grid-template-columns:280px 1fr;gap:14px}
@media(max-width:900px){.sisi{grid-template-columns:1fr}}
.daftar{max-height:520px;overflow:auto}
.item{padding:7px 9px;border-radius:7px;cursor:pointer;display:flex;justify-content:space-between;
gap:8px}
.item:hover{background:#f3f4f6}.item.on{background:var(--acc2);color:var(--acc);font-weight:600}
.gate{border:1px solid #fcd9a6;background:var(--warnbg);border-radius:var(--r);padding:16px;
margin-bottom:14px}
.gate h2{color:var(--warn)}
.gate .isi{background:#fff;border:1px solid #f0e0c8;border-radius:8px;padding:14px 16px;
max-height:46vh;overflow:auto}
.gate .isi p{margin:0 0 10px}
.gate .isi ul{margin:0 0 10px;padding-left:20px}
.gate .isi li{margin:2px 0}
.gate .isi h3{font-size:14px;margin:14px 0 6px}
.gate .isi code{background:#f6f7f9;padding:1px 5px;border-radius:4px;font-size:12px}
.gate details{margin:6px 0 10px}
.gate details summary{cursor:pointer;color:var(--warn);font-size:13px}
.gate details pre{margin-top:8px;max-height:260px;font-size:12px}
.gate .angkaBesar{font-weight:650}
.pesan{position:fixed;right:16px;bottom:16px;background:#111827;color:#fff;padding:10px 14px;
border-radius:8px;font-size:13px;max-width:380px;box-shadow:0 6px 24px rgba(0,0,0,.18);
opacity:0;transition:.2s;pointer-events:none}
.pesan.tampil{opacity:1}
.sw{display:flex;gap:8px;align-items:center;margin:6px 0}
.sw input{width:auto}
.doc{max-height:64vh;overflow:auto;padding:4px 6px 20px;line-height:1.7}
.doc h1{font-size:20px;margin:18px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--garis)}
.doc h2{font-size:17px;margin:20px 0 8px;text-transform:none;letter-spacing:0;color:var(--fg)}
.doc h3{font-size:15px;margin:16px 0 6px}
.doc h4{font-size:14px;margin:14px 0 6px;color:var(--dim)}
.doc p{margin:0 0 12px}
.doc ul,.doc ol{margin:0 0 12px;padding-left:22px}
.doc li{margin:3px 0}
.doc code{background:#f1f3f5;padding:1px 5px;border-radius:4px;font-size:12.5px}
.doc pre{background:#0f172a;color:#e2e8f0;padding:12px 14px;border-radius:8px;max-height:none;
margin:0 0 14px}
.doc pre code{background:none;color:inherit;padding:0;font-size:12.5px}
.doc pre.kode{position:relative;padding-top:26px}
.doc pre.kode[data-bahasa]::before{content:attr(data-bahasa);position:absolute;
top:6px;right:10px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;
color:#94a3b8}
.doc pre.kode.keluaran{background:#f6f7f9;color:#1f2937;
border:1px solid var(--garis)}
.doc pre.kode.keluaran::before{color:#94a3b8}
.doc blockquote{margin:0 0 12px;padding:6px 14px;border-left:3px solid var(--acc);
background:var(--acc2);border-radius:0 6px 6px 0}
.doc blockquote p{margin:0}
.doc table{margin:0 0 14px}
.doc table th,.doc table td{border:1px solid var(--garis);padding:6px 9px}
.doc table th{background:#f6f7f9}
.doc hr{border:0;border-top:1px solid var(--garis);margin:18px 0}
.doc a{word-break:break-word}
.doc img{max-width:100%}
.bacaKepala{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;
margin-bottom:10px}
"""

LOGIN = r"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Masuk — AI Academy</title>
<style>__GAYA__
.wrap{min-height:100vh;display:grid;place-items:center;padding:20px}
form{background:#fff;border:1px solid var(--garis);border-radius:var(--r);padding:24px;
width:100%;max-width:360px}
form h1{font-size:18px;margin:0 0 4px}
form p{margin:0 0 18px;color:var(--dim);font-size:13px}
form label{margin-top:12px}
form button{width:100%;margin-top:18px}
.galat{color:var(--bad);font-size:13px;margin-top:10px;min-height:18px}
</style></head><body><div class="wrap">
<form onsubmit="masuk(event)">
  <h1>AI Academy</h1>
  <p>Panel produksi materi ajar.</p>
  <label>Nama pengguna</label><input id="u" autocomplete="username" autofocus>
  <label>Kata sandi</label><input id="p" type="password" autocomplete="current-password">
  <button class="pri" type="submit">Masuk</button>
  <div class="galat" id="galat"></div>
</form></div>
<script>
async function masuk(e){e.preventDefault();
  const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({user:document.getElementById("u").value,
                         sandi:document.getElementById("p").value})});
  const j=await r.json();
  if(j.ok){location.reload();}else{document.getElementById("galat").textContent=j.msg||"Gagal.";}
}
</script></body></html>
""".replace("__GAYA__", GAYA)

HALAMAN = r"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Academy</title>
<style>__GAYA__</style></head><body>
<header>
  <h1>AI Academy</h1>
  <select id="pilihProyek" style="width:auto;min-width:180px" onchange="pilih(this.value)"></select>
  <span id="statusPil"></span>
  <span class="tumbuh"></span>
  <span class="kecil" id="akun" title="Login Claude Code di mesin ini — kuotanya dipakai bersama editor"></span>
  <button class="pri" onclick="tab('baru')">+ Proyek baru</button>
  <button onclick="keluar()">Keluar</button>
</header>
<nav>
  <button id="t-proyek" class="on" onclick="tab('proyek')">Proyek</button>
  <button id="t-ringkas" onclick="tab('ringkas')">Ringkasan</button>
  <button id="t-materi" onclick="tab('materi')">Materi</button>
  <button id="t-berkas" onclick="tab('berkas')">Berkas &amp; opsi</button>
  <button id="t-moodle" onclick="tab('moodle')">Moodle</button>
  <button id="t-setelan" onclick="tab('setelan')">Pengaturan</button>
  <button id="t-baru" onclick="tab('baru')">Proyek baru</button>
</nav>
<main>
  <div id="proyek"></div>
  <div id="ringkas" hidden><div id="kotakGate"></div><div id="isiRingkas"></div></div>
  <div id="materi" hidden></div>
  <div id="berkas" hidden></div>
  <div id="moodle" hidden></div>
  <div id="setelan" hidden></div>
  <div id="baru" hidden></div>
</main>
<div class="pesan" id="pesan"></div>
<script>
let aktif=null, D=null, TAB="proyek", berkasAktif=null, SET=null, BAWAAN=null;
let PROYEK=[], ARSIP=[], gateKunci="", materiTanda="", BACA=null, bacaMentah=false, bacaTanda="";
let ikutiLog=true;
const tgl=t=>new Date(t*1000).toLocaleString("id-ID",{day:"2-digit",month:"short",
  hour:"2-digit",minute:"2-digit"});
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const rp=v=>"$"+(Number(v)||0).toFixed(2);

function pesan(t){const e=document.getElementById("pesan");e.textContent=t;
  e.classList.add("tampil");setTimeout(()=>e.classList.remove("tampil"),4000);}
async function api(u,o){const r=await fetch(u,o);
  if(r.status===401){location.reload();return {};} return r.json();}
async function post(u,d){return api(u,{method:"POST",
  headers:{"Content-Type":"application/json"},body:JSON.stringify(d)});}
async function keluar(){await post("/api/logout",{});location.reload();}

function tab(n){TAB=n;
  for(const x of ["proyek","ringkas","materi","berkas","moodle","setelan","baru"]){
    document.getElementById(x).hidden=(x!==n);
    document.getElementById("t-"+x).classList.toggle("on",x===n);}
  if(n==="moodle")muatMoodle();
  if(n==="setelan")muatSetelan();
  if(n==="baru")gambarBaru();
  if(n==="proyek")muatArsip();
  if(D)gambar();}

async function muatDaftar(){
  const j=await api("/api/proyek"); if(!j.proyek)return;
  BAWAAN=j.opsi_bawaan; PROYEK=j.proyek;
  document.getElementById("akun").textContent=
    j.api_key?"API key":(j.akun?("akun: "+j.akun):"akun Claude tidak terbaca");
  const s=document.getElementById("pilihProyek");
  const lama=aktif; s.innerHTML="";
  for(const p of j.proyek){
    const o=document.createElement("option");
    o.value=p.nama;o.textContent=`${p.nama} — ${p.tahap} (${rp(p.biaya)})`;s.appendChild(o);}
  if(!j.proyek.length){
    s.innerHTML='<option value="">(belum ada proyek)</option>';
    aktif=null;D=null;
    if(TAB!=="baru"&&TAB!=="setelan"&&TAB!=="proyek")tab("proyek");
    if(TAB==="proyek")gambarProyek();
    return;}
  aktif=(lama&&j.proyek.some(p=>p.nama===lama))?lama:j.proyek[0].nama;
  s.value=aktif;
  if(TAB==="proyek")gambarProyek();
  muatDetail();
}
async function muatArsip(){const j=await api("/api/arsip");ARSIP=j.arsip||[];gambarProyek();}
function pilih(n){aktif=n;berkasAktif=null;BACA=null;materiTanda="";muatDetail();}
function buka(n){aktif=n;berkasAktif=null;BACA=null;materiTanda="";
  document.getElementById("pilihProyek").value=n;tab("ringkas");muatDetail();}

async function arsipkan(n){
  if(!confirm(`Arsipkan proyek "${n}"?\n\nProyek dipindahkan ke workspace/.arsip dan bisa `
    +`dipulihkan dari tab Proyek. Tidak ada berkas yang dihapus.`))return;
  const j=await post("/api/arsipkan",{project:n});pesan(j.msg);
  if(j.ok){aktif=null;}await muatDaftar();muatArsip();}
async function gantiNama(n){
  const baru=prompt(`Nama baru untuk "${n}":`,n); if(!baru||baru===n)return;
  const j=await post("/api/ganti-nama",{project:n,baru});pesan(j.msg);
  if(j.ok)aktif=baru; await muatDaftar();}
async function duplikat(n){
  const baru=prompt(`Nama proyek baru dengan setelan "${n}":`,n+"-2"); if(!baru)return;
  const j=await post("/api/duplikat",{project:n,baru});pesan(j.msg);await muatDaftar();}
async function pulihkan(nama){
  const baru=prompt("Pulihkan sebagai nama proyek:",nama.replace(/-\d{8}-\d{6}$/,""));
  if(!baru)return;
  const j=await post("/api/pulihkan",{nama,baru});pesan(j.msg);await muatDaftar();muatArsip();}
async function hapusArsip(nama){
  const k=prompt(`HAPUS PERMANEN dan tidak bisa dibatalkan.\n\n`
    +`Ketik nama arsipnya persis untuk melanjutkan:\n${nama}`);
  if(!k)return;
  const j=await post("/api/hapus-arsip",{nama,konfirmasi:k});pesan(j.msg);muatArsip();}

async function muatDetail(){
  if(!aktif)return; const j=await api("/api/detail?project="+encodeURIComponent(aktif));
  if(j.error)return; D=j; gambar();
}

function statusPil(){
  if(!D)return "";
  if(D.gate)return '<span class="pil warn">menunggu jawaban: '+esc(D.gate.label)+'</span>';
  if(D.berjalan)return '<span class="pil ok">berjalan · '+esc(D.sekarang||"")+'</span>';
  if(D.tahap==="selesai")return '<span class="pil ok">selesai</span>';
  return '<span class="pil">berhenti · '+esc(D.tahap)+'</span>';
}

// Teks gate ditulis untuk terminal (baris polos). Di layar, teks mentah begitu
// sulit dibaca — jadi diubah jadi paragraf, daftar, dan blok yang bisa dilipat.
function formatGate(q){
  const baris=String(q||"").split("\n");
  let html="", daftar=[], kutip=null;
  const tutupDaftar=()=>{if(daftar.length){html+="<ul>"+daftar.join("")+"</ul>";daftar=[];}};
  const hias=t=>esc(t)
    .replace(/`([^`]+)`/g,"<code>$1</code>")
    .replace(/((?:[A-Za-z]:\\|\/)?[\w.\/\\-]+\.(?:md|txt|docx|pptx|json|py))/g,"<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g,"<b>$1</b>");
  for(const b of baris){
    if(b.trim()==="-----"){                       // cuplikan silabus / blok mentah
      if(kutip===null){tutupDaftar();kutip=[];}
      else{html+=`<details><summary>Lihat cuplikan (${kutip.length} baris)</summary>`
        +`<pre>${esc(kutip.join("\n"))}</pre></details>`;kutip=null;}
      continue;}
    if(kutip!==null){kutip.push(b);continue;}
    const t=b.trim();
    if(!t){tutupDaftar();continue;}
    if(/^[-*·✗•]\s+/.test(t)){daftar.push("<li>"+hias(t.replace(/^[-*·✗•]\s+/,""))+"</li>");continue;}
    tutupDaftar();
    if(/^(Point yang DIESKALASI|Pertanyaan terkumpul|Teks silabus|Yang akan diproduksi|Yang dikeluhkan)/i.test(t))
      html+="<h3>"+hias(t.replace(/:$/,""))+"</h3>";
    else html+="<p>"+hias(t)+"</p>";}
  tutupDaftar();
  if(kutip!==null)html+=`<details><summary>Lihat cuplikan</summary><pre>${esc(kutip.join("\n"))}</pre></details>`;
  return html;
}

function kartuGate(){
  if(!D.gate)return "";
  return `<div class="gate"><h2>Gate ${esc(D.gate.label)} menunggu jawaban Anda</h2>
    <div class="isi">${formatGate(D.gate.question)}</div>
    <div class="baris" style="margin-top:12px">
      <button class="pri" onclick="jawab('y')">Setuju, lanjutkan</button>
      <button class="bad" onclick="jawab('q')">Berhenti</button>
    </div>
    <div style="margin-top:12px">
      <label>Atau tulis masukan / jawaban pertanyaan</label>
      <textarea id="jawabTeks" placeholder="Contoh: point 3 terlalu panjang, pangkas bagian sejarahnya."></textarea>
      <button style="margin-top:8px" onclick="jawab(document.getElementById('jawabTeks').value)">Kirim masukan</button>
    </div></div>`;
}

function kartuKemajuan(){
  const p=D.point||[], siap=p.filter(x=>x.status==="siap").length,
        esk=p.filter(x=>x.status==="eskalasi").length;
  const chip=x=>`<span class="pil ${x.status==="siap"?"ok":x.status==="eskalasi"?"bad":"acc"}"
      title="putaran ${x.putaran}">${esc(x.kode)} · ${esc(x.status)}</span>`;
  return `<div class="kartu"><h2>Kemajuan</h2>
    <div class="grid g3">
      <div><div class="angka">${D.pertemuan_selesai??0}<span class="kecil"> / ${D.pertemuan_total??"?"}</span></div>
        <div class="kecil">pertemuan disetujui</div></div>
      <div><div class="angka">${siap}<span class="kecil"> / ${D.point_total??p.length}</span></div>
        <div class="kecil">point siap${esk?`, ${esk} eskalasi`:""}</div></div>
      <div><div class="angka">${D.skor_pemeriksaan??"–"}${D.skor_pemeriksaan!=null?"%":""}</div>
        <div class="kecil">skor pemeriksa otomatis</div></div>
    </div>
    ${D.point_aktif?`<p class="kecil" style="margin:12px 0 4px">Sedang dikerjakan:
      <b>point ${esc(D.point_aktif)}</b> ${esc(D.point_judul||"")}</p>`:""}
    <div class="baris" style="margin-top:10px">${p.map(chip).join("")||'<span class="kecil">Belum ada point.</span>'}</div>
  </div>`;
}

function kartuBiaya(){
  const c=D.biaya||{}, k=D.kuota||{};
  const baris=Object.entries(c).filter(([x])=>x!=="total").sort((a,b)=>b[1]-a[1]).slice(0,8)
    .map(([x,v])=>`<tr><td>${esc(x)}</td><td style="text-align:right">${rp(v)}</td></tr>`).join("");
  return `<div class="kartu"><h2>Biaya &amp; kuota</h2>
    <div class="angka">${rp(c.total)}</div>
    <div class="kecil">plafon proyek: ${D.plafon&&Number(D.plafon)>0?rp(D.plafon):"tanpa batas"}</div>
    ${k.status?`<p class="kecil" style="margin-top:8px">Kuota ${esc(k.type||"")}:
      <span class="pil ${k.status==="rejected"?"bad":"warn"}">${esc(k.status)}</span>
      ${k.resets_at?" reset "+esc(k.resets_at):""}</p>`:""}
    <table style="margin-top:10px">${baris||'<tr><td class="kecil">belum ada biaya</td></tr>'}</table>
    <p class="kecil" style="margin-top:8px">Penolakan tool: ${D.penolakan||0} ·
      Opsi: ${esc([D.opsi.slide?"slide":"tanpa slide",
                   D.opsi.ekspor_docx?"DOCX":"tanpa DOCX",
                   D.opsi.ekspor_pptx?"PPTX":"tanpa PPTX",
                   D.opsi.point_halaman+" hal",
                   "maks "+D.opsi.point_maks_putaran+" putaran"].join(" · "))}</p>
  </div>`;
}

function kartuKendali(){
  const tahap=["kurikulum","blueprint","produksi","akhir"];
  const d=D.diagnosa||{};
  const warna={"berjalan":"ok","menunggu-gate":"warn","kunci-basi":"bad","berhenti":""}[d.keadaan]||"";
  return `<div class="kartu"><h2>Kendali &amp; pemulihan</h2>
    <div class="baris" style="margin-bottom:8px">
      <span class="pil ${warna}">${esc(d.keadaan||"?")}</span>
      <span class="kecil">${esc((d.saran||"").split("\n")[0])}</span>
    </div>
    <div class="baris">
      ${D.berjalan?`<button class="bad" onclick="stop()">Hentikan pipeline</button>
          <span class="kecil">PID ${D.pid} · ${esc(D.sekarang||"")}</span>`
        :`<button class="pri" onclick="mulai('lanjut')">Lanjutkan dari titik terakhir</button>
          <select id="tahapPilih" style="width:auto">
            ${tahap.map(t=>`<option${t===D.tahap?" selected":""}>${t}</option>`).join("")}</select>
          <button onclick="mulai('resume')">Mulai dari tahap ini</button>`}
      ${D.kunci_basi?`<button class="bad" onclick="bersihkanKunci()">Bersihkan kunci basi</button>`:""}
    </div>
    <p class="kecil" style="margin-top:8px">Proses yang mati tidak menghilangkan pekerjaan:
      point yang sudah siap tidak ditulis ulang, dan tahap yang terputus disambung dari
      sesi terakhirnya.</p>
  </div>`;
}

function kartuLog(){
  const baris=(D.log||[]);
  return `<div class="kartu"><h2>Log pipeline</h2>
    <div class="baris" style="margin-bottom:8px">
      <button onclick="ikutiLog=!ikutiLog;gambar()">
        ${ikutiLog?"Berhenti mengikuti":"Ikuti baris terbaru"}</button>
      <a href="/api/berkas?project=${encodeURIComponent(D.nama)}&path=docs/pipeline.log"
        target="_blank"><button>Buka log penuh</button></a>
      <span class="kecil">${baris.length} baris terakhir</span>
    </div>
    <div class="log" id="logPipa">${baris.map(b=>esc(b)).join("<br>")||"—"}</div></div>`;
}

function kartuDokumen(){
  const t=(n)=>`<a href="/api/berkas?project=${encodeURIComponent(D.nama)}&path=docs/${n}" target="_blank">${esc(n)}</a>`;
  return `<div class="kartu"><h2>Dokumen perencanaan</h2>
    <p>${D.dokumen.map(t).join(" · ")||'<span class="kecil">Belum ada.</span>'}</p></div>`;
}

function kartuAktivitas(){
  const b=(D.events||[]).slice(-40).reverse().map(e=>{
    const t=new Date(e.t*1000).toLocaleTimeString("id-ID");
    let s;
    switch(e.kind){
      case "stage_start": s=`▶ ${e.label} mulai (${e.model||"?"})`;break;
      case "stage_end": s=`${e.ok?"✓":"✗"} ${e.label} · ${e.turns} turn · ${rp(e.cost)}`;break;
      case "point": s=`✎ point ${e.pertemuan}.${e.point} putaran ${e.putaran} → ${e.status}`;break;
      case "gate": s=`⏸ ${e.label}`;break;
      case "gate_answer": s=`▶ jawaban (${e.source}): ${e.answer}`;break;
      case "pemeriksaan": s=`☑ pemeriksaan: ${e.skor}%`;break;
      case "tool_denied": s=`⛔ ${e.label} ditolak ${e.tool}`;break;
      case "error": s=`!! ${e.label||""} ${e.error}`;break;
      case "jaringan": s=`jaringan putus saat ${e.label} — menunggu ${e.jeda}s (percobaan ${e.percobaan})`;break;
      case "export": s=`📄 ekspor ${e.label}`;break;
      default: return "";}
    return `<div>${t} ${esc(s)}</div>`;}).filter(Boolean).join("");
  return `<div class="kartu"><h2>Aktivitas</h2><div class="log">${b||"—"}</div></div>`;
}

function gambarProyek(){
  const baris=PROYEK.map(p=>`<tr>
    <td><b>${esc(p.nama)}</b>${p.nama===aktif?' <span class="pil acc">aktif</span>':""}
      ${p.gate?`<br><span class="pil warn">gate ${esc(p.gate)}</span>`:""}</td>
    <td>${esc(p.tahap)}</td><td>${p.pertemuan}</td><td>${rp(p.biaya)}</td>
    <td class="kecil">${tgl(p.diubah)}</td>
    <td>${p.berjalan?'<span class="pil ok">berjalan</span>':'<span class="pil">berhenti</span>'}</td>
    <td style="white-space:nowrap">
      <button onclick="buka('${p.nama}')">Buka</button>
      <button onclick="gantiNama('${p.nama}')" ${p.berjalan?"disabled":""}>Ganti nama</button>
      <button onclick="duplikat('${p.nama}')">Duplikat</button>
      <button class="bad" onclick="arsipkan('${p.nama}')" ${p.berjalan?"disabled":""}>Arsipkan</button>
    </td></tr>`).join("");
  const arsip=ARSIP.map(a=>`<tr><td>${esc(a.nama)}</td><td>${a.pertemuan}</td>
    <td>${a.mb} MB</td><td class="kecil">${tgl(a.diubah)}</td>
    <td style="white-space:nowrap">
      <button onclick="pulihkan('${a.nama}')">Pulihkan</button>
      <button class="bad" onclick="hapusArsip('${a.nama}')">Hapus permanen</button>
    </td></tr>`).join("");
  document.getElementById("proyek").innerHTML=
    (PROYEK.length?`<div class="kartu"><h2>Proyek</h2><table>
      <tr><th>Nama</th><th>Tahap</th><th>Pertemuan</th><th>Biaya</th><th>Diubah</th>
        <th>Status</th><th></th></tr>${baris}</table>
      <p class="kecil" style="margin-top:10px">Arsipkan memindahkan proyek ke
        <code>workspace/.arsip</code> — tidak ada berkas yang dihapus, dan bisa dipulihkan
        di bawah. Ganti nama dan arsip hanya bisa saat pipeline berhenti.</p></div>`
    :`<div class="kartu"><h2>Proyek</h2><p>Belum ada proyek.</p>
      <button class="pri" onclick="tab('baru')">Buat proyek pertama</button></div>`)
    +`<div class="kartu"><h2>Arsip</h2>${arsip?`<table>
      <tr><th>Arsip</th><th>Pertemuan</th><th>Ukuran</th><th>Diarsipkan</th><th></th></tr>
      ${arsip}</table>`:'<p class="kecil">Kosong.</p>'}</div>`;
}

function gambarBerkas(){
  const s=(D.silabus||[]).map(x=>`<tr><td>
      <a href="/api/berkas?project=${encodeURIComponent(D.nama)}&path=sumber/${encodeURIComponent(x.nama)}"
        target="_blank">${esc(x.nama)}</a></td>
      <td>${Math.max(1,Math.round(x.byte/1024))} KB</td>
      <td>${x.nama==="silabus.txt"?'<span class="kecil">dipakai pipeline</span>'
        :`<button class="bad" onclick="hapusSilabus('${esc(x.nama)}')">hapus</button>`}</td></tr>`).join("");
  const o=D.opsi||{};
  const adaKlien=(D.dokumen||[]).includes("KLIEN.md");
  document.getElementById("berkas").innerHTML=`
  <div class="grid g2">
    <div class="kartu"><h2>Silabus</h2>
      <table>${s||'<tr><td class="kecil">Belum ada.</td></tr>'}</table>
      <div class="baris" style="margin-top:10px">
        <input type="file" id="fsil2" accept=".md,.txt,.docx,.pdf" style="width:auto"
          onchange="document.getElementById('sil2').textContent=this.files[0]?('siap diunggah: '+this.files[0].name):''">
        <button id="btnSil2" onclick="unggahSilabus()">Unggah</button>
        <span class="kecil" id="sil2"></span></div>
      <p class="kecil">Berkas di tabel di atas sudah tersimpan di proyek. Silabus baru
        dipakai saat tahap Kurikulum dijalankan ulang.</p>
    </div>
    <div class="kartu"><h2>Konteks klien</h2>
      ${adaKlien?`<p><a href="/api/berkas?project=${encodeURIComponent(D.nama)}&path=docs/KLIEN.md"
          target="_blank">KLIEN.md</a>
        <button class="bad" onclick="hapusKlien()">hapus</button></p>`
        :'<p class="kecil">Belum ada. Semua peran membacanya kalau ada.</p>'}
      <div class="baris" style="margin-top:10px">
        <input type="file" id="fkl2" accept=".md,.txt" style="width:auto"
          onchange="document.getElementById('kl2').textContent=this.files[0]?('siap diunggah: '+this.files[0].name):''">
        <button id="btnKl2" onclick="unggahKlien()">Unggah / ganti</button>
        <span class="kecil" id="kl2"></span></div>
    </div>
  </div>
  <div class="kartu"><h2>Opsi produksi proyek ini</h2>
    <div class="grid g3">
      <div><label>Panjang point (halaman)</label><input id="oHal" value="${esc(o.point_halaman||"")}"></div>
      <div><label>Maks. putaran telaah</label><input id="oPut" value="${o.point_maks_putaran||3}"></div>
      <div><label>Model semua peran</label><select id="oModel">
        <option value=""${!o.model?" selected":""}>ikut .env</option>
        ${["opus","sonnet","haiku"].map(m=>`<option${o.model===m?" selected":""}>${m}</option>`).join("")}
      </select></div>
    </div>
    <div class="sw" style="margin-top:12px"><input type="checkbox" id="oSlide" ${o.slide?"checked":""}>
      <label style="margin:0">Buat slide</label></div>
    <div class="sw"><input type="checkbox" id="oDocx" ${o.ekspor_docx?"checked":""}>
      <label style="margin:0">Ekspor DOCX</label></div>
    <div class="sw"><input type="checkbox" id="oPptx" ${o.ekspor_pptx?"checked":""}>
      <label style="margin:0">Ekspor PPTX</label></div>
    <div class="baris" style="margin-top:12px"><button class="pri" onclick="simpanOpsi()">Simpan opsi</button>
      <span class="kecil">Berlaku untuk tahap yang dijalankan setelah ini.</span></div>
  </div>`;
}
async function unggahSilabus(){
  const f=document.getElementById("fsil2").files[0]; if(!f)return pesan("Pilih berkas dulu.");
  const b=document.getElementById("btnSil2"); b.disabled=true; b.textContent="Mengunggah…";
  const fd=new FormData();fd.append("project",aktif);fd.append("silabus",f);
  const j=await api("/api/unggah",{method:"POST",body:fd});
  b.disabled=false; b.textContent="Unggah";
  document.getElementById("sil2").textContent=j.ok?"tersimpan.":"";
  document.getElementById("fsil2").value="";
  pesan(j.msg);muatDetail();}
async function hapusSilabus(n){if(!confirm(`Hapus '${n}'?`))return;
  const j=await post("/api/hapus-silabus",{project:aktif,nama:n});pesan(j.msg);muatDetail();}
async function unggahKlien(){
  const f=document.getElementById("fkl2").files[0]; if(!f)return pesan("Pilih berkas dulu.");
  const b=document.getElementById("btnKl2"); b.disabled=true; b.textContent="Mengunggah…";
  const fd=new FormData();fd.append("project",aktif);fd.append("klien",f);
  const j=await api("/api/unggah-klien",{method:"POST",body:fd});
  b.disabled=false; b.textContent="Unggah / ganti";
  document.getElementById("kl2").textContent=j.ok?"tersimpan.":"";
  document.getElementById("fkl2").value="";
  pesan(j.msg);muatDetail();}
async function hapusKlien(){if(!confirm("Hapus konteks klien?"))return;
  const j=await post("/api/hapus-klien",{project:aktif});pesan(j.msg);muatDetail();}
async function simpanOpsi(){
  const j=await post("/api/opsi",{project:aktif,opsi:{
    point_halaman:document.getElementById("oHal").value,
    point_maks_putaran:document.getElementById("oPut").value,
    model:document.getElementById("oModel").value,
    slide:document.getElementById("oSlide").checked,
    ekspor_docx:document.getElementById("oDocx").checked,
    ekspor_pptx:document.getElementById("oPptx").checked}});
  pesan(j.msg);muatDetail();}

function gambar(){
  document.getElementById("statusPil").innerHTML=statusPil();
  if(TAB==="proyek"){gambarProyek();}
  else if(TAB==="berkas"){gambarBerkas();}
  else if(TAB==="ringkas"){
    // Kotak gate hanya digambar ulang kalau gate-nya BERGANTI. Kalau ikut
    // digambar tiap polling, posisi scroll dan masukan yang sedang diketik
    // hilang tiap 4 detik.
    const kunci=D.gate?`${D.gate.label}@${D.gate.since}`:"";
    if(kunci!==gateKunci){
      gateKunci=kunci;
      document.getElementById("kotakGate").innerHTML=kartuGate();
    }
    document.getElementById("isiRingkas").innerHTML=
      kartuKemajuan()+`<div class="grid g2">${kartuBiaya()}${kartuKendali()}</div>`
      +kartuDokumen()+kartuAktivitas()+kartuLog();
    if(ikutiLog){const l=document.getElementById("logPipa"); if(l)l.scrollTop=l.scrollHeight;}
  }else if(TAB==="materi"){gambarMateri();}
}

// Penyaji Markdown seadanya, cukup untuk berkas yang diproduksi pipeline:
// judul, daftar, tabel, blok kode, kutipan, tebal/miring, dan kode sebaris.
// Semua teks di-escape lebih dulu, jadi isi berkas tidak bisa menyuntik HTML.
function mdKeHtml(teks){
  const baris=String(teks||"").replace(/\r/g,"").split("\n");
  let html="", daftar=null, tabel=null, kode=null, bahasa="";
  const inline=t=>esc(t)
    .replace(/`([^`]+)`/g,(m,x)=>"<code>"+x+"</code>")
    .replace(/\*\*([^*]+)\*\*/g,"<b>$1</b>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g,"$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  const tutupDaftar=()=>{if(daftar){html+=`</${daftar}>`;daftar=null;}};
  const tutupTabel=()=>{if(tabel){html+="</table>";tabel=null;}};
  const selTabel=b=>b.trim().replace(/^\||\|$/g,"").split("|").map(x=>x.trim());
  for(let i=0;i<baris.length;i++){
    const b=baris[i], t=b.trim();
    if(/^```/.test(t)){                                   // blok kode
      if(kode===null){tutupDaftar();tutupTabel();kode=[];
        bahasa=t.replace(/^`+/,"").trim().toLowerCase();}
      else{
        // Blok keluaran dibedakan dari blok perintah: pembaca membandingkan
        // layarnya dengan blok `text`, bukan mengetik ulang isinya.
        const keluaran=(bahasa==="text"||bahasa==="")?" keluaran":"";
        html+=`<pre class="kode${keluaran}"`
            +(bahasa?` data-bahasa="${esc(bahasa)}"`:"")
            +`><code>`+esc(kode.join("\n"))+"</code></pre>";
        kode=null;bahasa="";}
      continue;}
    if(kode!==null){kode.push(b);continue;}
    if(!t){tutupDaftar();tutupTabel();continue;}
    if(/^\|/.test(t)){                                    // tabel
      const sel=selTabel(t);
      if(/^[\s|:-]+$/.test(t))continue;                   // baris pemisah
      if(!tabel){tutupDaftar();html+="<table>";tabel="th";
        html+="<tr>"+sel.map(x=>"<th>"+inline(x)+"</th>").join("")+"</tr>";continue;}
      html+="<tr>"+sel.map(x=>"<td>"+inline(x)+"</td>").join("")+"</tr>";continue;}
    tutupTabel();
    let m=t.match(/^(#{1,6})\s+(.*)$/);
    if(m){tutupDaftar();const n=Math.min(m[1].length,4);
      html+=`<h${n}>${inline(m[2])}</h${n}>`;continue;}
    if(/^(---+|\*\*\*+)$/.test(t)){tutupDaftar();html+="<hr>";continue;}
    if(/^>\s?/.test(t)){tutupDaftar();
      html+="<blockquote><p>"+inline(t.replace(/^>\s?/,""))+"</p></blockquote>";continue;}
    m=t.match(/^[-*+]\s+(.*)$/);
    if(m){if(daftar!=="ul"){tutupDaftar();html+="<ul>";daftar="ul";}
      html+="<li>"+inline(m[1])+"</li>";continue;}
    m=t.match(/^(\d+)[.)]\s+(.*)$/);
    if(m){if(daftar!=="ol"){tutupDaftar();html+="<ol>";daftar="ol";}
      html+="<li>"+inline(m[2])+"</li>";continue;}
    tutupDaftar();
    html+="<p>"+inline(t)+"</p>";}
  tutupDaftar();tutupTabel();
  if(kode!==null)html+="<pre><code>"+esc(kode.join("\n"))+"</code></pre>";
  return html;
}

function gambarBaca(){
  const el=document.getElementById("panelBaca"); if(!el)return;
  // Panel ini ikut terpanggil tiap penyegaran 4 detik. Menulis innerHTML saat
  // isinya sama membuat posisi scroll pembaca melompat ke atas, jadi hanya
  // digambar ulang kalau berkas atau mode tampilannya berganti.
  const kunci=BACA?`${BACA.path}|${bacaMentah}|${(BACA.isi||"").length}`:"kosong";
  if(kunci===bacaTanda&&el.dataset.terisi==="1")return;
  bacaTanda=kunci; el.dataset.terisi="1";
  if(!BACA){el.innerHTML='<h2>Pembaca</h2><p class="kecil">Pilih berkas di kiri '
    +'untuk membacanya di sini.</p>';return;}
  const md=/\.md$/i.test(BACA.nama||"");
  el.innerHTML=`<div class="bacaKepala">
      <h2 style="margin:0">${esc(BACA.nama)}</h2>
      <div class="baris">
        ${md?`<button onclick="bacaMentah=!bacaMentah;gambarBaca()">
          ${bacaMentah?"Tampilkan terformat":"Tampilkan teks mentah"}</button>`:""}
        <a href="/api/berkas?project=${encodeURIComponent(D.nama)}&path=${encodeURIComponent(BACA.path)}"
          target="_blank"><button>Buka berkas</button></a>
      </div></div>
    ${(md&&!bacaMentah)?`<div class="doc">${mdKeHtml(BACA.isi)}</div>`
      :`<pre>${esc(BACA.isi)}</pre>`}
    ${BACA.terpotong?'<p class="kecil">Isi dipotong karena berkasnya sangat besar.</p>':""}`;
}

function gambarMateri(){
  const pohon=D.pohon||[];
  const daftar=pohon.map(p=>`<div style="margin-bottom:10px">
      <div class="kecil" style="font-weight:600;color:var(--fg)">${esc(p.nama)}</div>
      ${p.berkas.map(b=>`<div class="item ${berkasAktif===b.path?"on":""}"
        onclick="bukaBerkas('${b.path}')"><span>${esc(b.nama)}</span>
        <span class="kecil">${b.kb} KB</span></div>`).join("")}</div>`).join("");
  const zip=(q)=>`/api/zip?project=${encodeURIComponent(D.nama)}${q}`;
  const unduh=(D.materi||[]).map(m=>`<tr><td>${esc(m.nama)}</td><td>${m.point}</td>
      <td>${m.disetujui?"✓":"—"}</td>
      <td>${m.unduh.map(f=>`<a href="/api/berkas?project=${encodeURIComponent(D.nama)}&path=materi/${m.nama}/${f}" target="_blank">${esc(f)}</a>`).join(" · ")||"—"}</td>
      <td style="white-space:nowrap">
        <a href="${zip("&pertemuan="+m.nama)}"><button>.zip</button></a>
        ${m.slide?"":`<button onclick="buatSlide('${m.nama.replace("pertemuan-","")}')">Buat slide</button>`}
        ${m.bahan_kurang?`<button onclick="buatBahan('${m.nama.replace("pertemuan-","")}')"
          title="${m.bahan_kurang} berkas ditampilkan di materi tetapi belum diserahkan"
          >Buat bahan kerja (${m.bahan_kurang})</button>`:""}
      </td></tr>`).join("");
  const adaTanpaSlide=(D.materi||[]).some(m=>!m.slide&&m.point>0);
  const kurangBahan=(D.materi||[]).reduce((n,m)=>n+(m.bahan_kurang||0),0);
  // Tab ini ikut disegarkan tiap 4 detik. Kalau innerHTML ditulis ulang tiap
  // kali, isi pembaca dan posisi scroll hilang — jadi hanya digambar ulang
  // kalau daftar berkasnya benar-benar berubah.
  const tanda=JSON.stringify([berkasAktif,
    (D.materi||[]).map(m=>[m.nama,m.point,m.disetujui,m.slide,m.bahan_kurang,m.unduh.length]),
    (D.pohon||[]).map(p=>[p.nama,p.berkas.map(b=>[b.nama,b.kb])])]);
  if(tanda===materiTanda){gambarBaca();return;}
  materiTanda=tanda;
  document.getElementById("materi").innerHTML=`
    <div class="kartu"><h2>Unduhan</h2>
      <div class="baris" style="margin-bottom:10px">
        <a href="${zip("")}"><button class="pri">Unduh semua materi (.zip)</button></a>
        <a href="${zip("&lengkap=1")}"><button>.zip termasuk catatan telaah</button></a>
        ${adaTanpaSlide?`<button onclick="buatSlide('semua')">Buat slide untuk semua pertemuan</button>`:""}
        ${kurangBahan?`<button onclick="buatBahan('semua')">Buat bahan kerja untuk semua pertemuan (${kurangBahan} berkas)</button>`:""}
      </div>
      <table>
      <tr><th>Pertemuan</th><th>Point</th><th>Disetujui</th><th>Berkas</th><th></th></tr>
      ${unduh||'<tr><td class="kecil">Belum ada materi.</td></tr>'}</table>
      <p class="kecil" style="margin-top:8px">Zip berisi materi ajar saja; catatan proses
        (review, catatan Writer) hanya ikut di zip kedua.</p></div>
    <div class="sisi">
      <div class="kartu"><h2>Berkas</h2><div class="daftar">${daftar||'<span class="kecil">Belum ada.</span>'}</div></div>
      <div class="kartu" id="panelBaca"></div>
    </div>`;
  bacaTanda="";          // panel baru: isinya memang harus digambar sekali
  gambarBaca();
}

async function buatSlide(pertemuan){
  if(!confirm(pertemuan==="semua"
      ?"Buat slide untuk semua pertemuan yang belum punya slide?\n\nIni memanggil model dan menambah biaya."
      :`Buat slide untuk pertemuan ${pertemuan}?\n\nIni memanggil model dan menambah biaya.`))return;
  const j=await post("/api/slide",{project:aktif,pertemuan});pesan(j.msg);muatDetail();}

let MOODLE=null;

async function muatMoodle(){
  const el=document.getElementById("moodle");
  if(!aktif){el.innerHTML='<div class="kartu"><p class="kecil">Pilih proyek dulu di tab Proyek.</p></div>';return;}
  const j=await api("/api/moodle?project="+encodeURIComponent(aktif));
  if(!j.ok){el.innerHTML=`<div class="kartu"><p class="kecil">${esc(j.msg||"Gagal membaca proyek.")}</p></div>`;return;}
  MOODLE=j; gambarMoodle();
}

function gambarMoodle(){
  const j=MOODLE, k=j.komposisi, r=j.rencana, s=j.setelan;
  const el=document.getElementById("moodle");

  // Setelan yang belum lengkap menghentikan unggahan, jadi disebut lebih dulu.
  const kurang=[];
  if(!s.url) kurang.push("URL server MCP");
  if(!s.token) kurang.push("Token web service");
  if(!s.kategori) kurang.push("Id kategori kursus");
  const blokSetelan=kurang.length
    ? `<div class="kartu"><h2>Setelan Moodle belum lengkap</h2>
        <p class="kecil">Belum diisi: <b>${kurang.map(esc).join(", ")}</b>.
        Isi di tab Pengaturan, grup Moodle.</p></div>` : "";

  const baris=k.pertemuan.map(x=>`<tr>
      <td>${x.no}</td><td>${esc(x.judul.slice(0,52))}</td>
      <td>${x.berkas.length||"—"}</td>
      <td>${x.quiz?"✓":"—"}</td><td>${x.praktik?"✓":"—"}</td>
      <td>${x.bahan?"✓":"—"}</td>
      <td>${x.siap?'<span class="pil ok">siap</span>':'<span class="pil bad">belum ada materi</span>'}</td>
    </tr>`).join("");

  const blokKomposisi=`<div class="kartu"><h2>Yang akan diunggah</h2>
    <table><tr><th>#</th><th>Pertemuan</th><th>Berkas</th><th>Quiz</th>
      <th>Praktik</th><th>Bahan</th><th></th></tr>${baris}</table>
    <p class="kecil" style="margin-top:8px">Dibaca dari proyek — bukan dari
      pengaturan. Pertemuan tanpa materi tidak ikut diunggah.</p></div>`;

  if(!r){
    el.innerHTML=blokSetelan+blokKomposisi+`<div class="kartu"><h2>Rencana unggah</h2>
      <p class="kecil">Belum ada rencana. Peran Moodle akan menyusunnya dari materi
        proyek ini: nama kursus, judul section, instruksi tiap tugas, pertanyaan
        feedback, dan bobot penilaian. <b>LMS belum disentuh sama sekali.</b></p>
      <div style="margin-top:10px"><label>Nama batch</label>
        <input id="mdBatch" placeholder="mis. Batch 2 — Oktober 2026"></div>
      <div class="baris" style="margin-top:10px">
        <button class="pri" onclick="susunRencana(false)">Susun rencana</button>
        <span class="kecil">Memanggil model, perkiraan di bawah $1.</span>
      </div></div>`;
    return;
  }

  const b=r.penilaian.bobot, al=r.penilaian.alasan||{};
  const bobotBaris=["quiz","praktik","proyek","kehadiran"].map(x=>`
    <tr><td style="text-transform:capitalize">${x}</td>
      <td style="white-space:nowrap"><input type="number" min="0" max="100"
        id="mdB-${x}" value="${b[x]}" style="width:72px" oninput="hitungTotal()">%</td>
      <td class="kecil">${esc(al[x]||"")}</td></tr>`).join("");

  const masalah=(j.masalah||[]);
  const blokMasalah=masalah.length
    ? `<div class="kartu"><h2>Rencana belum bisa dijalankan</h2>
        <ul class="kecil">${masalah.map(m=>`<li>${esc(m)}</li>`).join("")}</ul>
        <p class="kecil">Perbaiki di sini, atau susun ulang rencananya.</p></div>` : "";

  const hasil=j.hasil?`<div class="kartu"><h2>Sudah pernah diunggah</h2>
      <p class="kecil">Kursus id <b>${j.hasil.kursus_id}</b>,
        ${j.hasil.pertemuan.length} pertemuan —
        ${j.hasil.masih_ada===false
            ? '<b>sudah tidak ada di Moodle</b> (dihapus di sana)'
            : j.hasil.masih_ada===null
              ? 'statusnya tidak bisa diperiksa sekarang'
              : 'masih ada di Moodle'}.
        Mengunggah lagi membuat kursus <b>baru</b>, bukan memperbarui yang itu.</p></div>`:"";

  el.innerHTML=blokSetelan+blokKomposisi+blokMasalah+`
    <div class="kartu"><h2>Rencana unggah</h2>
      <div class="grid g2">
        <div><label>Nama kursus</label>
          <input id="mdNama" value="${esc(r.kursus.fullname)}"></div>
        <div><label>Kode kursus (shortname)</label>
          <input id="mdShort" value="${esc(r.kursus.shortname)}"></div>
      </div>
      <p class="kecil" style="margin-top:10px">Tiap pertemuan mendapat folder
        materi, quiz, tugas praktik, dan feedback sesuai yang ada di proyek.</p>
      <table style="margin-top:6px"><tr><th>#</th><th>Section</th><th>Folder</th>
        <th>Quiz</th><th>Praktik</th><th>Feedback</th></tr>
        ${r.pertemuan.map(x=>`<tr><td>${x.no}</td>
          <td>${esc((x.section||"").slice(0,40))}</td>
          <td>${x.folder_materi?esc(x.folder_materi.nama):"—"}</td>
          <td>${x.quiz?esc(x.quiz.nama):"—"}</td>
          <td>${x.praktik?esc(x.praktik.nama):"—"}</td>
          <td>${x.feedback?`${esc(x.feedback.nama)} (${(x.feedback.pertanyaan||[]).length})`:"—"}</td>
        </tr>`).join("")}
      </table>
      ${r.proyek_akhir?`<p class="kecil" style="margin-top:8px">Proyek akhir:
        <b>${esc(r.proyek_akhir.nama)}</b> di pertemuan ${r.proyek_akhir.pertemuan}.</p>`:""}
      <p class="kecil">Absensi: <b>${esc((r.absensi||{}).nama||"Absensi Pelatihan")}</b>
        — modul dibuat, sesinya diisi trainer di Moodle.</p>
    </div>

    <div class="kartu"><h2>Penilaian</h2>
      <table><tr><th>Kategori</th><th>Bobot</th><th>Alasan</th></tr>${bobotBaris}
        <tr><td><b>Total</b></td><td><b id="mdTotal">—</b></td>
          <td class="kecil">harus tepat 100</td></tr>
        <tr><td>Nilai lulus</td>
          <td><input type="number" min="50" max="100" id="mdLulus"
            value="${r.penilaian.nilai_lulus}" style="width:72px">%</td>
          <td class="kecil">batas lulus kursus</td></tr></table>
      <p class="kecil" style="margin-top:8px">Bobot disusun peran Moodle dari
        komposisi pelatihan ini. Kalau diubah, alasannya tidak ikut berubah.
        Hitungan cadangan tanpa model:
        quiz ${j.bobot_hitungan.quiz} / praktik ${j.bobot_hitungan.praktik} /
        proyek ${j.bobot_hitungan.proyek} / kehadiran ${j.bobot_hitungan.kehadiran}.</p>
    </div>

    ${hasil}

    <div class="kartu"><h2>Unggah</h2>
      <div class="grid g2">
        <div><label>Kategori Moodle</label>
          <select id="mdKat"><option value="">memuat dari Moodle…</option></select></div>
        <div><label>Kursus template <span class="kecil">(opsional)</span></label>
          <select id="mdTpl"><option value="">memuat dari Moodle…</option></select></div>
      </div>
      <p class="kecil" id="mdPilihanPesan" style="margin-top:6px"></p>
      <p class="kecil">Kursus <b>selalu dibuat baru</b> dari materi proyek ini.
        Template hanya menumpangkan isi kursus lain di atasnya — berguna kalau ada
        pengaturan atau halaman baku yang ingin ikut, dan sebaiknya
        <b>dikosongkan</b> untuk materi yang berdiri sendiri.</p>
      <div class="baris" style="margin-top:12px">
        <button onclick="simpanRencana()">Simpan perubahan</button>
        <button onclick="susunRencana(true)">Susun ulang rencana</button>
        <button class="pri" onclick="unggahMoodle()"
          ${masalah.length?"disabled":""}>Unggah ke Moodle</button>
      </div>
      <p class="kecil" style="margin-top:8px">Unggah dikerjakan kode biasa tanpa
        model. Kursus dibuat baru tiap kali ditekan.</p>
      <pre id="mdLog" style="margin-top:10px;display:none"></pre>
    </div>`;
  hitungTotal();
  isiPilihanMoodle(s);
}

async function isiPilihanMoodle(s){
  const kat=document.getElementById("mdKat"), tpl=document.getElementById("mdTpl");
  if(!kat||!tpl)return;
  const pesan=document.getElementById("mdPilihanPesan");
  const j=await api("/api/moodle-pilihan");
  if(!j.ok){
    // Tanpa daftar, id tetap bisa diisi tangan supaya Moodle yang sedang
    // bermasalah tidak mengunci fitur ini sama sekali.
    kat.outerHTML='<input id="mdKat" placeholder="id kategori" value="'+(s.kategori||"")+'">';
    tpl.outerHTML='<input id="mdTpl" placeholder="id template" value="'+(s.template||"")+'">';
    pesan.innerHTML='<b>'+esc(j.msg||"Daftar tidak bisa diambil")+'</b> — isi id-nya manual.';
    return;
  }
  kat.innerHTML=j.kategori.map(c=>
    `<option value="${c.id}" ${String(c.id)===String(s.kategori)?"selected":""}>${esc(c.nama)} (${c.jumlah} kursus)</option>`).join("");
  tpl.innerHTML='<option value="">— tanpa template —</option>'+j.kursus.map(c=>
    `<option value="${c.id}" ${String(c.id)===String(s.template)?"selected":""}>${esc(c.nama.slice(0,60))} · ${esc(c.kode)}</option>`).join("");
  pesan.textContent=`${j.kategori.length} kategori dan ${j.kursus.length} kursus dibaca dari Moodle.`;
}

function hitungTotal(){
  const el=document.getElementById("mdTotal"); if(!el)return;
  let n=0; for(const x of ["quiz","praktik","proyek","kehadiran"]){
    const i=document.getElementById("mdB-"+x); if(i)n+=Number(i.value||0);}
  el.textContent=n+"%"; el.style.color=(n===100)?"var(--ok)":"var(--bad)";
}

function rencanaDariForm(){
  const r=JSON.parse(JSON.stringify(MOODLE.rencana));
  r.kursus.fullname=document.getElementById("mdNama").value.trim();
  r.kursus.shortname=document.getElementById("mdShort").value.trim().toUpperCase();
  for(const x of ["quiz","praktik","proyek","kehadiran"])
    r.penilaian.bobot[x]=Number(document.getElementById("mdB-"+x).value||0);
  r.penilaian.nilai_lulus=Number(document.getElementById("mdLulus").value||70);
  return r;
}

async function simpanRencana(){
  const j=await post("/api/moodle-simpan",{project:aktif,rencana:rencanaDariForm()});
  pesan(j.msg+((j.masalah||[]).length?" — "+j.masalah.join("; "):""));
  await muatMoodle();
}

async function susunRencana(ulang){
  if(ulang&&!confirm("Susun ulang rencana? Suntingan Anda pada rencana yang ada akan ditimpa."))return;
  const batch=(document.getElementById("mdBatch")||{}).value||"";
  const j=await post("/api/moodle-rencana",{project:aktif,batch,ulang:ulang?"ulang":""});
  pesan(j.msg);
}

async function unggahMoodle(){
  if(!confirm("Unggah ke Moodle sekarang?\n\nKursus BARU akan dibuat di LMS. "
    +"Materi proyek tidak berubah."))return;
  const log=document.getElementById("mdLog");
  log.style.display="block"; log.textContent="Mengunggah…";
  const j=await post("/api/moodle-unggah",{project:aktif,
    kategori:document.getElementById("mdKat").value,
    template:document.getElementById("mdTpl").value});
  log.textContent=(j.log||[]).join("\n")+"\n\n"+(j.msg||"");
  pesan(j.msg); await muatMoodle();
}

async function buatBahan(pertemuan){
  if(!confirm(pertemuan==="semua"
      ?"Bangun berkas kerja peserta untuk semua pertemuan?\n\nPoint, handbook, latihan, "
       +"dan quiz TIDAK disentuh. Ini memanggil model dan menambah biaya."
      :`Bangun berkas kerja peserta untuk pertemuan ${pertemuan}?\n\nPoint, handbook, `
       +`latihan, dan quiz TIDAK disentuh. Ini memanggil model dan menambah biaya.`))return;
  const j=await post("/api/bahan",{project:aktif,pertemuan});pesan(j.msg);muatDetail();}

async function bukaBerkas(path){
  berkasAktif=path; gambarMateri();
  const j=await api(`/api/isi?project=${encodeURIComponent(aktif)}&path=${encodeURIComponent(path)}`);
  BACA={path, nama:j.nama||path.split("/").pop(), isi:j.isi||j.error||"",
        terpotong:!!j.terpotong};
  gambarBaca();
}

async function muatSetelan(){
  const j=await api("/api/setelan"); SET=j.setelan||[]; gambarSetelan();
  isiSetelanMoodle();
}

async function isiSetelanMoodle(){
  const kolom=[...document.querySelectorAll("#setelan select[data-sumber]")];
  if(!kolom.length)return;
  const j=await api("/api/moodle-pilihan");
  for(const el of kolom){
    const nilai=el.value;
    if(!j.ok){
      // LMS tidak terjawab: kembalikan ke isian id supaya setelan tetap
      // bisa diubah, dan katakan kenapa daftarnya tidak muncul.
      el.outerHTML='<input id="'+el.id+'" value="'+esc(nilai)+'" '+
        'title="'+esc(j.msg||"")+'" placeholder="id — daftar nama tidak bisa diambil">';
      continue;
    }
    const daftar=el.dataset.sumber==="kategori"
      ? j.kategori.map(c=>[c.id, c.nama+" ("+c.jumlah+" kursus)"])
      : j.kursus.map(c=>[c.id, c.nama.slice(0,60)+" · "+c.kode]);
    const kosong=el.dataset.sumber==="kategori"
      ? "— belum dipilih —" : "— tanpa template —";
    el.innerHTML='<option value="">'+kosong+'</option>'+
      daftar.map(([id,teks])=>
        `<option value="${id}" ${String(id)===String(nilai)?"selected":""}>${esc(teks)}</option>`).join("");
    // Id yang tersimpan tetapi kursusnya sudah tidak ada tidak boleh hilang
    // diam-diam — kalau lenyap, unggahan berikutnya gagal tanpa sebab jelas.
    if(nilai && el.value!==String(nilai)){
      el.insertAdjacentHTML("afterbegin",
        `<option value="${esc(nilai)}" selected>id ${esc(nilai)} — sudah tidak ada di Moodle</option>`);
    }
  }
}
function gambarSetelan(){
  const grup={};
  for(const s of SET){(grup[s.grup]=grup[s.grup]||[]).push(s);}
  const kolom=s=>{
    const id="set-"+s.kunci;
    if(s.tipe==="pilihan")
      return `<div><label>${esc(s.label)}</label><select id="${id}">
        ${s.pilihan.map(p=>`<option${p===s.nilai?" selected":""}>${esc(p)}</option>`).join("")}</select></div>`;
    if(s.tipe==="moodle")
      // Diisi setelah kartu tergambar; nilai sekarang ditahan di option
      // sementara supaya tidak hilang kalau daftar gagal diambil.
      return `<div><label>${esc(s.label)}</label>
        <select id="${id}" data-sumber="${esc(s.sumber||"")}">
          <option value="${esc(s.nilai)}" selected>${s.nilai?"id "+esc(s.nilai):"— kosong —"} · memuat…</option>
        </select></div>`;
    const ph=s.tipe==="sandi"?(s.terisi?"terisi — kosongkan untuk membiarkan":"belum diisi"):"";
    return `<div><label>${esc(s.label)}${s.tipe==="sandi"&&s.terisi?' <span class="pil ok">terisi</span>':""}</label>
      <input id="${id}" ${s.tipe==="sandi"?'type="password"':""} value="${esc(s.nilai)}" placeholder="${esc(ph)}"></div>`;};
  const akun=document.getElementById("akun").textContent||"";
  const kartuAkun=`<div class="kartu"><h2>Akun yang dipakai pipeline</h2>
    <p>${esc(akun||"-")}</p>
    <p class="kecil">Pipeline memakai login <code>claude</code> di mesin ini, sama dengan
      editor — jadi kuotanya dipakai bersama.</p>
    <p class="kecil"><b>Ganti akun langganan:</b> jalankan <code>claude</code> di terminal
      lalu <code>/login</code>. Tidak bisa dari sini karena butuh alur login lewat browser.
      Akun baru dipakai mulai tahap berikutnya, jadi paling aman dilakukan saat pipeline
      menunggu gate.</p>
    <p class="kecil"><b>Pakai API key terpisah:</b> isi <code>ANTHROPIC_API_KEY</code> di
      grup Autentikasi di bawah. Pipeline lalu memakai kredit API dan berhenti memotong
      kuota langganan Anda.</p>
    <div class="baris" style="margin-top:10px">
      <button onclick="terapkanSetelan()">Terapkan ke pipeline yang sedang berjalan</button>
      <span class="kecil">Pipeline dihentikan lalu dilanjutkan dari titik terakhir —
        setelan baru baru berlaku setelah ini.</span>
    </div></div>`;
  document.getElementById("setelan").innerHTML=kartuAkun+
    Object.entries(grup).map(([g,l])=>`<div class="kartu"><h2>${esc(g)}</h2>
      <div class="grid g3">${l.map(kolom).join("")}</div>
      ${g==="Telegram"?`<div class="baris" style="margin-top:12px">
        <button onclick="ujiTelegram()">Kirim pesan uji</button>
        <span class="kecil">Menguji token dan chat id dengan mengirim satu pesan nyata.</span></div>`:""}
      </div>`).join("")
    +`<div class="baris"><button class="pri" onclick="simpanSetelan()">Simpan pengaturan</button>
      <span class="kecil">Kolom rahasia yang dikosongkan tidak mengubah nilai lama.</span></div>`;
}
async function terapkanSetelan(){
  if(!aktif)return pesan("Pilih proyek dulu di tab Proyek.");
  if(!confirm(`Hentikan pipeline proyek "${aktif}" lalu jalankan lagi dengan setelan baru?\n\n`
    +`Tidak ada pekerjaan yang hilang: point yang sudah siap tidak ditulis ulang.`))return;
  pesan("Menerapkan setelan…");
  const j=await post("/api/terapkan-setelan",{project:aktif});pesan(j.msg);muatDetail();}

async function simpanSetelan(){
  const d={};
  for(const s of SET){const e=document.getElementById("set-"+s.kunci); if(e)d[s.kunci]=e.value;}
  const j=await post("/api/setelan",{setelan:d}); pesan(j.msg); muatSetelan();
}
async function ujiTelegram(){
  const t=document.getElementById("set-TELEGRAM_BOT_TOKEN").value;
  const c=document.getElementById("set-TELEGRAM_CHAT_ID").value;
  pesan("Mengirim pesan uji…");
  const j=await post("/api/uji-telegram",{token:t,chat:c}); pesan(j.msg);
}

function gambarBaru(){
  const o=BAWAAN||{point_halaman:"10–20",point_maks_putaran:3};
  document.getElementById("baru").innerHTML=`
  <div class="kartu"><h2>1. Silabus <span class="pil" id="statusSil">belum dipilih</span></h2>
    <div class="drop" id="drop" onclick="document.getElementById('fsil').click()">
      <div id="dropIsi"><b>Seret berkas silabus ke sini</b><br>
        <span class="kecil">.md, .txt, .docx, .pdf — atau klik untuk memilih</span></div></div>
    <input type="file" id="fsil" accept=".md,.txt,.docx,.pdf" hidden onchange="pilihSilabus()">
    <div style="margin-top:12px"><label>Atau tempel teks silabus</label>
      <textarea id="teksSil" oninput="cekSiap()"
        placeholder="Pertemuan 1: ...&#10;Point:&#10;1. ...&#10;2. ..."></textarea></div>
    <p class="kecil">Berkas baru benar-benar diunggah saat Anda menekan
      <b>Buat proyek &amp; mulai</b> di bawah.</p>
  </div>
  <div class="grid g2">
    <div class="kartu"><h2>2. Proyek</h2>
      <div><label>Nama proyek</label>
        <input id="nmProyek" oninput="cekSiap()" placeholder="mis. ai-produktivitas-dika"></div>
      <div style="margin-top:10px"><label>Pertemuan pilot (kosong = pertemuan pertama)</label>
        <input id="pilotNo" inputmode="numeric" placeholder="1"></div>
      <div style="margin-top:10px"><label>Konteks klien (opsional, .md)</label>
        <input type="file" id="fklien" accept=".md,.txt" onchange="pilihKlien()">
        <div id="namaKlien" class="kecil" style="margin-top:6px"></div></div>
    </div>
    <div class="kartu"><h2>3. Opsi produksi</h2>
      <div class="grid g2">
        <div><label>Panjang point (halaman)</label><input id="opHal" value="${esc(o.point_halaman)}"></div>
        <div><label>Maks. putaran telaah</label><input id="opPut" value="${o.point_maks_putaran}"></div>
      </div>
      <div style="margin-top:10px"><label>Model semua peran</label>
        <select id="opModel"><option value="">ikut .env</option>
          <option>opus</option><option>sonnet</option><option>haiku</option></select></div>
      <div class="sw" style="margin-top:12px"><input type="checkbox" id="opSlide" ${o.slide!==false?"checked":""}>
        <label style="margin:0">Buat slide (matikan untuk hemat biaya)</label></div>
      <div class="sw"><input type="checkbox" id="opDocx" ${o.ekspor_docx!==false?"checked":""}>
        <label style="margin:0">Ekspor DOCX</label></div>
      <div class="sw"><input type="checkbox" id="opPptx" ${o.ekspor_pptx!==false?"checked":""}>
        <label style="margin:0">Ekspor PPTX</label></div>
      <div class="sw" style="margin-top:12px"><input type="checkbox" id="opMax" onchange="presetMax()">
        <label style="margin:0"><b>Mutu maksimal</b> — tanpa plafon biaya, 5 putaran telaah</label></div>
      <p class="kecil">Kuota langganan tetap dapat menunda pekerjaan; pipeline menunggu reset lalu lanjut sendiri.</p>
    </div>
  </div>
  <div class="baris"><button class="pri" id="tblBuat" onclick="buatProyek()" disabled>
      Buat proyek &amp; mulai</button>
    <span class="kecil" id="alasanBuat">Pilih silabus dan isi nama proyek dulu.</span></div>`;
  const d=document.getElementById("drop");
  d.ondragover=e=>{e.preventDefault();d.classList.add("over");};
  d.ondragleave=()=>d.classList.remove("over");
  d.ondrop=e=>{e.preventDefault();d.classList.remove("over");
    document.getElementById("fsil").files=e.dataTransfer.files;pilihSilabus();};
  cekSiap();
}
const kb=b=>Math.max(1,Math.round(b/1024))+" KB";
function pilihSilabus(){
  const f=document.getElementById("fsil").files[0];
  const d=document.getElementById("drop"), isi=document.getElementById("dropIsi");
  if(f){
    d.classList.add("terisi");
    isi.innerHTML=`<div class="berkas"><b>✓ ${esc(f.name)}</b>
      <span class="kecil">${kb(f.size)} · belum diunggah</span>
      <button onclick="event.stopPropagation();batalSilabus()">Ganti</button></div>`;
    const n=document.getElementById("nmProyek");
    if(!n.value)n.value=f.name.replace(/\.[^.]+$/,"").toLowerCase()
      .replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,40);
  }else{
    d.classList.remove("terisi");
    isi.innerHTML=`<b>Seret berkas silabus ke sini</b><br>
      <span class="kecil">.md, .txt, .docx, .pdf — atau klik untuk memilih</span>`;
  }
  cekSiap();
}
function batalSilabus(){document.getElementById("fsil").value="";pilihSilabus();}
function pilihKlien(){
  const f=document.getElementById("fklien").files[0];
  document.getElementById("namaKlien").innerHTML=
    f?`<span class="pil ok">✓ ${esc(f.name)} · ${kb(f.size)} · belum diunggah</span>`:"";
}
function cekSiap(){
  const f=document.getElementById("fsil"); if(!f)return;
  const adaBerkas=!!f.files[0], teks=document.getElementById("teksSil").value.trim();
  const nama=document.getElementById("nmProyek").value.trim();
  const namaOk=/^[A-Za-z0-9_-]+$/.test(nama);
  const st=document.getElementById("statusSil");
  st.textContent=adaBerkas?"berkas dipilih":(teks?"teks ditempel":"belum dipilih");
  st.className="pil "+((adaBerkas||teks)?"ok":"");
  let alasan="";
  if(!adaBerkas&&!teks)alasan="Pilih berkas silabus, atau tempel teksnya.";
  else if(!nama)alasan="Isi nama proyek.";
  else if(!namaOk)alasan="Nama proyek hanya boleh huruf, angka, - dan _.";
  document.getElementById("tblBuat").disabled=!!alasan;
  document.getElementById("alasanBuat").textContent=
    alasan||"Silabus diunggah lalu pipeline berjalan sampai gate pertama.";
}
function presetMax(){if(document.getElementById("opMax").checked){
  document.getElementById("opPut").value=5;
  document.getElementById("opModel").value="opus";}}

async function buatProyek(){
  const fd=new FormData();
  fd.append("nama",document.getElementById("nmProyek").value.trim());
  const f=document.getElementById("fsil").files[0]; if(f)fd.append("silabus",f);
  const k=document.getElementById("fklien").files[0]; if(k)fd.append("klien",k);
  fd.append("teks",document.getElementById("teksSil").value);
  fd.append("pilot",document.getElementById("pilotNo").value);
  fd.append("point_halaman",document.getElementById("opHal").value);
  fd.append("point_maks_putaran",document.getElementById("opPut").value);
  fd.append("model",document.getElementById("opModel").value);
  fd.append("slide",document.getElementById("opSlide").checked?"1":"0");
  fd.append("ekspor_docx",document.getElementById("opDocx").checked?"1":"0");
  fd.append("ekspor_pptx",document.getElementById("opPptx").checked?"1":"0");
  if(document.getElementById("opMax").checked)fd.append("mutu_maksimal","1");
  const tbl=document.getElementById("tblBuat");
  tbl.disabled=true; const teksLama=tbl.textContent; tbl.textContent="Mengunggah…";
  document.getElementById("alasanBuat").textContent="Mengunggah silabus dan menjalankan pipeline…";
  const j=await api("/api/proyek-baru",{method:"POST",body:fd});
  tbl.textContent=teksLama; tbl.disabled=false;
  pesan(j.msg||"Selesai.");
  document.getElementById("alasanBuat").textContent=j.msg||"";
  if(j.ok){aktif=j.project;await muatDaftar();tab("ringkas");}
}

async function mulai(aksi){
  const t=document.getElementById("tahapPilih");
  const j=await post("/api/mulai",{project:aktif,aksi,teks:aksi==="resume"?(t?t.value:""):""});
  pesan(j.msg);muatDetail();}
async function bersihkanKunci(){
  const j=await post("/api/bersihkan-kunci",{project:aktif});pesan(j.msg);muatDetail();}
async function stop(){const j=await post("/api/stop",{project:aktif});pesan(j.msg);muatDetail();}
async function jawab(t){if(!String(t||"").trim())return pesan("Jawaban kosong.");
  const j=await post("/api/gate",{project:aktif,jawaban:t});
  pesan(j.msg);
  if(j.ok){gateKunci="terkirim";
    document.getElementById("kotakGate").innerHTML=
      '<div class="kartu"><h2>Jawaban terkirim</h2><p class="kecil">Menunggu pipeline '
      +'melanjutkan…</p></div>';}
  muatDetail();}

muatDaftar();muatArsip();
setInterval(()=>{if(TAB!=="baru"&&TAB!=="setelan"&&aktif){muatDetail();}},4000);
setInterval(muatDaftar,15000);
</script></body></html>
""".replace("__GAYA__", GAYA)


# ---------------------------------------------------------------------------
def main():
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("DASHBOARD_PORT", 8770) or 8770)
    lokal = host in ("127.0.0.1", "localhost", "::1")

    # Panel ini menjalankan pipeline, dan peran Tugas di dalamnya punya akses
    # Bash. Membukanya ke jaringan tanpa sandi berarti menyerahkan eksekusi
    # perintah ke siapa pun yang bisa menjangkau port ini.
    if not lokal and not (os.getenv("DASHBOARD_PASS") or "").strip():
        print(f"DASHBOARD_HOST={host} bukan alamat lokal, tetapi DASHBOARD_PASS kosong.\n"
              f"Isi DASHBOARD_PASS di .env, atau biarkan DASHBOARD_HOST=127.0.0.1 dan "
              f"akses lewat SSH tunnel:\n  ssh -L {port}:127.0.0.1:{port} user@server")
        sys.exit(2)

    WS.mkdir(exist_ok=True)
    tg = control.start_telegram_listener()
    srv = ThreadingHTTPServer((host, port), Handler)
    sandi = bool((os.getenv("DASHBOARD_PASS") or "").strip())
    print(f"AI Academy dashboard: http://{host}:{port}")
    print(f"  masuk    : {'pengguna + kata sandi' if sandi else 'tanpa login (hanya lokal)'}")
    print(f"  telegram : {'aktif' if tg else 'tidak dikonfigurasi'}")
    print("  Ctrl+C untuk berhenti.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard berhenti.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
