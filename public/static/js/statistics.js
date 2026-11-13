/* EcoBudget — graphiques de la page Statistiques */
(function () {
    const EMERALD = "#20A889";
    const CORAL = "#E76F51";
    const PALETTE = ["#20A889", "#E76F51", "#3E8E7E", "#F2A488", "#7FD1B9", "#B85C45", "#A8DCCB", "#8B9A96"];
    const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
    const CUR = document.body.dataset.currency || "DA";
    const da = (v) => nf.format(v) + " " + CUR;
    let charts = [];

    function theme() {
        const s = getComputedStyle(document.documentElement);
        return {
            text: s.getPropertyValue("--muted").trim(),
            grid: s.getPropertyValue("--border").trim(),
            surface: s.getPropertyValue("--surface").trim(),
        };
    }

    function axes(t) {
        return {
            x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
            y: { beginAtZero: true, grid: { color: t.grid }, ticks: { callback: (v) => nf.format(v) } },
        };
    }

    function build(d) {
        charts.forEach((c) => c.destroy());
        charts = [];
        const t = theme();
        Chart.defaults.font.family = "Inter, system-ui, sans-serif";
        Chart.defaults.color = t.text;
        const small = d.labels.length > 31;   // beaucoup de points : on retire les marqueurs

        const cat = document.getElementById("chart-categories");
        if (cat && d.categories.length) {
            charts.push(new Chart(cat, {
                type: "doughnut",
                data: {
                    labels: d.categories.map((c) => c.name),
                    datasets: [{
                        data: d.categories.map((c) => c.amount),
                        backgroundColor: d.categories.map((_, i) => PALETTE[i % PALETTE.length]),
                        borderColor: t.surface, borderWidth: 3,
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: "62%",
                    plugins: {
                        legend: { position: "bottom", labels: { usePointStyle: true } },
                        tooltip: { callbacks: { label: (ctx) => `${ctx.label} : ${da(ctx.parsed)}` } },
                    },
                },
            }));
        }

        const exp = document.getElementById("chart-expense");
        if (exp) {
            charts.push(new Chart(exp, {
                type: "line",
                data: {
                    labels: d.labels,
                    datasets: [{
                        label: "Dépenses", data: d.expense, borderColor: CORAL,
                        backgroundColor: "rgba(231, 111, 81, .15)", fill: true, tension: .3,
                        pointRadius: small ? 0 : 3,
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, scales: axes(t),
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (ctx) => `Dépenses : ${da(ctx.parsed.y)}` } },
                    },
                },
            }));
        }

        const cmp = document.getElementById("chart-compare");
        if (cmp) {
            charts.push(new Chart(cmp, {
                type: "bar",
                data: {
                    labels: d.labels,
                    datasets: [
                        { label: "Revenus", data: d.income, backgroundColor: EMERALD, borderRadius: 4 },
                        { label: "Dépenses", data: d.expense, backgroundColor: CORAL, borderRadius: 4 },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, scales: axes(t),
                    plugins: {
                        legend: { position: "bottom", labels: { usePointStyle: true } },
                        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label} : ${da(ctx.parsed.y)}` } },
                    },
                },
            }));
        }

        const sav = document.getElementById("chart-savings");
        if (sav) {
            charts.push(new Chart(sav, {
                type: "line",
                data: {
                    labels: d.labels,
                    datasets: [{
                        label: "Épargne cumulée", data: d.savings, borderColor: EMERALD,
                        backgroundColor: "rgba(32, 168, 137, .15)", fill: true, tension: .25,
                        pointRadius: small ? 0 : 3,
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, scales: axes(t),
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (ctx) => `Épargne : ${da(ctx.parsed.y)}` } },
                    },
                },
            }));
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const holder = document.getElementById("stats-data");
        if (!holder || typeof Chart === "undefined") return;
        let data;
        try { data = JSON.parse(holder.dataset.charts); } catch (e) { return; }
        build(data);
        new MutationObserver(() => build(data)).observe(document.documentElement, {
            attributes: true, attributeFilter: ["data-theme"],
        });
    });
})();