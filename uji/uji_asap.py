"""Uji asap: jalankan pipeline penuh dengan jawaban gate yang tetap.

    python uji/uji_asap.py contoh/silabus-contoh.md --project uji-baseline

Gunanya membandingkan dua versi prompt/kode secara adil. Kalau gate dijawab
manusia, masukan yang berbeda di tiap run membuat hasilnya tidak bisa
dibandingkan — jadi di sini jawabannya dipatok:

    KURIKULUM, BLUEPRINT, PILOT,  -> y     (setujui tanpa masukan)
    PERTEMUAN-*
    lainnya (KUOTA, GAGAL-*,      -> q     (berhenti, jangan menambah biaya)
             TELAAH-GAGAL-*, PAKET-GAGAL-*, PLAFON, ...)

Point dibuat pendek (--halaman, bawaan 1–2) supaya satu uji tidak menghabiskan
kuota; yang diuji adalah alurnya, bukan panjang tulisan.

Model semua peran dipatok lewat --model (bawaan sonnet) HANYA untuk proses uji,
tanpa menyentuh .env produksi. Yang dibandingkan adalah dua versi prompt pada
model yang sama, jadi model yang lebih murah tetap memberi perbandingan adil.

Uji tidak pernah menunggu kuota: QUOTA_WAIT=ask dipaksakan, sehingga kuota
habis selalu memunculkan gate KUOTA yang dijawab 'q'. Menunggu berhari-hari
demi uji tidak masuk akal, dan kuota yang sama dipakai pemiliknya bekerja.

Jawaban dikirim lewat docs/GATE_JAWAB.txt, kanal yang sama dengan dashboard.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "workspace"

# monitor.ask membuang GATE_JAWAB.txt yang tertinggal tepat setelah gate dibuka.
# Menulis terlalu cepat berarti jawaban kita ikut terbuang — jadi tunggu dulu,
# dan tulis ulang kalau gate yang sama masih menunggu.
JEDA_JAWAB = 6
ULANG_SETELAH = 30


def jawaban_untuk(label: str, pertanyaan: str = "") -> str:
    # "!!" di pertanyaan gate = Python sendiri menemukan masalah (mis. point
    # tanpa capaian di ringkasan blueprint). Uji berhenti di situ alih-alih
    # menyetujui dan membayar produksi atas rencana yang cacat.
    if "!!" in pertanyaan:
        return "q"
    if label in ("KURIKULUM", "BLUEPRINT", "PILOT") or label.startswith("PERTEMUAN-"):
        return "y"
    return "q"


def baca_status(docs: Path) -> dict:
    p = docs / "status.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}           # sedang ditulis; baca lagi di putaran berikutnya


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("silabus")
    ap.add_argument("--project", required=True)
    ap.add_argument("--pilot", type=int)
    ap.add_argument("--model", default="sonnet",
                    help="model untuk semua peran selama uji (bawaan: sonnet)")
    ap.add_argument("--halaman", default="1–2", help="POINT_HALAMAN selama uji (bawaan: 1–2)")
    ap.add_argument("--klien", help="berkas konteks klien, diteruskan ke academy.py")
    ap.add_argument("--resume", help="lanjutkan proyek yang sudah ada dari tahap ini "
                                     "(mis. produksi), alih-alih mulai baru")
    a = ap.parse_args()

    docs = WS / a.project / "docs"
    if (docs / "STATE.txt").exists() and not a.resume:
        print(f"Proyek '{a.project}' sudah pernah dijalankan. Pakai nama lain supaya "
              f"hasil uji tidak tercampur.")
        sys.exit(2)
    docs.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-u", "academy.py", a.silabus, "--project", a.project]
    if a.resume:
        cmd += ["--resume", a.resume]
    if a.pilot:
        cmd += ["--pilot", str(a.pilot)]
    if a.klien:
        cmd += ["--klien", a.klien]
    # load_dotenv() di roles.py/academy.py tidak menimpa variabel yang sudah
    # ada, jadi nilai di sini menang atas .env tanpa mengubah berkasnya.
    env = {**os.environ, "QUOTA_WAIT": "ask", "POINT_HALAMAN": a.halaman}
    for peran in ("KURIKULUM", "BLUEPRINT", "WRITER", "REVIEWER", "FAKTA", "SLIDE", "TUGAS", "EDITOR"):
        env[f"MODEL_{peran}"] = a.model

    log = (docs / "pipeline.log").open("a", encoding="utf-8")
    mulai = time.time()
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env)
    print(f"[uji] pipeline PID {proc.pid}, model {a.model}: {' '.join(cmd[2:])}", flush=True)

    dijawab: dict[str, float] = {}      # kunci gate -> waktu jawaban terakhir ditulis
    terlihat: dict[str, float] = {}     # kunci gate -> waktu pertama terlihat
    while proc.poll() is None:
        g = baca_status(docs).get("gate")
        if g:
            kunci = f"{g.get('label')}@{g.get('since')}"
            sekarang = time.time()
            terlihat.setdefault(kunci, sekarang)
            terakhir = dijawab.get(kunci)
            perlu = (terakhir is None and sekarang - terlihat[kunci] >= JEDA_JAWAB) or \
                    (terakhir is not None and sekarang - terakhir >= ULANG_SETELAH)
            if perlu:
                ans = jawaban_untuk(g.get("label", ""), g.get("question", ""))
                (docs / "GATE_JAWAB.txt").write_text(ans, encoding="utf-8")
                dijawab[kunci] = sekarang
                menit = (sekarang - mulai) / 60
                print(f"[uji] {menit:5.1f} mnt  gate {g.get('label')!r} -> {ans!r}"
                      + ("  (ulang)" if terakhir else ""), flush=True)
        time.sleep(3)

    log.close()
    st = baca_status(docs)
    print(f"[uji] selesai: exit={proc.returncode}, "
          f"{(time.time() - mulai) / 60:.1f} menit, "
          f"biaya ${(st.get('cost') or {}).get('total', 0):.2f}", flush=True)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
