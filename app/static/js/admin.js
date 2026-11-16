document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("adminMenuToggle");
    const sidebar = document.getElementById("adminSidebar");
    if (toggle && sidebar) {
        toggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
            toggle.setAttribute("aria-expanded", sidebar.classList.contains("open") ? "true" : "false");
        });
    }
});
