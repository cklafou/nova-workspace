# Last updated: 2026-10-03 11:00:25
import unittest
from report import report
class ReportTests(unittest.TestCase):
    def test_paid_quantities(self):
        self.assertEqual(report([{'paid':True,'quantity':2,'unit_cents':1299},{'paid':False,'quantity':4,'unit_cents':500},{'paid':True,'quantity':1,'unit_cents':1099}]),{'paid_orders':2,'total_cents':3697})
    def test_empty(self):
        self.assertEqual(report([]),{'paid_orders':0,'total_cents':0})
if __name__=='__main__':unittest.main()
