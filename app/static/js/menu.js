document.addEventListener("DOMContentLoaded", () => {
    // MENU SELECTION
    const menuChoices = document.querySelectorAll(".menu-choice");

    if (menuChoices.length) {
        const guestInput = document.getElementById("guestCount");
        const selectedMenu = document.getElementById("selectedMenu");
        const perPerson = document.getElementById("perPerson");
        const summaryGuests = document.getElementById("summaryGuests");
        const menuTotal = document.getElementById("menuTotal");

        function updateMenuSummary() {
            const guests = Math.max(1, Number(guestInput.value) || 1);
            guestInput.value = guests;

            const selected = [...menuChoices].filter(item => item.checked);
            const pricePerPerson = selected.reduce(
                (total, item) => total + Number(item.dataset.price), 0
            );

            selectedMenu.innerHTML = "";

            if (!selected.length) {
                selectedMenu.innerHTML =
                    '<p class="summary-empty">Your selected dishes will appear here.</p>';
            } else {
                selected.forEach(item => {
                    const dish = document.createElement("div");
                    dish.className = "selected-dish";

                    const name = document.createElement("span");
                    name.textContent = item.dataset.name;

                    const price = document.createElement("strong");
                    price.textContent = `₹${Number(item.dataset.price).toLocaleString("en-IN")}`;

                    dish.append(name, price);
                    selectedMenu.appendChild(dish);
                });
            }

            perPerson.textContent = `₹${pricePerPerson.toLocaleString("en-IN")}`;
            summaryGuests.textContent = guests;
            menuTotal.textContent =
                `₹${(pricePerPerson * guests).toLocaleString("en-IN")}`;
        }

        menuChoices.forEach(item => {
            item.addEventListener("change", updateMenuSummary);
        });

        guestInput.addEventListener("input", updateMenuSummary);
        updateMenuSummary();
    }

    // EVENT PACKAGE SELECTION
    const packages = document.querySelectorAll('input[name="eventPackage"]');

    if (packages.length) {
        const continueLink = document.getElementById("continuePackage");
        if (continueLink) continueLink.dataset.baseUrl = continueLink.href;
        const chosenPackage = document.getElementById("chosenPackage");
        const packagePrice = document.getElementById("packagePrice");

        function updatePackage() {
            const selected = document.querySelector(
                'input[name="eventPackage"]:checked'
            );

            if (!selected) return;

            const name = selected.dataset.name || selected.value;
            const price = Number(selected.dataset.price);

            chosenPackage.textContent = name;
            packagePrice.textContent =
                `₹${price.toLocaleString("en-IN")} per person`;

            const continueLink = document.getElementById("continuePackage");
            if (continueLink) {
                continueLink.href = `${continueLink.dataset.baseUrl}?package_id=${encodeURIComponent(selected.value)}`;
            }

            document.querySelectorAll(".package-card").forEach(card => {
                const radio = card.querySelector('input[name="eventPackage"]');
                card.classList.toggle("selected", radio.checked);

                const label = card.querySelector(".package-select");
                label.textContent = radio.checked
                    ? "Selected package"
                    : "Select package";
            });
        }

        packages.forEach(option => {
            option.addEventListener("change", updatePackage);
        });

        updatePackage();
    }
});