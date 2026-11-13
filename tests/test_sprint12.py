"""Contratos financeiros/temporais da carteira compartilhada, sem rede."""
import copy
from dataclasses import replace
from decimal import Decimal, localcontext, Inexact
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from replayquant.catalog import Catalog
from replayquant.reporting import canonical, wire
from replayquant.shared_config import load_shared, SharedConfig, Allocation
from replayquant.shared_engine import SharedSession, SharedRequest, MINUTE, replay_shared
from replayquant.shared_reporting import shared_manifest, shared_report, shared_html, write_shared
from replayquant.validation import ValidationError

ROOT = Path(__file__).resolve().parent.parent
D = Decimal


def inputs(name='compartilhada'):
    return load_shared(ROOT/f'experiments/sprint12-{name}.json')


def boundary(session, source, index, requests=(), change_open=None):
    at = source.config.window.start+index*MINUTE
    closes = [c for _, stream in source.datasets for c in stream if c.close_time == at]
    openings = [c.opening() for _, stream in source.datasets for c in stream if c.open_time == at]
    if change_open:
        openings = change_open(openings)
    session.on_boundary(at, closes, openings, requests)
    return session


def prefix(source, index):
    s = SharedSession(source.config)
    for i in range(index+1):
        boundary(s, source, i)
    return s


class SharedFinancialTests(unittest.TestCase):
    def test_canonical_and_multipair_manual_values(self):
        for name, q in [('compartilhada',D('.000084')),('multipar',D('.00420'))]:
            with self.subTest(name=name):
                data=inputs(name); s=replay_shared(data)
                self.assertEqual((s.cash,s.fees,s.exit_code), (D('989.95'),D('.05'),0))
                self.assertEqual(len(s.evaluations),16)
                self.assertEqual(len(s.signals),4)
                self.assertEqual([f['quantity'] for f in s.fills[:2]], [D('.000166'),q])
                self.assertEqual(s.accounts, dict(sma=D('493.32680'),ema=D('496.62320'),UNALLOCATED=D(0)))
                self.assertEqual([t['net_pnl'] for t in s.trades],[D('-6.67320'),D('-3.37680')])
                report=shared_report(s,data,shared_manifest(data))
                self.assertEqual(report['metrics']['portfolio_return_pct']['value'],'-1.005000000000')
                if name=='multipar':
                    self.assertEqual(report['metrics']['joint_exposure_seconds'],120)
                    self.assertEqual(set(report['balances']['assets']),{'BTC','ETH'})
                else:
                    self.assertEqual(report['benchmarks'][1]['gross_equity'],D('799.201'))
                for point in s.equity:
                    contrib=[p for p in s.contributions if p['seq']==point['seq']]
                    self.assertEqual(sum((p['pnl'] for p in contrib),D(0))+s.config.initial_cash,point['gross_equity'])
                    self.assertEqual(point['cash_available']+point['cash_reserved'],point['cash_total'])
                self.assertEqual(s.reconcile()['status'],'PASSED')

    def test_revalidation_rejects_second_buy_without_resizing(self):
        s=replay_shared(inputs('limite'))
        self.assertEqual((s.cash,s.fees,s.exit_code),(D('993.32680'),D('.03320'),2))
        rejected=[o for o in s.orders.values() if o['status']=='REJECTED']
        self.assertEqual(len(rejected),1)
        self.assertEqual((rejected[0]['quantity'],rejected[0]['reason']),(D('.000084'),'EXPOSURE_INSTRUMENT'))
        self.assertEqual(s.reserved_cash(),0)
        self.assertIn('INSUFFICIENT_ASSET',[d['reason'] for d in s.decisions])

    def test_priority_swap_changes_owner_only(self):
        data=inputs(); c=data.config
        data=replace(data,config=replace(c,strategies=tuple(replace(a,priority=1-a.priority) for a in c.strategies)))
        s=replay_shared(data)
        self.assertEqual(s.fills[0]['strategy_id'],'ema')
        self.assertEqual(s.accounts['ema'],D('493.32680'))
        self.assertEqual(s.cash,D('989.95'))

    def test_residual_cannot_be_borrowed(self):
        data=inputs(); c=data.config
        data=replace(data,config=replace(c,strategies=tuple(replace(a,allocation_fraction=D('.2')) for a in c.strategies)))
        s=replay_shared(data)
        self.assertEqual(s.accounts['UNALLOCATED'],D(600))
        self.assertLess(sum((f['gross']+f['fee'] for f in s.fills if f['side']=='BUY'),D(0)),D(400))

    def test_ownership_and_individual_exit(self):
        data=inputs();s=prefix(data,5)
        own=s.own_lot('sma','BTCUSDT');other=s.own_lot('ema','BTCUSDT')
        requests=[SharedRequest('foreign','sma','BTCUSDT','SELL',other['lot_id']),
                  SharedRequest('missing','sma','BTCUSDT','SELL','absent'),
                  SharedRequest('valid','sma','BTCUSDT','SELL',own['lot_id'])]
        boundary(s,data,6,requests)
        self.assertEqual([d['reason'] for d in s.decisions if d['signal_id'] in ('foreign','missing')],
                         ['OWNERSHIP_MISMATCH','INSUFFICIENT_ASSET'])
        self.assertEqual(s.own_lot('sma','BTCUSDT'),None)
        self.assertIsNotNone(s.own_lot('ema','BTCUSDT'))
        self.assertEqual(s.assets['BTC'],other['quantity'])

    def test_sell_transfer_cancel_and_duplicate_are_isolated(self):
        data=inputs();s=prefix(data,5)
        lot=s.own_lot('sma','BTCUSDT')
        # Teste do coordenador de intenções no fechamento, antes da fase OPEN.
        s.phase='SELL_REQUESTS'
        sell=SharedRequest('manual','sma','BTCUSDT','SELL')
        s.process_request(sell)
        order=next(o for o in s.pending.values() if o['side']=='SELL')
        reserve=lot['reservation_id']
        self.assertEqual(s.reserves[reserve]['holder'],order['order_id'])
        cancel=SharedRequest('cancel','sma','BTCUSDT','CANCEL',target_order_id=order['order_id'])
        s.process_request(cancel)
        self.assertEqual(s.reserves[reserve]['holder'],lot['lot_id']+':protection')
        count=len(s.events);s.process_request(cancel);self.assertEqual(len(s.events),count)
        self.assertEqual(s.reserves[s.own_lot('ema','BTCUSDT')['reservation_id']]['status'],'ACTIVE')

    def test_buy_cancel_releases_exactly_once(self):
        data=inputs();s=prefix(data,3)
        s.process_request(SharedRequest('early','sma','BTCUSDT','BUY'))
        order=next(iter(s.pending.values()));amount=s.reserved_cash()
        self.assertGreater(amount,0)
        s.process_request(SharedRequest('cancel','sma','BTCUSDT','CANCEL',target_order_id=order['order_id']))
        self.assertEqual(s.reserved_cash(),0)
        self.assertEqual(s.cash,D(1000))
        self.assertEqual(sum(r['action']=='RELEASED' for r in s.reservations),1)

    def test_gap_protection_preempts_only_own_sell(self):
        data=inputs();s=prefix(data,5)
        # Alterar apenas a próxima cotação OPEN, sem antecipá-la ao sinal.
        boundary(s,data,6,[SharedRequest('exit','sma','BTCUSDT','SELL')],
                 lambda os:[replace(o,price=D('50000')) for o in os])
        sells=[f for f in s.fills if f['side']=='SELL']
        self.assertEqual(len(sells),2)
        self.assertTrue(all(f['reason']=='GAP_STOP' for f in sells))
        self.assertEqual(sum(o.get('reason')=='PROTECTION_PREEMPTED' for o in s.orders.values()),1)
        self.assertEqual(s.assets['BTC'],0)
        self.assertEqual(len(s.trades),2)

    def test_stop_first_different_brackets_and_entry_candle_ignored(self):
        data=inputs();s=prefix(data,5)
        candles=dict(data.datasets)['BTCUSDT']
        # Range do candle de entrada é ignorado mesmo com ambos os toques.
        c=replace(candles[5],high=D('300000'),low=D('10000'))
        s.on_boundary(c.close_time,[c],[candles[6].opening()])
        self.assertEqual(len(s.fills),2)
        # Cada lote tem seus próprios níveis; o mesmo range pode resolver ambos.
        next_c=replace(candles[6],high=D('300000'),low=D('10000'))
        s.on_boundary(next_c.close_time,[next_c],[candles[7].opening()])
        sells=[f for f in s.fills if f['side']=='SELL']
        self.assertEqual(len(sells),2)
        self.assertTrue(all(f['reference_price']==D('60000') and f['reason']=='STOP' for f in sells))
        self.assertTrue(all(e['ambiguous'] for e in s.events if e['type']=='PROTECTIVE_TRIGGER'))

    def test_six_candidates_ties_and_zero_minimums(self):
        data=inputs();c=data.config
        allocations=tuple(replace(a,risk=replace(a.risk,risk_fraction=D('1'))) for a in c.strategies)
        c=replace(c,strategies=allocations,portfolio=replace(c.portfolio,exposure_fraction=D('.03001')))
        data=replace(data,config=c);s=prefix(data,4)
        sizing=s.size('sma','BTCUSDT')
        self.assertEqual(len(sizing['candidates']),6)
        self.assertEqual(sizing['limiters'],['exposure_instrument','exposure_portfolio'])
        self.assertEqual(Fraction(sizing['quantity'])/Fraction(c.instrument('BTCUSDT').instrument_filters.step)%1,0)
        # Sem espaço depois de comprometer a capacidade, não se aumenta o lote.
        s.process_request(SharedRequest('fill-cap','sma','BTCUSDT','BUY'))
        s.process_request(SharedRequest('last','ema','BTCUSDT','BUY'))
        self.assertEqual(s.decisions[-1]['reason'],'BELOW_MINIMUMS')
        self.assertIsNotNone(s.decisions[-1]['sizing'])

    def test_different_protections_on_same_physical_asset(self):
        data=inputs();c=data.config
        c=replace(c,strategies=tuple(replace(a,risk=replace(a.risk,stop_fraction=D('.2'))) if a.id=='ema' else a for a in c.strategies))
        data=replace(data,config=c);s=prefix(data,5)
        candles=dict(data.datasets)['BTCUSDT']
        boundary(s,data,6)  # Candle da entrada, proteção ainda inelegível.
        # Low de 80000 toca stop EMA=96000 e não toca SMA=60000.
        boundary(s,data,7)
        sells=[f for f in s.fills if f['side']=='SELL']
        self.assertEqual([(f['strategy_id'],f['reason']) for f in sells],[('ema','STOP'),('sma',None)])
        self.assertEqual(sells[0]['reference_price'],D(96000))
        self.assertEqual(len(s.trades),2)

    def test_hierarchical_revalidation_limit_precedence(self):
        data=inputs();s=prefix(data,4)
        s.process_request(SharedRequest('manual','sma','BTCUSDT','BUY'))
        order=next(iter(s.pending.values()));opening=dict(data.datasets)['BTCUSDT'][4].opening()
        opening=replace(opening,at=s.at,price=s.marks['BTCUSDT'][0])
        # Aumentar somente compromissos concorrentes; a candidatura própria é excluída.
        with patch.object(s,'commitments',return_value=(D(1000),D(1000))):
            self.assertEqual(s.revalidate(order,opening)[0],'EXPOSURE_PORTFOLIO')
        old=s.config
        s.config=replace(old,portfolio=replace(old.portfolio,exposure_fraction=D(1)))
        with patch.object(s,'commitments',side_effect=lambda owner=None,symbol=None,exclude=None:(D(100) if symbol else D(0),D(0))):
            self.assertEqual(s.revalidate(order,opening)[0],'EXPOSURE_INSTRUMENT')
        s.config=replace(old,instrument_limits=(('BTCUSDT',D(1)),),portfolio=replace(old.portfolio,exposure_fraction=D(1)))
        with patch.object(s,'commitments',side_effect=lambda owner=None,symbol=None,exclude=None:(D(600) if owner else D(0),D(0))):
            self.assertEqual(s.revalidate(order,opening)[0],'EXPOSURE_STRATEGY')
        with patch.object(s,'commitments',return_value=(D(0),D(100))):
            self.assertEqual(s.revalidate(order,opening)[0],'OPEN_RISK_LIMIT')

    def test_context_is_local(self):
        with localcontext() as ctx:
            ctx.prec=3;ctx.traps[Inexact]=True
            s=replay_shared(inputs())
            self.assertEqual(ctx.prec,3)
            self.assertEqual(s.cash,D('989.95'))


class SharedBoundaryTests(unittest.TestCase):
    def test_api_file_parity_permutation_dedup_and_conflict(self):
        data=inputs('multipar');s=SharedSession(data.config)
        for i in range(9):
            at=data.config.window.start+i*MINUTE
            cs=[c for _, stream in data.datasets for c in stream if c.close_time==at]
            os=[c.opening() for _, stream in data.datasets for c in stream if c.open_time==at]
            s.on_boundary(at,cs[::-1]*2,os[::-1]*2)
            before=canonical(s.events)
            s.on_boundary(at,cs,os)
            self.assertEqual(canonical(s.events),before)
            if os:
                with self.assertRaises(ValidationError):
                    s.on_boundary(at,cs,[replace(os[0],price=D(1)),*os[1:]])
                self.assertEqual(canonical(s.events),before)
        s.finish();reference=replay_shared(data)
        self.assertEqual(canonical(s.events),canonical(reference.events))
        before=canonical(s.events);s.finish();self.assertEqual(canonical(s.events),before)

    def test_invalid_and_out_of_order_boundary_are_atomic(self):
        data=inputs();s=prefix(data,1);before=copy.deepcopy(s.__dict__)
        with self.assertRaises(ValidationError):boundary(s,data,3)
        self.assertEqual(canonical(s.events),canonical(before['events']))
        with self.assertRaises(ValidationError):
            boundary(s,data,2,[SharedRequest('x','unknown','BTCUSDT','BUY')])
        self.assertEqual(canonical(s.events),canonical(before['events']))

    def test_injected_failure_rolls_back_indicators_and_ledger(self):
        data=inputs();s=prefix(data,4);before=canonical(s.events)
        with patch.object(SharedSession,'fill',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):boundary(s,data,5)
        self.assertEqual(canonical(s.events),before)
        self.assertEqual(len(s.evaluations),8)
        self.assertEqual(s.cash,D(1000))
        boundary(s,data,5)
        self.assertEqual(len(s.fills),2)

    def test_future_open_does_not_change_close_approvals(self):
        data=inputs();a=prefix(data,4);b=copy.deepcopy(a)
        boundary(a,data,5)
        boundary(b,data,5,change_open=lambda os:[replace(o,price=D('220000')) for o in os])
        self.assertEqual(canonical(a.decisions),canonical(b.decisions))
        reserves=lambda s:[r for r in s.reservations if r['phase']=='BUY_ARBITRATION']
        self.assertEqual(canonical(reserves(a)),canonical(reserves(b)))
        self.assertEqual(len(b.fills),0)
        self.assertEqual(b.reserved_cash(),0)
        self.assertTrue(any(e.get('reason')=='RISK_BUDGET_EXCEEDED' for e in b.events))

    def test_global_gap_keeps_close_signals_and_reservations(self):
        data=inputs('multipar');s=prefix(data,4)
        at=data.config.window.start+5*MINUTE
        cs=[c for _,stream in data.datasets for c in stream if c.close_time==at]
        os=[c.opening() for sym,stream in data.datasets if sym=='BTCUSDT' for c in stream if c.open_time==at]
        s.on_boundary(at,cs,os)
        self.assertTrue(s.interrupted)
        self.assertEqual(len(s.signals),2)
        self.assertEqual(len(s.fills),0)
        self.assertGreater(s.reserved_cash(),D(30))
        self.assertEqual(s.cash,D(1000))
        self.assertEqual(s.marks['BTCUSDT'],(D(120000),at))
        self.assertFalse(any(e['phase']=='OPEN_MARKS' and e['at']==at for e in s.events))
        s.finish();self.assertGreater(s.reserved_cash(),0)
        self.assertEqual(s.exit_code,1)

    def test_initial_missing_stream_interrupts_without_open_batch(self):
        data=inputs('multipar');s=SharedSession(data.config)
        opening=dict(data.datasets)['BTCUSDT'][0].opening()
        s.on_boundary(data.config.window.start,[],[opening])
        self.assertTrue(s.interrupted)
        self.assertEqual(s.marks,{})

    def test_no_observations_is_unavailable(self):
        data=inputs();data=replace(data,datasets=tuple((s,()) for s,_ in data.datasets))
        s=replay_shared(data);r=shared_report(s,data,shared_manifest(data))
        self.assertEqual((s.cash,s.exit_code,len(s.fills)),(D(1000),2,0))
        self.assertEqual(r['metrics']['portfolio_return_pct']['value'],None)
        self.assertEqual(r['benchmarks'][1]['gross_equity'],None)

    def test_finalization_cannot_hide_an_unclosed_prefix(self):
        data=inputs();s=prefix(data,5);before=canonical(s.events)
        for kwargs in ({}, {'unavailable':True}, {'unavailable':1}):
            with self.assertRaises(ValidationError):s.finish(**kwargs)
            self.assertEqual(canonical(s.events),before)

    def test_delisting_retains_lot_and_releases_base(self):
        data=inputs();end=data.config.window.start+6*MINUTE
        catalog=replace(data.config.catalog,instruments=tuple(replace(i,available_until=end) if i.symbol=='BTCUSDT' else i for i in data.config.catalog.instruments))
        data=replace(data,config=replace(data.config,catalog=catalog),datasets=tuple((s,tuple(c for c in cs if c.close_time<=end)) for s,cs in data.datasets))
        s=replay_shared(data)
        self.assertEqual(s.assets['BTC'],D('.000250'))
        self.assertTrue(all(l['protection_status']=='INSTRUMENT_UNAVAILABLE' for l in s.active_lots()))
        self.assertTrue(all(r['status']!='ACTIVE' for r in s.reserves.values()))
        self.assertEqual(s.marks['BTCUSDT'][1],end)

    def test_late_listing_does_not_warm_with_excluded_history(self):
        data=inputs('multipar');start=data.config.window.start+2*MINUTE
        catalog=replace(data.config.catalog,instruments=tuple(replace(i,available_from=start) if i.symbol=='ETHUSDT' else i for i in data.config.catalog.instruments))
        data=replace(data,config=replace(data.config,catalog=catalog),datasets=tuple((s,tuple(c for c in cs if s!='ETHUSDT' or c.open_time>=start)) for s,cs in data.datasets))
        s=replay_shared(data)
        evaluations=[e['evaluation'] for e in s.evaluations if e['symbol']=='ETHUSDT']
        self.assertEqual(len(evaluations),6)
        self.assertEqual(evaluations[0]['count'],1)
        self.assertEqual(evaluations[0]['missing_reason'],'WARMUP')
        self.assertFalse(s.interrupted)

    def test_boundary_numeric_equivalence_has_same_digest(self):
        data=inputs();s=SharedSession(data.config)
        opening=dict(data.datasets)['BTCUSDT'][0].opening()
        s.on_boundary(opening.at,[],[opening,replace(opening,price=D('100000.0000'))])
        events=canonical(s.events)
        s.on_boundary(opening.at,[],[opening])
        self.assertEqual(canonical(s.events),events)

    def test_invalid_instrument_and_future_open_roll_back(self):
        data=inputs();s=SharedSession(data.config);opening=dict(data.datasets)['BTCUSDT'][0].opening()
        before=canonical(s.events)
        for op in [replace(opening,symbol='ETHUSDT'),replace(opening,at=opening.at+MINUTE)]:
            with self.assertRaises(ValidationError):s.on_boundary(opening.at,[],[op])
            self.assertEqual(canonical(s.events),before)

    def test_stale_held_price_and_future_price(self):
        data=inputs('multipar');s=prefix(data,5)
        s.at += 2*MINUTE
        s.marks['BTCUSDT']=(D(100000),s.at)
        self.assertEqual(s.buy_reason('sma','BTCUSDT'),'PORTFOLIO_PRICE_STALE')
        s.marks['BTCUSDT']=(D(100000),s.at+MINUTE)
        with self.assertRaises(ValidationError):s.buy_reason('sma','BTCUSDT')

    def test_global_and_strategy_blocks_equality_persist_and_sell(self):
        data=inputs();s=prefix(data,5)
        owner='sma'
        for scope,prefix_name in [('PORTFOLIO','PORTFOLIO'),(owner,'STRATEGY')]:
            s=prefix(data,5)
            guard=s.guards[scope]
            # Igualdade do limiar com observações sem transferir capital ao ledger.
            peak=guard.current['peak'];seq=s.seq+1
            guard=guard.observe(s.at,seq,'TEST_LOSS',peak*D('.1'))
            guard=guard.observe(s.at,seq+1,'TEST_RECOVERY',peak)
            s.guards[scope]=guard
            self.assertEqual(s.buy_reason(owner,'BTCUSDT'),prefix_name+'_DAILY_LOSS_BLOCKED')
            s.seq=seq+1
            s.process_request(SharedRequest('exit',owner,'BTCUSDT','SELL'))
            self.assertTrue(s.decisions[-1]['approved'])
            tomorrow=s.at.replace(hour=0,minute=0)+24*60*MINUTE
            s.guards[scope]=guard.observe(tomorrow,seq+2,'NEXT_DAY',peak)
            self.assertTrue(s.guards[scope].current['drawdown_blocked'])
            self.assertFalse(s.guards[scope].current['daily_blocked'])


class SharedConfigAndArtifactTests(unittest.TestCase):
    def test_api_invalid_types_and_fraction_sum(self):
        c=inputs().config
        for kwargs in [dict(schema_version=True),dict(catalog=None),dict(strategies=list(c.strategies)),dict(fee_rate=D('NaN'))]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValidationError):replace(c,**kwargs)
        for kwargs in [dict(priority=True),dict(id='UNALLOCATED'),dict(symbols=('BTCUSDT','BTCUSDT'))]:
            with self.assertRaises(ValidationError):replace(c.strategies[0],**kwargs)
        with self.assertRaises(ValidationError):
            replace(c,strategies=tuple(replace(a,allocation_fraction=D('.500000000001')) for a in c.strategies))
        with self.assertRaises(ValidationError):SharedSession(None)

    def test_json_strict_validation_before_output(self):
        original=json.loads((ROOT/'experiments/sprint12-compartilhada.json').read_text())
        original['catalog']=str(ROOT/'data/catalogo/sprint11-instrumentos.json')
        original['datasets'][0]['path']=str(ROOT/'data/fixtures/sprint12-btc-candles.json')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'recipe.json'
            variants=[]
            for key,value in [('schema_version',True),('filters',{}),('source','OTHER')]:
                v=copy.deepcopy(original);v[key]=value;variants.append(v)
            v=copy.deepcopy(original);v['strategies'][0]['priority']=True;variants.append(v)
            v=copy.deepcopy(original);v['datasets']*=2;variants.append(v)
            v=copy.deepcopy(original);v['strategies'][0]['symbols']=['ETHUSDT'];variants.append(v)
            for v in variants:
                p.write_text(json.dumps(v))
                with self.assertRaises(ValidationError):load_shared(p)
            p.write_text('{"schema_version":7,"schema_version":7}')
            with self.assertRaises(ValidationError):load_shared(p)

    def test_recipe_permutation_preserves_identity_and_events(self):
        data=inputs('multipar');meta=shared_manifest(data)
        value=json.loads((ROOT/'experiments/sprint12-multipar.json').read_text())
        value['catalog']=str(ROOT/'data/catalogo/sprint11-instrumentos.json')
        for d in value['datasets']:d['path']=str(ROOT/Path('experiments')/d['path'])
        value['strategies'].reverse();value['datasets'].reverse()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'permuted.json';p.write_text(json.dumps(value))
            other=load_shared(p);other_meta=shared_manifest(other)
        self.assertEqual(meta['run_id'],other_meta['run_id'])
        self.assertNotEqual(meta['recipe_hash'],other_meta['recipe_hash'])
        self.assertEqual(canonical(replay_shared(data,meta['run_id']).events),canonical(replay_shared(other,other_meta['run_id']).events))

    def test_fifteen_artifacts_and_html_are_repeatable(self):
        data=inputs('multipar');m=shared_manifest(data);s=replay_shared(data,m['run_id']);r=shared_report(s,data,m)
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            write_shared(a,m,r);write_shared(b,m,r)
            self.assertEqual(len(list(a.iterdir())),15)
            self.assertFalse((a/'INCOMPLETE').exists())
            self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},{p.name:p.read_bytes() for p in b.iterdir()})
            with self.assertRaises(FileExistsError):write_shared(a,m,r)
        html=shared_html(r)
        self.assertIn('USDT/ETH',html);self.assertIn('Candles BTCUSDT',html)
        self.assertIn('@media print',html)
        self.assertNotIn('<script',html)
        self.assertEqual(html,shared_html(r))

    def test_export_write_failure_keeps_incomplete_without_manifest(self):
        data=inputs();m=shared_manifest(data);r=shared_report(replay_shared(data),data,m)
        original=Path.write_text
        def fail(path,*args,**kwargs):
            if path.name=='ledger.jsonl':raise OSError('injected')
            return original(path,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'out'
            with patch.object(Path,'write_text',fail),self.assertRaises(OSError):write_shared(target,m,r)
            self.assertTrue((target/'INCOMPLETE').exists());self.assertFalse((target/'manifest.json').exists())

    def test_cli_other_cwd_and_all_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            for i,fmt in enumerate(('json','html','texto','markdown')):
                result=subprocess.run([sys.executable,'-m','replayquant','carteira','--config',str(ROOT/'experiments/sprint12-compartilhada.json'),
                                       '--saida',str(Path(tmp)/str(i)),'--formato',fmt,'--analise'],cwd=tmp,
                                      env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertTrue(result.stdout)


if __name__=='__main__':unittest.main()
