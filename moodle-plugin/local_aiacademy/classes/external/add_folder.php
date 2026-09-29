<?php
// Bagian dari AI Academy. Dilisensikan sama dengan proyek induknya.

/**
 * Buat folder berisi seluruh berkas area draft di sebuah section kursus.
 *
 * @package    local_aiacademy
 * @copyright  2026 AI Academy
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_aiacademy\external;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/mod/folder/lib.php');

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;
use local_aiacademy\helper;

/**
 * Seluruh berkas di satu area draft menjadi satu modul folder.
 *
 * Dipakai untuk materi satu pertemuan: handbook, slide, latihan, kunci,
 * praktik, dan bahan kerja berada dalam satu folder, sehingga section hari itu
 * tidak dipenuhi enam modul terpisah.
 */
class add_folder extends external_api {

    /**
     * @return external_function_parameters
     */
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'     => new external_value(PARAM_INT, 'id kursus'),
            'sectionnum'   => new external_value(PARAM_INT, 'nomor section, 0 = General'),
            'name'         => new external_value(PARAM_TEXT, 'nama folder yang tampil di kursus'),
            'draftitemid'  => new external_value(PARAM_INT,
                'itemid area draft hasil core_files_upload'),
            'intro'        => new external_value(PARAM_RAW, 'keterangan singkat', VALUE_DEFAULT, ''),
            'replace'      => new external_value(PARAM_BOOL,
                'hapus dulu modul bernama sama di section itu', VALUE_DEFAULT, true),
            'inline'       => new external_value(PARAM_BOOL,
                'tampilkan isi folder langsung di halaman kursus', VALUE_DEFAULT, false),
        ]);
    }

    /**
     * @param int $courseid
     * @param int $sectionnum
     * @param string $name
     * @param int $draftitemid
     * @param string $intro
     * @param bool $replace
     * @param bool $inline
     * @return array
     */
    public static function execute(int $courseid, int $sectionnum, string $name,
            int $draftitemid, string $intro = '', bool $replace = true,
            bool $inline = false): array {
        $p = self::validate_parameters(self::execute_parameters(), [
            'courseid'    => $courseid,
            'sectionnum'  => $sectionnum,
            'name'        => $name,
            'draftitemid' => $draftitemid,
            'intro'       => $intro,
            'replace'     => $replace,
            'inline'      => $inline,
        ]);

        [$course, ] = helper::siapkan($p['courseid'], $p['sectionnum']);
        $jumlah = helper::jumlah_berkas_draft($p['draftitemid']);

        $dihapus = 0;
        if ($p['replace']) {
            $dihapus = helper::hapus_senama($course, $p['sectionnum'], $p['name']);
        }

        $mi = helper::moduleinfo($course, 'folder', $p['sectionnum'], $p['name']);
        $mi->intro = $p['intro'];

        // Nama field filemanager di mod_form folder.
        $mi->files = $p['draftitemid'];

        $mi->display = $p['inline'] ? FOLDER_DISPLAY_INLINE : FOLDER_DISPLAY_PAGE;
        $mi->showexpanded        = 1;
        $mi->showdownloadfolder  = 1;
        $mi->forcedownload       = 1;
        $mi->revision            = 1;

        $hasil = create_module($mi);

        return helper::balasan($hasil, $dihapus, $jumlah);
    }

    /**
     * @return external_single_structure
     */
    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cmid'       => new external_value(PARAM_INT, 'id course module yang dibuat'),
            'instanceid' => new external_value(PARAM_INT, 'id instance modul'),
            'name'       => new external_value(PARAM_TEXT, 'nama modul'),
            'sectionnum' => new external_value(PARAM_INT, 'nomor section'),
            'filecount'  => new external_value(PARAM_INT, 'jumlah berkas dari draft'),
            'replaced'   => new external_value(PARAM_INT, 'jumlah modul senama yang dihapus'),
        ]);
    }
}
