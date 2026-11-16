import re
from datetime import date, time, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import User, RestaurantProfile, Venue, Menu, MenuItem, Package, Availability, Booking, Notification


def csrf(client, path="/login"):
    response = client.get(path)
    match = re.search(rb'const token\s*=\s*"?([^";]+)', response.data)
    assert match, path
    return match.group(1).decode()


def login(client, email, path="/login"):
    token = csrf(client, path)
    endpoint = "/restaurant/login" if path == "/restaurant/login" else "/login"
    response = client.post(endpoint, data={
        "_csrf_token": token,
        "email": email,
        "password": "password12345",
    })
    assert response.status_code in (302, 303)


def test_customer_restaurant_and_admin_pages_render(app, client):
    with app.app_context():
        customer = User(full_name="Render Customer", email="render-customer@example.test", role="customer")
        partner = User(full_name="Render Partner", email="render-partner@example.test", role="restaurant")
        admin = User(full_name="Render Admin", email="render-admin@example.test", role="admin")
        for user in (customer, partner, admin):
            user.set_password("password12345")
        profile = RestaurantProfile(user=partner, business_name="Render Restaurant", verification_status="approved", city="Pune")
        venue = Venue(restaurant=profile, name="Render Venue", venue_type="Restaurant", address="Test Road", city="Pune", state="Maharashtra", min_capacity=1, max_capacity=80, price_per_person=Decimal("500"), base_price=Decimal("100"), status="published", is_published=True)
        menu = Menu(venue=venue, name="Render Menu", description="Menu", is_active=True)
        item = MenuItem(menu=menu, name="Render Dish", category="Starter", price=Decimal("100"), dietary_type="veg")
        package = Package(venue=venue, name="Render Package", description="Package", price_per_person=Decimal("700"), min_guests=1, max_guests=80, is_active=True)
        event_date = date.today() + timedelta(days=15)
        slot = Availability(venue=venue, available_date=event_date, start_time=time(9), end_time=time(18), is_available=True)
        booking = Booking(booking_reference="PP-RENDERTEST", customer=customer, venue=venue, package=package, event_name="Render Event", event_type="Corporate", event_date=event_date, duration="2 hours", organiser_name=customer.full_name, contact_email=customer.email, contact_phone="9876543210", start_time=time(10), end_time=time(12), guest_count=10, total_amount=Decimal("7100"), status="pending")
        notification = Notification(user=customer, title="Test", message="Test notification", category="booking")
        db.session.add_all([customer, partner, admin, profile, venue, menu, item, package, slot, booking, notification])
        db.session.commit()
        venue_id = db.session.query(Venue.id).filter_by(name="Render Venue").scalar()
        menu_id = db.session.query(Menu.id).filter_by(name="Render Menu").scalar()
        booking_id = db.session.query(Booking.id).filter_by(booking_reference="PP-RENDERTEST").scalar()
        restaurant_id = db.session.query(RestaurantProfile.id).filter_by(business_name="Render Restaurant").scalar()

    login(client, "render-customer@example.test")
    customer_pages = [
        "/customer/dashboard", "/customer/explore", f"/customer/venue/{venue_id}",
        f"/customer/venue/{venue_id}/menu", f"/customer/venue/{venue_id}/packages",
        f"/customer/venue/{venue_id}/book", "/customer/profile", "/customer/bookings",
        f"/customer/bookings/{booking_id}", "/customer/notifications",
    ]
    for path in customer_pages:
        response = client.get(path)
        assert response.status_code in (200, 302), (path, response.status_code)

    client.post("/logout", data={"_csrf_token": csrf(client, "/")})
    login(client, "render-partner@example.test", "/restaurant/login")
    partner_pages = [
        "/restaurant/", "/restaurant/onboarding", "/restaurant/profile",
        "/restaurant/venues", "/restaurant/venues/add", f"/restaurant/venues/{venue_id}/edit",
        "/restaurant/menus", "/restaurant/menus/add", f"/restaurant/menus/{menu_id}/items",
        "/restaurant/packages", "/restaurant/packages/add", "/restaurant/availability",
        "/restaurant/booking-requests", "/restaurant/upcoming-events",
        f"/restaurant/bookings/{booking_id}", "/restaurant/settings",
        f"/restaurant/venues/{venue_id}/photos",
    ]
    for path in partner_pages:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)

    client.post("/logout", data={"_csrf_token": csrf(client, "/")})
    login(client, "render-admin@example.test")
    admin_pages = [
        "/admin/", "/admin/restaurants", f"/admin/restaurants/{restaurant_id}",
        "/admin/venues", "/admin/bookings", f"/admin/bookings/{booking_id}",
        "/admin/customers", "/admin/reports", "/admin/settings",
    ]
    for path in admin_pages:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
