"""G0 deterministic checks. No network, orders or strategy evaluation."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal as PythonDecimal, ROUND_FLOOR as PY_ROUND_FLOOR
import hashlib
import json

D = lambda x: PythonDecimal(str(x))
START, DEV_END, END = date(2010, 1, 1), date(2019, 12, 31), date(2025, 12, 31)

def guard(day, purpose):
    if purpose not in ('quality', 'accounting'):
        raise ValueError('unsupported purpose')
    if not START <= day <= (END if purpose == 'quality' else DEV_END):
        raise ValueError('window denied')

@dataclass(frozen=True)
class G0DailyBar:
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
        qty = max(0, int(((self.cash-self.fee)/price).to_integral_value(rounding=PY_ROUND_FLOOR)))
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
        """Replay using independently derived quantities; validate every recorded result.

        Input prices/distributions/factors still require independent source review.
        A coherent rewrite of all source inputs cannot be authenticated by replay.
        """
        guard(day, 'accounting')
        price, tolerance = D(price), D(tolerance)
        if not price.is_finite() or price <= 0 or tolerance != D('0.01'):
            raise ValueError('invalid valuation or altered reconciliation tolerance')
        cash, qty, bought = self.initial, 0, False
        previous = START
        seen_actions = set()
        mismatch = False
        error = D(0)
        try:
            for kind, event_day, delta, *detail in self.events:
                event_day = date.fromisoformat(event_day)
                guard(event_day, 'accounting')
                if event_day < previous or event_day > day:
                    raise ValueError('invalid event chronology')
                previous = event_day
                if kind != 'buy':
                    key = (kind, event_day)
                    if key in seen_actions: raise ValueError('duplicate journal action')
                    seen_actions.add(key)
                recorded_delta = D(delta)
                if not recorded_delta.is_finite(): raise ValueError('nonfinite cash delta')
                if kind == 'buy':
                    recorded_qty, execution_price, fee = detail
                    execution_price, fee = D(execution_price), D(fee)
                    if (bought or self.signal_day is None or event_day <= self.signal_day
                            or not execution_price.is_finite() or execution_price <= 0
                            or not fee.is_finite() or fee != self.fee):
                        raise ValueError('invalid buy input')
                    n = max(0, int(((cash-fee)/execution_price).to_integral_value(rounding=PY_ROUND_FLOOR)))
                    if n <= 0: raise ValueError('unfunded buy')
                    mismatch |= recorded_qty != n
                    expected_delta = -(D(n)*execution_price+fee)
                    qty += n
                    bought = True
                elif kind == 'dividend':
                    recorded_qty, distribution = detail
                    distribution = D(distribution)
                    if not distribution.is_finite() or distribution <= 0:
                        raise ValueError('invalid dividend input')
                    mismatch |= recorded_qty != qty
                    expected_delta = D(qty)*distribution
                elif kind == 'split':
                    recorded_qty, factor, recorded_whole, ref = detail
                    factor, ref = D(factor), D(ref)
                    if not factor.is_finite() or factor <= 0 or not ref.is_finite() or ref < 0:
                        raise ValueError('invalid split input')
                    exact = D(qty)/factor
                    whole = int(exact.to_integral_value(rounding=PY_ROUND_FLOOR))
                    fraction = exact-D(whole)
                    if fraction and ref <= 0: raise ValueError('missing cash-in-lieu input')
                    mismatch |= recorded_qty != qty or recorded_whole != whole
                    expected_delta = fraction*ref
                    qty = whole
                else:
                    raise ValueError('unknown journal event')
                # Raw recorded cash deltas are audit outputs, never replay inputs.
                mismatch |= recorded_delta != expected_delta
                error = max(error, abs(recorded_delta-expected_delta))
                cash += expected_delta
            error = max(error, abs(cash-self.cash), abs(D(qty-self.qty)*price),
                        abs(cash+D(qty)*price-self.value(day,price)))
            mismatch |= bought != self.bought
            if not error.is_finite(): raise ValueError('nonfinite reconciliation')
        except (ValueError, TypeError, ArithmeticError):
            return False, D('Infinity')
        return not mismatch and error <= tolerance, error


def compare_samples(rows, config, dividend_reference=None):
    """Validate exactly preregistered SPY samples; never trust row tolerances.

    dividend_reference must come from the complete development-window cloud run,
    independently of the selected comparison rows. Provenance remains reviewable,
    not cryptographically authenticated by this routine.
    """
    required_prices = set(config['price_sample_dates'])
    locked = {'price': D('0.01'), 'dividend': D('0.000001'), 'split': D('0.00000001')}
    if len(required_prices) != 5 or len(config['price_sample_dates']) != 5:
        raise ValueError('invalid preregistered price dates')
    for value in required_prices: guard(date.fromisoformat(value), 'accounting')
    if config.get('sample_tolerances') != {k: str(v) for k,v in locked.items()}:
        raise ValueError('altered frozen sample tolerances')
    failures, prices, dividends, seen = [], set(), set(), set()
    required_dividends = None
    qc_dividends = {}
    if dividend_reference is not None:
        ref = dividend_reference
        if (ref.get('symbol') != 'SPY' or ref.get('start') != str(START)
                or ref.get('end') != str(DEV_END) or ref.get('complete') is not True):
            raise ValueError('incomplete or wrong dividend reference')
        dates = ref['event_dates']
        if dates != sorted(set(dates)) or len(dates) < 2:
            raise ValueError('invalid dividend chronology')
        for value in dates: guard(date.fromisoformat(value), 'accounting')
        first = ref['first_two']
        if [x['date'] for x in first] != dates[:2]:
            raise ValueError('reference does not select earliest two dividends')
        required_dividends = set(dates[:2])
        for r in first:
            value = D(r['qc_value'])
            if not value.is_finite() or value <= 0: raise ValueError('invalid reference dividend')
            qc_dividends[r['date']] = value
    for r in rows:
        guard(date.fromisoformat(r['date']), 'accounting')
        kind, day = r['kind'], r['date']
        if kind not in locked: raise ValueError('invalid sample kind')
        if r.get('symbol') != 'SPY': raise ValueError('sample must identify SPY')
        key = (kind, day)
        if key in seen: raise ValueError('duplicate sample')
        seen.add(key)
        if kind == 'price' and (day not in required_prices or r.get('field') != 'close'):
            raise ValueError('wrong price date or field')
        if kind in ('dividend', 'split') and r.get('field') != {'dividend':'distribution', 'split':'factor'}[kind]:
            raise ValueError('wrong corporate action field')
        if kind == 'dividend' and required_dividends is not None and day not in required_dividends:
            raise ValueError('not one of earliest two SPY dividends')
        if r['normalization'] != 'raw' or not r['source_url'] or not r['license_note']:
            raise ValueError('missing provenance/raw convention')
        a,b,t = map(D, (r['qc_value'],r['independent_value'],r['tolerance']))
        if (not all(x.is_finite() for x in (a,b,t)) or min(a,b)<=0
                or t != locked[kind] or not r['tolerance_reason']):
            raise ValueError('invalid sample or altered frozen tolerance')
        if kind == 'dividend' and required_dividends is not None and a != qc_dividends[day]:
            raise ValueError('QC dividend differs from source reference')
        diff = abs(a-b)
        if diff > locked[kind]: failures.append(dict(date=day,kind=kind,difference=str(diff)))
        if kind == 'price': prices.add(day)
        if kind == 'dividend': dividends.add(day)
    complete = prices == required_prices and required_dividends is not None and dividends == required_dividends
    return dict(status='FAIL' if failures else ('PASS' if complete else 'BLOCKED'),
                price_days=len(prices), dividend_events=len(dividends), failures=failures,
                dividend_reference='available' if required_dividends is not None else 'BLOCKED: complete cloud event reference required')
