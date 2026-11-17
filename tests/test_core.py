import unittest
from datetime import date
from decimal import Decimal
from quant_g0.core import Bar,Quality,Ledger,guard,compare_samples
A,B,C=date(2010,1,4),date(2010,1,5),date(2010,1,6)
def bar(day=A,**kw):
    row=dict(day=day,open=100,high=101,low=99,close=100,volume=10);row.update(kw);return Bar(**row)
def bought(fee='0'):
    b=Ledger(fee=fee); b.signal(A); b.buy(B,100);return b
class CoreTests(unittest.TestCase):
    def test_good_quality(self):
        q=Quality([A]);q.add(bar());self.assertEqual(q.summary()['status'],'PASS')
    def test_missing(self):
        q=Quality([A,B]);q.add(bar());self.assertEqual(q.summary()['missing'],1)
    def test_duplicate(self):
        q=Quality([A]);q.add(bar());q.add(bar());self.assertEqual(q.summary()['duplicates'],1)
    def test_invalid_prices(self):
        for row in [bar(open=0),bar(close=-1),bar(high=98),bar(low=102),bar(volume=-1),bar(close=float('nan')),bar(open=float('inf'))]:
            with self.subTest(row=row):
                q=Quality([A]);self.assertFalse(q.add(row));self.assertEqual(q.summary()['status'],'FAIL')
    def test_zero_volume(self):
        q=Quality([A]);q.add(bar(volume=0));self.assertEqual(q.summary()['status'],'FAIL')
    def test_unexpected_session(self):
        q=Quality([A]);q.add(bar(B));self.assertEqual(q.summary()['unexpected'],1)
    def test_fee_and_remaining_cash(self):
        b=bought('1');self.assertEqual(b.qty,99);self.assertEqual(b.cash,Decimal(99))
    def test_insufficient(self):
        b=Ledger(initial='50');b.signal(A)
        with self.assertRaises(ValueError): b.buy(B,100)
        self.assertEqual(b.cash,50)
    def test_dividend_conservation(self):
        b=bought();before=b.value(B,100);b.action(C,'dividend',1,'d');self.assertEqual(b.value(C,99),before)
    def test_adjusted_rejected(self):
        with self.assertRaises(ValueError):Ledger(normalization='adjusted')
    def test_duplicate_dividend_rejected(self):
        b=bought();b.action(C,'dividend',1,'d')
        with self.assertRaises(ValueError):b.action(C,'dividend',1,'d')
    def test_split_conservation(self):
        b=bought();before=b.value(B,100);b.action(C,'split','.5','s');self.assertEqual(b.qty,200);self.assertEqual(b.value(C,50),before)
    def test_fractional_split_blocks(self):
        b=bought('1')
        with self.assertRaises(ValueError):b.action(C,'split',2,'s')
        self.assertEqual(b.qty,99)
    def test_fractional_split_cash(self):
        b=bought('1');before=b.value(B,100);b.action(C,'split',2,'s',200);self.assertEqual(b.value(C,200),before)
    def test_cash_reconciliation(self):
        b=bought('1');self.assertTrue(b.reconcile(B,100)[0]);b.cash+=Decimal('.02');self.assertFalse(b.reconcile(B,100)[0])
    def test_share_reconciliation(self):
        b=bought();b.qty+=1;self.assertFalse(b.reconcile(B,100)[0])
    def test_signal_then_fill(self):
        b=Ledger();b.signal(A)
        with self.assertRaises(ValueError):b.buy(A,100)
        with self.assertRaises(ValueError):b.buy(date(2010,1,3),100)
        b.buy(B,100);self.assertTrue(b.bought)
    def test_no_signal(self):
        with self.assertRaises(ValueError):Ledger().buy(B,100)
    def test_holdout_and_validation_accounting_denied(self):
        for d in [date(2020,1,1),date(2023,1,1),date(2025,12,31)]:
            with self.assertRaises(ValueError):guard(d,'accounting')
            guard(d,'quality')
    def test_outside_quality_denied(self):
        for d in [date(2009,12,31),date(2026,1,1)]:
            with self.assertRaises(ValueError):guard(d,'quality')
    def test_purpose_denied(self):
        with self.assertRaises(ValueError):guard(A,'ranking')
    def test_missing_independent_evidence(self):self.assertEqual(compare_samples([])['status'],'BLOCKED')
    def test_independent_samples(self):
        rows=[]
        for kind,n in [('price',5),('dividend',2)]:
            for i in range(n): rows.append(dict(date=f'2010-01-{4+i:02d}',kind=kind,qc_value='100',independent_value='100',normalization='raw',source_url='https://example.test/synthetic',license_note='SYNTHETIC unit test only',tolerance='.01',tolerance_reason='synthetic cent precision'))
        self.assertEqual(compare_samples(rows)['status'],'PASS');rows[0]['independent_value']='101';self.assertEqual(compare_samples(rows)['status'],'FAIL')
    def test_sample_holdout_denied(self):
        with self.assertRaises(ValueError):compare_samples([dict(date='2023-01-03')])
    def test_invalid_fee(self):
        for fee in ['-1','NaN','Infinity']:
            with self.assertRaises(ValueError):Ledger(fee=fee)
if __name__=='__main__':unittest.main()
