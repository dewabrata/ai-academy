<?php
// Bagian dari AI Academy. Dilisensikan sama dengan proyek induknya.

/**
 * Buat resource berkas di sebuah section kursus.
 *
 * @package    local_aiacademy
 * @copyright  2026 AI Academy
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_aiacademy\external;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/mod/resource/lib.php');

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;
use local_aiacademy\helper;

/**
 * Satu berkas dari area draft menjadi satu modul resource.
 */
class add_resource extends external_api {

    /**
     * @return external_function_parameters
     */
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'     => new external_value(PARAM_INT, 'id kursus'),
            'sectionnum'   => new external_value(PARAM_INT, 'nomor section, 0 = General'),
            'name'         => new external_value(PARAM_TEXT, 'nama modul yang tampil di kursus'),
            'draftitemid'  => new external_value(PARAM_INT,
                'itemid area draft hasil core_files_upload'),
            'intro'        => new external_value(PARAM_RAW, 'keterangan singkat', VALUE_DEFAULT, ''),
            'replace'      => new external_value(PARAM_BOOL,
                'hapus dulu modul bernama sama di section itu', VALUE_DEFAULT, true),
        ]);
    }

    /**
     * @param int $courseid
     * @param int $sectionnum
     * @param string $name
     * @param int $draftitemid
     * @param string $intro
     * @param bool $replace
     * @return array
     */
    public static function execute(int $courseid, int $sectionnum, string $name,
            int $draftitemid, string $intro = '', bool $replace = true): array {
        $p = self::validate_parameters(self::execute_parameters(), [
            'courseid'    => $courseid,
            'sectionnum'  => $sectionnum,
            'name'        => $name,
            'draftitemid' => $draftitemid,
            'intro'       => $intro,
            'replace'     => $replace,
        ]);

        [$course, ] = helper::siapkan($p['courseid'], $p['sectionnum']);
        $jumlah = helper::jumlah_berkas_draft($p['draftitemid']);

        $dihapus = 0;
        if ($p['replace']) {
            $dihapus = helper::hapus_senama($course, $p['sectionnum'], $p['name']);
        }

        $mi = helper::moduleinfo($course, 'resource', $p['sectionnum'], $p['name']);
        $mi->intro = $p['intro'];

        // `files` adalah nama field filemanager di mod_form resource; nilainya
        // itemid draft, dan Moodle yang memindahkan isinya ke area modul.
        $mi->files = $p['draftitemid'];

        // Bawaan yang diminta mod_resource. display AUTO membiarkan Moodle
        // memilih antara membuka langsung atau menampilkan halaman perantara,
        // sesuai jenis berkasnya.
        $mi->display        = RESOURCELIB_DISPLAY_AUTO;
        $mi->printintro     = $p['intro'] === '' ? 0 : 1;
        $mi->showsize       = 1;
        $mi->showtype       = 1;
        $mi->showdate       = 0;
        $mi->popupwidth     = 620;
        $mi->popupheight    = 450;
        $mi->filterfiles    = 0;
        $mi->revision       = 1;

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
