# This adapter is bundled with core.py into main.py by tools/build_cloud.py.
from AlgorithmImports import (
    QCAlgorithm, Resolution, TimeZones, DataNormalizationMode, SplitType,
)
from datetime import datetime, timedelta

class G0Audit(QCAlgorithm):
    def initialize(self):
        if self.live_mode:
            raise RuntimeError('G0 refuses live execution')
        self.set_start_date(2010, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.set_cash(10000)
        self.settings.daily_precise_end_time = True
        self.assets = {}
        self.quality = {}
        self.actions = {}
        self.books = [Ledger(fee=f) for f in CONFIG['fees_usd']]
        self.max_error = D(0)
        self.reconciled_days = 0
        self.accounting_block = None
        self.last_dev = None
        self.div_sample_count = 0
        self.dev_dividends = []
        for ticker in CONFIG['symbols']:
            security = self.add_equity(ticker, Resolution.DAILY, fill_forward=False,
                                      extended_market_hours=False,
                                      data_normalization_mode=DataNormalizationMode.RAW)
            symbol = security.symbol
            self.assets[ticker] = symbol
            expected=[]
            dt=datetime(2010,1,1)
            while dt.date() <= END:
                if security.exchange.hours.is_date_open(dt): expected.append(dt.date())
                dt += timedelta(days=1)
            self.quality[ticker] = Quality(expected)
            self.actions[ticker] = dict(dividends=0,splits=0,invalid=0)
        self.debug('G0_CONFIG '+json.dumps(CONFIG,sort_keys=True))
        self.debug('G0_BOUNDARY no orders; no holdout performance; raw; ex-date dividend cash; no warmup')

    def on_data(self, data):
        for ticker,symbol in self.assets.items():
            dividend=data.dividends.get(symbol)
            split=data.splits.get(symbol)
            actions=[]
            if split and split.type == SplitType.SPLIT_OCCURRED:
                self.actions[ticker]['splits'] += 1
                actions.append(('split',split.split_factor,split.time.date()))
            if dividend:
                self.actions[ticker]['dividends'] += 1
                actions.append(('dividend',dividend.distribution,dividend.time.date()))
            for kind,val,day in actions:
                if not D(val).is_finite() or D(val)<=0:
                    self.actions[ticker]['invalid'] += 1
                if ticker=='SPY' and START <= day <= DEV_END:
                    if kind == 'dividend':
                        self.dev_dividends.append(dict(date=str(day),qc_value=str(val)))
                    if kind=='dividend' and self.div_sample_count<2:
                        self.debug('G0_SAMPLE '+json.dumps(dict(date=str(day),kind=kind,value=str(val),normalization='raw')))
                        self.div_sample_count+=1
                    if not self.accounting_block:
                        try:
                            for book in self.books:
                                # Fractional reverse splits intentionally block until a legally sourced cash-in-lieu price is supplied.
                                book.action(day,kind,val,f'{kind}:{day}')
                        except Exception as exc:
                            self.accounting_block=str(exc)
            bar=data.bars.get(symbol)
            if bar is None: continue
            day=bar.time.date()
            row=G0DailyBar(day,float(bar.open),float(bar.high),float(bar.low),float(bar.close),float(bar.volume))
            valid=self.quality[ticker].add(row)
            if ticker!='SPY' or not START <= day <= DEV_END: continue
            if str(day) in CONFIG['price_sample_dates']:
                self.debug('G0_SAMPLE '+json.dumps(dict(date=str(day),kind='price',field='close',value=str(bar.close),normalization='raw')))
            if not valid:
                self.accounting_block='invalid SPY bar'
            if self.accounting_block: continue
            try:
                for book in self.books:
                    if book.signal_day is None: book.signal(day)
                    elif not book.bought: book.buy(day,bar.open)
                    ok,error=book.reconcile(day,bar.close)
                    self.max_error=max(self.max_error,error)
                    if not ok: raise ValueError('journal reconciliation failed')
                self.reconciled_days+=1
                self.last_dev=(day,D(bar.close))
            except Exception as exc:
                self.accounting_block=str(exc)

    def on_end_of_algorithm(self):
        for ticker in CONFIG['symbols']:
            result=self.quality[ticker].summary()
            result.update(symbol=ticker,actions=self.actions[ticker],
                          listing_status='BLOCKED: issuer inception/listing evidence required',
                          calendar='LEAN exchange hours; independent calendar review pending',
                          timezone='America/New_York',normalization='RAW')
            self.debug('G0_QUALITY '+json.dumps(result,sort_keys=True))
        spy_quality = self.quality['SPY']
        expected_dev = {d for d in spy_quality.expected if d <= DEV_END}
        observed_dev = {d for d in spy_quality.seen if d <= DEV_END}
        dates = [r['date'] for r in self.dev_dividends]
        complete = (expected_dev == observed_dev and bool(expected_dev)
                    and not spy_quality.duplicates and not spy_quality.invalid
                    and not self.actions['SPY']['invalid']
                    and dates == sorted(set(dates)))
        reference = dict(symbol='SPY',start=str(START),end=str(DEV_END),
                         complete=complete,event_dates=dates,
                         first_two=self.dev_dividends[:2])
        self.debug('G0_DIVIDEND_REFERENCE '+json.dumps(reference,sort_keys=True))
        self.debug('G0_CASH '+json.dumps(dict(initial_usd='10000',end_usd='10000',interest='0',assumption=True)))
        if self.accounting_block or self.last_dev is None:
            self.debug('G0_ACCOUNTING BLOCKED '+str(self.accounting_block or 'no development data'))
        else:
            day,close=self.last_dev
            for book in self.books:
                self.debug('G0_ACCOUNTING '+json.dumps(dict(end=str(day),fee=str(book.fee),
                    cash=str(book.cash),shares=book.qty,nav=str(book.value(day,close)),
                    journal_max_error=str(self.max_error),days=self.reconciled_days,
                    platform_reconciliation='BLOCKED: no platform positions; shadow journal check only',
                    timing='next observed session open; historical accounting simulation, not real order')))
        self.debug('G0_END BLOCKED until issuer/listing, independent samples, licensing and platform reconciliation reviewed')
