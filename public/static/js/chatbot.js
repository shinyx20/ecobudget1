/* EcoBot : assistant simple (réponses prédéfinies) */
document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("chatbot");
    if (!root) return;

    const toggle = document.getElementById("chatbot-toggle");
    const panel = document.getElementById("chatbot-panel");
    const closeBtn = document.getElementById("chatbot-close");
    const log = document.getElementById("chatbot-log");
    const form = document.getElementById("chatbot-form");
    const input = document.getElementById("chatbot-input");
    let greeted = false;
    let busy = false;

    function scrollDown() { log.scrollTop = log.scrollHeight; }

    function addMessage(text, who, link) {
        const div = document.createElement("div");
        div.className = "bot-msg " + who;
        div.textContent = text;                       // textContent : pas de HTML injecté
        if (link && link.url) {
            const a = document.createElement("a");
            a.href = link.url;
            a.className = "bot-link";
            a.textContent = link.label + " →";
            div.appendChild(a);
        }
        log.appendChild(div);
        scrollDown();
        return div;
    }

    async function ask(payload, label) {
        if (busy) return;
        busy = true;
        addMessage(label, "user");
        const typing = addMessage("EcoBot écrit…", "bot typing");

        const res = await postJson("/chatbot/ask", payload);
        typing.remove();
        if (res.ok) addMessage(res.data.reply, "bot", res.data.link);
        else addMessage("Désolé, je rencontre un problème. Réessayez dans un instant.", "bot");
        busy = false;
    }

    function openPanel() {
        panel.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        if (!greeted) {
            addMessage("Bonjour ! 👋 Je suis EcoBot. Comment puis-je vous aider ?", "bot");
            greeted = true;
        }
        setTimeout(() => input.focus(), 50);
    }

    function closePanel() {
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
    }

    toggle.addEventListener("click", () => (panel.hidden ? openPanel() : closePanel()));
    closeBtn.addEventListener("click", closePanel);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !panel.hidden) closePanel();
    });

    // Boutons de sujets prédéfinis
    root.querySelectorAll("[data-topic]").forEach((chip) =>
        chip.addEventListener("click", () => ask({ topic: chip.dataset.topic }, chip.textContent.trim()))
    );

    // Question écrite
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) { input.focus(); return; }
        input.value = "";
        ask({ message: text }, text);
    });
});