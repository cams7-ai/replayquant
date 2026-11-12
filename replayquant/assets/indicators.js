/* Fronteira gráfica: números aproximados somente para renderização. */
(() => {
    'use strict';
    const container = document.getElementById('indicator-chart');
    const error = document.getElementById('indicator-error');
    try {
        const data = JSON.parse(document.getElementById('indicator-data').textContent);
        const L = window.LightweightCharts;
        const chart = L.createChart(container, {
            autoSize: false,
            width: container.clientWidth,
            height: container.clientHeight,
            layout: {background: {color: '#ffffff'}, textColor: '#334155', attributionLogo: false},
            leftPriceScale: {visible: true, scaleMargins: data.rsi ? {top: 0, bottom: 0} : {top: 0.1, bottom: 0.1}},
            rightPriceScale: {visible: false},
            timeScale: {timeVisible: true, secondsVisible: false},
        });
        const colors = ['#087e83', '#9260b8'];
        data.series.forEach((item, index) => {
            const options = {title: item.name, color: colors[index], priceScaleId: 'left', lineWidth: 2};
            if (data.rsi) {
                options.autoscaleInfoProvider = () => ({priceRange: {minValue: 0, maxValue: 100}});
            }
            const line = chart.addSeries(L.LineSeries, options);
            line.setData(item.points.map(p => ({time: p.time, value: Number(p.value)})));
            if (data.rsi) {
                ['oversold', 'overbought'].forEach(key => line.createPriceLine({
                    price: Number(data.parameters[key]), title: key, color: '#64748b',
                    lineStyle: L.LineStyle.Dashed, axisLabelVisible: true,
                }));
            }
        });
        chart.timeScale().fitContent();
        const observer = new ResizeObserver(() => {
            if (container.clientWidth > 0 && container.clientHeight > 0) {
                chart.resize(container.clientWidth, container.clientHeight, true);
                chart.timeScale().fitContent();
            }
        });
        observer.observe(container);
        chart.subscribeCrosshairMove(event => {
            if (event.time === undefined) return;
            const values = data.series.map(item => {
                const point = item.points.find(p => p.time === event.time);
                return point ? `${item.name} = ${point.value}` : '';
            }).filter(Boolean);
            document.getElementById('indicator-readout').textContent =
                new Date(event.time * 1000).toISOString() + ' · ' + values.join(' · ');
        });
        const snapshot = () => {
            document.getElementById('indicator-print-image').src = chart.takeScreenshot(true).toDataURL('image/png');
        };
        window.addEventListener('beforeprint', snapshot);
        container.dataset.ready = 'true';
    } catch (exception) {
        error.hidden = false;
        error.textContent = 'Falha no gráfico de indicadores. Consulte a tabela de valores exatos.';
        container.dataset.ready = 'error';
    }
})();
