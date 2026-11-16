from app.extensions import db
from app.models import User, RestaurantProfile, Venue


def test_partner_cannot_edit_another_partners_venue(app, client):
    with app.app_context():
        owner = User(full_name="Owner A", email="a@example.test", role="restaurant")
        owner.set_password("password123")
        profile = RestaurantProfile(user=owner, business_name="Owner A Business", verification_status="approved")
        venue = Venue(restaurant=profile, name="A Venue", venue_type="Hall", address="A Road", city="Pune", min_capacity=1, max_capacity=100, price_per_person=100, base_price=0)
        other = User(full_name="Owner B", email="b@example.test", role="restaurant")
        other.set_password("password123")
        other_profile = RestaurantProfile(user=other, business_name="Owner B Business", verification_status="approved")
        db.session.add_all([owner, profile, venue, other, other_profile])
        db.session.commit()
        venue_id = venue.id
    with client:
        login_page = client.get("/restaurant/login")
        import re
        token = re.search(rb'const token = "([^"]+)"', login_page.data).group(1).decode()
        client.post("/restaurant/login", data={"_csrf_token": token, "email": "b@example.test", "password": "password123"})
        response = client.get(f"/restaurant/venues/{venue_id}/edit")
        assert response.status_code in (302, 404)
