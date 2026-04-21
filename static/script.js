document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/api/data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        processAndRenderData(data);
    } catch (error) {
        console.error("Could not fetch data:", error);
        document.getElementById('summaryCards').innerHTML = `<p style="color: #ef4444; grid-column: 1/-1; text-align: center;">Error loading data. Is the backend running?</p>`;
    }
});

function processAndRenderData(rawData) {
    // rawData is an object with date string keys
    const dates = Object.keys(rawData).sort();
    
    let totalProfit = 0;
    let totalBuy = 0;
    let totalSell = 0;
    
    const dailyProfits = [];
    const cumulativeProfits = [];
    const buyVolumes = [];
    const sellVolumes = [];
    
    dates.forEach(date => {
        const dayData = rawData[date];
        
        totalProfit += dayData.profit;
        totalBuy += dayData.buy_amount;
        totalSell += dayData.sell_amount;
        
        dailyProfits.push(dayData.profit);
        cumulativeProfits.push(totalProfit);
        buyVolumes.push(dayData.buy_amount);
        sellVolumes.push(dayData.sell_amount);
    });

    // Update summary cards
    document.getElementById('totalProfit').textContent = `₹${totalProfit.toFixed(2)}`;
    // Color profit green if positive, red if negative
    if (totalProfit < 0) {
        document.getElementById('totalProfit').style.color = 'var(--loss-color)';
    }
    document.getElementById('totalBuy').textContent = `${totalBuy.toFixed(2)} USDT`;
    document.getElementById('totalSell').textContent = `${totalSell.toFixed(2)} USDT`;

    // Common Chart.js options for dark theme
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: '#f8fafc' }
            },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                titleColor: '#f8fafc',
                bodyColor: '#e2e8f0',
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1,
                padding: 12,
                cornerRadius: 8
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#94a3b8' }
            },
            y: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#94a3b8' }
            }
        }
    };

    // 1. Daily Profit Chart (Bar)
    const ctxDaily = document.getElementById('dailyProfitChart').getContext('2d');
    new Chart(ctxDaily, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [{
                label: 'Daily Profit (₹)',
                data: dailyProfits,
                backgroundColor: dailyProfits.map(p => p >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'),
                borderColor: dailyProfits.map(p => p >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)'),
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: commonOptions
    });

    // 2. Cumulative Profit Chart (Line)
    const ctxCumulative = document.getElementById('cumulativeProfitChart').getContext('2d');
    // Create gradient
    const gradient = ctxCumulative.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.5)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

    new Chart(ctxCumulative, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Cumulative Profit (₹)',
                data: cumulativeProfits,
                borderColor: '#3b82f6',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#3b82f6',
                pointBorderColor: '#0f172a',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            ...commonOptions,
            interaction: {
                intersect: false,
                mode: 'index',
            }
        }
    });

    // 3. Trading Volume Chart (Bar - Buy vs Sell)
    const ctxVolume = document.getElementById('volumeChart').getContext('2d');
    new Chart(ctxVolume, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Buy Volume (USDT)',
                    data: buyVolumes,
                    backgroundColor: 'rgba(59, 130, 246, 0.7)',
                    borderColor: 'rgb(59, 130, 246)',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Sell Volume (USDT)',
                    data: sellVolumes,
                    backgroundColor: 'rgba(167, 139, 250, 0.7)',
                    borderColor: 'rgb(167, 139, 250)',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    ...commonOptions.plugins.tooltip,
                    mode: 'index',
                    intersect: false
                }
            }
        }
    });
}
