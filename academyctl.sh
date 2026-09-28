#!/usr/bin/env bash
# Kendali dashboard AI Academy: start, stop, restart, status, log, reset.
#
# Yang dikelola skrip ini hanyalah dashboard. Pipeline produksi dijalankan oleh
# dashboard sebagai proses terpisah dengan kuncinya sendiri di .locks/, dan
# sengaja TIDAK ikut mati saat dashboard berhenti — satu pertemuan bisa berjam-jam
# dan puluhan dolar, jadi menutup panel tidak boleh membuangnya. Karena itu
# `stop` hanya menghentikan panel; hentikan pipeline dari dalam dashboard atau
# dengan `python control.py stop <proyek>`.
#
# Di server, lebih baik pakai systemd (lihat deploy/ai-academy.service) dan
# simpan skrip ini untuk pemeriksaan cepat.
set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$AKAR/.locks/dashboard.pid"
LOGDIR="$AKAR/logs"
LOGFILE="$LOGDIR/dashboard.log"

merah()  { printf '\033[31m%s\033[0m\n' "$*"; }
hijau()  { printf '\033[32m%s\033[0m\n' "$*"; }
kuning() { printf '\033[33m%s\033[0m\n' "$*"; }
biru()   { printf '\033[36m%s\033[0m\n' "$*"; }

python_bin() {
    if [ -x "$AKAR/.venv/bin/python" ]; then
        echo "$AKAR/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        command -v python3
    else
        merah "Python tidak ketemu. Buat venv dulu: python3 -m venv .venv" >&2
        exit 1
    fi
}

port_dashboard() {
    # .env dibaca langsung supaya skrip tidak perlu menjalankan Python hanya
    # untuk tahu portnya.
    local nilai=""
    if [ -f "$AKAR/.env" ]; then
        nilai="$(grep -E '^[[:space:]]*DASHBOARD_PORT[[:space:]]*=' "$AKAR/.env" \
                 | tail -1 | cut -d= -f2- | tr -d '[:space:]' || true)"
    fi
    case "$nilai" in
        ''|*[!0-9]*) echo 8770 ;;
        *)           echo "$nilai" ;;
    esac
}

dashboard_pid() {
    [ -f "$PIDFILE" ] || return 1
    local p
    p="$(tr -d '[:space:]' < "$PIDFILE")"
    case "$p" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$p" 2>/dev/null || return 1
    # PID dipakai ulang kernel setelah proses lama mati. Pastikan ini memang
    # proses Python, bukan program lain yang kebetulan mewarisi nomornya.
    ps -p "$p" -o args= 2>/dev/null | grep -q 'dashboard\.py' || return 1
    echo "$p"
}

port_terbuka() {
    # /dev/tcp bawaan bash: tidak butuh nc, ss, maupun Python. Yang lain bisa
    # tidak terpasang di server minimal, dan "alat tidak ada" akan terbaca
    # sebagai "port tertutup" — kesimpulan yang salah dan menyesatkan.
    local port="$1"
    (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && exec 3>&- && return 0
    return 1
}

cmd_start() {
    if pid="$(dashboard_pid)"; then
        kuning "Dashboard sudah berjalan (PID $pid)."
        return 0
    fi
    local port
    port="$(port_dashboard)"
    if port_terbuka "$port"; then
        merah "Port $port sudah dipakai proses lain. Cek: ss -ltnp | grep $port"
        exit 1
    fi

    mkdir -p "$LOGDIR" "$(dirname "$PIDFILE")"
    printf '\n===== %s :: dashboard start =====\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOGFILE"

    # setsid supaya dashboard lepas dari terminal dan tidak ikut mati saat
    # sesi SSH ditutup. -u supaya lognya tidak tertahan di buffer.
    setsid "$(python_bin)" -u "$AKAR/dashboard.py" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    local p
    p="$(cat "$PIDFILE")"

    # Tunggu sampai port benar-benar menerima koneksi, bukan sekadar "proses
    # sudah dibuat": dashboard bisa mati saat start karena .env salah.
    for _ in $(seq 1 40); do
        sleep 0.25
        if port_terbuka "$port"; then
            hijau "Dashboard jalan (PID $p) - http://127.0.0.1:$port"
            return 0
        fi
        kill -0 "$p" 2>/dev/null || break
    done
    merah "Dashboard gagal start. Lihat lognya:"
    tail -40 "$LOGFILE" || true
    rm -f "$PIDFILE"
    exit 1
}

cmd_stop() {
    if ! pid="$(dashboard_pid)"; then
        rm -f "$PIDFILE"
        echo "Dashboard tidak berjalan."
        return 0
    fi
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
    done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo "Dashboard (PID $pid) dihentikan. Pipeline yang sedang jalan TIDAK ikut berhenti."
}

cmd_status() {
    local port
    port="$(port_dashboard)"
    biru "Dashboard"
    if pid="$(dashboard_pid)"; then
        echo "  proses : jalan (PID $pid)"
    else
        echo "  proses : berhenti"
    fi
    if port_terbuka "$port"; then
        echo "  port   : $port (menerima koneksi)"
    else
        echo "  port   : $port (tertutup)"
    fi
    echo "  url    : http://127.0.0.1:$port"
    echo "  log    : $LOGFILE"
    echo
    biru "Pipeline"
    "$(python_bin)" "$AKAR/control.py" status
}

cmd_log() {
    local baris="${2:-60}"
    if [ ! -f "$LOGFILE" ]; then
        echo "Belum ada log. Jalankan './academyctl.sh start' dulu."
        return 0
    fi
    if [ "${1:-}" = "-f" ] || [ "${1:-}" = "--ikuti" ]; then
        tail -n "$baris" -f "$LOGFILE"
    else
        tail -n "${1:-60}" "$LOGFILE"
    fi
}

cmd_reset() {
    local yakin="" materi=""
    for arg in "$@"; do
        case "$arg" in
            --yakin)  yakin=1 ;;
            --materi) materi=1 ;;
        esac
    done
    if [ "${AI_ACADEMY_ENV:-}" != "dev" ] && [ -z "$yakin" ]; then
        merah "reset hanya untuk pengembangan."
        echo "Jalankan di mesin dev dengan AI_ACADEMY_ENV=dev, atau tambahkan --yakin."
        exit 2
    fi

    cmd_stop

    echo "Membersihkan keadaan runtime:"
    for f in "$AKAR"/.locks/*.lock "$PIDFILE" "$LOGDIR"/*.log \
             "$AKAR/status.json" "$AKAR/events.jsonl"; do
        [ -e "$f" ] || continue
        rm -f "$f"
        echo "  hapus  ${f#"$AKAR"/}"
    done
    while IFS= read -r d; do
        rm -rf "$d"
        echo "  hapus  ${d#"$AKAR"/}"
    done < <(find "$AKAR" -name __pycache__ -type d -not -path '*/.venv/*' 2>/dev/null)

    if [ -n "$materi" ]; then
        # Diarsipkan, bukan dihapus: satu proyek bisa bernilai puluhan dolar
        # biaya produksi, dan reset yang tidak bisa dibatalkan itu jebakan.
        local ws="$AKAR/workspace" arsip cap
        arsip="$ws/.arsip"
        cap="$(date '+%Y%m%d-%H%M%S')"
        if [ -d "$ws" ]; then
            mkdir -p "$arsip"
            for d in "$ws"/*/; do
                [ -d "$d" ] || continue
                local nama
                nama="$(basename "$d")"
                [ "$nama" = ".arsip" ] && continue
                mv "$d" "$arsip/$nama-$cap"
                echo "  arsip  workspace/$nama -> .arsip/$nama-$cap"
            done
        fi
    else
        echo "  workspace/ tidak disentuh (tambahkan --materi untuk mengarsipkannya)."
    fi
    hijau "Reset selesai."
}

case "${1:-status}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_stop; sleep 0.5; cmd_start ;;
    status)  cmd_status ;;
    log)     shift; cmd_log "$@" ;;
    reset)   shift; cmd_reset "$@" ;;
    *)
        cat <<EOF
Kendali dashboard AI Academy.

    ./academyctl.sh start              jalankan dashboard di latar belakang
    ./academyctl.sh stop               hentikan dashboard (pipeline dibiarkan)
    ./academyctl.sh restart            stop lalu start
    ./academyctl.sh status             keadaan dashboard, port, dan pipeline
    ./academyctl.sh log [-f] [baris]   log dashboard
    ./academyctl.sh reset [--yakin] [--materi]
                                       bersihkan keadaan runtime (HANYA dev)

reset menolak jalan kecuali AI_ACADEMY_ENV=dev atau diberi --yakin.
Tanpa --materi, isi workspace/ tidak disentuh.
EOF
        exit 2 ;;
esac
