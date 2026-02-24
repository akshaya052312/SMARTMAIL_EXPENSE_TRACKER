// ========== SmartMail Expense Tracker — India Edition ==========
// Core JavaScript utilities

// ========== Indian Currency Formatting ==========
function formatINR(amount) {
    if (amount === null || amount === undefined) return '₹0';
    amount = parseFloat(amount);
    if (isNaN(amount)) return '₹0';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

function formatINRFull(amount) {
    if (amount === null || amount === undefined) return '₹0.00';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(parseFloat(amount));
}

function formatCompact(amount) {
    amount = parseFloat(amount) || 0;
    if (amount >= 10000000) return '₹' + (amount / 10000000).toFixed(1) + ' Cr';
    if (amount >= 100000) return '₹' + (amount / 100000).toFixed(1) + ' L';
    if (amount >= 1000) return '₹' + (amount / 1000).toFixed(1) + 'K';
    return formatINR(amount);
}

// ========== Indian Date Formatting (DD/MM/YYYY) ==========
function formatDateIndian(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
}

function formatDateTimeIndian(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${dd}/${mm}/${yyyy} ${hh}:${min}`;
}

// ========== Indian Financial Year ==========
function getCurrentFY() {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    // FY starts April (month index 3)
    if (month >= 3) {
        return { start: `${year}-04-01`, end: `${year + 1}-03-31`, label: `FY ${year}-${year + 1}` };
    } else {
        return { start: `${year - 1}-04-01`, end: `${year}-03-31`, label: `FY ${year - 1}-${year}` };
    }
}

// ========== Auth Helpers ==========
async function checkAuth() {
    try {
        const res = await fetch('/api/user');
        const data = await res.json();
        if (!data.success) {
            window.location.href = '/login';
            return null;
        }
        return data.user;
    } catch (e) {
        window.location.href = '/login';
        return null;
    }
}

async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (e) {}
    window.location.href = '/login';
}

// ========== API Helpers ==========
async function apiGet(url) {
    const res = await fetch(url);
    return res.json();
}

async function apiPost(url, body) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    return res.json();
}

async function apiDelete(url) {
    const res = await fetch(url, { method: 'DELETE' });
    return res.json();
}

// ========== Toast Notification ==========
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
        padding: 12px 24px; border-radius: 12px; font-size: 0.85rem; font-weight: 500;
        color: white; z-index: 10000; opacity: 0; transition: opacity 0.3s;
        font-family: 'Inter', sans-serif;
    `;
    const colors = { success: '#059669', error: '#dc2626', info: '#4F46E5', warning: '#f59e0b' };
    toast.style.background = colors[type] || colors.info;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; });
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== Category Icons ==========
const categoryIcons = {
    'Food Delivery': '🍕',
    'Groceries': '🛒',
    'Online Shopping': '🛍️',
    'Travel & Transport': '🚗',
    'Entertainment': '🎬',
    'Utilities & Bills': '💡',
    'Healthcare': '🏥',
    'Education': '📚',
    'EMI & Loans': '🏦',
    'Investments': '📈',
    'Other': '📦'
};

function getCategoryIcon(category) {
    return categoryIcons[category] || '📦';
}

console.log('SmartMail Expense Tracker — India Edition 🇮🇳');