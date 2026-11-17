"""Offline namespace regression, not a real LEAN execution."""
import ast
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal as NativeDecimal
import importlib.util
from pathlib import Path
import sys
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]

class DotNetDecimal:
    def __init__(self, value):
        if not isinstance(value,float):
            raise TypeError("argument 1 ('value') expected float, got str")

class PlatformBar:
    def __init__(self,*args):raise TypeError('platform Bar cannot construct G0DailyBar')

class FakeAlgorithm:
    def __init__(self):
        self.live_mode=False;self.settings=types.SimpleNamespace();self.logs=[]
    def set_start_date(self,*args):self.start=args
    def set_end_date(self,*args):self.end=args
    def set_time_zone(self,*args):pass
    def set_cash(self,*args):pass
    def add_equity(self,ticker,*args,**kwargs):
        hours=types.SimpleNamespace(is_date_open=lambda dt:dt.weekday()<5)
        return types.SimpleNamespace(symbol=ticker,exchange=types.SimpleNamespace(hours=hours))
    def debug(self,line):self.logs.append(line)

@contextmanager
def hostile_platform():
    fake=types.ModuleType('AlgorithmImports')
    fake.Decimal=DotNetDecimal;fake.Bar=PlatformBar;fake.ROUND_FLOOR='INVALID_PLATFORM_ROUNDING'
    fake.QCAlgorithm=FakeAlgorithm
    fake.Resolution=types.SimpleNamespace(DAILY='daily')
    fake.TimeZones=types.SimpleNamespace(NEW_YORK='America/New_York')
    fake.DataNormalizationMode=types.SimpleNamespace(RAW='raw')
    fake.SplitType=types.SimpleNamespace(SPLIT_OCCURRED='split')
    old=sys.modules.get('AlgorithmImports');sys.modules['AlgorithmImports']=fake
    try:yield fake
    finally:
        if old is None:sys.modules.pop('AlgorithmImports',None)
        else:sys.modules['AlgorithmImports']=old

@contextmanager
def bundle():
    with hostile_platform():
        name='_g0_r02_bundle'
        spec=importlib.util.spec_from_file_location(name,ROOT/'quantconnect/main.py')
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        try:spec.loader.exec_module(module);yield module
        finally:sys.modules.pop(name,None)

class R02Compatibility(unittest.TestCase):
    def test_reproduce_reported_wildcard_failure(self):
        with hostile_platform():
            ns={}
            exec('from decimal import Decimal\nD = lambda x: Decimal(str(x))\nfrom AlgorithmImports import *',ns)
            with self.assertRaisesRegex(TypeError,'expected float'):ns['D']('10000')
            self.assertIs(ns['Bar'],PlatformBar)
    def test_decimal_and_bar_survive_hostile_exports(self):
        with bundle() as m:
            for value in ('10000','0.01',1,1.25,NativeDecimal('0.1')):
                self.assertIs(type(m.D(value)),NativeDecimal)
            self.assertIs(m.PythonDecimal,NativeDecimal)
            row=m.G0DailyBar(datetime(2010,1,4).date(),100,101,99,100,10)
            self.assertEqual(row.close,100)
            self.assertNotIn('Bar',m.__dict__)
            self.assertNotIn('Decimal',m.__dict__)
    def test_initialize_and_on_data_with_conflicting_platform_names(self):
        with bundle() as m:
            a=m.G0Audit();a.initialize()
            self.assertEqual(a.start,(2010,1,1));self.assertEqual(a.end,(2025,12,31))
            self.assertEqual(len(a.assets),8)
            self.assertTrue(all(type(b.cash) is NativeDecimal for b in a.books))
            for dt in [datetime(2010,1,4),datetime(2010,1,5)]:
                bars={symbol:types.SimpleNamespace(time=dt,open=100,high=101,low=99,close=100,volume=10) for symbol in a.assets.values()}
                a.on_data(types.SimpleNamespace(dividends={},splits={},bars=bars))
            self.assertEqual(a.books[0].qty,100);self.assertEqual(a.books[1].qty,99)
            self.assertIsNone(a.accounting_block)
            self.assertTrue(a.books[1].reconcile(datetime(2010,1,5).date(),100)[0])
    def test_no_wildcard_imports_in_generated_bundle(self):
        tree=ast.parse((ROOT/'quantconnect/main.py').read_text())
        self.assertFalse(any(isinstance(n,ast.ImportFrom) and any(a.name=='*' for a in n.names) for n in ast.walk(tree)))
