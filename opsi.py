"""Opsi produksi per proyek: `docs/OPSI.json`, dengan bawaan dari `.env`.

Opsi hidup di berkas, bukan hanya di dashboard, supaya pipeline yang dijalankan
dari terminal berperilaku sama. Proyek lama yang tidak punya berkas ini memakai
bawaan `.env`, jadi perilakunya tidak berubah.

    {"slide": true, "ekspor_docx": true, "ekspor_pptx": true, "ekspor_xlsx": true,
     "point_halaman": "10-20", "point_maks_putaran": 3, "model": ""}

`model` kosong berarti ikut `MODEL_<PERAN>` di `.env`.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KUNCI = ("slide", "ekspor_docx", "ekspor_pptx", "ekspor_xlsx", "point_halaman",
         "point_maks_putaran", "model")


def _env_bool(nama: str, bawaan: bool) -> bool:
    v = (os.getenv(nama) or "").strip().lower()
    if not v:
        return bawaan
    return v not in ("0", "false", "no", "tidak", "off")


def bawaan() -> dict:
    return {
        "slide": _env_bool("OPSI_SLIDE", True),
        "ekspor_docx": _env_bool("OPSI_EKSPOR_DOCX", True),
        "ekspor_pptx": _env_bool("OPSI_EKSPOR_PPTX", True),
        "ekspor_xlsx": _env_bool("OPSI_EKSPOR_XLSX", True),
        "point_halaman": (os.getenv("POINT_HALAMAN") or "10–20").strip(),
        "point_maks_putaran": int(os.getenv("POINT_MAKS_PUTARAN") or 3),
        "model": (os.getenv("OPSI_MODEL") or "").strip(),
    }


def _bersihkan(mentah: dict) -> dict:
    """Ambil hanya kunci yang dikenal, dengan tipe yang benar. Nilai aneh dari
    UI atau berkas yang disunting tangan tidak boleh menjatuhkan pipeline."""
    out = bawaan()
    for k in ("slide", "ekspor_docx", "ekspor_pptx", "ekspor_xlsx"):
        if k in mentah:
            out[k] = bool(mentah[k])
    if str(mentah.get("point_halaman", "")).strip():
        out["point_halaman"] = str(mentah["point_halaman"]).strip()[:20]
    try:
        putaran = int(mentah.get("point_maks_putaran") or 0)
        if putaran > 0:
            out["point_maks_putaran"] = min(putaran, 10)
    except (TypeError, ValueError):
        pass
    if str(mentah.get("model", "")).strip():
        out["model"] = str(mentah["model"]).strip()[:60]
    return out


def baca(ws: Path) -> dict:
    p = Path(ws) / "docs" / "OPSI.json"
    try:
        return _bersihkan(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return bawaan()


def tulis(ws: Path, mentah: dict) -> Path:
    docs = Path(ws) / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    p = docs / "OPSI.json"
    p.write_text(json.dumps(_bersihkan(mentah), ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return p


def ringkas(o: dict) -> str:
    bagian = [f"point {o['point_halaman']} halaman", f"maks. {o['point_maks_putaran']} putaran"]
    if not o["slide"]:
        bagian.append("tanpa slide")
    if not o["ekspor_docx"]:
        bagian.append("tanpa DOCX")
    if not o["ekspor_pptx"]:
        bagian.append("tanpa PPTX")
    if not o["ekspor_xlsx"]:
        bagian.append("tanpa XLSX")
    if o["model"]:
        bagian.append(f"model {o['model']}")
    return ", ".join(bagian)
