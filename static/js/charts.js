/**
 * charts.js - Chart.js visualizations for FinTrack
 */

let categoryChartInstance = null;
let sourceChartInstance = null;
let trendChartInstance = null;

// Currency Formatter (INR)
const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(val || 0);
};

/**
 * Initializes or updates the Category Expenses Donut Chart
 */
function renderCategoryChart(categoryData) {
    const ctx = document.getElementById('categoryDonutChart');
    if (!ctx) return;

    if (categoryChartInstance) {
        categoryChartInstance.destroy();
    }

    if (!categoryData || categoryData.length === 0) {
        ctx.parentElement.innerHTML = `
            <div class="h-64 flex flex-col items-center justify-center text-slate-400">
                <i data-lucide="pie-chart" class="w-12 h-12 mb-2 stroke-1 opacity-40"></i>
                <p class="text-sm">No expense records found for this month</p>
            </div>`;
        if (window.lucide) lucide.createIcons();
        return;
    }

    const labels = categoryData.map(c => c.name);
    const dataValues = categoryData.map(c => c.amount);
    const bgColors = categoryData.map(c => c.color || '#6366F1');

    categoryChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: dataValues,
                backgroundColor: bgColors,
                borderColor: '#1E293B',
                borderWidth: 2,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94A3B8',
                        padding: 12,
                        font: { size: 11, family: 'Inter' },
                        boxWidth: 12,
                        boxHeight: 12,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: '#0F172A',
                    titleColor: '#F8FAFC',
                    bodyColor: '#CBD5E1',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: function (context) {
                            const val = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                            return ` ${context.label}: ${formatCurrency(val)} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Initializes or updates the Source Comparison (Bank vs Credit Card) Bar Chart
 */
function renderSourceChart(bankAmount, ccAmount, emiAmount) {
    const ctx = document.getElementById('sourceBarChart');
    if (!ctx) return;

    if (sourceChartInstance) {
        sourceChartInstance.destroy();
    }

    sourceChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Bank Expenses', 'Credit Card Spends', 'Loan & CC EMIs'],
            datasets: [{
                label: 'Monthly Outflow',
                data: [bankAmount, ccAmount, emiAmount],
                backgroundColor: [
                    'rgba(2, 132, 199, 0.8)',   // Sky/Bank
                    'rgba(99, 102, 241, 0.8)',  // Indigo/CC
                    'rgba(239, 68, 68, 0.8)'    // Red/EMI
                ],
                borderColor: [
                    '#0284C7',
                    '#6366F1',
                    '#EF4444'
                ],
                borderWidth: 1,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderWidth: 1,
                    callbacks: {
                        label: (ctx) => ` Outflow: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#94A3B8', font: { size: 11, family: 'Inter' } }
                },
                y: {
                    grid: { color: 'rgba(51, 65, 85, 0.4)' },
                    ticks: {
                        color: '#94A3B8',
                        font: { size: 11, family: 'Inter' },
                        callback: (val) => '₹' + (val >= 1000 ? (val / 1000).toFixed(0) + 'k' : val)
                    }
                }
            }
        }
    });
}

/**
 * Initializes or updates the 6-Month Trend Chart
 */
function renderTrendChart(monthsTrend) {
    const ctx = document.getElementById('trendChart');
    if (!ctx || !monthsTrend || monthsTrend.length === 0) return;

    if (trendChartInstance) {
        trendChartInstance.destroy();
    }

    const labels = monthsTrend.map(m => m.label);
    const incomeData = monthsTrend.map(m => m.income);
    const expensesData = monthsTrend.map(m => m.total_expenses);
    const emiData = monthsTrend.map(m => m.emi_expenses);

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Income',
                    data: incomeData,
                    backgroundColor: 'rgba(34, 197, 94, 0.75)',
                    borderColor: '#22C55E',
                    borderWidth: 1,
                    borderRadius: 6
                },
                {
                    label: 'Total Expenses',
                    data: expensesData,
                    backgroundColor: 'rgba(239, 68, 68, 0.75)',
                    borderColor: '#EF4444',
                    borderWidth: 1,
                    borderRadius: 6
                },
                {
                    label: 'EMI Share',
                    data: emiData,
                    type: 'line',
                    borderColor: '#F59E0B',
                    backgroundColor: '#F59E0B',
                    borderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94A3B8',
                        font: { size: 11, family: 'Inter' },
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderWidth: 1,
                    callbacks: {
                        label: (ctx) => ` ${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#94A3B8', font: { size: 11, family: 'Inter' } }
                },
                y: {
                    grid: { color: 'rgba(51, 65, 85, 0.4)' },
                    ticks: {
                        color: '#94A3B8',
                        font: { size: 11, family: 'Inter' },
                        callback: (val) => '₹' + (val >= 1000 ? (val / 1000).toFixed(0) + 'k' : val)
                    }
                }
            }
        }
    });
}
