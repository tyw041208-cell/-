"""G0 deterministic checks. No network, orders or strategy evaluation."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json

D = lambda x: Decimal(str(x))
START, DEV_END, END = date(2010, 1, 1), date(2019, 12, 31), date(2025, 12, 31)

def guard(day, purpose):
    if purpose not in ('quality', 'accounting'):
        raise ValueError('unsupported purpose')
    if not START <= day <= (END if purpose == 'quality' else DEV_END):
        raise ValueError('window denied')

@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float

class Quality:
    def __init__(self, expected):
        self.expected = set(expected)
        self.seen = set()
        self.count = self.duplicates = self.invalid = self.zero_volume = 0
        self.hash = hashlib.sha256()
        self.first = self.last = None

    def add(self, bar):
        guard(bar.day, 'quality')
        self.count += 1
        self.duplicates += bar.day in self.seen
        self.seen.add(bar.day)
        self.first = min(self.first or bar.day, bar.day)
        self.last = max(self.last or bar.day, bar.day)
        p = [D(x) for x in (bar.open, bar.high, bar.low, bar.close, bar.volume)]
        valid = all(x.is_finite() for x in p)
        if valid:
            o,h,l,c,v = p
            valid = min(o,h,l,c) > 0 and l <= min(o,c) <= max(o,c) <= h and v >= 0
            self.zero_volume += v == 0
        self.invalid += not valid
        self.hash.update(repr(bar).encode())
        return valid

    def summary(self):
        missing = self.expected - self.seen
        extra = self.seen - self.expected
        return dict(rows=self.count, first=str(self.first), last=str(self.last),
                    missing=len(missing), unexpected=len(extra), duplicates=self.duplicates,
                    invalid=self.invalid, zero_volume=self.zero_volume,
                    sha256=self.hash.hexdigest(),
                    status='PASS' if self.count and not (missing or extra or self.duplicates or self.invalid or self.zero_volume) else 'FAIL')

class Ledger:
    """Raw prices + ex-date cash convention. All prices/fees are USD assumptions."""
    def __init__(self, fee='0', initial='10000', normalization='raw'):
        if normalization != 'raw':
            raise ValueError('dividend cash requires raw prices')
        self.initial = self.cash = D(initial)
        self.fee = D(fee)
        if not self.cash.is_finite() or not self.fee.is_finite() or min(self.cash,self.fee)<0:
            raise ValueError('invalid cash/fee')
        self.qty = 0
        self.signal_day = None
        self.bought = False
        self.events = []
        self.event_ids = set()

    def signal(self, day):
        guard(day, 'accounting')
        if self.signal_day is None: self.signal_day = day

    def buy(self, day, price):
        guard(day, 'accounting')
        price = D(price)
        if not price.is_finite() or price <= 0: raise ValueError('invalid price')
        if self.signal_day is None or day <= self.signal_day: raise ValueError('lookahead')
        if self.bought: raise ValueError('already bought')
        qty = max(0, int(((self.cash-self.fee)/price).to_integral_value(rounding=ROUND_FLOOR)))
        if qty == 0: raise ValueError('insufficient funds')
        delta = -(qty*price+self.fee)
        self.cash += delta; self.qty += qty; self.bought = True
        self.events.append(('buy', str(day), str(delta), qty, str(price), str(self.fee)))

    def action(self, day, kind, value, event_id, reference=None):
        guard(day, 'accounting')
        if event_id in self.event_ids: raise ValueError('duplicate action')
        value=D(value)
        if not value.is_finite() or value <= 0: raise ValueError('invalid action')
        if kind == 'dividend':
            delta=self.qty*value; self.cash += delta
            self.events.append(('dividend', str(day), str(delta), self.qty, str(value)))
        elif kind == 'split':
            exact=D(self.qty)/value; whole=int(exact)
            fraction=exact-whole
            if fraction and reference is None: raise ValueError('fractional split requires post-split cash-in-lieu price')
            ref=D(reference or 0)
            if not ref.is_finite() or ref < 0: raise ValueError('invalid reference')
            delta=fraction*ref
            self.cash += delta; old=self.qty; self.qty=whole
            self.events.append(('split',str(day),str(delta),old,str(value),whole,str(ref)))
        else: raise ValueError('unsupported action')
        self.event_ids.add(event_id)

    def value(self, day, price):
        guard(day,'accounting'); price=D(price)
        if not price.is_finite() or price <= 0: raise ValueError('invalid valuation')
        return self.cash+self.qty*price

    def reconcile(self, day, price, tolerance='0.01'):
        """Rebuild cash and holdings from journal; never read mutable cash/qty."""
        cash=self.initial; qty=0
        for event in self.events:
            kind, _, delta, *detail=event
            if kind=='buy':
                n, execution_price, fee = detail
                cash -= D(n)*D(execution_price)+D(fee)
                qty += n
            elif kind=='dividend':
                original_qty, distribution = detail
                cash += D(original_qty)*D(distribution)
            elif kind=='split':
                original_qty, factor, whole, ref = detail
                cash += (D(original_qty)/D(factor)-D(whole))*D(ref)
                qty = whole
        error=max(abs(cash-self.cash), abs(D(qty-self.qty)*D(price)),
                  abs(cash+qty*D(price)-self.value(day,price)))
        return error <= D(tolerance), error

def compare_samples(rows):
    """Only licensed development-window raw samples; missing evidence blocks."""
    prices=set(); dividends=set(); failures=[]
    for r in rows:
        guard(date.fromisoformat(r['date']), 'accounting')
        if r['kind'] not in ('price','dividend','split'): raise ValueError('invalid sample kind')
        if r['normalization']!='raw' or not r['source_url'] or not r['license_note']:
            raise ValueError('missing provenance/raw convention')
        a,b,t=map(D,(r['qc_value'],r['independent_value'],r['tolerance']))
        if not all(x.is_finite() for x in (a,b,t)) or min(a,b)<=0 or t<0 or not r['tolerance_reason']:
            raise ValueError('invalid sample')
        diff=abs(a-b)
        if diff>t: failures.append(dict(date=r['date'],kind=r['kind'],difference=str(diff)))
        if r['kind']=='price': prices.add(r['date'])
        if r['kind']=='dividend': dividends.add(r['date'])
    return dict(status='FAIL' if failures else ('PASS' if len(prices)>=5 and len(dividends)>=2 else 'BLOCKED'),
                price_days=len(prices), dividend_events=len(dividends), failures=failures)
