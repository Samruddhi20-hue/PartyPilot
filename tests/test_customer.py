from app.extensions import db
from app.models import User, RestaurantProfile, Venue


def test_customer_cannot_open_restaurant_dashboard(app, client, csrf_token):
    with app.app_context():
        user = User(full_name="Customer", email="c@example.test", role="customer")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        email = user.email
    client.post("/login", data={"_csrf_token": csrf_token, "email": email, "password": "password123"})
    response = client.get("/restaurant/")
    assert response.status_code in (302, 303)


def test_unapproved_venue_is_not_public(app, client):
    with app.app_context():
        user = User(full_name="Partner", email="p@example.test", role="restaurant")
        user.set_password("password123")
        profile = RestaurantProfile(user=user, business_name="Private Partner", verification_status="pending")
        venue = Venue(restaurant=profile, name="Private Venue", venue_type="Hall", address="Test address", city="Pune", min_capacity=1, max_capacity=100, price_per_person=100, base_price=0, status="published", is_published=True)
        db.session.add_all([user, profile, venue])
        db.session.commit()
    response = client.get("/venue/1")
    assert response.status_code == 404
