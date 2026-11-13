/* EcoBudget — graphiques Chart.js (dashboard) */
(function () {
    const EMERALD = "#20A889";
    const CORAL = "#E76F51";
    const PALETTE = ["#20A889", "#E76F51", "#3E8E7E", "#F2A488", "#7FD1B9", "#B85C45", "#A8DCCB", "#8B9A96"];
    const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
    const CUR = document.body.dataset.currency || "DA";
    const da = (v) => nf.format(v) + " " + CUR;
    let charts = [];

    function themeColors() {
        const s = getComputedStyle(document.documentElement);
        return {
            text: s.getPropertyValue("--muted").trim(),
            grid: s.getPropertyValue("--border").trim(),
            surface: s.getPropertyValue("--surface").trim(),
        };
    }

    function build(data) {
        charts.forEach((c) => c.destroy());
        charts = [];

        const t = themeColors();
        Chart.defaults.font.family = "Inter, system-ui, sans-serif";
        Chart.defaults.color = t.text;

        const monthly = document.getElementById("chart-monthly");
        if (monthly) {
            charts.push(new Chart(monthly, {
                type: "bar",
                data: {
                    labels: data.months,
                    datasets: [
                        { label: "Revenus", data: data.income, backgroundColor: EMERALD, borderRadius: 6 },
                        { label: "Dépenses", data: data.expense, backgroundColor: CORAL, borderRadius: 6 },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom", labels: { usePointStyle: true } },
                        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label} : ${da(ctx.parsed.y)}` } },
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: { beginAtZero: true, grid: { color: t.grid }, ticks: { callback: (v) => nf.format(v) } },
                    },
                },
            }));
        }

        const cat = document.getElementById("chart-categories");
        if (cat && data.categories.length) {
            charts.push(new Chart(cat, {
                type: "doughnut",
                data: {
                    labels: data.categories.map((c) => c.name),
                    datasets: [{
                        data: data.categories.map((c) => c.amount),
                        backgroundColor: data.categories.map((_, i) => PALETTE[i % PALETTE.length]),
                        borderColor: t.surface,
                        borderWidth: 3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "62%",
                    plugins: {
                        legend: { position: "bottom", labels: { usePointStyle: true } },
                        tooltip: { callbacks: { label: (ctx) => `${ctx.label} : ${da(ctx.parsed)}` } },
                    },
                },
            }));
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const holder = document.getElementById("dash-data");
        if (!holder || typeof Chart === "undefined") return;

        let data;
        try { data = JSON.parse(holder.dataset.charts); } catch (e) { return; }

        build(data);
        // Redessine les graphiques quand on bascule clair / sombre
        new MutationObserver(() => build(data)).observe(document.documentElement, {
            attributes: true, attributeFilter: ["data-theme"],
        });
    });
})();