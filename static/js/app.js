/**
 * app.js - Main Application Controller for FinTrack
 * Handles Single-Page routing, state, API interactions, modals, and event bindings.
 */

// Application State
const state = {
    currentUser: null,
    accounts: [],
    categories: [],
    loans: [],
    transactions: [],
    dashboard: null,
    currentTab: 'dashboard',
    activeLoanForSchedule: null
};

// ---------------------------------------------------------
// INITIALIZATION & LIFECYCLE
// ---------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
    // Set default month in transaction filter to current month
    const today = new Date();
    const curMonthStr = today.toISOString().slice(0, 7);
    const monthFilter = document.getElementById('txFilterMonth');
    if (monthFilter) monthFilter.value = curMonthStr;

    // Initialize Lucide icons
    if (window.lucide) lucide.createIcons();

    // Setup Tab Navigation
    setupTabNavigation();

    // Setup Global Event Listeners & Auth Forms
    setupEventListeners();
    setupAuthListeners();

    // Check Authentication Status
    await checkAuth();
});

async function checkAuth() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        const overlay = document.getElementById('authOverlay');
        const headerUser = document.getElementById('headerUserSection');
        const headerSignIn = document.getElementById('headerSignInBtn');

        if (data.authenticated && data.user) {
            state.currentUser = data.user;
            if (overlay) {
                overlay.classList.add('hidden');
                overlay.classList.remove('flex');
            }
            if (headerUser) headerUser.classList.remove('hidden');
            if (headerSignIn) headerSignIn.classList.add('hidden');
            
            const nameEl = document.getElementById('userDisplayName');
            const avatarEl = document.getElementById('userAvatar');
            const displayName = data.user.full_name || data.user.username;
            if (nameEl) nameEl.textContent = displayName;
            if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();

            // Load this user's private data
            await loadInitialData();
        } else {
            state.currentUser = null;
            if (overlay) {
                overlay.classList.remove('hidden');
                overlay.classList.add('flex');
            }
            if (headerUser) headerUser.classList.add('hidden');
            if (headerSignIn) headerSignIn.classList.remove('hidden');
        }
    } catch (err) {
        console.error("Auth check error:", err);
    }
}

async function loadInitialData() {
    await Promise.all([
        fetchCategories(),
        fetchAccounts(),
        fetchDashboard()
    ]);
}

// ---------------------------------------------------------
// TAB ROUTING
// ---------------------------------------------------------

function setupTabNavigation() {
    const tabs = document.querySelectorAll('.nav-tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTab = tab.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });
}

function switchTab(tabId) {
    state.currentTab = tabId;

    // Update Tab Buttons UI
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        const isTarget = btn.getAttribute('data-tab') === tabId;
        if (isTarget) {
            btn.classList.add('bg-indigo-600', 'text-white', 'shadow-md');
            btn.classList.remove('text-slate-400', 'hover:bg-slate-800/80', 'hover:text-slate-200');
        } else {
            btn.classList.remove('bg-indigo-600', 'text-white', 'shadow-md');
            btn.classList.add('text-slate-400', 'hover:bg-slate-800/80', 'hover:text-slate-200');
        }
    });

    // Toggle Content Views
    document.querySelectorAll('.tab-view').forEach(view => {
        view.classList.add('hidden');
    });

    const targetView = document.getElementById(`tabView-${tabId}`);
    if (targetView) {
        targetView.classList.remove('hidden');
        targetView.classList.add('animate-fade-in');
    }

    // Refresh view specific data
    if (tabId === 'dashboard') {
        fetchDashboard();
    } else if (tabId === 'loans') {
        fetchLoans();
    } else if (tabId === 'accounts') {
        fetchAccounts();
    } else if (tabId === 'transactions') {
        fetchTransactions();
    } else if (tabId === 'calculator') {
        if (window.updateCalculatorUI) updateCalculatorUI();
    }

    if (window.lucide) lucide.createIcons();
}

// ---------------------------------------------------------
// API DATA FETCHERS
// ---------------------------------------------------------

async function fetchDashboard() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json();
        state.dashboard = data;

        // Render Summary Cards
        renderSummaryCards(data);

        // Render Car Loan Widget
        renderCarLoanWidget(data.car_loan_widget);

        // Render Upcoming EMI & CC Due Alerts
        renderUpcomingAlerts(data.upcoming_emis, data.cc_dues);

        // Render Charts
        if (window.renderCategoryChart) {
            renderCategoryChart(data.category_data);
        }
        if (window.renderSourceChart) {
            renderSourceChart(data.month_bank_spends, data.month_cc_spends, data.month_emi_outflow);
        }
        if (window.renderTrendChart) {
            renderTrendChart(data.months_trend);
        }

        // Render Dashboard Recent Transactions
        renderDashboardRecentTransactions(data.recent_transactions);

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Error fetching dashboard:", err);
    }
}

async function fetchAccounts() {
    try {
        const res = await fetch('/api/accounts');
        const accounts = await res.json();
        state.accounts = accounts;

        // Update select dropdowns across all modals
        updateAccountSelectDropdowns(accounts);

        // Render Accounts View if visible
        renderAccountsView(accounts);

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Error fetching accounts:", err);
    }
}

async function fetchCategories() {
    try {
        const res = await fetch('/api/categories');
        const cats = await res.json();
        state.categories = cats;

        // Populate Category Dropdowns
        const catSelect = document.getElementById('txCategory');
        const filterCatSelect = document.getElementById('txFilterCategory');

        const optionsHtml = cats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

        if (catSelect) catSelect.innerHTML = `<option value="">Select Category</option>` + optionsHtml;
        if (filterCatSelect) filterCatSelect.innerHTML = `<option value="">All Categories</option>` + optionsHtml;
    } catch (err) {
        console.error("Error fetching categories:", err);
    }
}

async function fetchLoans() {
    try {
        const res = await fetch('/api/loans');
        const loans = await res.json();
        state.loans = loans;

        renderLoansView(loans);

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Error fetching loans:", err);
    }
}

async function fetchTransactions() {
    try {
        const month = document.getElementById('txFilterMonth')?.value || '';
        const accId = document.getElementById('txFilterAccount')?.value || '';
        const catId = document.getElementById('txFilterCategory')?.value || '';
        const type = document.getElementById('txFilterType')?.value || '';
        const query = document.getElementById('txFilterSearch')?.value || '';

        const params = new URLSearchParams();
        if (month) params.append('month', month);
        if (accId) params.append('account_id', accId);
        if (catId) params.append('category_id', catId);
        if (type) params.append('type', type);
        if (query) params.append('q', query);

        const res = await fetch(`/api/transactions?${params.toString()}`);
        const txs = await res.json();
        state.transactions = txs;

        renderTransactionsTable(txs);

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Error fetching transactions:", err);
    }
}

// ---------------------------------------------------------
// UI RENDERERS: DASHBOARD
// ---------------------------------------------------------

function renderSummaryCards(d) {
    const elBank = document.getElementById('dashTotalBank');
    const elCC = document.getElementById('dashTotalCC');
    const elCCLimit = document.getElementById('dashCCLimitBar');
    const elCCLimitText = document.getElementById('dashCCLimitText');
    const elIncome = document.getElementById('dashMonthIncome');
    const elExpense = document.getElementById('dashMonthExpense');
    const elNet = document.getElementById('dashNetCashflow');
    const elEmi = document.getElementById('dashMonthEmi');

    if (elBank) elBank.textContent = formatCurrency(d.total_bank_balance);
    if (elCC) elCC.textContent = formatCurrency(d.total_cc_outstanding);
    if (elIncome) elIncome.textContent = formatCurrency(d.month_income);
    if (elExpense) elExpense.textContent = formatCurrency(d.month_expenses);
    if (elEmi) elEmi.textContent = formatCurrency(d.month_emi_outflow);

    if (elNet) {
        elNet.textContent = formatCurrency(d.net_cashflow);
        if (d.net_cashflow >= 0) {
            elNet.className = 'text-xl font-bold text-emerald-400';
        } else {
            elNet.className = 'text-xl font-bold text-rose-400';
        }
    }

    if (elCCLimit) {
        elCCLimit.style.width = `${Math.min(100, d.cc_utilization)}%`;
        if (d.cc_utilization > 50) {
            elCCLimit.className = 'h-full bg-rose-500 rounded-full transition-all duration-500';
        } else if (d.cc_utilization > 30) {
            elCCLimit.className = 'h-full bg-amber-500 rounded-full transition-all duration-500';
        } else {
            elCCLimit.className = 'h-full bg-indigo-500 rounded-full transition-all duration-500';
        }
    }

    if (elCCLimitText) {
        elCCLimitText.textContent = `${d.cc_utilization}% used of ${formatCurrency(d.total_cc_limit)} limit`;
    }
}

function renderCarLoanWidget(widget) {
    const container = document.getElementById('carLoanSpotlight');
    if (!container) return;

    if (!widget) {
        container.innerHTML = `
            <div class="p-6 rounded-2xl glass-card flex flex-col items-center justify-center text-center py-10">
                <div class="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                    <i data-lucide="car" class="w-6 h-6"></i>
                </div>
                <h3 class="text-base font-semibold text-white">No Car Loan Tracked Yet</h3>
                <p class="text-xs text-slate-400 max-w-sm mt-1 mb-4">Add your personal car loan to track monthly EMIs, vehicle payoff progress, and payment schedule.</p>
                <button onclick="openAddLoanModal('car_loan')" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition">
                    <i data-lucide="plus" class="w-4 h-4"></i> Add Car Loan
                </button>
            </div>
        `;
        return;
    }

    const { loan, total_installments, paid_installments, remaining_installments, principal_paid, remaining_principal, progress_pct, next_emi } = widget;

    container.innerHTML = `
        <div class="p-6 rounded-2xl glass-card relative overflow-hidden border border-slate-700/70 shadow-xl bg-gradient-to-br from-slate-900/95 to-slate-800/80">
            <!-- Header Badge & Car Info -->
            <div class="flex flex-wrap items-start justify-between gap-4">
                <div class="flex items-center gap-3.5">
                    <div class="w-12 h-12 rounded-xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 shadow-inner">
                        <i data-lucide="car" class="w-6 h-6"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="text-lg font-bold text-white tracking-tight">${loan.name}</h3>
                            <span class="px-2 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 rounded-full border border-emerald-500/30">Active Loan</span>
                        </div>
                        <p class="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                            <span>${loan.vehicle_details || 'Personal Car'}</span>
                            <span>•</span>
                            <span class="text-slate-300 font-medium">${loan.lender_bank || 'Bank'}</span>
                        </p>
                    </div>
                </div>

                <!-- Monthly EMI Amount Box -->
                <div class="bg-slate-800/90 border border-slate-700/60 rounded-xl px-4 py-2.5 text-right">
                    <div class="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Monthly EMI</div>
                    <div class="text-xl font-extrabold text-red-400">${formatCurrency(loan.emi_amount)}</div>
                </div>
            </div>

            <!-- Progress Bar & Metrics -->
            <div class="mt-5 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="text-slate-400 font-medium">Loan Repayment Progress</span>
                    <span class="text-indigo-400 font-bold">${progress_pct}% (${paid_installments} of ${total_installments} EMIs Paid)</span>
                </div>
                <div class="w-full h-3 bg-slate-800 rounded-full overflow-hidden p-0.5 border border-slate-700">
                    <div class="h-full bg-gradient-to-r from-red-500 via-indigo-500 to-emerald-500 rounded-full transition-all duration-700" style="width: ${progress_pct}%"></div>
                </div>
                <div class="flex justify-between text-[11px] text-slate-400 pt-0.5">
                    <span>Principal Paid: <strong class="text-emerald-400 font-medium">${formatCurrency(principal_paid)}</strong></span>
                    <span>Remaining Principal: <strong class="text-slate-200 font-medium">${formatCurrency(remaining_principal)}</strong></span>
                </div>
            </div>

            <!-- Next Due Alert / Action Bar -->
            <div class="mt-5 pt-4 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
                <div class="flex items-center gap-2 text-xs">
                    <div class="w-2 h-2 rounded-full ${next_emi ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}"></div>
                    <span class="text-slate-300">
                        ${next_emi ? `Next EMI Due: <strong class="text-white">${next_emi.due_date}</strong> (Inst #${next_emi.installment_no})` : 'All scheduled EMIs are fully settled!'}
                    </span>
                </div>

                <div class="flex items-center gap-2">
                    <button onclick="openAmortizationModal(${loan.id})" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition flex items-center gap-1.5">
                        <i data-lucide="table" class="w-3.5 h-3.5"></i> View Schedule
                    </button>
                    ${next_emi ? `
                        <button onclick="promptPayEMI(${loan.id}, ${next_emi.id}, ${next_emi.installment_no}, ${next_emi.emi_amount})" class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-semibold rounded-lg shadow transition flex items-center gap-1.5">
                            <i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i> Pay Next EMI
                        </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function renderUpcomingAlerts(emis, ccDues) {
    const emiContainer = document.getElementById('upcomingEmiList');
    const ccContainer = document.getElementById('upcomingCcDuesList');

    // Render Upcoming EMIs
    if (emiContainer) {
        if (!emis || emis.length === 0) {
            emiContainer.innerHTML = `<div class="p-4 text-center text-xs text-slate-400">No pending EMIs due in the next 35 days.</div>`;
        } else {
            emiContainer.innerHTML = emis.map(item => {
                const isOverdue = item.days_left < 0;
                const badgeClass = isOverdue ? 'bg-rose-500/20 text-rose-300 border-rose-500/30' :
                                   item.days_left <= 5 ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                                   'bg-slate-700/60 text-slate-300 border-slate-600';
                const dueText = isOverdue ? `${Math.abs(item.days_left)} days OVERDUE` :
                                item.days_left === 0 ? 'DUE TODAY' :
                                `In ${item.days_left} days (${item.due_date})`;

                return `
                    <div class="p-3 rounded-xl bg-slate-800/40 border border-slate-700/50 flex items-center justify-between gap-3 hover:border-slate-600 transition">
                        <div class="flex items-center gap-3">
                            <div class="w-9 h-9 rounded-lg ${item.loan_type === 'car_loan' ? 'bg-red-500/15 text-red-400' : 'bg-indigo-500/15 text-indigo-400'} flex items-center justify-center">
                                <i data-lucide="${item.loan_type === 'car_loan' ? 'car' : 'credit-card'}" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <h4 class="text-xs font-semibold text-white">${item.loan_name}</h4>
                                <p class="text-[10px] text-slate-400">Inst #${item.installment_no} • ${item.lender_bank || ''}</p>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-xs font-bold text-slate-200">${formatCurrency(item.emi_amount)}</div>
                            <span class="inline-block mt-0.5 px-1.5 py-0.5 text-[9px] font-semibold rounded border ${badgeClass}">
                                ${dueText}
                            </span>
                        </div>
                        <button onclick="promptPayEMI(${item.loan_id}, ${item.id}, ${item.installment_no}, ${item.emi_amount})" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium rounded-lg transition ml-1">
                            Pay
                        </button>
                    </div>
                `;
            }).join('');
        }
    }

    // Render Credit Card Bill Due Dates
    if (ccContainer) {
        if (!ccDues || ccDues.length === 0) {
            ccContainer.innerHTML = `<div class="p-4 text-center text-xs text-slate-400">No active credit cards found.</div>`;
        } else {
            ccContainer.innerHTML = ccDues.map(card => {
                const daysText = card.days_left <= 3 ? `Due in ${card.days_left} days!` : `Due in ${card.days_left} days`;
                return `
                    <div class="p-3 rounded-xl bg-slate-800/40 border border-slate-700/50 flex items-center justify-between gap-3 hover:border-slate-600 transition">
                        <div class="flex items-center gap-3">
                            <div class="w-9 h-9 rounded-lg bg-indigo-500/15 text-indigo-400 flex items-center justify-center">
                                <i data-lucide="credit-card" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <h4 class="text-xs font-semibold text-white">${card.name}</h4>
                                <p class="text-[10px] text-slate-400">Card ending ${card.last4 ? `•••• ${card.last4}` : ''}</p>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-xs font-bold text-indigo-300">${formatCurrency(card.outstanding)}</div>
                            <span class="inline-block mt-0.5 px-1.5 py-0.5 text-[9px] font-medium rounded bg-slate-700 text-slate-300">
                                ${card.due_date} (${daysText})
                            </span>
                        </div>
                        <button onclick="openPayCardModal(${card.account_id}, '${card.name}', ${card.outstanding})" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium rounded-lg transition ml-1">
                            Pay Bill
                        </button>
                    </div>
                `;
            }).join('');
        }
    }
}

function renderDashboardRecentTransactions(txs) {
    const tbody = document.getElementById('dashRecentTxBody');
    if (!tbody) return;

    if (!txs || txs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-xs text-slate-400">No transactions recorded yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = txs.map(tx => {
        const isExpense = tx.type === 'expense';
        const isIncome = tx.type === 'income';
        const isEmi = tx.type === 'emi_payment';
        const isCcPay = tx.type === 'cc_bill_payment';

        let amountColor = 'text-rose-400';
        let prefix = '-';
        if (isIncome) {
            amountColor = 'text-emerald-400';
            prefix = '+';
        } else if (isCcPay) {
            amountColor = 'text-blue-400';
            prefix = '⇄ ';
        }

        const sourceBadge = tx.account_type === 'credit_card'
            ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full badge-cc">
                 <i data-lucide="credit-card" class="w-3 h-3"></i> ${tx.account_name}
               </span>`
            : `<span class="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full badge-bank">
                 <i data-lucide="building-2" class="w-3 h-3"></i> ${tx.account_name}
               </span>`;

        return `
            <tr class="border-b border-slate-800/60 hover:bg-slate-800/30 text-xs transition">
                <td class="py-3 px-4 text-slate-400">${tx.date}</td>
                <td class="py-3 px-4 font-medium text-white">${tx.description}</td>
                <td class="py-3 px-4">
                    <span class="inline-block px-2 py-0.5 text-[10px] font-medium rounded-md bg-slate-800 text-slate-300 border border-slate-700">
                        ${tx.category_name || 'General'}
                    </span>
                </td>
                <td class="py-3 px-4">${sourceBadge}</td>
                <td class="py-3 px-4 text-right font-semibold ${amountColor}">
                    ${prefix}${formatCurrency(tx.amount)}
                </td>
            </tr>
        `;
    }).join('');
}

// ---------------------------------------------------------
// UI RENDERERS: ACCOUNTS & CARDS
// ---------------------------------------------------------

function renderAccountsView(accounts) {
    const ccContainer = document.getElementById('accountsCreditCardGrid');
    const bankContainer = document.getElementById('accountsBankGrid');

    const creditCards = accounts.filter(a => a.type === 'credit_card');
    const bankAccounts = accounts.filter(a => a.type in {'bank': 1, 'cash': 1});

    // Credit Cards Grid
    if (ccContainer) {
        if (creditCards.length === 0) {
            ccContainer.innerHTML = `<div class="col-span-full p-6 text-center text-xs text-slate-400 glass-card rounded-2xl">No Credit Cards added. Add your credit card to track spends and bill payments.</div>`;
        } else {
            ccContainer.innerHTML = creditCards.map(card => {
                const util = card.utilization_pct || 0;
                return `
                    <div class="credit-card-ui flex flex-col justify-between h-56 text-white shadow-2xl relative">
                        <!-- Top Bank & Chip -->
                        <div class="flex justify-between items-start">
                            <div>
                                <span class="text-[10px] uppercase tracking-widest text-indigo-200 font-semibold">Credit Card</span>
                                <h4 class="text-base font-bold tracking-tight">${card.name}</h4>
                            </div>
                            <div class="credit-card-chip shadow-sm"></div>
                        </div>

                        <!-- Card Number Mask -->
                        <div class="text-sm font-mono tracking-widest text-indigo-100/90 py-1">
                            •••• •••• •••• ${card.account_number_last4 || '0000'}
                        </div>

                        <!-- Balance & Limit Info -->
                        <div class="bg-black/30 backdrop-blur-sm rounded-xl p-3 border border-white/10 mt-auto">
                            <div class="flex justify-between items-end text-xs">
                                <div>
                                    <div class="text-[9px] uppercase text-indigo-200 tracking-wider">Total Outstanding</div>
                                    <div class="text-sm font-bold text-white">${formatCurrency(card.balance)}</div>
                                </div>
                                <div class="text-right">
                                    <div class="text-[9px] uppercase text-indigo-200 tracking-wider">Available Limit</div>
                                    <div class="text-sm font-semibold text-emerald-300">${formatCurrency(card.available_limit)}</div>
                                </div>
                            </div>
                            <div class="w-full bg-slate-800/80 h-1.5 rounded-full overflow-hidden mt-2">
                                <div class="h-full bg-indigo-400 rounded-full" style="width: ${Math.min(100, util)}%"></div>
                            </div>
                        </div>

                        <!-- Action Bar -->
                        <div class="flex justify-between items-center pt-2 text-[10px] text-indigo-200">
                            <span>Due Day: <strong>${card.payment_due_day}th</strong> of month</span>
                            <button onclick="openPayCardModal(${card.id}, '${card.name}', ${card.balance})" class="px-2.5 py-1 bg-white/20 hover:bg-white/30 text-white font-semibold rounded-lg backdrop-blur-md transition">
                                Pay Bill
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }

    // Bank Accounts Grid
    if (bankContainer) {
        if (bankAccounts.length === 0) {
            bankContainer.innerHTML = `<div class="col-span-full p-6 text-center text-xs text-slate-400 glass-card rounded-2xl">No bank accounts added.</div>`;
        } else {
            bankContainer.innerHTML = bankAccounts.map(acc => `
                <div class="p-5 rounded-2xl glass-card glass-card-hover border border-slate-700/60 flex flex-col justify-between">
                    <div class="flex items-start justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-sky-500/15 border border-sky-500/30 text-sky-400 flex items-center justify-center">
                                <i data-lucide="${acc.type === 'cash' ? 'wallet' : 'building-2'}" class="w-5 h-5"></i>
                            </div>
                            <div>
                                <h4 class="text-sm font-bold text-white">${acc.name}</h4>
                                <p class="text-[11px] text-slate-400 capitalize">${acc.type} A/c ${acc.account_number_last4 ? `••${acc.account_number_last4}` : ''}</p>
                            </div>
                        </div>
                    </div>

                    <div class="my-4">
                        <div class="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Available Balance</div>
                        <div class="text-2xl font-black text-white mt-0.5">${formatCurrency(acc.balance)}</div>
                    </div>

                    <div class="pt-3 border-t border-slate-800 flex justify-between items-center text-xs">
                        <button onclick="openAddExpenseModalWithAccount(${acc.id})" class="text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1 transition">
                            <i data-lucide="plus" class="w-3.5 h-3.5"></i> Log Expense
                        </button>
                        <button onclick="deleteAccount(${acc.id})" class="text-slate-500 hover:text-rose-400 transition" title="Delete Account">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        }
    }
}

// ---------------------------------------------------------
// UI RENDERERS: LOANS & EMIs
// ---------------------------------------------------------

function renderLoansView(loans) {
    const grid = document.getElementById('loansCardGrid');
    if (!grid) return;

    if (!loans || loans.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full p-12 text-center text-slate-400 glass-card rounded-2xl">
                <i data-lucide="car" class="w-12 h-12 mx-auto mb-3 opacity-30 stroke-1"></i>
                <h3 class="text-base font-semibold text-white">No Loans or EMIs Tracked</h3>
                <p class="text-xs text-slate-400 max-w-sm mx-auto mt-1 mb-4">Track your personal car loan, credit card EMIs, or home loans with amortization schedule.</p>
                <button onclick="openAddLoanModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg">
                    Add Your First Loan / EMI
                </button>
            </div>
        `;
        return;
    }

    grid.innerHTML = loans.map(loan => {
        const isCar = loan.type === 'car_loan';
        const isCc = loan.type === 'credit_card_emi';
        const iconName = isCar ? 'car' : (isCc ? 'credit-card' : 'landmark');
        const iconBg = isCar ? 'bg-red-500/15 text-red-400 border-red-500/30' :
                       isCc ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' :
                       'bg-indigo-500/15 text-indigo-400 border-indigo-500/30';

        const nextEmi = loan.next_emi;

        return `
            <div class="p-5 rounded-2xl glass-card glass-card-hover border border-slate-700/70 flex flex-col justify-between">
                <!-- Header -->
                <div class="flex items-start justify-between gap-3">
                    <div class="flex items-center gap-3">
                        <div class="w-11 h-11 rounded-xl ${iconBg} border flex items-center justify-center">
                            <i data-lucide="${iconName}" class="w-5 h-5"></i>
                        </div>
                        <div>
                            <span class="text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${isCar ? 'bg-red-500/20 text-red-300' : 'bg-indigo-500/20 text-indigo-300'}">
                                ${loan.type.replace('_', ' ')}
                            </span>
                            <h4 class="text-sm font-bold text-white mt-1">${loan.name}</h4>
                            <p class="text-[11px] text-slate-400">${loan.vehicle_details || loan.lender_bank || ''}</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-[9px] uppercase font-semibold text-slate-400">Monthly EMI</div>
                        <div class="text-base font-extrabold text-red-400">${formatCurrency(loan.emi_amount)}</div>
                    </div>
                </div>

                <!-- Metrics Grid -->
                <div class="grid grid-cols-2 gap-2 my-4 bg-slate-800/40 p-3 rounded-xl border border-slate-800 text-xs">
                    <div>
                        <span class="text-[10px] text-slate-400">Principal Loan</span>
                        <div class="font-semibold text-white">${formatCurrency(loan.principal_amount)}</div>
                    </div>
                    <div>
                        <span class="text-[10px] text-slate-400">Interest Rate</span>
                        <div class="font-semibold text-white">${loan.interest_rate}% p.a.</div>
                    </div>
                    <div>
                        <span class="text-[10px] text-slate-400">Principal Paid</span>
                        <div class="font-semibold text-emerald-400">${formatCurrency(loan.principal_paid)}</div>
                    </div>
                    <div>
                        <span class="text-[10px] text-slate-400">Remaining Principal</span>
                        <div class="font-semibold text-rose-300">${formatCurrency(loan.remaining_principal)}</div>
                    </div>
                </div>

                <!-- Progress Bar -->
                <div class="space-y-1.5 mb-4">
                    <div class="flex justify-between text-[11px]">
                        <span class="text-slate-400">Paid: ${loan.paid_installments} of ${loan.total_installments} EMIs</span>
                        <span class="text-indigo-400 font-bold">${loan.progress_pct}%</span>
                    </div>
                    <div class="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div class="h-full bg-gradient-to-r from-red-500 to-indigo-500 rounded-full transition-all duration-500" style="width: ${loan.progress_pct}%"></div>
                    </div>
                </div>

                <!-- Action Footer -->
                <div class="pt-3 border-t border-slate-800 flex justify-between items-center text-xs">
                    <button onclick="openAmortizationModal(${loan.id})" class="text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1 transition">
                        <i data-lucide="calendar" class="w-3.5 h-3.5"></i> Amortization Schedule
                    </button>
                    ${nextEmi ? `
                        <button onclick="promptPayEMI(${loan.id}, ${nextEmi.id}, ${nextEmi.installment_no}, ${nextEmi.emi_amount})" class="px-2.5 py-1 bg-red-600 hover:bg-red-500 text-white text-[11px] font-semibold rounded-lg shadow transition">
                            Pay EMI #${nextEmi.installment_no}
                        </button>
                    ` : '<span class="text-[11px] text-emerald-400 font-semibold">Fully Settled</span>'}
                </div>
            </div>
        `;
    }).join('');
}

// ---------------------------------------------------------
// UI RENDERERS: TRANSACTIONS
// ---------------------------------------------------------

function renderTransactionsTable(txs) {
    const tbody = document.getElementById('txTableBody');
    const countBadge = document.getElementById('txCountBadge');
    if (!tbody) return;

    if (countBadge) countBadge.textContent = `${txs.length} transactions found`;

    if (!txs || txs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-12 text-center text-xs text-slate-400">No transactions match your search filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = txs.map(tx => {
        const isExpense = tx.type === 'expense';
        const isIncome = tx.type === 'income';
        const isEmi = tx.type === 'emi_payment';
        const isCcPay = tx.type === 'cc_bill_payment';

        let amountColor = 'text-rose-400';
        let prefix = '-';
        if (isIncome) {
            amountColor = 'text-emerald-400';
            prefix = '+';
        } else if (isCcPay) {
            amountColor = 'text-blue-400';
            prefix = '⇄ ';
        }

        const sourceBadge = tx.account_type === 'credit_card'
            ? `<span class="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-full badge-cc">
                 <i data-lucide="credit-card" class="w-3 h-3"></i> ${tx.account_name}
               </span>`
            : `<span class="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-full badge-bank">
                 <i data-lucide="building-2" class="w-3 h-3"></i> ${tx.account_name}
               </span>`;

        return `
            <tr class="border-b border-slate-800/60 hover:bg-slate-800/40 text-xs transition">
                <td class="py-3 px-4 text-slate-400 whitespace-nowrap">${tx.date}</td>
                <td class="py-3 px-4">
                    <div class="font-semibold text-white">${tx.description}</div>
                    ${tx.notes ? `<div class="text-[10px] text-slate-400">${tx.notes}</div>` : ''}
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                    <span class="inline-block px-2.5 py-0.5 text-[10px] font-medium rounded-md bg-slate-800 text-slate-300 border border-slate-700">
                        ${tx.category_name || 'General'}
                    </span>
                </td>
                <td class="py-3 px-4 whitespace-nowrap">${sourceBadge}</td>
                <td class="py-3 px-4 text-right font-bold ${amountColor} whitespace-nowrap">
                    ${prefix}${formatCurrency(tx.amount)}
                </td>
                <td class="py-3 px-4 text-center whitespace-nowrap">
                    <button onclick="deleteTransaction(${tx.id})" class="text-slate-500 hover:text-rose-400 transition" title="Delete transaction">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// ---------------------------------------------------------
// MODAL CONTROLLERS & ACTIONS
// ---------------------------------------------------------

function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('hidden');
        el.classList.add('flex');
        if (window.lucide) lucide.createIcons();
    }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
    }
}

function updateAccountSelectDropdowns(accounts) {
    const selects = [
        document.getElementById('txAccount'),
        document.getElementById('txFilterAccount'),
        document.getElementById('loanLinkedAccount'),
        document.getElementById('payCardBankSelect'),
        document.getElementById('payEmiBankSelect')
    ];

    const bankOptions = accounts.filter(a => a.type in {'bank': 1, 'cash': 1})
        .map(a => `<option value="${a.id}">🏦 ${a.name} (Bal: ${formatCurrency(a.balance)})</option>`).join('');

    const ccOptions = accounts.filter(a => a.type === 'credit_card')
        .map(a => `<option value="${a.id}">💳 ${a.name} (Due: ${formatCurrency(a.balance)})</option>`).join('');

    selects.forEach(sel => {
        if (!sel) return;
        const currentVal = sel.value;
        if (sel.id === 'txAccount') {
            sel.innerHTML = `
                <optgroup label="Bank Accounts & Cash">${bankOptions}</optgroup>
                <optgroup label="Credit Cards">${ccOptions}</optgroup>
            `;
        } else if (sel.id === 'payCardBankSelect' || sel.id === 'payEmiBankSelect' || sel.id === 'loanLinkedAccount') {
            sel.innerHTML = bankOptions;
        } else if (sel.id === 'txFilterAccount') {
            sel.innerHTML = `<option value="">All Accounts & Cards</option>` +
                `<optgroup label="Bank Accounts">${bankOptions}</optgroup>` +
                `<optgroup label="Credit Cards">${ccOptions}</optgroup>`;
        }
        if (currentVal) sel.value = currentVal;
    });
}

// Open Add Expense modal and set default account
function openAddExpenseModalWithAccount(accId) {
    openModal('modalAddExpense');
    const sel = document.getElementById('txAccount');
    if (sel && accId) sel.value = accId;
}

// Open Add Loan modal
function openAddLoanModal(type = 'car_loan') {
    openModal('modalAddLoan');
    const typeSelect = document.getElementById('loanType');
    if (typeSelect) {
        typeSelect.value = type;
        toggleVehicleFields(type);
    }
}

function toggleVehicleFields(loanType) {
    const vehGroup = document.getElementById('vehicleDetailsGroup');
    if (vehGroup) {
        if (loanType === 'car_loan') {
            vehGroup.classList.remove('hidden');
        } else {
            vehGroup.classList.add('hidden');
        }
    }
}

// Pay Credit Card Modal
function openPayCardModal(cardId, cardName, outstanding) {
    openModal('modalPayCard');
    document.getElementById('payCardId').value = cardId;
    document.getElementById('payCardName').textContent = cardName;
    document.getElementById('payCardOutstanding').textContent = formatCurrency(outstanding);
    document.getElementById('payCardAmount').value = outstanding;
}

// Pay EMI Modal
function promptPayEMI(loanId, scheduleId, installmentNo, amount) {
    openModal('modalPayEmi');
    document.getElementById('payEmiLoanId').value = loanId;
    document.getElementById('payEmiScheduleId').value = scheduleId;
    document.getElementById('payEmiInstNo').textContent = `Installment #${installmentNo}`;
    document.getElementById('payEmiAmount').textContent = formatCurrency(amount);
}

// View Amortization Schedule Modal
async function openAmortizationModal(loanId) {
    openModal('modalAmortization');
    const container = document.getElementById('amortizationTableBody');
    const title = document.getElementById('amortizationLoanTitle');
    container.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-xs text-slate-400">Loading schedule...</td></tr>`;

    try {
        const res = await fetch(`/api/loans/${loanId}`);
        const loan = await res.json();
        title.textContent = `${loan.name} • Amortization Schedule`;

        container.innerHTML = loan.schedule.map(row => {
            const isPaid = row.status === 'paid';
            return `
                <tr class="border-b border-slate-800/60 hover:bg-slate-800/30 text-xs">
                    <td class="py-2.5 px-4 font-semibold text-white">#${row.installment_no}</td>
                    <td class="py-2.5 px-4 text-slate-400">${row.due_date}</td>
                    <td class="py-2.5 px-4 text-right font-bold text-white">${formatCurrency(row.emi_amount)}</td>
                    <td class="py-2.5 px-4 text-right text-emerald-400">${formatCurrency(row.principal_component)}</td>
                    <td class="py-2.5 px-4 text-right text-rose-400">${formatCurrency(row.interest_component)}</td>
                    <td class="py-2.5 px-4 text-right text-slate-300">${formatCurrency(row.remaining_principal)}</td>
                    <td class="py-2.5 px-4 text-center">
                        ${isPaid ? `
                            <span class="px-2 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30">
                                Paid ${row.paid_date ? `(${row.paid_date})` : ''}
                            </span>
                        ` : `
                            <button onclick="closeModal('modalAmortization'); promptPayEMI(${loan.id}, ${row.id}, ${row.installment_no}, ${row.emi_amount})" class="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-semibold rounded">
                                Pay Now
                            </button>
                        `}
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        console.error("Error loading amortization schedule:", err);
    }
}

// ---------------------------------------------------------
// FORM SUBMISSIONS
// ---------------------------------------------------------

function setupEventListeners() {
    // 1. Add Transaction Form
    const formAddTx = document.getElementById('formAddTransaction');
    if (formAddTx) {
        formAddTx.addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                type: document.getElementById('txType').value,
                amount: parseFloat(document.getElementById('txAmount').value),
                account_id: parseInt(document.getElementById('txAccount').value),
                category_id: document.getElementById('txCategory').value ? parseInt(document.getElementById('txCategory').value) : null,
                date: document.getElementById('txDate').value || new Date().toISOString().slice(0, 10),
                description: document.getElementById('txDescription').value.trim(),
                tags: document.getElementById('txTags').value.trim(),
                notes: document.getElementById('txNotes').value.trim()
            };

            const res = await fetch('/api/transactions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (res.ok) {
                closeModal('modalAddExpense');
                formAddTx.reset();
                showToast("Transaction logged successfully!");
                await loadInitialData();
                if (state.currentTab === 'transactions') fetchTransactions();
            } else {
                const err = await res.json();
                showToast(err.error || "Failed to log transaction", "error");
            }
        });
    }

    // 2. Add Loan Form
    const formAddLoan = document.getElementById('formAddLoan');
    if (formAddLoan) {
        formAddLoan.addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                name: document.getElementById('loanName').value.trim(),
                type: document.getElementById('loanType').value,
                vehicle_details: document.getElementById('loanVehicleDetails').value.trim(),
                lender_bank: document.getElementById('loanLender').value.trim(),
                principal_amount: parseFloat(document.getElementById('loanPrincipal').value),
                interest_rate: parseFloat(document.getElementById('loanRate').value),
                tenure_months: parseInt(document.getElementById('loanTenure').value),
                start_date: document.getElementById('loanStartDate').value || new Date().toISOString().slice(0, 10),
                emi_day_of_month: parseInt(document.getElementById('loanEmiDay').value) || 5,
                linked_account_id: document.getElementById('loanLinkedAccount').value ? parseInt(document.getElementById('loanLinkedAccount').value) : null,
                notes: document.getElementById('loanNotes').value.trim()
            };

            const res = await fetch('/api/loans', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (res.ok) {
                const data = await res.json();
                closeModal('modalAddLoan');
                formAddLoan.reset();
                showToast(`Loan added! Monthly EMI: ${formatCurrency(data.emi_amount)}`);
                await loadInitialData();
                if (state.currentTab === 'loans') fetchLoans();
            } else {
                const err = await res.json();
                showToast(err.error || "Failed to create loan", "error");
            }
        });
    }

    // 3. Add Account Form
    const formAddAccount = document.getElementById('formAddAccount');
    if (formAddAccount) {
        formAddAccount.addEventListener('submit', async (e) => {
            e.preventDefault();
            const accType = document.getElementById('newAccType').value;
            const body = {
                name: document.getElementById('newAccName').value.trim(),
                type: accType,
                account_number_last4: document.getElementById('newAccLast4').value.trim(),
                balance: parseFloat(document.getElementById('newAccBalance').value) || 0,
                credit_limit: parseFloat(document.getElementById('newAccLimit').value) || 0,
                payment_due_day: parseInt(document.getElementById('newAccDueDay').value) || 20
            };

            const res = await fetch('/api/accounts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (res.ok) {
                closeModal('modalAddAccount');
                formAddAccount.reset();
                showToast("Account created successfully!");
                await loadInitialData();
                if (state.currentTab === 'accounts') fetchAccounts();
            } else {
                const err = await res.json();
                showToast(err.error || "Failed to add account", "error");
            }
        });
    }

    // 4. Pay Credit Card Bill Form
    const formPayCard = document.getElementById('formPayCard');
    if (formPayCard) {
        formPayCard.addEventListener('submit', async (e) => {
            e.preventDefault();
            const cardId = document.getElementById('payCardId').value;
            const body = {
                bank_account_id: parseInt(document.getElementById('payCardBankSelect').value),
                amount: parseFloat(document.getElementById('payCardAmount').value),
                payment_date: document.getElementById('payCardDate').value || new Date().toISOString().slice(0, 10),
                notes: document.getElementById('payCardNotes').value.trim()
            };

            const res = await fetch(`/api/accounts/${cardId}/pay-bill`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (res.ok) {
                closeModal('modalPayCard');
                showToast("Credit Card bill payment recorded!");
                await loadInitialData();
                if (state.currentTab === 'accounts') fetchAccounts();
                if (state.currentTab === 'transactions') fetchTransactions();
            } else {
                const err = await res.json();
                showToast(err.error || "Payment failed", "error");
            }
        });
    }

    // 5. Pay EMI Confirmation Form
    const formPayEmi = document.getElementById('formPayEmi');
    if (formPayEmi) {
        formPayEmi.addEventListener('submit', async (e) => {
            e.preventDefault();
            const loanId = document.getElementById('payEmiLoanId').value;
            const body = {
                emi_schedule_id: parseInt(document.getElementById('payEmiScheduleId').value),
                bank_account_id: parseInt(document.getElementById('payEmiBankSelect').value),
                payment_date: document.getElementById('payEmiDate').value || new Date().toISOString().slice(0, 10)
            };

            const res = await fetch(`/api/loans/${loanId}/pay-emi`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (res.ok) {
                closeModal('modalPayEmi');
                showToast("Loan EMI payment recorded and bank debited!");
                await loadInitialData();
                if (state.currentTab === 'loans') fetchLoans();
                if (state.currentTab === 'transactions') fetchTransactions();
            } else {
                const err = await res.json();
                showToast(err.error || "EMI Payment failed", "error");
            }
        });
    }

    // Dynamic UI toggles inside Add Account modal
    const accTypeSelect = document.getElementById('newAccType');
    if (accTypeSelect) {
        accTypeSelect.addEventListener('change', () => {
            const isCC = accTypeSelect.value === 'credit_card';
            const ccGroup = document.getElementById('newAccCreditCardFields');
            const balLabel = document.getElementById('newAccBalanceLabel');
            if (ccGroup) ccGroup.classList.toggle('hidden', !isCC);
            if (balLabel) balLabel.textContent = isCC ? 'Current Outstanding Balance (₹)' : 'Opening Balance (₹)';
        });
    }

    // Dynamic UI toggles inside Add Loan modal
    const loanTypeSelect = document.getElementById('loanType');
    if (loanTypeSelect) {
        loanTypeSelect.addEventListener('change', () => {
            toggleVehicleFields(loanTypeSelect.value);
        });
    }

    // Filter bar bindings in Transactions tab
    ['txFilterMonth', 'txFilterAccount', 'txFilterCategory', 'txFilterType'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', fetchTransactions);
    });

    const searchInput = document.getElementById('txFilterSearch');
    if (searchInput) {
        let debounceTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(fetchTransactions, 300);
        });
    }
}

// Delete Account
async function deleteAccount(accId) {
    if (!confirm("Are you sure you want to delete this account?")) return;
    const res = await fetch(`/api/accounts/${accId}`, { method: 'DELETE' });
    if (res.ok) {
        showToast("Account deleted");
        await loadInitialData();
        if (state.currentTab === 'accounts') fetchAccounts();
    }
}

// Delete Transaction
async function deleteTransaction(txId) {
    if (!confirm("Delete this transaction? Balances will be automatically reversed.")) return;
    const res = await fetch(`/api/transactions/${txId}`, { method: 'DELETE' });
    if (res.ok) {
        showToast("Transaction deleted");
        await loadInitialData();
        if (state.currentTab === 'transactions') fetchTransactions();
    }
}

// Seed Demo Data Action
async function seedDemoData() {
    if (!confirm("This will load realistic sample data for your Car Loan, Credit Cards, and Expenses. Continue?")) return;
    try {
        const res = await fetch('/api/seed', { method: 'POST' });
        if (res.ok) {
            showToast("Realistic demo data successfully loaded!");
            await loadInitialData();
            switchTab('dashboard');
        } else {
            showToast("Failed to load demo data", "error");
        }
    } catch (err) {
        console.error(err);
    }
}

// Toast Notification
function showToast(msg, type = 'success') {
    const toast = document.getElementById('appToast');
    const toastMsg = document.getElementById('appToastMsg');
    if (!toast || !toastMsg) return;

    toastMsg.textContent = msg;
    toast.className = `fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl text-xs font-semibold border ${
        type === 'success' ? 'bg-emerald-950/90 text-emerald-200 border-emerald-500/40' : 'bg-rose-950/90 text-rose-200 border-rose-500/40'
    } animate-fade-in`;

    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 4000);
}

// ---------------------------------------------------------
// AUTHENTICATION CONTROLLER
// ---------------------------------------------------------

function switchAuthMode(mode) {
    const isSignIn = mode === 'signin';
    const formSignIn = document.getElementById('formSignIn');
    const formSignUp = document.getElementById('formSignUp');
    const btnSignIn = document.getElementById('tabBtnSignIn');
    const btnSignUp = document.getElementById('tabBtnSignUp');
    const errBanner = document.getElementById('authErrorBanner');

    if (errBanner) errBanner.classList.add('hidden');

    if (isSignIn) {
        if (formSignIn) formSignIn.classList.remove('hidden');
        if (formSignUp) formSignUp.classList.add('hidden');
        if (btnSignIn) {
            btnSignIn.className = 'py-2 rounded-lg bg-indigo-600 text-white shadow-md transition';
        }
        if (btnSignUp) {
            btnSignUp.className = 'py-2 rounded-lg text-slate-400 hover:text-slate-200 transition';
        }
    } else {
        if (formSignIn) formSignIn.classList.add('hidden');
        if (formSignUp) formSignUp.classList.remove('hidden');
        if (btnSignIn) {
            btnSignIn.className = 'py-2 rounded-lg text-slate-400 hover:text-slate-200 transition';
        }
        if (btnSignUp) {
            btnSignUp.className = 'py-2 rounded-lg bg-emerald-600 text-white shadow-md transition';
        }
    }

    if (window.lucide) lucide.createIcons();
}

function fillDemoLogin() {
    const u = document.getElementById('loginUsername');
    const p = document.getElementById('loginPassword');
    if (u) u.value = 'admin';
    if (p) p.value = 'admin123';
}

function showAuthError(msg) {
    const errBanner = document.getElementById('authErrorBanner');
    const errMsg = document.getElementById('authErrorMsg');
    if (errBanner && errMsg) {
        errMsg.textContent = msg;
        errBanner.classList.remove('hidden');
    }
}

function setupAuthListeners() {
    // 1. Sign In Form
    const formIn = document.getElementById('formSignIn');
    if (formIn) {
        formIn.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                const data = await res.json();
                if (res.ok && data.user) {
                    state.currentUser = data.user;
                    document.getElementById('authOverlay').classList.add('hidden');
                    document.getElementById('headerUserSection').classList.remove('hidden');
                    
                    const nameEl = document.getElementById('userDisplayName');
                    const avatarEl = document.getElementById('userAvatar');
                    const displayName = data.user.full_name || data.user.username;
                    if (nameEl) nameEl.textContent = displayName;
                    if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();

                    showToast(`Welcome back, ${displayName}!`);
                    await loadInitialData();
                    switchTab('dashboard');
                } else {
                    showAuthError(data.error || "Login failed. Check your User ID and password.");
                }
            } catch (err) {
                showAuthError("Server connection error. Please try again.");
            }
        });
    }

    // 2. Sign Up Form
    const formUp = document.getElementById('formSignUp');
    if (formUp) {
        formUp.addEventListener('submit', async (e) => {
            e.preventDefault();
            const full_name = document.getElementById('regFullName').value.trim();
            const username = document.getElementById('regUsername').value.trim();
            const password = document.getElementById('regPassword').value;
            const email = document.getElementById('regEmail').value.trim();

            try {
                const res = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ full_name, username, password, email })
                });

                const data = await res.json();
                if (res.ok && data.user) {
                    state.currentUser = data.user;
                    document.getElementById('authOverlay').classList.add('hidden');
                    document.getElementById('headerUserSection').classList.remove('hidden');

                    const nameEl = document.getElementById('userDisplayName');
                    const avatarEl = document.getElementById('userAvatar');
                    const displayName = data.user.full_name || data.user.username;
                    if (nameEl) nameEl.textContent = displayName;
                    if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();

                    showToast(`Account created! Welcome, ${displayName}.`);
                    await loadInitialData();
                    switchTab('dashboard');
                } else {
                    showAuthError(data.error || "Registration failed.");
                }
            } catch (err) {
                showAuthError("Server connection error. Please try again.");
            }
        });
    }
}

function showAuthOverlay() {
    const overlay = document.getElementById('authOverlay');
    if (overlay) {
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
    }
}

async function handleLogout() {
    if (!confirm("Are you sure you want to sign out?")) return;
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        state.currentUser = null;
        showAuthOverlay();
        const headerUser = document.getElementById('headerUserSection');
        const headerSignIn = document.getElementById('headerSignInBtn');
        if (headerUser) headerUser.classList.add('hidden');
        if (headerSignIn) headerSignIn.classList.remove('hidden');
        showToast("Signed out successfully.");
    } catch (err) {
        console.error("Logout error:", err);
    }
}
