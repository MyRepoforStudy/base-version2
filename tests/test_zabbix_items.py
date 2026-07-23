import unittest

from app.services.zabbix_items import operating_system_item_label, patch_inventory_from_items


class ZabbixPatchItemTests(unittest.TestCase):
    def test_extracts_patch_inventory(self):
        values = {
            "system.uname": "Linux app01 5.15.0-143-generic #153-Ubuntu SMP x86_64",
            "linux.updates.pending": "17",
            "linux.updates.security": "3",
            "linux.reboot.required": "yes",
            "linux.patch.last": "2026-07-20T10:30:00Z",
        }
        result = patch_inventory_from_items(values)
        self.assertEqual(result["kernel_version"], "5.15.0-143-generic")
        self.assertEqual(result["updates_pending"], 17)
        self.assertEqual(result["security_updates_pending"], 3)
        self.assertIs(result["reboot_required"], True)
        self.assertTrue(result["has_patch_data"])
        self.assertEqual(result["last_patch_at"].isoformat(), "2026-07-20T10:30:00+00:00")

    def test_missing_items_remain_unknown(self):
        result = patch_inventory_from_items({})
        self.assertIsNone(result["updates_pending"])
        self.assertIsNone(result["security_updates_pending"])
        self.assertIsNone(result["reboot_required"])
        self.assertFalse(result["has_patch_data"])

    def test_extracts_readable_os_from_zabbix_json(self):
        value = '{"os_type":"linux","product_name":"Ubuntu","version_full":"Ubuntu 24.04.2 LTS","version":"24.04"}'
        self.assertEqual(
            operating_system_item_label({"system.sw.os.get": value}),
            "Ubuntu 24.04.2 LTS",
        )


if __name__ == "__main__":
    unittest.main()
