document.addEventListener("DOMContentLoaded", () => {
    // Prevent selecting a date in the past.
    const dateInput = document.getElementById("eventDate");

    if (dateInput) {
        const today = new Date();
        const localToday = new Date(
            today.getTime() - today.getTimezoneOffset() * 60000
        ).toISOString().split("T")[0];

        dateInput.min = localToday;
    }

    // Validate the booking form.
    const bookingForm = document.getElementById("eventBookingForm");

    if (bookingForm) {
        bookingForm.addEventListener("submit", event => {
            const guests = Number(
                document.getElementById("guestCountForm").value
            );
            const error = document.getElementById("bookingFormError");

            error.hidden = true;
            error.textContent = "";

            const guestInput = document.getElementById("guestCountForm");
            const minimum = Number(guestInput.min || 1);
            const maximum = Number(guestInput.max || 999999);
            if (guests < minimum || guests > maximum) {
                event.preventDefault();
                error.textContent = `Please enter between ${minimum} and ${maximum} guests.`;
                error.hidden = false;
                return;
            }

            if (!bookingForm.reportValidity()) {
                event.preventDefault();
            }
        });
    }

    // Filter bookings by status.
    const tabs = document.querySelectorAll(".booking-tab");
    const bookingCards = document.querySelectorAll(".my-booking-card");
    const noBookings = document.getElementById("noBookings");

    if (tabs.length && bookingCards.length) {
        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                tabs.forEach(item => item.classList.remove("active"));
                tab.classList.add("active");

                const status = tab.dataset.status;
                let visibleCount = 0;

                bookingCards.forEach(card => {
                    const visible =
                        status === "all" || card.dataset.status === status;

                    card.hidden = !visible;
                    if (visible) visibleCount++;
                });

                if (noBookings) {
                    noBookings.hidden = visibleCount !== 0;
                }
            });
        });
    }
});