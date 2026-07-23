import unittest

from app.services.zabbix_items import (
    filesystem_inventory_from_items,
    operating_system_item_label,
    patch_inventory_from_items,
    performance_inventory_from_items,
)


class ZabbixItemTests(unittest.TestCase):
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

    def test_extracts_performance_and_root_disk_metrics(self):
        values = {
            "system.cpu.util[,idle]": "82.5",
            "vm.memory.size[pused]": "71.25",
            "system.cpu.load[all,avg1]": "1.82",
            "vfs.fs.size[/,total]": str(100 * 1024**3),
            "vfs.fs.size[/,used]": str(84 * 1024**3),
            "vfs.fs.size[/var,total]": str(50 * 1024**3),
            "vfs.fs.size[/var,used]": str(47 * 1024**3),
        }
        result = performance_inventory_from_items(values)
        self.assertEqual(result["cpu_utilization_pct"], 17.5)
        self.assertEqual(result["memory_utilization_pct"], 71.2)
        self.assertEqual(result["load_average_1m"], 1.82)
        self.assertEqual(result["root_disk_total_gb"], 100.0)
        self.assertEqual(result["root_disk_used_gb"], 84.0)
        self.assertEqual(result["root_disk_used_pct"], 84.0)
        self.assertTrue(result["has_performance_data"])
        filesystems = filesystem_inventory_from_items(values)
        self.assertEqual([filesystem["mount_point"] for filesystem in filesystems], ["/", "/var"])
        self.assertEqual(filesystems[1]["used_pct"], 94.0)


if __name__ == "__main__":
    unittest.main()
