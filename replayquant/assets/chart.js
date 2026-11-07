/* ReplayQuant: renderização local. Number é usado somente no gráfico; valores exatos permanecem nas strings. */
(() => {
    'use strict';
    const container = document.getElementById('candle-chart');
    const error = document.getElementById('chart-error');
    const controls = document.getElementById('chart-controls');
    try {
        const data = JSON.parse(document.getElementById('chart-data').textContent);
        const L = window.LightweightCharts;
        const colors = {gain: '#14794e', loss: '#bd2636', neutral: '#546779', buy: '#2563eb'};
        const num = value => {
            const number = Number(value);
            if (!Number.isFinite(number) || number <= 0) throw new Error('Preço inválido no gráfico');
            return number;
        };
        const text = value => String(value).replace('.', ',');
        const utc = time => new Date(time * 1000).toISOString().replace('T', ' ').replace('.000Z', ' UTC');
        const priceStrings = data.executions.map(f => f.price).concat(data.candles.map(c => c.close));
        const precision = Math.min(12, priceStrings.reduce((digits, price) =>
            Math.max(digits, (price.replace(/0+$/, '').split('.')[1] || '').length), 2));
        const priceFormatter = new Intl.NumberFormat('pt-BR', {useGrouping: false, maximumFractionDigits: precision});
        const chart = L.createChart(container, {
            autoSize: true,
            height: 470,
            layout: {background: {type: L.ColorType.Solid, color: '#ffffff'}, textColor: '#546779',
                     fontFamily: 'system-ui, sans-serif', attributionLogo: true},
            leftPriceScale: {visible: true, minimumWidth: 110, borderColor: '#dbe4ea'},
            rightPriceScale: {visible: false},
            timeScale: {timeVisible: true, secondsVisible: false, borderColor: '#dbe4ea',
                        rightOffset: 2, minBarSpacing: 0.5},
            localization: {locale: 'pt-BR', timeFormatter: utc,
                           priceFormatter: price => priceFormatter.format(price)},
            grid: {vertLines: {color: '#dbe4ea', style: L.LineStyle.Dotted},
                   horzLines: {color: '#e2e8f0', style: L.LineStyle.Solid}},
            crosshair: {mode: L.CrosshairMode.Normal,
                        vertLine: {style: L.LineStyle.Dotted, color: '#64748b'},
                        horzLine: {style: L.LineStyle.Dotted, color: '#64748b'}},
        });
        const series = chart.addSeries(L.CandlestickSeries, {
            priceScaleId: 'left', upColor: '#16835b', downColor: '#c23b45',
            wickUpColor: '#16835b', wickDownColor: '#c23b45', borderVisible: false,
            priceFormat: {type: 'price', precision, minMove: 10 ** -precision},
        });
        series.setData(data.candles.map(c => ({time: c.time, open: num(c.open),
            high: num(c.high), low: num(c.low), close: num(c.close)})));
        const markers = L.createSeriesMarkers(series, data.executions.map(f => ({
            id: f.id, time: f.time, price: num(f.price), position: f.side === 'BUY' ? 'atPriceBottom' : 'atPriceTop',
            color: colors[f.classification], shape: f.side === 'BUY' ? 'arrowUp' : 'arrowDown',
            text: f.side === 'BUY' ? 'COMPRA' : 'VENDA',
        })), {autoScale: true});
        for (const trade of data.trades) {
            const line = chart.addSeries(L.LineSeries, {color: colors[trade.classification],
                priceScaleId: 'left', lineStyle: L.LineStyle.Dashed, lineWidth: 2,
                lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false});
            line.setData([{time: trade.buy_time, value: num(trade.buy_price)},
                          {time: trade.sell_time, value: num(trade.sell_price)}]);
        }
        const byTime = new Map(data.candles.map(c => [c.time, c]));
        const fillsByTime = new Map();
        for (const fill of data.executions) {
            if (!fillsByTime.has(fill.time)) fillsByTime.set(fill.time, []);
            fillsByTime.get(fill.time).push(fill);
        }
        const readout = document.getElementById('chart-readout');
        const show = time => {
            const c = byTime.get(time);
            if (!c) return;
            const details = [`${utc(time)} · Abertura ${text(c.open)} · Máxima ${text(c.high)} · ` +
                `Mínima ${text(c.low)} · Fechamento ${text(c.close)} USDT/BTC · Volume ${text(c.volume)} BTC`];
            for (const f of fillsByTime.get(time) || []) {
                details.push(`${f.side === 'BUY' ? 'COMPRA' : 'VENDA'}: ${text(f.quantity)} BTC a ${text(f.price)} USDT/BTC; ` +
                    `taxa ${text(f.fee)} USDT` + (f.net !== null ? `; resultado líquido ${f.net} USDT` : ''));
            }
            readout.textContent = details.join('\n');
        };
        show(data.candles[data.candles.length - 1].time);
        chart.subscribeCrosshairMove(param => { if (param.time !== undefined) show(param.time); });
        chart.timeScale().fitContent();
        controls.hidden = false;
        controls.addEventListener('click', event => {
            const button = event.target.closest('button[data-chart-action]');
            if (!button) return;
            const action = button.dataset.chartAction;
            if (action === 'all') chart.timeScale().fitContent();
            else if (action === 'recent') {
                chart.timeScale().setVisibleLogicalRange({from: Math.max(-0.5, data.candles.length - 60.5),
                                                         to: data.candles.length - 0.5});
            } else {
                const range = chart.timeScale().getVisibleLogicalRange();
                if (!range) return;
                const middle = (range.from + range.to) / 2;
                const span = Math.max(6, (range.to - range.from) * (action === 'in' ? 0.67 : 1.5));
                chart.timeScale().setVisibleLogicalRange({from: middle - span / 2, to: middle + span / 2});
            }
        });
        window.addEventListener('beforeprint', () => {
            document.getElementById('chart-print-image').src = chart.takeScreenshot(true).toDataURL('image/png');
        });
        container.dataset.chartReady = 'true';
        // API da biblioteca fica disponível no próprio elemento para inspeção e integração local.
        container.replayquantChart = {chart, series, markers};
    } catch (exception) {
        container.hidden = true;
        error.hidden = false;
        error.textContent = 'Não foi possível desenhar o gráfico. Os valores exatos continuam nas tabelas deste relatório.';
        container.dataset.chartReady = 'error';
        console.error('ReplayQuant: falha ao renderizar o gráfico', exception);
    }
})();
