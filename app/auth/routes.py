
import re

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import login_user, logout_user, current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.auth import auth
from app.extensions import db
from app.models import User, RestaurantProfile


def normalize_email(email):
    return (email or "").strip().lower()


def valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def find_user_by_email(email):
    return User.query.filter(
        func.lower(User.email) == normalize_email(email)
    ).first()


def create_customer(full_name, email, phone, password):
    user = User(
        full_name=full_name,
        email=email,
        phone=phone or None,
        role="customer",
    )
    user.set_password(password)
    db.session.add(user)
    return user


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "1"

        user = find_user_by_email(email)

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        if not user.is_active:
            flash("Your account is currently inactive.", "warning")
            return render_template("auth/login.html")

        if user.role not in ("customer", "admin"):
            flash("Please use the restaurant partner login.", "warning")
            return redirect(url_for("auth.restaurant_login"))

        login_user(user, remember=remember)
        flash("Welcome back!", "success")
        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/login.html")


@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        account_type = request.form.get("account_type", "customer")

        if account_type == "restaurant":
            return redirect(url_for("auth.restaurant_register"))

        return register_customer(
            full_name=request.form.get("name"),
            email=request.form.get("email"),
            phone=None,
            password=request.form.get("password"),
        )

    return render_template("auth/register.html")


@auth.route("/customer/register", methods=["GET", "POST"])
def customer_register():
    if request.method == "POST":
        return register_customer(
            full_name=request.form.get("full_name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            password=request.form.get("password"),
            confirm_password=request.form.get("confirm_password"),
        )

    return render_template("auth/customer_register.html")


def register_customer(
    full_name,
    email,
    phone,
    password,
    confirm_password=None,
):
    full_name = (full_name or "").strip()
    email = normalize_email(email)
    phone = (phone or "").strip() or None

    if not full_name or not email or not password:
        flash("Please complete all required fields.", "danger")
        return redirect(request.referrer or url_for("auth.register"))

    if not valid_email(email):
        flash("Please enter a valid email address.", "danger")
        return redirect(request.referrer or url_for("auth.register"))

    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "danger")
        return redirect(request.referrer or url_for("auth.register"))

    if confirm_password is not None and password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("auth.customer_register"))

    if find_user_by_email(email):
        flash("An account with this email already exists.", "danger")
        return redirect(request.referrer or url_for("auth.register"))

    if phone and User.query.filter_by(phone=phone).first():
        flash("This phone number is already registered.", "danger")
        return redirect(request.referrer or url_for("auth.register"))

    try:
        user = create_customer(full_name, email, phone, password)
        db.session.commit()
        login_user(user)
        flash("Your account has been created successfully!", "success")
        return redirect(url_for("customer.dashboard"))

    except IntegrityError:
        db.session.rollback()
        flash("This email or phone number is already registered.", "danger")
        return redirect(request.referrer or url_for("auth.register"))


@auth.route("/restaurant/register", methods=["GET", "POST"])
def restaurant_register():
    if request.method == "POST":
        owner_name = (request.form.get("owner_name") or "").strip()
        business_name = (request.form.get("restaurant_name") or "").strip()
        email = normalize_email(request.form.get("email"))
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password", "")

        if not all([owner_name, business_name, email, phone, password]):
            flash("Please complete all required fields.", "danger")
            return render_template("auth/restaurant_register.html")

        if not valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/restaurant_register.html")

        if not re.fullmatch(r"[6-9]\d{9}", phone):
            flash("Please enter a valid 10-digit mobile number.", "danger")
            return render_template("auth/restaurant_register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return render_template("auth/restaurant_register.html")

        if find_user_by_email(email):
            flash("An account with this email already exists.", "danger")
            return render_template("auth/restaurant_register.html")

        if User.query.filter_by(phone=phone).first():
            flash("This phone number is already registered.", "danger")
            return render_template("auth/restaurant_register.html")

        try:
            user = User(
                full_name=owner_name,
                email=email,
                phone=phone,
                role="restaurant",
            )
            user.set_password(password)

            profile = RestaurantProfile(
                user=user,
                business_name=business_name,
                contact_email=email,
                contact_phone=phone,
                verification_status="pending",
            )

            db.session.add(user)
            db.session.add(profile)
            db.session.commit()

            flash(
                "Partner account created. Your restaurant is awaiting verification.",
                "success",
            )
            return redirect(url_for("auth.restaurant_login"))

        except IntegrityError:
            db.session.rollback()
            flash("This email or phone number is already registered.", "danger")

    return render_template("auth/restaurant_register.html")


@auth.route("/restaurant/login", methods=["GET", "POST"])
def restaurant_login():
    if current_user.is_authenticated:
        if current_user.role == "restaurant":
            return redirect(url_for("home"))
        logout_user()

    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        remember = request.form.get("remember") in ("1", "on", "true")

        user = find_user_by_email(email)

        if (
            not user
            or not user.check_password(password)
            or not user.is_active
            or user.role != "restaurant"
        ):
            flash("Invalid restaurant login details.", "danger")
            return render_template("auth/restaurant_login.html")

        login_user(user, remember=remember)
        flash("Welcome to your partner account!", "success")
        return redirect(url_for("restaurant.dashboard"))

    return render_template("auth/restaurant_login.html")


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))

        if not valid_email(email):
            flash("Please enter a valid email address.", "danger")
        else:
            flash(
                "Password recovery by email is not enabled yet. Please contact support.",
                "info",
            )

    return render_template("auth/forgot_password.html")


@auth.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("You have been logged out.", "success")

    return redirect(url_for("home"))
