import unittest
from datetime import date
from types import SimpleNamespace

from app.services.host_health import (
    disk_capacity_status,
    server_health,
    utilization_status,
)


class HostHealthTests(unittest.TestCase):
    def test_healthy_server_scores_100(self):
        host = SimpleNamespace(
            monitoring_status="ok",
            problem_count=0,
            cpu_utilization_pct=22.0,
            memory_utilization_pct=48.0,
            root_disk_used_pct=35.0,
            os_support_end_date=date(2099, 12, 31),
        )
        health = server_health(host)
        self.assertEqual(health.score, 100)
        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.reasons, ())

    def test_critical_server_accumulates_operational_risk(self):
        host = SimpleNamespace(
            monitoring_status="down",
            problem_count=3,
            cpu_utilization_pct=96.0,
            memory_utilization_pct=91.0,
            root_disk_used_pct=97.0,
            os_support_end_date=date(2020, 1, 1),
        )
        health = server_health(host)
        self.assertEqual(health.score, 0)
        self.assertEqual(health.status, "critical")
        self.assertGreaterEqual(len(health.reasons), 5)

    def test_metric_status_thresholds(self):
        self.assertEqual(utilization_status(None), "unknown")
        self.assertEqual(utilization_status(75), "warning")
        self.assertEqual(utilization_status(90), "critical")
        self.assertEqual(disk_capacity_status(79.9), "healthy")
        self.assertEqual(disk_capacity_status(80), "warning")
        self.assertEqual(disk_capacity_status(95), "critical")


if __name__ == "__main__":
    unittest.main()
