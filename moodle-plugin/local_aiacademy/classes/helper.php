<?php
// Bagian dari AI Academy. Dilisensikan sama dengan proyek induknya.

/**
 * Bagian yang dipakai bersama kedua fungsi web service.
 *
 * @package    local_aiacademy
 * @copyright  2026 AI Academy
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_aiacademy;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/course/modlib.php');

/**
 * Pembantu pembuatan modul.
 */
class helper {

    /**
     * Pastikan kursus ada, penggunanya berwenang, dan section-nya benar-benar ada.
     *
     * Section diperiksa lebih dulu karena `create_module()` akan membuat section
     * baru secara diam-diam kalau nomornya di luar jangkauan — dan materi yang
     * mendarat di section yang tidak diniatkan lebih sulit disadari daripada
     * kegagalan yang terang-terangan.
     *
     * @param int $courseid
     * @param int $sectionnum nomor section (0 = General)
     * @return array [\stdClass $course, \context_course $context]
     */
    public static function siapkan(int $courseid, int $sectionnum): array {
        global $DB;

        $course = get_course($courseid);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        $ada = $DB->record_exists('course_sections',
            ['course' => $course->id, 'section' => $sectionnum]);
        if (!$ada) {
            throw new \moodle_exception('sectiontidakada', 'local_aiacademy', '', $sectionnum);
        }

        return [$course, $context];
    }

    /**
     * Bungkus validate_context supaya helper bisa dipakai di luar external_api.
     *
     * @param \context $context
     */
    protected static function validate_context(\context $context): void {
        \core_external\external_api::validate_context($context);
    }

    /**
     * Hapus modul bernama sama di section itu.
     *
     * Tombol unggah bisa ditekan dua kali, dan pipeline bisa dijalankan ulang
     * setelah materi direvisi. Tanpa ini kursus terisi modul kembar yang isinya
     * berbeda-beda, dan peserta tidak tahu mana yang berlaku.
     *
     * @param \stdClass $course
     * @param int $sectionnum
     * @param string $name
     * @return int jumlah modul yang dihapus
     */
    public static function hapus_senama(\stdClass $course, int $sectionnum, string $name): int {
        $dihapus = 0;
        $modinfo = get_fast_modinfo($course);
        foreach ($modinfo->get_cms() as $cm) {
            if ((int)$cm->sectionnum === $sectionnum && $cm->name === $name) {
                course_delete_module($cm->id);
                $dihapus++;
            }
        }
        if ($dihapus > 0) {
            rebuild_course_cache($course->id, true);
        }
        return $dihapus;
    }

    /**
     * Pastikan area draft benar-benar berisi berkas.
     *
     * Draft yang kosong menghasilkan resource tanpa isi — modul yang terlihat
     * ada di kursus tetapi tidak bisa dibuka peserta. Lebih baik gagal.
     *
     * @param int $draftitemid
     * @return int jumlah berkas
     */
    public static function jumlah_berkas_draft(int $draftitemid): int {
        global $USER;

        $usercontext = \context_user::instance($USER->id);
        $fs = get_file_storage();
        $berkas = $fs->get_area_files($usercontext->id, 'user', 'draft', $draftitemid,
            'filename', false);
        $jumlah = count($berkas);
        if ($jumlah === 0) {
            throw new \moodle_exception('draftkosong', 'local_aiacademy', '', $draftitemid);
        }
        return $jumlah;
    }

    /**
     * Nilai bawaan yang diminta add_moduleinfo, agar pemanggil tidak perlu tahu
     * seluruh kolom formulir modul.
     *
     * @param \stdClass $course
     * @param string $modulename
     * @param int $sectionnum
     * @param string $name
     * @return \stdClass
     */
    public static function moduleinfo(\stdClass $course, string $modulename,
            int $sectionnum, string $name): \stdClass {
        $mi = new \stdClass();
        $mi->modulename          = $modulename;
        $mi->course              = $course->id;
        $mi->section             = $sectionnum;
        $mi->visible             = 1;
        $mi->visibleoncoursepage = 1;
        $mi->name                = $name;
        $mi->intro               = '';
        $mi->introformat         = FORMAT_HTML;
        $mi->cmidnumber          = '';
        $mi->groupmode           = NOGROUPS;
        $mi->groupingid          = 0;
        $mi->completion          = COMPLETION_DISABLED;
        $mi->completionview      = 0;
        $mi->completionexpected  = 0;
        $mi->availabilityconditionsjson = null;
        return $mi;
    }

    /**
     * Bentuk balasan yang sama untuk kedua fungsi.
     *
     * @param \stdClass $hasil hasil create_module()
     * @param int $dihapus
     * @param int $jumlahberkas
     * @return array
     */
    public static function balasan(\stdClass $hasil, int $dihapus, int $jumlahberkas): array {
        return [
            'cmid'        => (int)$hasil->coursemodule,
            'instanceid'  => (int)$hasil->instance,
            'name'        => (string)$hasil->name,
            'sectionnum'  => (int)$hasil->section,
            'filecount'   => $jumlahberkas,
            'replaced'    => $dihapus,
        ];
    }
}
