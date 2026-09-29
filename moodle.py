"""Klien MCP Moodle: satu-satunya tempat kode ini bicara ke LMS.

Server MCP Moodle mengekspos SELURUH fungsi web service sebagai tool — di LMS
Juara Coding jumlahnya 1049. Dua akibatnya menentukan bentuk modul ini:

1. **Daftar tool tidak diambil ulang.** Balasan `tools/list` besar dan sempat
   melewati batas waktu 60 detik. Daftarnya disimpan ke berkas dan dipakai dari
   situ; `--segarkan` untuk mengambil ulang.
2. **Hanya tool di daftar putih yang boleh dipanggil.** Hook penjaga di
   `hooks_sdk.py` hanya mengawasi Write, Edit, dan Bash — tool MCP lewat tanpa
   diperiksa. Token yang dipakai milik admin, jadi satu kesalahan bisa mengenai
   seluruh LMS. Daftar putih di bawah memuat yang memang dibutuhkan, dan tidak
   memuat satu pun fungsi penghapus.

Dipakai `moodle_unggah.py`. Tidak memanggil model sama sekali.
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

AKAR = Path(__file__).parent
load_dotenv(AKAR / ".env")

SIMPAN_TOOL = AKAR / ".moodle-tools.json"
BATAS_WAKTU = 180
BATAS_DAFTAR = 300          # tools/list jauh lebih lambat daripada tools/call

# Tool yang boleh dipanggil. Penghapusan TIDAK ada di sini dengan sengaja:
# kursus salah unggah lebih baik dihapus manusia lewat UI Moodle, yang meminta
# konfirmasi, daripada oleh kode yang salah menghitung id.
DIIZINKAN = {
    # membaca
    "core_webservice_get_site_info",
    "core_course_get_categories",
    "core_course_get_courses",
    "core_course_get_courses_by_field",
    "core_course_get_contents",
    "local_moodlia_get_grade_items",
    "local_moodlia_get_folder_files",
    "local_moodlia_get_feedback_items",
    "local_moodlia_get_question_categories",
    # membuat & mengubah
    "core_course_create_courses",
    "core_course_update_courses",
    "core_course_import_course",
    "core_files_upload",
    "local_moodlia_create_module",
    "local_moodlia_update_module",
    "local_moodlia_move_module",
    "local_moodlia_create_section",
    "local_moodlia_update_section",
    "local_moodlia_upload_folder_file",
    "local_moodlia_update_resource",
    "local_moodlia_create_feedback_item",
    "local_moodlia_create_grade_category",
    "local_moodlia_update_grade_item",
    "local_moodlia_set_course_grade_pass",
    "local_moodlia_create_question",
    "local_moodlia_create_question_category",
    "local_moodlia_add_question_to_quiz",
    "local_moodlia_add_random_questions_to_quiz",
    "local_questions_importer_ws_import_xml",
    "mod_attendance_add_attendance",
    "mod_attendance_add_session",
    "enrol_manual_enrol_users",
}


class MoodleError(RuntimeError):
    """Kegagalan yang harus dilihat manusia, bukan diulang diam-diam."""


class Klien:
    """Satu sesi MCP. Dibuat sekali per proses unggah."""

    def __init__(self, url: str = "", token: str = ""):
        self.url = (url or os.getenv("MOODLE_MCP_URL") or "").strip()
        self.token = (token or os.getenv("MOODLE_TOKEN") or "").strip()
        self.sid = None
        self._tool = None
        if not self.url or not self.token:
            raise MoodleError(
                "MOODLE_MCP_URL atau MOODLE_TOKEN belum diisi. "
                "Isi di tab Pengaturan dashboard.")

    # ---- lapisan JSON-RPC ------------------------------------------------
    def _rpc(self, metode: str, params=None, batas: int = BATAS_WAKTU) -> dict:
        body = {"jsonrpc": "2.0", "id": 1, "method": metode}
        if params is not None:
            body["params"] = params
        head = {"Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {self.token}"}
        if self.sid:
            head["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=head, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=batas) as r:
                teks = r.read().decode("utf-8", "replace")
                h = dict(r.headers)
        except urllib.error.HTTPError as e:
            raise MoodleError(f"HTTP {e.code} dari Moodle: "
                              f"{e.read().decode('utf-8', 'replace')[:200]}") from e
        except (urllib.error.URLError, OSError) as e:
            raise MoodleError(f"Tidak bisa menghubungi Moodle: {e}") from e
        if not self.sid:
            self.sid = h.get("Mcp-Session-Id") or h.get("mcp-session-id")
        # Balasan bisa JSON biasa atau SSE.
        if teks.lstrip().startswith(("event:", "data:")):
            for b in teks.splitlines():
                if b.startswith("data:"):
                    return json.loads(b[5:].strip())
        return json.loads(teks) if teks.strip() else {}

    def mulai(self):
        hasil = self._rpc("initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "ai-academy", "version": "1.0"}})
        self._rpc("notifications/initialized", {})
        return ((hasil.get("result") or {}).get("serverInfo") or {})

    # ---- memanggil tool --------------------------------------------------
    def panggil(self, nama: str, arg: dict):
        """Jalankan satu tool. Mengembalikan (isi, galat); galat berupa teks."""
        if nama not in DIIZINKAN:
            raise MoodleError(
                f"Tool '{nama}' tidak ada di daftar putih moodle.DIIZINKAN. "
                f"Tambahkan di sana lebih dulu kalau memang dibutuhkan.")
        j = self._rpc("tools/call", {"name": nama, "arguments": arg})
        if "error" in j:
            d = (j["error"].get("data") or {})
            return None, (d.get("errorcode")
                          or str(j["error"].get("message", ""))[:200])
        isi = (j.get("result") or {}).get("content") or []
        teks = "\n".join(x.get("text", "") for x in isi if x.get("type") == "text")
        if (j.get("result") or {}).get("isError"):
            return None, teks[:200]
        try:
            data = json.loads(teks)
        except ValueError:
            return teks, None
        # Server membungkus muatan Moodle dalam {"result": ...}.
        if isinstance(data, dict) and set(data) == {"result"}:
            data = data["result"]
        if isinstance(data, dict) and data.get("exception"):
            return None, f"{data.get('errorcode')}: {data.get('message')}"
        return data, None

    def wajib(self, nama: str, arg: dict, konteks: str = ""):
        """Seperti panggil(), tetapi kegagalan menghentikan unggahan."""
        hasil, galat = self.panggil(nama, arg)
        if galat:
            raise MoodleError(f"{konteks or nama} gagal: {galat}")
        return hasil

    # ---- daftar tool -----------------------------------------------------
    def daftar_tool(self, segarkan: bool = False) -> dict:
        if self._tool is not None and not segarkan:
            return self._tool
        if SIMPAN_TOOL.exists() and not segarkan:
            try:
                self._tool = json.loads(SIMPAN_TOOL.read_text(encoding="utf-8"))
                return self._tool
            except (OSError, ValueError):
                pass
        d = self._rpc("tools/list", {}, batas=BATAS_DAFTAR)
        self._tool = {a["name"]: a for a in (d.get("result") or {}).get("tools") or []}
        try:
            SIMPAN_TOOL.write_text(json.dumps(self._tool, ensure_ascii=False),
                                   encoding="utf-8")
        except OSError:
            pass
        return self._tool

    def periksa_kesiapan(self) -> list[str]:
        """Tool yang dibutuhkan tetapi tidak ada di server. Kosong = siap.

        Dijalankan sebelum unggahan supaya kekurangan plugin ketahuan di awal,
        bukan setengah jalan saat kursus sudah terbentuk sebagian.
        """
        ada = set(self.daftar_tool())
        return sorted(DIIZINKAN - ada)


def unggah_berkas(k: Klien, uid: int, nama: str, isi: bytes, itemid: int = 0) -> int:
    """Taruh satu berkas di area draft pengguna, kembalikan itemid-nya.

    Beberapa berkas dengan itemid yang sama menumpuk di satu area — itulah cara
    mengirim satu folder berisi banyak berkas.
    """
    import base64
    hasil = k.wajib("core_files_upload", {
        "contextlevel": "user", "instanceid": uid, "component": "user",
        "filearea": "draft", "itemid": itemid, "filepath": "/",
        "filename": nama, "filecontent": base64.b64encode(isi).decode(),
    }, konteks=f"unggah {nama}")
    return int(hasil["itemid"])


def _cli():
    import sys
    k = Klien()
    info = k.mulai()
    print(f"server   : {info.get('name')} {info.get('version')}")
    t = k.daftar_tool(segarkan="--segarkan" in sys.argv)
    print(f"tool     : {len(t)} (disimpan di {SIMPAN_TOOL.name})")
    kurang = k.periksa_kesiapan()
    print(f"daftar putih: {len(DIIZINKAN)} tool")
    if kurang:
        print(f"BELUM ADA di server ({len(kurang)}):")
        for x in kurang:
            print("   ", x)
    else:
        print("semua tool yang dibutuhkan tersedia.")
    situs, _ = k.panggil("core_webservice_get_site_info", {})
    if situs:
        print(f"situs    : {situs.get('sitename')} (pengguna {situs.get('username')}, "
              f"id {situs.get('userid')})")


if __name__ == "__main__":
    _cli()
