/**
 * emi_calc.js - Interactive EMI & Amortization Schedule Calculator
 */

let emiPieChartInstance = null;

function calculateClientEMI(principal, annualRate, tenureMonths) {
    if (principal <= 0 || tenureMonths <= 0) return { emi: 0, totalInterest: 0, totalPayable: 0, schedule: [] };

    const monthlyRate = (annualRate / 100) / 12;
    let emi = 0;

    if (monthlyRate === 0) {
        emi = principal / tenureMonths;
    } else {
        const factor = Math.pow(1 + monthlyRate, tenureMonths);
        emi = (principal * monthlyRate * factor) / (factor - 1);
    }
    emi = Math.round(emi * 100) / 100;

    let remaining = principal;
    let totalInterest = 0;
    const schedule = [];

    for (let i = 1; i <= tenureMonths; i++) {
        const interest = Math.round((remaining * monthlyRate) * 100) / 100;
        totalInterest += interest;
        let principalComp = Math.round((emi - interest) * 100) / 100;

        let actualEmi = emi;
        if (i === tenureMonths || principalComp > remaining) {
            principalComp = Math.round(remaining * 100) / 100;
            actualEmi = Math.round((principalComp + interest) * 100) / 100;
            remaining = 0;
        } else {
            remaining = Math.round((remaining - principalComp) * 100) / 100;
        }

        schedule.push({
            month: i,
            emi: actualEmi,
            principal: principalComp,
            interest: interest,
            remaining: remaining
        });
    }

    return {
        emi,
        totalInterest: Math.round(totalInterest),
        totalPayable: Math.round(principal + totalInterest),
        schedule
    };
}

function updateCalculatorUI() {
    const principalInput = document.getElementById('calcPrincipal');
    const rateInput = document.getElementById('calcRate');
    const tenureInput = document.getElementById('calcTenure');

    if (!principalInput || !rateInput || !tenureInput) return;

    const principal = parseFloat(principalInput.value) || 0;
    const annualRate = parseFloat(rateInput.value) || 0;
    const tenureMonths = parseInt(tenureInput.value) || 1;

    const result = calculateClientEMI(principal, annualRate, tenureMonths);

    // Update Text displays
    const displayEmi = document.getElementById('calcEmiResult');
    const displayInterest = document.getElementById('calcInterestResult');
    const displayPayable = document.getElementById('calcPayableResult');

    if (displayEmi) displayEmi.textContent = formatCurrency(result.emi);
    if (displayInterest) displayInterest.textContent = formatCurrency(result.totalInterest);
    if (displayPayable) displayPayable.textContent = formatCurrency(result.totalPayable);

    // Update Donut Chart
    const ctx = document.getElementById('calcPieChart');
    if (ctx) {
        if (emiPieChartInstance) {
            emiPieChartInstance.destroy();
        }
        emiPieChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Principal Loan', 'Total Interest'],
                datasets: [{
                    data: [principal, result.totalInterest],
                    backgroundColor: ['#3B82F6', '#EF4444'],
                    borderColor: '#1E293B',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94A3B8', font: { size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: (c) => ` ${c.label}: ${formatCurrency(c.parsed)}`
                        }
                    }
                }
            }
        });
    }

    // Render Amortization Schedule Table preview (first 12 months or full)
    const tableBody = document.getElementById('calcScheduleBody');
    if (tableBody) {
        tableBody.innerHTML = result.schedule.map(row => `
            <tr class="border-b border-slate-800/60 hover:bg-slate-800/40 text-xs">
                <td class="py-2.5 px-4 text-slate-300 font-medium">Month ${row.month}</td>
                <td class="py-2.5 px-4 text-right font-semibold text-white">${formatCurrency(row.emi)}</td>
                <td class="py-2.5 px-4 text-right text-emerald-400 font-medium">${formatCurrency(row.principal)}</td>
                <td class="py-2.5 px-4 text-right text-rose-400 font-medium">${formatCurrency(row.interest)}</td>
                <td class="py-2.5 px-4 text-right text-slate-300">${formatCurrency(row.remaining)}</td>
            </tr>
        `).join('');
    }
}

// Attach listeners on load
document.addEventListener('DOMContentLoaded', () => {
    const inputs = ['calcPrincipal', 'calcRate', 'calcTenure'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', updateCalculatorUI);
        }
    });

    // Quick chip selectors
    document.querySelectorAll('.calc-chip-principal').forEach(btn => {
        btn.addEventListener('click', () => {
            const val = btn.getAttribute('data-val');
            const el = document.getElementById('calcPrincipal');
            if (el) {
                el.value = val;
                updateCalculatorUI();
            }
        });
    });

    document.querySelectorAll('.calc-chip-tenure').forEach(btn => {
        btn.addEventListener('click', () => {
            const val = btn.getAttribute('data-val');
            const el = document.getElementById('calcTenure');
            if (el) {
                el.value = val;
                updateCalculatorUI();
            }
        });
    });
});
