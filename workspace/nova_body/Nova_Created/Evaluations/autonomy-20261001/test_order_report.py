# Last updated: 2026-10-04 15:01:24
import unittest
from order_report import summarize

class ReportTests(unittest.TestCase):
    def test_paid_quantity(self):
        self.assertEqual(summarize([{"status": "paid", "unit_cents": 1250, "quantity": 2}]),
                         {"paid_orders": 1, "total_cents": 2500})

    def test_empty(self):
        self.assertEqual(summarize([]), {"paid_orders": 0, "total_cents": 0})

if __name__ == "__main__":
    unittest.main()
