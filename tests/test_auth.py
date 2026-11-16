from app.extensions import db
from app.models import User


def test_customer_registration_creates_account_and_logs_in(client, csrf_token):
    response = client.post("/customer/register", data={
        "_csrf_token": csrf_token,
        "full_name": "Test Customer",
        "email": "customer@example.test",
        "phone": "9876543210",
        "password": "strong-test-password",
        "confirm_password": "strong-test-password",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"created successfully" in response.data.lower()


def test_public_admin_registration_is_not_available(client):
    response = client.get("/admin/register")
    assert response.status_code == 404


def test_post_without_csrf_is_rejected(client):
    response = client.post("/login", data={"email": "x@example.test", "password": "bad"})
    assert response.status_code == 400


def test_admin_settings_update_profile_and_password(app, client):
    import re
    from app.extensions import db
    from app.models import User

    with app.app_context():
        admin = User(full_name="Admin User", email="admin-settings@example.test", role="admin")
        admin.set_password("initial-password-123")
        db.session.add(admin)
        db.session.commit()

    login_page = client.get("/login")
    token = re.search(rb'const token = "([^"]+)"', login_page.data).group(1).decode()
    client.post("/login", data={
        "_csrf_token": token,
        "email": "admin-settings@example.test",
        "password": "initial-password-123",
    })

    settings = client.get("/admin/settings")
    assert settings.status_code == 200
    with client.session_transaction() as session_data:
        token = session_data["_csrf_token"]
    response = client.post("/admin/settings", data={
        "_csrf_token": token,
        "action": "profile",
        "full_name": "Updated Admin",
        "email": "updated-admin@example.test",
        "phone": "9876543210",
    })
    assert response.status_code == 302

    response = client.post("/admin/settings", data={
        "_csrf_token": token,
        "action": "password",
        "current_password": "initial-password-123",
        "new_password": "updated-password-123",
        "confirm_password": "updated-password-123",
    })
    assert response.status_code == 302

    with app.app_context():
        updated = User.query.filter_by(email="updated-admin@example.test").one()
        assert updated.full_name == "Updated Admin"
        assert updated.check_password("updated-password-123")


def test_admin_cli_creates_admin_without_public_registration(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin"],
        input="CLI Administrator\ncli-admin@example.test\nvery-strong-cli-password\nvery-strong-cli-password\n",
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        from app.models import User
        admin = User.query.filter_by(email="cli-admin@example.test").one()
        assert admin.role == "admin"
        assert admin.check_password("very-strong-cli-password")
