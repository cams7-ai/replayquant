"""Experimento offline de sementes em um sufixo comum, sem carteira."""
import argparse
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from .data import load_inputs
from .metrics import ratio
from .reporting import json_text
from .strategies import REGISTRY
from .strategy_models import CrossParameters, RSIParameters
from decimal import Decimal


def investigate(data_path, config_path):
    inputs = load_inputs(data_path, config_path)
    if len(inputs.candles) < 80:
        raise ValueError('Experimento requer ao menos 80 candles contíguos')
    spec = inputs.config.strategy
    parameters = RSIParameters(14, Decimal(30), Decimal(70)) if spec.name == 'RSI_REVERSION' else CrossParameters(9, 21)
    spec = replace(spec, parameters=parameters)
    suffix = inputs.candles[50:80]
    histories = {}
    for prior in (0, 10, 50):
        strategy = REGISTRY.create(spec)
        evaluations = {}
        for candle in inputs.candles[50-prior:80]:
            evaluation = strategy.on_close(candle)
            if candle.open_time >= suffix[0].open_time:
                evaluations[candle.close_time] = evaluation
        histories[prior] = evaluations
    rows = []
    counts = []
    for prior in (0, 10):
        compared = unavailable = mismatches = 0
        for candle in suffix:
            left, right = histories[prior][candle.close_time], histories[50][candle.close_time]
            comparable = left['signal_ready'] and right['signal_ready']
            differences = {}
            if comparable:
                compared += 1
                for key, value in left['values'].items():
                    other = right['values'][key]
                    a = Fraction(int(value['numerator']), int(value['denominator']))
                    b = Fraction(int(other['numerator']), int(other['denominator']))
                    differences[key] = ratio(abs(a-b), value['unit'])
                mismatches += left['side'] != right['side']
            else:
                unavailable += 1
            rows.append(dict(at=candle.close_time, prior_candles=prior, reference_prior_candles=50,
                             comparable=comparable, missing_reason=None if comparable else 'WARMUP',
                             absolute_differences=differences, side=left['side'], reference_side=right['side'],
                             signal_difference=comparable and left['side'] != right['side']))
        counts.append(dict(prior_candles=prior, comparable=compared, unavailable=unavailable,
                           signal_differences=mismatches))
    return dict(strategy=spec, data_hash=inputs.data_hash, suffix_start=suffix[0].open_time,
                suffix_end=suffix[-1].close_time, policy='INDICATORS_ONLY_COMMON_SUFFIX',
                summary=counts, comparisons=rows)


def main():
    parser = argparse.ArgumentParser(description='Estabilidade do aquecimento em sufixo comum')
    parser.add_argument('--dados', default='data/fixtures/sprint07-candles-expandido.json')
    parser.add_argument('--config', required=True)
    parser.add_argument('--saida', required=True)
    args = parser.parse_args()
    result = investigate(args.dados, args.config)
    with Path(args.saida).open('x', encoding='utf-8') as output:
        output.write(json_text(result))


if __name__ == '__main__':
    main()
