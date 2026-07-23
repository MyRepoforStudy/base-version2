import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.capacity_sla import availability_sla, capacity_forecast


class CapacitySlaTests(unittest.TestCase):
    def test_forecasts_capacity_threshold_from_growth(self):
        now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
        snapshots = [
            SimpleNamespace(
                observed_at=now - timedelta(days=day),
                disk_mount="/var",
                disk_used_pct=80 - day,
            )
            for day in range(7, -1, -1)
        ]
        forecast = capacity_forecast(
            snapshots,
            current_pct=80,
            mount_point="/var",
            target_pct=95,
            now=now,
        )
        self.assertEqual(forecast.daily_growth_pct, 1.0)
        self.assertEqual(forecast.days_remaining, 15)
        self.assertEqual(forecast.status, "warning")

    def test_marks_capacity_as_collecting_without_history(self):
        now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
        forecast = capacity_forecast(
            [
                SimpleNamespace(
                    observed_at=now,
                    disk_mount="/",
                    disk_used_pct=50,
                )
            ],
            current_pct=50,
            mount_point="/",
            now=now,
        )
        self.assertEqual(forecast.status, "collecting")
        self.assertIsNone(forecast.forecast_at)

    def test_calculates_weighted_availability(self):
        now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
        snapshots = []
        for hours_ago in range(24, -1, -1):
            snapshots.append(
                SimpleNamespace(
                    observed_at=now - timedelta(hours=hours_ago),
                    monitoring_status="down" if hours_ago == 12 else "ok",
                )
            )
        sla = availability_sla(
            snapshots,
            target_percent=99,
            window_days=1,
            max_gap_seconds=7200,
            now=now,
        )
        self.assertEqual(sla.coverage_pct, 100.0)
        self.assertAlmostEqual(sla.availability_pct, 95.833, places=3)
        self.assertEqual(sla.status, "missed")


if __name__ == "__main__":
    unittest.main()
