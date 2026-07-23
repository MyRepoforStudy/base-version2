import unittest
from datetime import UTC, date, datetime

from app.services.compliance import (
    detect_os_family_version,
    lifecycle_status,
    last_reboot_at,
    normalize_criticality,
    parse_date_value,
    patch_status,
    resolve_os_lifecycle,
)


class ComplianceTests(unittest.TestCase):
    def test_detects_supported_os_versions(self):
        self.assertEqual(
            detect_os_family_version("Ubuntu 22.04.5 LTS"),
            ("Ubuntu", "22.04"),
        )
        self.assertEqual(
            detect_os_family_version("Oracle Linux Server release 8.10"),
            ("OEL", "8"),
        )
        self.assertEqual(
            detect_os_family_version("Red Hat Enterprise Linux release 9.4"),
            ("RHEL", "9"),
        )
        self.assertEqual(
            detect_os_family_version("Debian GNU/Linux 12 (bookworm)"),
            ("Debian", "12"),
        )

    def test_lifecycle_catalog_and_override(self):
        ubuntu = resolve_os_lifecycle("Ubuntu 22.04.5 LTS")
        self.assertEqual(ubuntu.support_end, date(2027, 5, 31))
        overridden = resolve_os_lifecycle("Ubuntu 22.04.5 LTS", date(2032, 5, 31))
        self.assertEqual(overridden.support_end, date(2032, 5, 31))
        self.assertEqual(overridden.source, "Zabbix tag override")

    def test_lifecycle_status_boundaries(self):
        today = date(2026, 7, 23)
        self.assertEqual(lifecycle_status(None, today), "unknown")
        self.assertEqual(lifecycle_status(date(2026, 7, 22), today), "eol")
        self.assertEqual(lifecycle_status(date(2027, 1, 1), today), "expiring")
        self.assertEqual(lifecycle_status(date(2029, 1, 1), today), "active")

    def test_patch_status_does_not_assume_compliance(self):
        self.assertEqual(patch_status(None, None, None), "unknown")
        self.assertEqual(patch_status(0, 0, False), "compliant")
        self.assertEqual(patch_status(2, 0, False), "action-required")
        self.assertEqual(patch_status(0, 1, False), "action-required")
        self.assertEqual(patch_status(0, 0, True), "action-required")

    def test_calculates_last_reboot_from_zabbix_observation(self):
        observed_at = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
        self.assertEqual(
            last_reboot_at(36 * 3600, observed_at),
            datetime(2026, 7, 22, 0, 0, tzinfo=UTC),
        )
        self.assertIsNone(last_reboot_at(None, observed_at))

    def test_normalizes_criticality_and_dates(self):
        self.assertEqual(normalize_criticality("P1"), "CRITICAL")
        self.assertEqual(normalize_criticality("tier_1"), "HIGH")
        self.assertEqual(normalize_criticality("unmapped"), "UNKNOWN")
        self.assertEqual(parse_date_value("2030-12-31"), date(2030, 12, 31))
        self.assertEqual(parse_date_value("31.12.2030"), date(2030, 12, 31))


if __name__ == "__main__":
    unittest.main()
