<?php
// Bagian dari AI Academy. Dilisensikan sama dengan proyek induknya.

/**
 * Pendaftaran fungsi web service.
 *
 * Moodle core tidak menyediakan cara membuat activity lewat web service:
 * `core_courseformat_new_module` menolak seluruh modul konten dengan
 * "does not support quick creation", dan `core_files_upload` hanya menerima
 * area draft pengguna. Dua fungsi di bawah menutup celah itu dengan memanggil
 * `create_module()` — API internal yang juga dipakai formulir Moodle sendiri.
 *
 * @package    local_aiacademy
 * @copyright  2026 AI Academy
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_aiacademy_add_resource' => [
        'classname'    => 'local_aiacademy\external\add_resource',
        'methodname'   => 'execute',
        'description'  => 'Buat resource berkas di sebuah section kursus dari area draft.',
        'type'         => 'write',
        'capabilities' => 'moodle/course:manageactivities',
        'ajax'         => false,
    ],
    'local_aiacademy_add_folder' => [
        'classname'    => 'local_aiacademy\external\add_folder',
        'methodname'   => 'execute',
        'description'  => 'Buat folder di sebuah section kursus, berisi seluruh berkas di area draft.',
        'type'         => 'write',
        'capabilities' => 'moodle/course:manageactivities',
        'ajax'         => false,
    ],
];

$services = [
    'AI Academy content service' => [
        'functions' => [
            'local_aiacademy_add_resource',
            'local_aiacademy_add_folder',
        ],
        'restrictedusers' => 0,
        'enabled'         => 1,
        'shortname'       => 'local_aiacademy',
        'downloadfiles'   => 0,
        'uploadfiles'     => 1,
    ],
];
