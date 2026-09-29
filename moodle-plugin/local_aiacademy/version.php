<?php
// Bagian dari AI Academy. Dilisensikan sama dengan proyek induknya.

/**
 * Berkas versi plugin.
 *
 * @package    local_aiacademy
 * @copyright  2026 AI Academy
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_aiacademy';
$plugin->version   = 2026092900;

// Moodle 4.5 (2024100700). Dipatok ke sini, bukan ke versi yang lebih lama,
// karena plugin ini memakai namespace core_external\ yang baru tersedia sejak
// Moodle 4.2 dan API section yang berubah di 4.4.
$plugin->requires  = 2024100700;

$plugin->maturity  = MATURITY_STABLE;
$plugin->release   = '1.0.0';
