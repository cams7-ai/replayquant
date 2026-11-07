/* Curvas por índice de evento: timestamps iguais são preservados, sem contas financeiras no JS. */
(() => {
    'use strict';
    const portfolios = JSON.parse(document.getElementById('equity-data').textContent);
    const L = window.LightweightCharts;
    for (const data of portfolios) {
        const element = document.getElementById(`equity-${data.portfolio}`);
        try {
            const chart = L.createChart(element, {
                autoSize: true, height: 300,
                layout: {background: {type: L.ColorType.Solid, color: 'white'}, textColor: '#546779', attributionLogo: true},
                leftPriceScale: {visible: true, minimumWidth: 100}, rightPriceScale: {visible: false},
                grid: {vertLines: {style: L.LineStyle.Dotted, color: '#dbe4ea'}, horzLines: {color: '#e2e8f0'}},
                timeScale: {minBarSpacing: 0.5, tickMarkFormatter: index => String(index)},
                localization: {locale: 'pt-BR', priceFormatter: value => new Intl.NumberFormat('pt-BR', {useGrouping:false, maximumFractionDigits:4}).format(value), timeFormatter: index => {
                    const p = data.points[index-1];
                    return p ? `Evento ${index} · ${p.at}` : String(index);
                }},
            });
            const series = chart.addSeries(L.LineSeries, {color: data.color, priceScaleId: 'left',
                priceFormat: {type: 'price', precision: 4, minMove: 0.0001}});
            series.setData(data.points.map(p => {
                const value = Number(p.gross_equity);
                if (!Number.isFinite(value)) throw new Error('Valor não finito');
                return {time: p.point_seq, value};
            }));
            const readout = document.getElementById(`equity-readout-${data.portfolio}`);
            const show = index => {
                const p = data.points[index-1];
                if (!p) return;
                readout.textContent = `Evento ${index} · ${p.at} · ${p.phase} · ` +
                    `Patrimônio bruto ${p.gross_equity.replace('.',',')} USDT · ` +
                    `Realizado ${p.realized_pnl.replace('.',',')} · Não realizado ${p.unrealized_pnl.replace('.',',')} USDT`;
            };
            show(data.points.length);
            chart.subscribeCrosshairMove(p => { if (p.time !== undefined) show(p.time); });
            chart.timeScale().fitContent();
            document.getElementById(`equity-fit-${data.portfolio}`).addEventListener('click', () => chart.timeScale().fitContent());
            window.addEventListener('beforeprint', () => {
                document.getElementById(`equity-print-${data.portfolio}`).src = chart.takeScreenshot(true).toDataURL('image/png');
            });
            element.replayquantEquity = {chart, series, points: data.points};
            element.dataset.chartReady = 'true';
        } catch (exception) {
            element.hidden = true;
            const error = document.getElementById(`equity-error-${data.portfolio}`);
            error.hidden = false;
            error.textContent = 'Curva indisponível no navegador; consulte os valores exatos na tabela.';
            element.dataset.chartReady = 'error';
            console.error('ReplayQuant: curva patrimonial', exception);
        }
    }
})();
