<#
.SYNOPSIS
    Kendali dashboard AI Academy di Windows: start, stop, restart, status, log, reset.

.DESCRIPTION
    Yang dikelola skrip ini hanyalah dashboard. Pipeline produksi dijalankan
    oleh dashboard sebagai proses terpisah dengan kuncinya sendiri di .locks/,
    dan sengaja TIDAK ikut mati saat dashboard berhenti — satu pertemuan bisa
    berjam-jam dan puluhan dolar, jadi menutup panel tidak boleh membuangnya.
    Karena itu `stop` hanya menghentikan panel; hentikan pipeline dari dalam
    dashboard atau dengan `python control.py stop <proyek>`.

.PARAMETER Perintah
    start    jalankan dashboard di latar belakang
    stop     hentikan dashboard (pipeline dibiarkan jalan)
    restart  stop lalu start
    status   keadaan dashboard, port, dan pipeline tiap proyek
    log      tampilkan log dashboard (-Ikuti untuk mengikuti)
    reset    bersihkan keadaan runtime — HANYA untuk pengembangan

.EXAMPLE
    .\academyctl.ps1 start
    .\academyctl.ps1 log -Ikuti
    .\academyctl.ps1 status
    .\academyctl.ps1 reset -Yakin
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'log', 'reset')]
    [string]$Perintah = 'status',

    # log: ikuti keluaran baru seperti `tail -f`
    [switch]$Ikuti,

    # log: jumlah baris terakhir
    [int]$Baris = 60,

    # reset: konfirmasi eksplisit, wajib kalau AI_ACADEMY_ENV bukan 'dev'
    [switch]$Yakin,

    # reset: ikut mengarsipkan proyek di workspace/ (tidak menghapus)
    [switch]$Materi
)

$ErrorActionPreference = 'Stop'
$AKAR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PIDFILE = Join-Path $AKAR '.locks\dashboard.pid'
$LOGDIR = Join-Path $AKAR 'logs'
$LOGFILE = Join-Path $LOGDIR 'dashboard.log'

function Get-Python {
    $venv = Join-Path $AKAR '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Python tidak ketemu. Buat venv dulu: python -m venv .venv"
}

function Get-Port {
    # .env dibaca langsung supaya skrip tidak perlu menjalankan Python hanya
    # untuk tahu portnya.
    $env_file = Join-Path $AKAR '.env'
    if (Test-Path $env_file) {
        $baris = Select-String -Path $env_file -Pattern '^\s*DASHBOARD_PORT\s*=' -ErrorAction SilentlyContinue
        if ($baris) {
            $nilai = ($baris[-1].Line -split '=', 2)[1].Trim()
            if ($nilai -match '^\d+$') { return [int]$nilai }
        }
    }
    return 8770
}

function Get-DashboardPid {
    if (-not (Test-Path $PIDFILE)) { return $null }
    $isi = (Get-Content $PIDFILE -Raw).Trim()
    if ($isi -notmatch '^\d+$') { return $null }
    $proc = Get-Process -Id ([int]$isi) -ErrorAction SilentlyContinue
    if (-not $proc) { return $null }
    # PID bisa dipakai ulang OS setelah proses lama mati. Pastikan ini memang
    # proses Python, bukan program lain yang kebetulan mewarisi nomornya.
    if ($proc.ProcessName -notmatch 'python') { return $null }
    return [int]$isi
}

function Test-Port([int]$port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port)
        $c.Close()
        return $true
    } catch { return $false }
}

function Start-Dashboard {
    $adaPid = Get-DashboardPid
    if ($adaPid) {
        Write-Host "Dashboard sudah berjalan (PID $adaPid)." -ForegroundColor Yellow
        return
    }
    $port = Get-Port
    if (Test-Port $port) {
        Write-Host "Port $port sudah dipakai proses lain. Cek dengan: netstat -ano | findstr $port" -ForegroundColor Red
        exit 1
    }

    New-Item -ItemType Directory -Force -Path $LOGDIR | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $PIDFILE) | Out-Null
    $py = Get-Python
    Add-Content -Path $LOGFILE -Encoding utf8 -Value @"

===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') :: dashboard start =====
"@

    # -u supaya keluaran tidak tertahan di buffer dan log terbaca saat diikuti.
    $proc = Start-Process -FilePath $py `
        -ArgumentList '-u', 'dashboard.py' `
        -WorkingDirectory $AKAR `
        -RedirectStandardOutput $LOGFILE.Replace('.log', '.out.log') `
        -RedirectStandardError $LOGFILE.Replace('.log', '.err.log') `
        -WindowStyle Hidden -PassThru

    Set-Content -Path $PIDFILE -Value $proc.Id -Encoding ascii

    # Tunggu sampai port benar-benar menerima koneksi, bukan sekadar "proses
    # sudah dibuat": dashboard bisa mati saat start karena .env salah.
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-Port $port) {
            Write-Host "Dashboard jalan (PID $($proc.Id)) - http://127.0.0.1:$port" -ForegroundColor Green
            return
        }
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
    }
    Write-Host "Dashboard gagal start. Lihat lognya:" -ForegroundColor Red
    Show-Log
    Remove-Item $PIDFILE -ErrorAction SilentlyContinue
    exit 1
}

function Stop-Dashboard {
    $adaPid = Get-DashboardPid
    if (-not $adaPid) {
        Remove-Item $PIDFILE -ErrorAction SilentlyContinue
        Write-Host "Dashboard tidak berjalan."
        return
    }
    Stop-Process -Id $adaPid -Force -ErrorAction SilentlyContinue
    Remove-Item $PIDFILE -ErrorAction SilentlyContinue
    Write-Host "Dashboard (PID $adaPid) dihentikan. Pipeline yang sedang jalan TIDAK ikut berhenti."
}

function Show-Status {
    $port = Get-Port
    $adaPid = Get-DashboardPid
    Write-Host "Dashboard" -ForegroundColor Cyan
    if ($adaPid) {
        Write-Host "  proses : jalan (PID $adaPid)"
    } else {
        Write-Host "  proses : berhenti"
    }
    Write-Host "  port   : $port $(if (Test-Port $port) { '(menerima koneksi)' } else { '(tertutup)' })"
    Write-Host "  url    : http://127.0.0.1:$port"
    Write-Host "  log    : $LOGFILE"
    Write-Host ""
    Write-Host "Pipeline" -ForegroundColor Cyan
    $py = Get-Python
    & $py (Join-Path $AKAR 'control.py') status
}

function Show-Log {
    $berkas = @($LOGFILE, $LOGFILE.Replace('.log', '.out.log'), $LOGFILE.Replace('.log', '.err.log')) |
        Where-Object { Test-Path $_ }
    if (-not $berkas) {
        Write-Host "Belum ada log. Jalankan '.\academyctl.ps1 start' dulu."
        return
    }
    $utama = $LOGFILE.Replace('.log', '.out.log')
    if (-not (Test-Path $utama)) { $utama = $berkas[0] }
    if ($Ikuti) {
        Get-Content $utama -Tail $Baris -Wait
    } else {
        foreach ($b in $berkas) {
            $isi = Get-Content $b -Tail $Baris -ErrorAction SilentlyContinue
            if ($isi) {
                Write-Host "--- $b" -ForegroundColor DarkGray
                $isi
            }
        }
    }
}

function Reset-Dev {
    $dev = $env:AI_ACADEMY_ENV -eq 'dev'
    if (-not $dev -and -not $Yakin) {
        Write-Host "reset hanya untuk pengembangan." -ForegroundColor Red
        Write-Host "Jalankan di mesin dev dengan AI_ACADEMY_ENV=dev, atau tambahkan -Yakin."
        exit 2
    }

    Stop-Dashboard

    Write-Host "Membersihkan keadaan runtime:"
    foreach ($pola in @('.locks\*.lock', '.locks\dashboard.pid', 'logs\*.log',
                        'status.json', 'events.jsonl')) {
        $jalur = Join-Path $AKAR $pola
        $kena = @(Get-ChildItem -Path $jalur -ErrorAction SilentlyContinue)
        foreach ($f in $kena) {
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            Write-Host "  hapus  $($f.FullName.Substring($AKAR.Length + 1))"
        }
    }
    Get-ChildItem -Path $AKAR -Filter '__pycache__' -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\.venv\\' } |
        ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  hapus  $($_.FullName.Substring($AKAR.Length + 1))"
        }

    if ($Materi) {
        # Diarsipkan, bukan dihapus: satu proyek bisa bernilai puluhan dolar
        # biaya produksi, dan reset yang tidak bisa dibatalkan itu jebakan.
        $ws = Join-Path $AKAR 'workspace'
        $arsip = Join-Path $ws '.arsip'
        if (Test-Path $ws) {
            New-Item -ItemType Directory -Force -Path $arsip | Out-Null
            $cap = Get-Date -Format 'yyyyMMdd-HHmmss'
            Get-ChildItem -Path $ws -Directory | Where-Object { $_.Name -ne '.arsip' } | ForEach-Object {
                Move-Item $_.FullName (Join-Path $arsip "$($_.Name)-$cap")
                Write-Host "  arsip  workspace\$($_.Name) -> .arsip\$($_.Name)-$cap"
            }
        }
    } else {
        Write-Host "  workspace\ tidak disentuh (tambahkan -Materi untuk mengarsipkannya)."
    }
    Write-Host "Reset selesai." -ForegroundColor Green
}

switch ($Perintah) {
    'start'   { Start-Dashboard }
    'stop'    { Stop-Dashboard }
    'restart' { Stop-Dashboard; Start-Sleep -Milliseconds 500; Start-Dashboard }
    'status'  { Show-Status }
    'log'     { Show-Log }
    'reset'   { Reset-Dev }
}
