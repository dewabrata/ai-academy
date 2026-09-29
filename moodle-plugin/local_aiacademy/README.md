# local_aiacademy — layanan konten AI Academy

Plugin Moodle yang membuka dua hal yang tidak disediakan Moodle core lewat web
service: **membuat activity** dan **memasukkan berkas ke dalamnya**.

## Kenapa plugin ini ada

Moodle tidak pernah membuka pembuatan activity ke web service. Activity dibuat
lewat `mod_form` milik masing-masing modul — kelas formulir dengan validasi dan
area berkas draft sendiri — dan Moodle tidak menggeneralisasikannya menjadi
fungsi eksternal.

Diuji pada Moodle 5.2 dengan 799 fungsi terdaftar:

| Yang dicoba | Hasil |
|---|---|
| `core_courseformat_new_module` dengan 12 jenis modul | semua ditolak: *"does not support quick creation"* |
| `core_files_upload` ke `mod_resource/content` | `codingerror` |
| `core_files_upload` ke area draft pengguna | berhasil |

Jadi berkas bisa sampai ke Moodle, tetapi berhenti di area draft yang tidak
terlihat peserta. Plugin ini menyambungkan sisanya dengan memanggil
`create_module()` — API internal yang juga dipakai formulir Moodle sendiri.

## Dua fungsi yang ditambahkan

```
local_aiacademy_add_resource(courseid, sectionnum, name, draftitemid,
                             intro = '', replace = true)

local_aiacademy_add_folder(courseid, sectionnum, name, draftitemid,
                           intro = '', replace = true, inline = false)
```

Keduanya mengembalikan `cmid`, `instanceid`, `name`, `sectionnum`, `filecount`,
dan `replaced`.

`add_resource` membuat satu modul File. `add_folder` membuat satu modul Folder
berisi **seluruh** berkas di area draft itu — dipakai untuk materi satu
pertemuan, supaya section hari itu tidak dipenuhi enam modul terpisah.

### `replace` menjadikannya bisa diulang

Bawaannya `true`: modul bernama sama di section itu dihapus lebih dulu. Tombol
unggah bisa ditekan dua kali, dan pipeline bisa dijalankan ulang setelah materi
direvisi. Tanpa ini kursus terisi modul kembar yang isinya berbeda-beda, dan
peserta tidak tahu mana yang berlaku.

### Yang ditolak, bukan dikerjakan diam-diam

- **Section tidak ada** → `sectiontidakada`. Tanpa pemeriksaan ini
  `create_module()` membuat section baru sendiri, dan materi mendarat di tempat
  yang tidak diniatkan — lebih sulit disadari daripada kegagalan terang-terangan.
- **Area draft kosong** → `draftkosong`. Draft kosong menghasilkan modul tanpa
  isi: terlihat ada di kursus, tetapi tidak bisa dibuka peserta.

## Pemasangan

Butuh **Moodle 4.5 atau lebih baru** (`requires = 2024100700`). Dipatok ke sana
karena memakai namespace `core_external\` (sejak 4.2) dan API section yang
berubah di 4.4.

1. Salin folder `local_aiacademy/` ke direktori `local/` instalasi Moodle.

   **Moodle 5.1 ke atas** memindahkan berkas web ke `/public`, jadi tujuannya
   `public/local/local_aiacademy/`. Kalau ragu, lihat di mana folder `local/`
   yang sudah berisi plugin lain.

2. Buka **Site administration → Notifications**, lalu selesaikan pemutakhiran.

3. Aktifkan fungsinya di layanan web service yang dipakai:
   **Site administration → Server → Web services → External services**.

   Plugin ini mendaftarkan layanan sendiri bernama *AI Academy content service*
   (shortname `local_aiacademy`). Kalau LMS sudah punya satu layanan yang
   dipakai bersama, tambahkan saja kedua fungsinya ke layanan itu.

4. Pastikan token yang dipakai punya kapabilitas
   `moodle/course:manageactivities` di kursus tujuannya.

## Alur pemakaian

```
1. core_files_upload            berkas ke area draft pengguna
                                contextlevel=user, instanceid=<userid>,
                                component=user, filearea=draft
                                Beberapa berkas ke itemid yang sama akan
                                menumpuk di satu area.

2. local_aiacademy_add_folder   folder di section hari itu, berisi semuanya
   atau _add_resource           satu berkas sebagai satu modul File
```

## Keamanan

- Kedua fungsi memeriksa `moodle/course:manageactivities` pada konteks kursus.
- Berkas diambil dari area draft **milik pengguna pemanggil sendiri**, jadi
  tidak bisa dipakai menarik berkas pengguna lain.
- Plugin tidak menyimpan data pribadi apa pun.
