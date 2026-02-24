/* ==========================================================
   NexusBoard — Dashboard JavaScript
   ========================================================== */

document.addEventListener('DOMContentLoaded', () => {

    // ── Intersection Observer for scroll animations ──
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );

    document.querySelectorAll('[data-animate]').forEach(el => observer.observe(el));

    // ── Sidebar Toggle ──
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const hamburger = document.getElementById('hamburgerMenu');
    const overlay = document.getElementById('overlay');

    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    hamburger.addEventListener('click', () => {
        sidebar.classList.add('mobile-open');
        overlay.classList.add('active');
    });

    overlay.addEventListener('click', () => {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
        document.getElementById('notifPanel').classList.remove('open');
    });

    // ── Sidebar Nav Active State ──
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            // Close mobile sidebar
            sidebar.classList.remove('mobile-open');
            overlay.classList.remove('active');
        });
    });

    // ── Profile Dropdown ──
    const profileSection = document.getElementById('profileSection');
    profileSection.addEventListener('click', (e) => {
        e.stopPropagation();
        profileSection.classList.toggle('open');
    });

    document.addEventListener('click', () => {
        profileSection.classList.remove('open');
    });

    // ── Notification Panel ──
    const notifBtn = document.getElementById('notifBtn');
    const notifPanel = document.getElementById('notifPanel');

    notifBtn.addEventListener('click', () => {
        notifPanel.classList.toggle('open');
        overlay.classList.toggle('active');
    });

    document.getElementById('markAllRead').addEventListener('click', () => {
        document.querySelectorAll('.notif-item.unread').forEach(el => {
            el.classList.remove('unread');
        });
    });

    // ── Populate Notifications ──
    const notifications = [
        { icon: 'fas fa-chart-line', type: 'info', title: 'Revenue Milestone', desc: 'Monthly revenue exceeded $80K target by 5.3%', time: '2 min ago', unread: true },
        { icon: 'fas fa-user-plus', type: 'success', title: 'New Enterprise Client', desc: 'TechCorp signed a $12K annual plan', time: '15 min ago', unread: true },
        { icon: 'fas fa-exclamation-triangle', type: 'warning', title: 'Server Load Alert', desc: 'CPU utilization reached 87% on us-east-1', time: '1 hour ago', unread: true },
        { icon: 'fas fa-check-circle', type: 'success', title: 'Deployment Complete', desc: 'v2.4.1 deployed to production successfully', time: '3 hours ago', unread: false },
        { icon: 'fas fa-bell', type: 'info', title: 'Scheduled Maintenance', desc: 'Database maintenance window tonight at 2 AM UTC', time: '5 hours ago', unread: false },
    ];

    const notifList = document.getElementById('notifList');
    notifList.innerHTML = notifications.map(n => `
        <div class="notif-item ${n.unread ? 'unread' : ''}">
            <div class="notif-icon ${n.type}"><i class="${n.icon}"></i></div>
            <div class="notif-content">
                <div class="notif-title">${n.title}</div>
                <div class="notif-desc">${n.desc}</div>
                <div class="notif-time">${n.time}</div>
            </div>
        </div>
    `).join('');

    // ── KPI Counter Animation ──
    function animateCounters() {
        document.querySelectorAll('.kpi-value[data-count]').forEach(el => {
            const target = parseFloat(el.dataset.count);
            const isDecimal = el.dataset.decimal === 'true';
            const suffix = el.dataset.suffix || '';
            const prefix = el.textContent.startsWith('$') ? '$' : '';
            const duration = 2000;
            const start = performance.now();

            function update(now) {
                const elapsed = now - start;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 4); // ease-out quart
                const current = eased * target;

                if (isDecimal) {
                    el.textContent = prefix + current.toFixed(1) + suffix;
                } else {
                    el.textContent = prefix + Math.floor(current).toLocaleString() + suffix;
                }

                if (progress < 1) requestAnimationFrame(update);
            }

            requestAnimationFrame(update);
        });
    }

    // Delay counter start for visual effect
    setTimeout(animateCounters, 600);

    // ── Revenue Chart ──
    const revenueCtx = document.getElementById('revenueChart').getContext('2d');

    const revenueGradient = revenueCtx.createLinearGradient(0, 0, 0, 280);
    revenueGradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    revenueGradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    const revenueGradient2 = revenueCtx.createLinearGradient(0, 0, 0, 280);
    revenueGradient2.addColorStop(0, 'rgba(139, 92, 246, 0.2)');
    revenueGradient2.addColorStop(1, 'rgba(139, 92, 246, 0)');

    new Chart(revenueCtx, {
        type: 'line',
        data: {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            datasets: [
                {
                    label: 'Revenue',
                    data: [42000, 48000, 45000, 52000, 58000, 56000, 62000, 68000, 64000, 72000, 78000, 84254],
                    borderColor: '#6366f1',
                    backgroundColor: revenueGradient,
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2.5,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#6366f1',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2,
                },
                {
                    label: 'Expenses',
                    data: [28000, 32000, 30000, 35000, 38000, 36000, 40000, 42000, 39000, 44000, 47000, 52000],
                    borderColor: '#8b5cf6',
                    backgroundColor: revenueGradient2,
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#8b5cf6',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2,
                    borderDash: [5, 5],
                }
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
                    ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } },
                    border: { display: false },
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
                    ticks: {
                        color: '#64748b',
                        font: { family: 'Inter', size: 11 },
                        callback: v => '$' + (v / 1000) + 'K',
                    },
                    border: { display: false },
                    beginAtZero: true,
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 45, 0.95)',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: true,
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y.toLocaleString()}`,
                    },
                },
            },
        },
    });

    // ── Traffic Doughnut Chart ──
    const trafficCtx = document.getElementById('trafficChart').getContext('2d');
    const trafficData = [
        { label: 'Direct', value: 35, color: '#6366f1' },
        { label: 'Organic', value: 28, color: '#8b5cf6' },
        { label: 'Referral', value: 20, color: '#ec4899' },
        { label: 'Social', value: 17, color: '#14b8a6' },
    ];

    new Chart(trafficCtx, {
        type: 'doughnut',
        data: {
            labels: trafficData.map(d => d.label),
            datasets: [{
                data: trafficData.map(d => d.value),
                backgroundColor: trafficData.map(d => d.color),
                borderColor: 'transparent',
                borderWidth: 0,
                spacing: 3,
                borderRadius: 5,
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 45, 0.95)',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: ctx => `${ctx.label}: ${ctx.parsed}%`,
                    },
                },
            },
        },
    });

    // Custom Legend
    const legendEl = document.getElementById('trafficLegend');
    legendEl.innerHTML = trafficData.map(d => `
        <div class="legend-item">
            <span class="legend-dot" style="background:${d.color}"></span>
            <span>${d.label} (${d.value}%)</span>
        </div>
    `).join('');

    // ── Sparkline Charts ──
    function createSparkline(canvasId, data, color) {
        const container = document.getElementById(canvasId);
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        const ctx = canvas.getContext('2d');

        const gradient = ctx.createLinearGradient(0, 0, 0, 40);
        gradient.addColorStop(0, color.replace('1)', '0.3)'));
        gradient.addColorStop(1, color.replace('1)', '0)'));

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map((_, i) => i),
                datasets: [{
                    data,
                    borderColor: color,
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { display: false },
                    y: { display: false },
                },
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                elements: { line: { capBezierPoints: true } },
            },
        });
    }

    createSparkline('sparkRevenue', [42, 48, 45, 52, 58, 56, 62, 68, 64, 72, 78, 84], 'rgba(99, 102, 241, 1)');
    createSparkline('sparkUsers', [18, 21, 19, 23, 20, 24, 22, 26, 25, 27, 28, 29], 'rgba(139, 92, 246, 1)');
    createSparkline('sparkOrders', [90, 105, 95, 110, 120, 115, 125, 130, 128, 135, 140, 143], 'rgba(16, 185, 129, 1)');
    createSparkline('sparkChurn', [6.2, 5.8, 6.0, 5.5, 5.3, 5.6, 5.1, 5.0, 5.2, 4.9, 4.8, 4.8], 'rgba(245, 158, 11, 1)');

    // ── Transactions ──
    const transactions = [
        { icon: 'fas fa-arrow-down', type: 'income', name: 'Enterprise Subscription', date: 'Feb 20, 2026', amount: '+$4,200', positive: true },
        { icon: 'fas fa-arrow-up', type: 'expense', name: 'AWS Infrastructure', date: 'Feb 19, 2026', amount: '-$1,840', positive: false },
        { icon: 'fas fa-exchange-alt', type: 'transfer', name: 'Payroll Transfer', date: 'Feb 18, 2026', amount: '-$12,500', positive: false },
        { icon: 'fas fa-arrow-down', type: 'income', name: 'Pro Plan Upgrade x3', date: 'Feb 17, 2026', amount: '+$897', positive: true },
        { icon: 'fas fa-arrow-up', type: 'expense', name: 'Marketing Ads', date: 'Feb 16, 2026', amount: '-$2,300', positive: false },
    ];

    const txList = document.getElementById('transactionsList');
    txList.innerHTML = transactions.map(t => `
        <div class="transaction-item">
            <div class="transaction-icon ${t.type}"><i class="${t.icon}"></i></div>
            <div class="transaction-details">
                <div class="transaction-name">${t.name}</div>
                <div class="transaction-date">${t.date}</div>
            </div>
            <div class="transaction-amount ${t.positive ? 'positive' : 'negative'}">${t.amount}</div>
        </div>
    `).join('');

    // ── Activity Feed ──
    const activities = [
        { avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=sarah', text: '<strong>Sarah Chen</strong> deployed <strong>v2.4.1</strong> to production', time: '5 min ago' },
        { avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=marcus', text: '<strong>Marcus Johnson</strong> closed 3 support tickets', time: '22 min ago' },
        { avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=priya', text: '<strong>Priya Patel</strong> updated the billing dashboard', time: '1 hour ago' },
        { avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=david', text: '<strong>David Kim</strong> added new API endpoint <strong>/v3/analytics</strong>', time: '3 hours ago' },
        { avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=emma', text: '<strong>Emma Wilson</strong> onboarded 2 new enterprise clients', time: '5 hours ago' },
    ];

    const activityFeed = document.getElementById('activityFeed');
    activityFeed.innerHTML = activities.map(a => `
        <div class="activity-item">
            <img class="activity-avatar" src="${a.avatar}" alt="avatar">
            <div class="activity-content">
                <div class="activity-text">${a.text}</div>
                <div class="activity-time">${a.time}</div>
            </div>
        </div>
    `).join('');

    // ── Products Table ──
    const products = [
        { name: 'NexusBoard Pro', color: '#6366f1', sales: '1,248', revenue: '$48,920', growth: '+18.2%', positive: true },
        { name: 'CloudSync Plus', color: '#8b5cf6', sales: '892', revenue: '$32,100', growth: '+12.5%', positive: true },
        { name: 'DataVault Enterprise', color: '#ec4899', sales: '567', revenue: '$28,450', growth: '+8.7%', positive: true },
        { name: 'API Gateway', color: '#14b8a6', sales: '423', revenue: '$15,680', growth: '-2.3%', positive: false },
        { name: 'DevKit Starter', color: '#f59e0b', sales: '1,890', revenue: '$9,450', growth: '+24.1%', positive: true },
    ];

    const productsBody = document.getElementById('productsTableBody');
    productsBody.innerHTML = products.map(p => `
        <tr>
            <td>
                <div class="product-name-cell">
                    <span class="product-color" style="background:${p.color}"></span>
                    <span class="product-name">${p.name}</span>
                </div>
            </td>
            <td>${p.sales}</td>
            <td>${p.revenue}</td>
            <td><span class="growth-badge ${p.positive ? 'positive' : 'negative'}">${p.growth}</span></td>
        </tr>
    `).join('');

    // ── Tab Pills (Revenue Chart) ──
    document.querySelectorAll('.tab-pills .pill').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.tab-pills .pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
        });
    });

    // ── Keyboard shortcut (⌘K / Ctrl+K) ──
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('globalSearch').focus();
        }
        if (e.key === 'Escape') {
            sidebar.classList.remove('mobile-open');
            overlay.classList.remove('active');
            notifPanel.classList.remove('open');
            profileSection.classList.remove('open');
        }
    });

    // ── Animate stat rings on load ──
    setTimeout(() => {
        document.querySelectorAll('.ring-fill').forEach(ring => {
            const dasharray = ring.getAttribute('stroke-dasharray');
            ring.style.strokeDasharray = '0, 100';
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    ring.style.strokeDasharray = dasharray;
                });
            });
        });
    }, 800);

});
