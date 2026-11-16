
const menuToggle = document.getElementById("menuToggle");
const navLinks = document.getElementById("navLinks");
const navActions = document.querySelector(".nav-actions");

menuToggle?.addEventListener("click", () => {
    navLinks.classList.toggle("active");
    navActions.classList.toggle("active");
});
