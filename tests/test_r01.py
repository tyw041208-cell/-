"""G0-R01 regression tests; every price/event here is SYNTHETIC, not evidence."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import unittest
from quant_g0.core import Ledger,compare_samples
CFG=json.loads((Path(__file__).resolve().parents[1]/'config/g0.json').read_text())
A,B,C,E=map(date.fromisoformat,['2010-01-04','2010-01-05','2010-01-06','2010-01-07'])
def book(fee='0'):
    b=Ledger(fee=fee);b.signal(A);b.buy(B,100);return b

def reference():
    return dict(symbol='SPY',start='2010-01-01',end='2019-12-31',complete=True,
                event_dates=['2010-03-19','2010-06-18','2010-09-17'],
                first_two=[dict(date='2010-03-19',qc_value='1'),dict(date='2010-06-18',qc_value='2')])
def samples():
    rows=[]
    for day in CFG['price_sample_dates']:
        rows.append(dict(symbol='SPY',field='close',date=day,kind='price',qc_value='100',independent_value='100',normalization='raw',source_url='https://example.test/SYNTHETIC',license_note='SYNTHETIC fixture only',tolerance='0.01',tolerance_reason='frozen synthetic precision'))
    for event in reference()['first_two']:
        rows.append(dict(symbol='SPY',field='distribution',date=event['date'],kind='dividend',qc_value=event['qc_value'],independent_value=event['qc_value'],normalization='raw',source_url='https://example.test/SYNTHETIC',license_note='SYNTHETIC fixture only',tolerance='0.000001',tolerance_reason='frozen synthetic precision'))
    return rows
class ReplayRegression(unittest.TestCase):
    def test_dividend_uses_rebuilt_qty(self):
        b=book();b.qty=101;b.action(C,'dividend',1,'d')
        self.assertFalse(b.reconcile(C,99)[0])
    def test_coherent_forged_dividend_qty_and_cash(self):
        b=book();b.action(C,'dividend',1,'d');b.events[1]=('dividend',str(C),'101',101,'1');b.cash=Decimal(101)
        self.assertFalse(b.reconcile(C,99)[0])
    def test_coherent_forged_split_results(self):
        b=book('1');b.action(C,'split',2,'s',200)
        e=list(b.events[1]);e[2]='0';e[3]=100;e[5]=50;b.events[1]=tuple(e);b.qty=50;b.cash=Decimal(99)
        self.assertFalse(b.reconcile(C,200)[0])
    def test_split_then_dividend_replays(self):
        b=book('1');b.action(C,'split',2,'s',200);b.action(E,'dividend','1','d')
        self.assertEqual(b.qty,49);self.assertEqual(b.cash,248);self.assertTrue(b.reconcile(E,199)[0])
    def test_original_cash_delta_tamper(self):
        b=book();e=list(b.events[0]);e[2]='-9999.999';b.events[0]=tuple(e)
        self.assertFalse(b.reconcile(B,100)[0])
    def test_dividend_recorded_qty_only_tamper(self):
        b=book();b.action(C,'dividend',1,'d');e=list(b.events[1]);e[3]=101;b.events[1]=tuple(e)
        self.assertFalse(b.reconcile(C,99)[0])
    def test_split_recorded_whole_only_tamper(self):
        b=book();b.action(C,'split','.5','s');e=list(b.events[1]);e[5]=199;b.events[1]=tuple(e)
        self.assertFalse(b.reconcile(C,50)[0])
    def test_buy_quantity_and_state_tamper(self):
        b=book();e=list(b.events[0]);e[3]=99;e[2]='-9900';b.events[0]=tuple(e);b.qty=99;b.cash=Decimal(100)
        self.assertFalse(b.reconcile(B,100)[0])
    def test_unknown_event(self):
        b=book();b.events.append(('unknown',str(C),'0'));self.assertFalse(b.reconcile(C,100)[0])
    def test_nan_journal(self):
        b=book();e=list(b.events[0]);e[2]='NaN';b.events[0]=tuple(e);self.assertFalse(b.reconcile(B,100)[0])
    def test_future_event(self):
        b=book();b.action(C,'dividend',1,'d');self.assertFalse(b.reconcile(B,100)[0])
    def test_reordered_events(self):
        b=book();b.action(C,'dividend',1,'d');b.events.reverse();self.assertFalse(b.reconcile(C,100)[0])
    def test_no_tolerance_override(self):
        with self.assertRaises(ValueError):book().reconcile(B,100,'100')
    def test_duplicate_journal_action_with_matching_state(self):
        b=book();b.action(C,'dividend',1,'d');b.events.append(b.events[-1]);b.cash+=Decimal(100)
        self.assertFalse(b.reconcile(C,99)[0])
class SampleRegression(unittest.TestCase):
    def check(self,rows=None,ref=None):return compare_samples(samples() if rows is None else rows,CFG,reference() if ref is None else ref)
    def test_exact_registered_samples(self):self.assertEqual(self.check()['status'],'PASS')
    def test_missing_reference_blocks(self):self.assertEqual(compare_samples(samples(),CFG)['status'],'BLOCKED')
    def test_missing_price_blocks(self):self.assertEqual(self.check(samples()[1:])['status'],'BLOCKED')
    def test_missing_dividend_blocks(self):self.assertEqual(self.check(samples()[:-1])['status'],'BLOCKED')
    def test_wrong_price_date(self):
        rows=samples();rows[0]['date']='2010-01-11'
        with self.assertRaises(ValueError):self.check(rows)
    def test_duplicate(self):
        rows=samples();rows.append(deepcopy(rows[0]))
        with self.assertRaises(ValueError):self.check(rows)
    def test_wrong_symbol(self):
        rows=samples();rows[0]['symbol']='QQQ'
        with self.assertRaises(ValueError):self.check(rows)
    def test_wrong_price_field(self):
        rows=samples();rows[0]['field']='open'
        with self.assertRaises(ValueError):self.check(rows)
    def test_later_dividend_cherry_pick(self):
        rows=samples();rows[-1]['date']='2010-09-17'
        with self.assertRaises(ValueError):self.check(rows)
    def test_forged_qc_distribution(self):
        rows=samples();rows[-1]['qc_value']='3';rows[-1]['independent_value']='3'
        with self.assertRaises(ValueError):self.check(rows)
    def test_each_tolerance_locked(self):
        for kind in ['price','dividend','split']:
            with self.subTest(kind=kind):
                rows=samples();row=deepcopy(rows[0]);row['kind']=kind;row['field']='factor' if kind=='split' else row['field'];row['date']='2010-07-01' if kind=='split' else row['date'];row['tolerance']='100'
                if kind=='dividend':row=deepcopy(rows[-1]);row['tolerance']='100';rows[-1]=row
                elif kind=='price':rows[0]=row
                else:rows.append(row)
                with self.assertRaises(ValueError):self.check(rows)
    def test_tolerance_config_tamper(self):
        cfg=deepcopy(CFG);cfg['sample_tolerances']['price']='100'
        with self.assertRaises(ValueError):compare_samples(samples(),cfg,reference())
    def test_diff_over_locked_tolerance(self):
        rows=samples();rows[0]['independent_value']='100.010001';self.assertEqual(self.check(rows)['status'],'FAIL')
    def test_dividend_precision(self):
        rows=samples();rows[-1]['independent_value']='2.000002';self.assertEqual(self.check(rows)['status'],'FAIL')
    def test_reference_incomplete(self):
        ref=reference();ref['complete']=False
        with self.assertRaises(ValueError):self.check(ref=ref)
    def test_reference_unsorted(self):
        ref=reference();ref['event_dates'].reverse()
        with self.assertRaises(ValueError):self.check(ref=ref)
    def test_reference_first_two_cherry_pick(self):
        ref=reference();ref['first_two'][1]['date']='2010-09-17'
        with self.assertRaises(ValueError):self.check(ref=ref)
    def test_reference_holdout(self):
        ref=reference();ref['event_dates'].append('2023-03-17')
        with self.assertRaises(ValueError):self.check(ref=ref)
    def test_valid_optional_split_and_boundary(self):
        rows=samples();row=deepcopy(rows[0]);row.update(kind='split',field='factor',date='2010-07-01',qc_value='.5',independent_value='.50000001',tolerance='0.00000001');rows.append(row)
        self.assertEqual(self.check(rows)['status'],'PASS');rows[-1]['independent_value']='.50000002';self.assertEqual(self.check(rows)['status'],'FAIL')

    def test_duplicate_dividend(self):
        rows=samples();rows.append(deepcopy(rows[-1]))
        with self.assertRaises(ValueError):self.check(rows)
    def test_wrong_corporate_action_field(self):
        rows=samples();rows[-1]['field']='payment_date'
        with self.assertRaises(ValueError):self.check(rows)
    def test_tighter_tolerance_also_denied(self):
        rows=samples();rows[0]['tolerance']='0.001'
        with self.assertRaises(ValueError):self.check(rows)
    def test_original_experiment_unchanged(self):
        self.assertEqual(CFG['symbols'],['SPY','QQQ','IWM','EFA','EEM','TLT','GLD','SHY'])
        self.assertEqual(CFG['price_sample_dates'],['2010-01-04','2010-01-05','2010-01-06','2010-01-07','2010-01-08'])
        self.assertEqual((CFG['quality_start'],CFG['quality_end'],CFG['accounting_end']),('2010-01-01','2025-12-31','2019-12-31'))
        self.assertEqual((CFG['initial_usd'],CFG['fees_usd'],CFG['interest_usd']),('10000',['0','1'],'0'))
