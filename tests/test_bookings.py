from decimal import Decimal
from types import SimpleNamespace
from app.bookings.routes import calculate_total


def test_package_price_calculation_uses_package_and_base_charge():
    venue = SimpleNamespace(base_price=Decimal("500.00"), price_per_person=Decimal("100.00"))
    package = SimpleNamespace(price_per_person=Decimal("750.00"))
    assert calculate_total(venue, package, 20) == Decimal("15500.00")


def test_standard_price_calculation_uses_venue_rate():
    venue = SimpleNamespace(base_price=Decimal("250.00"), price_per_person=Decimal("300.00"))
    assert calculate_total(venue, None, 10) == Decimal("3250.00")


def test_customer_can_submit_booking_with_published_availability(app, client):
    from datetime import date, time, timedelta
    import re
    from app.extensions import db
    from app.models import User, RestaurantProfile, Venue, Availability, Booking, Notification

    with app.app_context():
        customer = User(full_name="Booking Customer", email="booking-customer@example.test", role="customer")
        customer.set_password("password12345")
        partner = User(full_name="Booking Partner", email="booking-partner@example.test", role="restaurant")
        partner.set_password("password12345")
        profile = RestaurantProfile(user=partner, business_name="Booking Restaurant", verification_status="approved")
        venue = Venue(
            restaurant=profile, name="Bookable Venue", venue_type="Restaurant",
            address="Test Road", city="Pune", state="Maharashtra",
            min_capacity=1, max_capacity=80, price_per_person=Decimal("500"),
            base_price=Decimal("100"), status="published", is_published=True,
        )
        event_date = date.today() + timedelta(days=20)
        slot = Availability(
            venue=venue, available_date=event_date,
            start_time=time(9, 0), end_time=time(18, 0), is_available=True,
        )
        db.session.add_all([customer, partner, profile, venue, slot])
        db.session.commit()

    login_page = client.get("/login")
    token = re.search(rb'const token = "([^"]+)"', login_page.data).group(1).decode()
    client.post("/login", data={
        "_csrf_token": token,
        "email": "booking-customer@example.test",
        "password": "password12345",
    })

    response = client.post("/customer/venue/1/book", data={
        "_csrf_token": token,
        "event_name": "Team Celebration",
        "event_type": "Corporate Party",
        "event_date": event_date.isoformat(),
        "event_time": "10:00",
        "duration": "2 hours",
        "guests": "20",
        "organiser_name": "Booking Customer",
        "company_name": "Example Co",
        "email": "booking-customer@example.test",
        "phone": "9876543210",
        "special_requests": "Projector required",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/customer/booking/summary")

    summary = client.get("/customer/booking/summary")
    assert summary.status_code == 200
    assert b"Team Celebration" in summary.data
    confirm_token = re.search(rb'const token = "([^"]+)"', summary.data).group(1).decode()
    confirmed = client.post("/customer/booking/confirm", data={"_csrf_token": confirm_token})
    assert confirmed.status_code == 302
    assert "/customer/booking/success/" in confirmed.headers["Location"]

    with app.app_context():
        saved = Booking.query.filter_by(event_name="Team Celebration").one()
        assert saved.total_amount == Decimal("10100.00")
        assert saved.end_time == time(12, 0)
        assert Notification.query.filter_by(user_id=saved.customer_id).count() == 1

    # A second request for the same venue/time must not create a duplicate booking.
    second_request = client.post("/customer/venue/1/book", data={
        "_csrf_token": confirm_token,
        "event_name": "Duplicate Event",
        "event_type": "Corporate Party",
        "event_date": event_date.isoformat(),
        "event_time": "10:00",
        "duration": "2 hours",
        "guests": "20",
        "organiser_name": "Booking Customer",
        "company_name": "Example Co",
        "email": "booking-customer@example.test",
        "phone": "9876543210",
    })
    assert second_request.status_code == 302
    client.get("/customer/booking/summary")
    blocked = client.post("/customer/booking/confirm", data={"_csrf_token": confirm_token})
    assert blocked.status_code == 302
    assert blocked.headers["Location"].endswith("/customer/venue/1/book")
    with app.app_context():
        assert Booking.query.filter_by(venue_id=1, event_date=event_date).count() == 1
