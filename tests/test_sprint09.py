"""Aceite da Sprint 09: risco exato, reservas e causalidade das proteções."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal as D, Inexact, ROUND_UP, localcontext
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from replayquant.data import load_inputs, parse_config
from replayquant.engine import replay, Session
from replayquant.models import Candle, SMAParameters
from replayquant.reporting import canonical, manifest, report, wire, write_artifacts
from replayquant.risk import EquityGuard, RiskSnapshot, evaluate, revalidate, size_at
from replayquant.risk_engine import RiskSession
from replayquant.risk_models import InstrumentFilters, RiskConfig, RiskParameters, RiskRequest
from replayquant.reservations import Reservation
from replayquant.html_report import html_report
from replayquant.exports import markdown_report, HEADERS
from replayquant.validation import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/fixtures/sprint09-candles.json'
CONFIG = ROOT/'experiments/sprint09-manual.json'


def encoded(obj):
    return json.dumps(obj).encode()


def inputs(suffix=''):
    return load_inputs(ROOT/f'data/fixtures/sprint09-candles{suffix}.json', CONFIG)


def cli(*args):
    return subprocess.run([sys.executable,'-m','replayquant',*map(str,args)],cwd=ROOT,
                          capture_output=True,text=True)


def action(id, at, side='BUY', target=None):
    return RiskRequest(id, at, side, target)


class RiskSizingTests(unittest.TestCase):
    def setUp(self):
        i=inputs();self.config=i.config;self.at=i.candles[0].close_time
        self.snapshot=RiskSnapshot(D('1000'),D('1000'),D('0'),D('100000'),self.at,self.at)

    def test_exact_budget_candidates_and_floor(self):
        decision=evaluate(self.config,self.snapshot);s=decision['sizing']
        self.assertTrue(decision['approved'])
        for name,expected in {'entry':'100000','stop':'90000','target':'120000','budget':'10',
                              'loss_per_unit':'10190','candidate_quantity':'.000981',
                              'outlay':'98.1981','planned_loss':'9.99639'}.items():
            self.assertEqual(s[name],D(expected),name)
        self.assertEqual(s['limiters'],['risk'])
        self.assertEqual(s['candidates']['risk']['numerator'],'1')
        self.assertEqual(s['candidates']['risk']['denominator'],'1019')
        self.assertGreater((s['candidate_quantity']+D('.000001'))*s['loss_per_unit'],s['budget'])

    def test_non_decimal_step_and_reference_btc_case(self):
        config=replace(self.config,instrument_filters=InstrumentFilters(D('.000000003'),D('.000000003'),D('0')))
        s=evaluate(config,self.snapshot)['sizing']
        self.assertEqual(s['candidate_quantity'],D('.000981354'))
        self.assertEqual(Fraction(s['candidate_quantity'])/Fraction(D('.000000003')),s['increments'])
        self.assertEqual(s['planned_loss'],D('9.99999726'))
        config=replace(config,instrument_filters=InstrumentFilters(D('.000001'),D('.000001'),D('0')))
        snapshot=replace(self.snapshot,price=D('100000'))
        s=size_at(config,snapshot,entry=D('100000'),stop=D('98000'))
        self.assertEqual(s['loss_per_unit'],D('2198'))
        self.assertEqual(s['candidate_quantity'],D('.004549'))
        self.assertEqual(s['outlay'],D('455.3549'))
        self.assertEqual(s['planned_loss'],D('9.998702'))

    def test_limiters_tie_and_minimum_equality_and_no_increase(self):
        config=replace(self.config,fee_rate=D('0'),risk=replace(self.config.risk,
                       risk_fraction=D('.1'),exposure_fraction=D('.2'),stop_fraction=D('.5')),
                       instrument_filters=InstrumentFilters(D('.000001'),D('.002'),D('200')))
        snapshot=replace(self.snapshot,free_balance=D('200'))
        d=evaluate(config,snapshot)
        self.assertTrue(d['approved'])
        self.assertEqual(d['approved_quantity'],D('.002'))
        self.assertEqual(d['sizing']['limiters'],['risk','exposure','cash'])
        for filters in (InstrumentFilters(D('.000001'),D('.002001'),D('200')),
                        InstrumentFilters(D('.000001'),D('.002'),D('200.01'))):
            rejected=evaluate(replace(config,instrument_filters=filters),snapshot)
            self.assertEqual(rejected['reason'],'BELOW_MINIMUMS')
            self.assertEqual(rejected['approved_quantity'],0)
            self.assertEqual(rejected['sizing']['candidate_quantity'],D('.002'))

    def test_precedence_missing_stale_future_and_snapshot_validation(self):
        cases=[({'daily_blocked':True,'drawdown_blocked':True,'price':None},'DAILY_LOSS_BLOCKED'),
               ({'drawdown_blocked':True,'price':None},'DRAWDOWN_BLOCKED'),
               ({'price':None},'PRICE_MISSING'),({'price_at':None},'PRICE_MISSING'),
               ({'evaluated_at':self.at+timedelta(seconds=61)},'PRICE_STALE'),
               ({'pending':True,'position_open':True},'ORDER_PENDING'),
               ({'position_open':True},'POSITION_OPEN'),({'reentry':True},'REENTRY_SAME_CANDLE'),
               ({'equity':D('0'),'free_balance':D('0')},'NON_POSITIVE_EQUITY'),
               ({'free_balance':D('0'),'exposure':D('1000')},'EXPOSURE_LIMIT'),
               ({'free_balance':D('0')},'INSUFFICIENT_CASH')]
        for changes,reason in cases:
            with self.subTest(reason=reason):
                d=evaluate(self.config,replace(self.snapshot,**changes))
                self.assertEqual(d['reason'],reason)
                self.assertIsNone(d['sizing'])
                self.assertEqual(d['approved_quantity'],0)
        self.assertTrue(evaluate(self.config,replace(self.snapshot,evaluated_at=self.at+timedelta(seconds=60)))['approved'])
        for changes in ({'price_at':self.at+timedelta(seconds=1),'daily_blocked':True},
                        {'free_balance':D('1001')},{'price':100.0},{'equity':D('NaN')},{'pending':1}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                replace(self.snapshot,**changes)

    def test_revalidation_keeps_budget_and_bracket(self):
        sizing=evaluate(self.config,self.snapshot)['sizing']
        reason,details=revalidate(self.config,replace(self.snapshot,price=D('101000')),sizing)
        self.assertEqual(reason,'RISK_BUDGET_EXCEEDED')
        self.assertEqual(details['planned_loss'],D('10.978371'))
        self.assertEqual(sizing['budget'],10)
        self.assertEqual(sizing['stop'],90000)
        for price in (D('90000'),D('120000')):
            self.assertEqual(revalidate(self.config,replace(self.snapshot,price=price),sizing)[0],'ENTRY_OUTSIDE_BRACKET')
        self.assertIsNone(revalidate(self.config,replace(self.snapshot,price=D('99000')),sizing)[0])
        self.assertEqual(revalidate(self.config,replace(self.snapshot,daily_blocked=True),sizing)[0],'DAILY_LOSS_BLOCKED')
        with self.assertRaises(ValidationError):revalidate(self.config,self.snapshot,{'candidate_quantity':True})

    def test_schema4_strict_json_and_python_models(self):
        original=json.loads(CONFIG.read_bytes())
        cases=[{'quantity':'1'},{'schema_version':True},{'mode':'OTHER'},{'orders':{}},
               {'strategy':{'name':'SMA_CROSS','short_window':2,'long_window':3}}]
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                parse_config(encoded({**original,**changes}))
        for key,value in [('risk_fraction','0'),('stop_fraction','1'),('target_fraction','1.1'),
                          ('max_price_age_seconds','0'),('drawdown_fraction',True),('daily_loss_fraction','NaN')]:
            obj=deepcopy(original);obj['risk'][key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):parse_config(encoded(obj))
        for obj in [CONFIG.read_bytes().replace(b'"mode": "MANUAL"',b'"mode": "MANUAL", "mode": "MANUAL"'),
                    encoded({**original,'instrument_filters':{'step':'.001','min_quantity':'0.001','min_notional':'0'}})]:
            with self.assertRaises(ValidationError):parse_config(obj)
        for changes in ({'initial_cash':True},{'risk':{}},{'instrument_filters':{}},{'orders':[]},
                        {'mode':'SMA'},{'fee_rate':D('1')}):
            with self.assertRaises(ValidationError):replace(self.config,**changes)
        with self.assertRaises(ValidationError):Session(self.config,'wrong-session')
        with self.assertRaises(ValidationError):RiskRequest('bad',self.at,'CANCEL')
        with self.assertRaises(ValidationError):RiskRequest('bad',self.at,'BUY','target')
        duplicate={**original,'orders':[original['orders'][0],original['orders'][0]]}
        self.assertEqual(len(parse_config(encoded(duplicate)).orders),2)
        conflict=deepcopy(duplicate);conflict['orders'][1]=dict(conflict['orders'][1],side='SELL')
        with self.assertRaises(ValidationError):parse_config(encoded(conflict))

    def test_context_isolation_for_sizing(self):
        expected=evaluate(self.config,self.snapshot)
        with localcontext() as ctx:
            ctx.prec=2;ctx.rounding=ROUND_UP;ctx.traps[Inexact]=True;ctx.flags[Inexact]=True
            before=(ctx.prec,ctx.rounding,dict(ctx.traps),dict(ctx.flags))
            actual=evaluate(self.config,self.snapshot)
            self.assertEqual(actual,expected)
            self.assertEqual(before,(ctx.prec,ctx.rounding,dict(ctx.traps),dict(ctx.flags)))


class EquityGuardTests(unittest.TestCase):
    def setUp(self):
        self.config=inputs().config
        self.at=inputs().candles[0].open_time.replace(hour=23,minute=59)

    def test_daily_latch_equality_recovery_and_utc_rollover(self):
        guard=EquityGuard(self.config.risk)
        guard=guard.observe(self.at,0,'INITIAL',D('1000'))
        guard=guard.observe(self.at,1,'FILL',D('970'))
        self.assertTrue(guard.current['daily_blocked'])
        self.assertFalse(guard.current['drawdown_blocked'])
        guard=guard.observe(self.at,2,'RECOVERY',D('1000'))
        self.assertTrue(guard.current['daily_blocked'])
        guard=guard.observe(self.at+timedelta(minutes=1),3,'OPEN',D('1000'))
        self.assertFalse(guard.current['daily_blocked'])
        self.assertFalse(guard.current['daily_base_partial'])

    def test_drawdown_persists_after_recovery_and_new_day(self):
        guard=EquityGuard(self.config.risk)
        for seq,value in enumerate(('1000','1050','990','1050')):
            guard=guard.observe(self.at,seq,'TEST',D(value))
        self.assertTrue(guard.current['drawdown_blocked'])
        guard=guard.observe(self.at+timedelta(days=1),4,'OPEN',D('1100'))
        self.assertTrue(guard.current['drawdown_blocked'])
        self.assertEqual(guard.current['drawdown']['value'],'0.000000000000')

    def test_zero_missing_daily_base_and_late_positive_base(self):
        guard=EquityGuard(self.config.risk)
        with self.assertRaises(ValidationError):guard.observe(self.at,0,'INITIAL',D('0'))
        guard=guard.observe(self.at,0,'INITIAL',D('1000'))
        next_day=self.at+timedelta(minutes=1)
        guard=guard.observe(next_day,1,'OPEN',D('0'))
        self.assertIsNone(guard.current['daily_base'])
        self.assertEqual(guard.current['daily_loss']['reason'],'NO_POSITIVE_DAILY_BASE')
        self.assertEqual(guard.current['drawdown']['value'],'1.000000000000')
        guard=guard.observe(next_day+timedelta(seconds=10),2,'FILL',D('1'))
        self.assertTrue(guard.current['daily_blocked'])
        self.assertTrue(guard.current['daily_base_partial'])
        self.assertEqual(guard.current['daily_base'],1)

    def test_duplicate_conflict_and_external_context(self):
        guard=EquityGuard(self.config.risk).observe(self.at,0,'INITIAL',D('1000'))
        self.assertIs(guard.observe(self.at,0,'INITIAL',D('1000')),guard)
        for at,seq,phase,value in [(self.at,0,'INITIAL',D('999')),(self.at-timedelta(seconds=1),1,'X',D('1000')),
                                   (self.at,False,'X',D('1000'))]:
            with self.assertRaises(ValidationError):guard.observe(at,seq,phase,value)
        with localcontext() as ctx:
            ctx.prec=2;ctx.traps[Inexact]=True
            before=(dict(ctx.flags),dict(ctx.traps))
            new=guard.observe(self.at,1,'FILL',D('950'))
            self.assertTrue(new.current['drawdown_blocked'])
            self.assertEqual(before,(dict(ctx.flags),dict(ctx.traps)))
        self.assertEqual(len(guard.history),1)


class RiskReplayTests(unittest.TestCase):
    def setUp(self):
        i=inputs();self.candles,self.config=i.candles,i.config

    def run_case(self,candles=None,config=None):
        return replay(candles or self.candles,config or self.config,'test')

    def test_canonical_ledger_reservations_and_independent_reconstruction(self):
        session=self.run_case();summary=report(session)
        self.assertEqual(session.balance.cash,D('990.00361'))
        self.assertEqual(session.balance.btc,0)
        self.assertEqual(session.fees,D('.18639'))
        self.assertEqual(summary['analysis']['metrics']['realized_pnl']['value'],D('-9.99639'))
        order=session.orders[0]
        self.assertEqual(order.quantity,D('.000981'))
        self.assertEqual([fill.price for fill in session.fills],[D('100000'),D('90000')])
        self.assertEqual(order.sizing['budget'],10)
        cr=ar=ca=aa=cash=asset=D('0')
        for row in session.ledger.entries:
            ca+=row.cash_available_delta;cr+=row.cash_reserved_delta
            aa+=row.asset_available_delta;ar+=row.asset_reserved_delta
            cash+=row.cash_delta;asset+=row.asset_delta
            self.assertEqual(ca+cr,cash);self.assertEqual(aa+ar,asset)
            self.assertTrue(all(x>=0 for x in (ca,cr,aa,ar)))
            self.assertEqual((cash,asset),(row.cash_after,row.asset_after))
            if row.entry_type in ('RESERVE','TRANSFER','RELEASE'):
                self.assertEqual((row.cash_delta,row.asset_delta,row.fee,row.gross),(0,0,0,0))
        reserve=next(e for e in session.ledger.entries if e.entry_type=='RESERVE')
        self.assertEqual(reserve.cash_reserved_after,D('98.1981'))
        self.assertEqual(reserve.cash_after,D('1000'))
        buy=next(e for e in session.ledger.entries if e.side=='BUY')
        self.assertEqual(buy.asset_reserved_after,D('.000981'))
        self.assertEqual(buy.asset_available_after,0)
        self.assertEqual(session.ledger.reconcile()['status'],'PASSED')
        self.assertFalse(summary['risk']['blocks']['daily_blocked'])
        self.assertFalse(summary['risk']['blocks']['drawdown_blocked'])
        for point in summary['analysis']['equity_curve']:
            self.assertEqual(point['cash_total']+point['asset_quantity']*(point['mark_price'] or 0),point['gross_equity'])
            self.assertEqual(self.config.initial_cash+point['realized_pnl']+point['unrealized_pnl'],point['gross_equity'])
        last=session.ledger.entries[-1]
        self.assertEqual((last.cash_reserved_after,last.asset_reserved_after),(0,0))

    def test_gap_target_and_ambiguous_stop_first(self):
        for suffix,cash,pnl,fees,origin,model,ambiguous in (
            ('-gap','980.20342','-19.79658','.17658','STOP','OPEN_EVENT',False),
            ('-alvo','1019.40418','19.40418','.21582','TARGET','BAR_CLOSE_RESOLUTION',False),
            ('-ambiguo','990.00361','-9.99639','.18639','STOP','BAR_CLOSE_RESOLUTION',True)):
            with self.subTest(suffix=suffix):
                i=inputs(suffix);session=replay(i.candles,i.config)
                self.assertEqual(session.balance.cash,D(cash));self.assertEqual(session.fees,D(fees))
                self.assertEqual(session.ledger.realized,D(pnl))
                detail=session.protection_groups[0].exit_details
                self.assertEqual(detail['exit_origin'],origin)
                self.assertEqual(detail['execution_time_model'],model)
                self.assertEqual(detail['ambiguous'],ambiguous)
                if suffix=='-gap':self.assertGreater(-session.ledger.realized,D('10'))
                self.assertEqual(len(session.fills),2)

    def test_range_resolution_phase_has_no_future_strategy_or_fake_time(self):
        session=self.run_case();events=session.events
        trigger=next(e for e in events if e['type']=='PROTECTION_TRIGGER')
        self.assertEqual(trigger['at'],self.candles[2].close_time)
        self.assertFalse(trigger['intrabar_time_known'])
        interval=[e['type'] for e in events if e['at']==trigger['at']]
        self.assertLess(interval.index('BAR_RANGE'),interval.index('PROTECTION_TRIGGER'))
        self.assertLess(interval.index('FILLED'),interval.index('CLOSE'))
        for event in events:
            if event['type']=='OPEN':self.assertFalse({'candle','high','low','close','volume'} & event.keys())
        trade=report(session)['analysis']['closed_trades'][0]
        self.assertEqual(trade['duration_seconds'],120)
        self.assertEqual(trade['execution_time_model'],'BAR_CLOSE_RESOLUTION')
        marks=[p for p in report(session)['analysis']['equity_curve'] if p['at']==trigger['at']]
        self.assertTrue(any(p['phase']=='PROTECTION_TRIGGER' and p['mark_price']==90000 for p in marks))

    def test_entry_candle_does_not_activate_protection(self):
        candles=list(self.candles)
        candles[1]=replace(candles[1],high=D('121000'),low=D('89000'))
        session=self.run_case(candles)
        self.assertEqual(session.balance.cash,D('990.00361'))
        self.assertEqual(session.fills[1].at,self.candles[2].close_time)
        self.assertEqual(session.protection_groups[0].eligible_at,self.candles[2].open_time)

    def test_cancel_releases_once_and_duplicate_action_is_inert(self):
        buy=self.config.orders[0];cancel=action('cancel',buy.at_close,'CANCEL',buy.id)
        config=replace(self.config,orders=(buy,cancel,cancel))
        session=self.run_case(config=config)
        self.assertEqual(session.balance.cash,1000);self.assertFalse(session.fills)
        self.assertEqual(session.fees,0)
        self.assertEqual(report(session)['exit_code'],0)
        self.assertEqual(len(session.orders),2)
        self.assertEqual(session.orders[0].status,'CANCELED')
        self.assertEqual(len([e for e in session.events if e['type']=='RELEASE']),1)
        before=canonical((session.events,session.ledger.history))
        session.submit(cancel)
        self.assertEqual(before,canonical((session.events,session.ledger.history)))
        with self.assertRaises(ValidationError):session.submit(replace(cancel,target_order_id='other'))
        invalid=self.run_case(config=replace(self.config,orders=(action('bad',buy.at_close,'CANCEL','missing'),)))
        self.assertEqual(invalid.orders[0].reason,'ORDER_NOT_PENDING')
        self.assertEqual(report(invalid)['exit_code'],2)

    def test_pending_cannot_spend_or_release_previous_reserve(self):
        buy=self.config.orders[0]
        config=replace(self.config,orders=(buy,action('concurrent',buy.at_close)))
        session=self.run_case(config=config)
        self.assertEqual(session.orders[1].reason,'ORDER_PENDING')
        self.assertEqual(session.orders[0].status,'FILLED')
        self.assertEqual(len([r for r in session.ledger.history if r['currency']=='USDT' and r['status']=='HELD']),1)
        self.assertEqual(session.balance.cash,D('990.00361'))

    def test_revalidation_rejects_without_reanchoring_or_fees(self):
        candles=list(self.candles);candles[1]=replace(candles[1],open=D('101000'))
        session=self.run_case(candles)
        self.assertFalse(session.fills);self.assertEqual(session.balance.cash,1000)
        self.assertEqual(session.fees,0);self.assertEqual(session.orders[0].reason,'RISK_BUDGET_EXCEEDED')
        self.assertEqual(session.orders[0].sizing['stop'],90000)
        self.assertEqual(session.ledger.entries[-1].cash_reserved_after,0)
        self.assertEqual(session.ledger.history[-1]['status'],'RELEASED')

    def test_favorable_open_returns_unused_cash_and_preserves_stop(self):
        candles=list(self.candles);candles[1]=replace(candles[1],open=D('99000'))
        session=self.run_case(candles)
        buy=next(e for e in session.ledger.entries if e.side=='BUY')
        self.assertEqual(buy.cash_after,D('902.783881'))
        self.assertEqual(buy.cash_reserved_after,0)
        self.assertEqual(session.orders[0].quantity,D('.000981'))
        self.assertEqual(session.protection_groups[0].stop,D('90000'))
        self.assertEqual(session.balance.cash,D('990.985591'))

    def test_gap_protection_preempts_common_sell_without_double_sale(self):
        i=inputs('-gap');sell=action('sell',i.candles[1].close_time,'SELL')
        session=self.run_case(i.candles,replace(self.config,orders=(*self.config.orders,sell)))
        common=next(o for o in session.orders if o.request.id=='sell')
        self.assertEqual(common.status,'CANCELED')
        self.assertEqual(common.reason,'PROTECTIVE_EXIT_PREEMPTED')
        self.assertEqual(len(session.fills),2);self.assertEqual(session.fees,D('.17658'))
        self.assertEqual(session.balance.cash,D('980.20342'))
        self.assertEqual(session.ledger.reconcile()['status'],'PASSED')

    def test_common_sell_precedes_range_and_cancel_restores_protection(self):
        sell=action('sell',self.candles[1].close_time,'SELL')
        session=self.run_case(config=replace(self.config,orders=(*self.config.orders,sell)))
        self.assertEqual(session.fills[1].price,102000)
        self.assertEqual(session.protection_groups[0].exit_details['exit_origin'],'MANUAL')
        self.assertFalse(any(e['type']=='PROTECTION_TRIGGER' for e in session.events))
        cancel=action('cancel-sell',sell.at_close,'CANCEL',sell.id)
        canceled=self.run_case(config=replace(self.config,orders=(*self.config.orders,sell,cancel)))
        self.assertEqual(canceled.fills[1].price,90000)
        self.assertEqual(canceled.balance.cash,D('990.00361'))
        self.assertEqual(canceled.ledger.reconcile()['status'],'PASSED')

    def test_blocks_do_not_disable_exit_and_no_reentry_same_candle(self):
        later=action('again',self.candles[2].close_time)
        session=self.run_case(config=replace(self.config,orders=(*self.config.orders,later)))
        self.assertEqual(session.orders[-1].reason,'REENTRY_SAME_CANDLE')
        blocked=self.run_case(config=replace(self.config,risk=replace(self.config.risk,daily_loss_fraction=D('.005')),
                                             orders=(*self.config.orders,later)))
        self.assertTrue(blocked.guard.current['daily_blocked'])
        self.assertEqual(blocked.orders[-1].reason,'DAILY_LOSS_BLOCKED')
        self.assertEqual(len(blocked.fills),2)
        # O bloqueio existente, sem tentativa recusada, não é código de falha.
        normal=self.run_case(config=replace(self.config,risk=replace(self.config.risk,daily_loss_fraction=D('.005'))))
        self.assertEqual(report(normal)['exit_code'],0)
        candles=list(self.candles)
        candles[1]=replace(candles[1],low=D('89000'),close=D('90000'))
        candles[2]=replace(candles[2],open=D('95000'))
        sell=action('exit-blocked',candles[1].close_time,'SELL')
        session=self.run_case(candles,replace(self.config,risk=replace(self.config.risk,daily_loss_fraction=D('.005')),
                                              orders=(*self.config.orders,sell)))
        self.assertEqual(len(session.fills),2)
        self.assertEqual(session.fills[-1].order_id,sell.id)

    def test_normal_end_releases_pending_and_open_position_is_kept(self):
        last=action('last',self.candles[-1].close_time)
        session=self.run_case(config=replace(self.config,orders=(last,)))
        self.assertEqual(session.orders[0].status,'UNEXECUTED')
        self.assertEqual(session.orders[0].reason,'NO_FUTURE_OPEN')
        self.assertEqual(session.ledger.entries[-1].cash_reserved_after,0)
        opened=self.run_case(self.candles[:2])
        self.assertEqual(opened.balance.btc,D('.000981'))
        self.assertEqual(opened.ledger.entries[-1].asset_reserved_after,0)
        self.assertEqual(opened.protection_groups[0].status,'ENDED_WITH_OPEN_POSITION')
        self.assertEqual(len(opened.fills),1)
        self.assertEqual(opened.ledger.realized,0)
        empty=self.run_case(config=replace(self.config,orders=()))
        self.assertEqual(report(empty)['exit_code'],0)
        self.assertEqual(report(empty)['analysis']['metrics']['win_rate_pct']['reason'],'NO_CLOSED_TRADES')

    def test_sma_signals_are_preserved_and_quantity_is_dynamic(self):
        i=load_inputs(ROOT/'data/fixtures/sprint07-candles.json',ROOT/'experiments/sprint09-sma.json')
        coarse=replace(i.config,instrument_filters=InstrumentFilters(D('.001'),D('.001'),D('0')))
        session=self.run_case(i.candles,coarse)
        self.assertEqual([o.reason for o in session.orders],['BELOW_MINIMUMS','INSUFFICIENT_ASSET'])
        self.assertEqual(report(session)['exit_code'],2)
        config=i.config
        filled=self.run_case(i.candles,config)
        self.assertEqual(len(filled.fills),2)
        self.assertEqual(filled.fills[0].quantity,D('.000962'))
        self.assertEqual(filled.balance.cash,D('999.8076'))
        self.assertEqual(filled.fees,D('.1924'))
        self.assertEqual(len(report(filled)['evaluations']),8)
        self.assertEqual([e['side'] for e in report(filled)['signals']],['BUY','SELL'])
        progressive=RiskSession(config,'offset')
        progressive.on_open(i.candles[0].opening());progressive.on_close(i.candles[0])
        at=i.candles[0].close_time.astimezone(timezone(timedelta(hours=-3)))
        progressive.handle_signal('external','BUY',at)
        signal=next(e for e in progressive.events if e['type']=='SIGNAL')
        self.assertEqual(signal['at'].utcoffset(),timedelta(0))
        self.assertIsNone(progressive.orders[0].reason)
        # Lacuna com posição já preenchida conserva a reserva única de BTC.
        active=RiskSession(config,'active-gap')
        for candle in i.candles[:5]:
            active.on_open(candle.opening());active.on_close(candle)
        before=active.ledger
        self.assertGreater(active.balance.btc,0)
        active.on_open(i.candles[6].opening())
        self.assertEqual(active.status,'INTERRUPTED')
        self.assertEqual(active.ledger,before)
        self.assertEqual(active.ledger.entries[-1].asset_reserved_after,active.balance.btc)
        self.assertEqual(active.protection_groups[0].status,'ACTIVE')

    def test_gap_preserves_prefix_pending_reserve_and_benchmarks(self):
        strategy=SMAParameters('SMA_CROSS',1,2)
        config=replace(self.config,mode='SMA',orders=(),strategy=strategy)
        candles=[]
        for index,close in enumerate((D('100000'),D('90000'),D('110000'))):
            source=self.candles[index]
            candles.append(replace(source,open=D('100000'),high=max(D('100000'),close),low=min(D('100000'),close),close=close))
        skipped=replace(self.candles[-1],open_time=self.candles[-1].open_time+timedelta(minutes=1),
                        close_time=self.candles[-1].close_time+timedelta(minutes=1))
        session=self.run_case((*candles,skipped),config)
        self.assertEqual(session.status,'INTERRUPTED')
        self.assertIsNotNone(session.pending)
        self.assertGreater(session.ledger.entries[-1].cash_reserved_after,0)
        self.assertFalse(session.fills)
        summary=report(session)
        self.assertEqual(summary['exit_code'],1)
        self.assertEqual(summary['analysis']['scope'],'ACCEPTED_PREFIX')
        self.assertEqual(summary['analysis']['observed_until'],candles[-1].close_time)
        self.assertTrue(all(b['observed_until']==candles[-1].close_time for b in summary['analysis']['benchmarks']))
        self.assertFalse(any(e['type']=='OPEN' and e['at']==skipped.open_time for e in session.events))
        with self.assertRaises(ValidationError):session.finish()
        with self.assertRaises(ValidationError):self.run_case((self.candles[0],self.candles[2]))

    def test_incremental_and_file_replay_are_identical_and_prefix_causal(self):
        file_session=self.run_case()
        progressive=RiskSession(self.config,'test')
        for candle in self.candles:
            progressive.on_open(candle.opening());progressive.on_close(candle)
            for request in self.config.orders:
                if request.at_close==candle.close_time:progressive.submit(request)
        progressive.finish()
        self.assertEqual(canonical(progressive.events),canonical(file_session.events))
        self.assertEqual(canonical(report(progressive)),canonical(report(file_session)))
        candles=list(self.candles);candles[1]=replace(candles[1],high=D('999000'),low=D('1000'),volume=D('0'))
        changed=self.run_case(candles)
        fill_seq=next(e['seq'] for e in file_session.events if e['type']=='FILLED')
        self.assertEqual(file_session.events[:fill_seq],changed.events[:fill_seq])
        # Nenhum preço do candle de entrada faz a proteção atuar retroativamente.
        self.assertEqual(file_session.fills[0],changed.fills[0])

    def test_duplicate_fill_candle_reserve_and_conflicts(self):
        session=RiskSession(self.config,'test')
        session.on_open(self.candles[0].opening());session.on_close(self.candles[0])
        session.submit(self.config.orders[0])
        before=canonical((session.events,session.ledger.entries,session.risk_records))
        session.on_close(self.candles[0]);session.submit(self.config.orders[0])
        self.assertEqual(before,canonical((session.events,session.ledger.entries,session.risk_records)))
        with self.assertRaises(ValidationError):session.on_close(replace(self.candles[0],volume=D('2')))
        ledger=session.ledger;row=ledger.entries[-1]
        self.assertIs(ledger.adjust(row.entry_type,'reservation-event:'+str(row.source_event_seq),row.at,
                                   row.source_event_seq,row.reservation_operations),ledger)
        with self.assertRaises(ValidationError):
            ledger.adjust(row.entry_type,'reservation-event:'+str(row.source_event_seq),row.at,row.source_event_seq,
                          (replace(row.reservation_operations[0],quantity=D('1')),))
        session=self.run_case();before=canonical((session.events,session.ledger.entries,session.risk_records))
        session.apply_fill(session.fills[0]);session.finish()
        self.assertEqual(before,canonical((session.events,session.ledger.entries,session.risk_records)))
        with self.assertRaises(ValidationError):session.apply_fill(replace(session.fills[0],fee=D('0')))
        # Snapshots não permitem alterar o histórico aceito.
        copy=session.ledger;copy.history[0]['quantity']=D('999')
        self.assertNotEqual(copy.history,session.ledger.history)
        with self.assertRaises(ValidationError):copy.reconcile()

    def test_arithmetic_and_ledger_failure_rollback_entire_transition(self):
        session=RiskSession(self.config,'atomic')
        session.on_open(self.candles[0].opening());session.on_close(self.candles[0])
        before=canonical((session.events,session.ledger.entries,session.orders,session.risk_records))
        with patch('replayquant.reservations.ReservationLedger.adjust',side_effect=ValidationError('falha aritmética fictícia')):
            with self.assertRaises(ValidationError):session.submit(self.config.orders[0])
        self.assertEqual(before,canonical((session.events,session.ledger.entries,session.orders,session.risk_records)))
        session.submit(self.config.orders[0])
        before=canonical((session.events,session.ledger.entries,session.orders,session.risk_records))
        with patch('replayquant.ledger.Ledger.prepare',side_effect=ValidationError('falha de preparação')):
            with self.assertRaises(ValidationError):session.on_open(self.candles[1].opening())
        self.assertEqual(before,canonical((session.events,session.ledger.entries,session.orders,session.risk_records)))
        # Falha real de representação exata também não deixa reserva/ordem parcial.
        config=replace(self.config,initial_cash=D('999999999999999999'),fee_rate=D('.123456789123'),
                       instrument_filters=InstrumentFilters(D('.000000000001'),D('.000000000001'),D('0')))
        tiny=replace(self.candles[0],open=D('0.000000000001'),high=D('0.000000000001'),
                     low=D('0.000000000001'),close=D('0.000000000001'))
        session=RiskSession(config,'inexact');session.on_open(tiny.opening());session.on_close(tiny)
        before=canonical((session.events,session.ledger.entries,session.orders))
        # Multiplicação de quantidade derivada longa pela taxa excede precisão 40.
        with self.assertRaisesRegex(ValidationError, 'não representável exatamente'):
            session.submit(config.orders[0])
        self.assertEqual(before,canonical((session.events,session.ledger.entries,session.orders)))

    def test_variable_quantities_close_distinct_lots_without_reusing_old_size(self):
        candles=list(self.candles)
        candles[3]=replace(candles[3],high=D('200000'),close=D('200000'))
        for minute in (4,5):
            base=self.candles[0]
            candles.append(replace(base,open_time=base.open_time+timedelta(minutes=minute),
                                   close_time=base.close_time+timedelta(minutes=minute),
                                   open=D('200000'),high=D('200000'),low=D('200000'),close=D('200000')))
        orders=(*self.config.orders,action('second',candles[3].close_time),
                action('second-exit',candles[4].close_time,'SELL'))
        session=self.run_case(candles,replace(self.config,orders=orders))
        self.assertEqual([f.quantity for f in session.fills],[D('.000981'),D('.000981'),D('.000485'),D('.000485')])
        self.assertEqual(len(session.ledger.trades),2)
        self.assertEqual(session.balance.cash,D('989.80961'))
        self.assertEqual(session.balance.btc,0)
        self.assertEqual(session.fees,D('.38039'))
        self.assertEqual(session.ledger.reconcile()['status'],'PASSED')

    def test_reserving_more_than_real_balance_fails_without_mutating_ledger(self):
        session=RiskSession(self.config,'over-reserve')
        session.on_open(self.candles[0].opening());session.on_close(self.candles[0])
        ledger=session.ledger
        before=canonical(ledger)
        with self.assertRaises(ValidationError):
            ledger.adjust('RESERVE','too-much',self.candles[0].close_time,10,
                          (Reservation('r','o','USDT',D('1001')),))
        self.assertEqual(before,canonical(ledger))
        self.assertEqual(before,canonical(session.ledger))

    def test_hostile_context_does_not_change_financial_or_presentational_result(self):
        expected=canonical(report(self.run_case()))
        with localcontext() as ctx:
            ctx.prec=2;ctx.rounding=ROUND_UP;ctx.traps[Inexact]=True;ctx.flags[Inexact]=True
            before=(ctx.prec,ctx.rounding,dict(ctx.traps),dict(ctx.flags))
            actual=canonical(report(self.run_case()))
            self.assertEqual(actual,expected)
            self.assertEqual(before,(ctx.prec,ctx.rounding,dict(ctx.traps),dict(ctx.flags)))


class RiskOutputTests(unittest.TestCase):
    def test_cli_formats_identity_and_automatic_analysis(self):
        for fmt in ('texto','json','markdown','html'):
            result=cli('demonstrar','--risco','--formato',fmt)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stderr,'')
            self.assertIn('SPRINT09_V1' if fmt=='json' else 'Risco',result.stdout)
        sma=cli('demonstrar','--risco','--estrategia','sma','--formato','json')
        self.assertEqual(sma.returncode,0,sma.stderr)
        self.assertEqual(sma.stderr,'')
        i=inputs();m=manifest(i)
        self.assertEqual(m,manifest(i,analysis=True))
        for value in (False,None,1,'true'):
            with self.assertRaises(ValidationError):manifest(i,analysis=value)
            with self.assertRaises(ValidationError):report(replay(i.candles,i.config),analysis=value)
        identity={k:m[k] for k in ('data_hash','config_hash','code_hash','python_version','analysis_policy','risk_policy')}
        self.assertEqual(sha256(canonical(identity)).hexdigest(),m['run_id'])
        self.assertEqual(cli('executar','--risco').returncode,2)

    def test_eleven_reproducible_files_exact_csvs_and_redundant_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs=[Path(temp)/'a',Path(temp)/'b']
            for index,out in enumerate(outputs):
                result=cli('executar','--dados',DATA,'--config',CONFIG,'--saida',out,'--formato','json',*(['--analise'] if index else []))
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout),json.loads((out/'report.json').read_bytes()))
            expected=set(HEADERS)|{'manifest.json','events.jsonl','report.json','ledger.jsonl','report.md','risk.jsonl','reservations.jsonl'}
            self.assertEqual({p.name for p in outputs[0].iterdir()},expected)
            self.assertEqual(len(expected),11)
            for name in expected:self.assertEqual((outputs[0]/name).read_bytes(),(outputs[1]/name).read_bytes(),name)
            for name in HEADERS:
                raw=(outputs[0]/name).read_text()
                rows=list(csv.DictReader(io.StringIO(raw)))
                header=HEADERS[name]+(['asset_available','asset_reserved'] if name=='equity.csv' else [])
                self.assertEqual(raw.splitlines()[0].split(','),header)
                self.assertTrue(all(r['schema_version']=='4' for r in rows))
            for name in ('events.jsonl','ledger.jsonl','risk.jsonl','reservations.jsonl'):
                rows=[json.loads(line) for line in (outputs[0]/name).read_text().splitlines()]
                self.assertTrue(all(r['schema_version']==4 for r in rows))
            contents={p.name:p.read_bytes() for p in outputs[0].iterdir()}
            refused=cli('executar','--dados',DATA,'--config',CONFIG,'--saida',outputs[0])
            self.assertEqual(refused.returncode,1)
            self.assertEqual(contents,{p.name:p.read_bytes() for p in outputs[0].iterdir()})

    def test_benchmarks_have_filters_without_strategy_risk_or_stops(self):
        i=inputs();s=replay(i.candles,i.config);r=report(s)
        hold=r['analysis']['benchmarks'][1]
        self.assertEqual(hold['parameters']['quantity'],D('.00999'))
        self.assertEqual(hold['parameters']['cash_residual'],D('.001'))
        self.assertEqual(hold['parameters']['risk_policy'],'PASSIVE_NO_STOPS_OR_BLOCKS')
        self.assertEqual(hold['metrics']['closed_trade_count']['value'],0)
        self.assertGreater(hold['metrics']['final_asset_quantity']['value'],s.fills[0].quantity)
        limited=replace(i.config,instrument_filters=InstrumentFilters(D('10'),D('10'),D('0')))
        hold=report(replay(i.candles,limited))['analysis']['benchmarks'][1]
        self.assertEqual(hold['status'],'UNAVAILABLE')

    def test_html_markdown_escape_context_and_modeled_resolution(self):
        i=inputs();config=replace(i.config,orders=(replace(i.config.orders[0],id='<script>alert(1)</script>'),))
        s=replay(i.candles,config);r=report(s)
        html=html_report(r);md=markdown_report(r)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('BAR_CLOSE_RESOLUTION',html)
        self.assertIn('STOP_FIRST',html)
        self.assertIn('sem atuação da proteção',html)
        self.assertIn('memória',html.lower())
        self.assertIn('Risco, reservas',md)
        self.assertIn('variável por risco',html)
        self.assertIn('1/1019',html)
        self.assertIn('Incrementos',md)
        self.assertNotIn('quantidade fixa: None',md)
        self.assertNotIn('piso no quantum 0.000000000001 BTC',md)
        self.assertNotIn('<script src=',html)
        self.assertNotIn('<link ',html)
        with localcontext() as ctx:
            ctx.prec=2;ctx.traps[Inexact]=True
            self.assertEqual(html_report(r),html)
            self.assertEqual(markdown_report(r),md)

    def test_write_failure_is_incomplete_and_invalid_input_creates_no_output(self):
        i=inputs();m=manifest(i);s=replay(i.candles,i.config,m['run_id']);r=report(s)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'failed'
            with patch.object(Path,'replace',side_effect=OSError('falha fictícia')):
                with self.assertRaises(OSError):write_artifacts(output,m,s,r)
            self.assertTrue((output/'INCOMPLETE').exists())
            self.assertFalse((output/'manifest.json').exists())
            bad=Path(temp)/'bad.json';bad.write_text('{"schema_version":true}')
            result=cli('executar','--dados',DATA,'--config',bad,'--saida',Path(temp)/'absent')
            self.assertEqual(result.returncode,1)
            self.assertFalse((Path(temp)/'absent').exists())


if __name__=='__main__':
    unittest.main()
