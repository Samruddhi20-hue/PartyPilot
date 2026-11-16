
from functools import wraps
from datetime import date
import re

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    flash,
    abort,
)
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    User,
    RestaurantProfile,
    Venue,
    Booking,
    Notification,
)

from app.admin import admin


# =====================================================
# ADMIN ACCESS CONTROL
# =====================================================

def admin_required(view_function):
    @wraps(view_function)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("auth.login"))

        return view_function(*args, **kwargs)

    return decorated_function


# =====================================================
# ADMIN LOGIN REDIRECT
# Admins use the existing authentication system.
# No public admin registration is provided.
# =====================================================

@admin.route("/login")
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))

        flash("Please log in with an administrator account.", "warning")

    return redirect(url_for("auth.login"))


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@admin.route("/")
@admin_required
def dashboard():
    total_customers = User.query.filter_by(
        role="customer"
    ).count()

    total_restaurants = RestaurantProfile.query.count()

    pending_restaurants = RestaurantProfile.query.filter_by(
        verification_status="pending"
    ).count()

    approved_restaurants = RestaurantProfile.query.filter_by(
        verification_status="approved"
    ).count()

    total_venues = Venue.query.count()

    published_venues = Venue.query.filter_by(
        is_published=True
    ).count()

    total_bookings = Booking.query.count()

    pending_bookings = Booking.query.filter_by(
        status="pending"
    ).count()

    confirmed_bookings = Booking.query.filter_by(
        status="confirmed"
    ).count()
    cancelled_bookings = Booking.query.filter_by(
        status="cancelled"
    ).count()

    recent_bookings = (
        Booking.query
        .order_by(Booking.created_at.desc())
        .limit(8)
        .all()
    )

    recent_restaurants = (
        RestaurantProfile.query
        .order_by(RestaurantProfile.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_customers=total_customers,
        total_restaurants=total_restaurants,
        pending_restaurants=pending_restaurants,
        approved_restaurants=approved_restaurants,
        total_venues=total_venues,
        published_venues=published_venues,
        total_bookings=total_bookings,
        pending_bookings=pending_bookings,
        confirmed_bookings=confirmed_bookings,
        cancelled_bookings=cancelled_bookings,
        recent_bookings=recent_bookings,
        recent_restaurants=recent_restaurants,
    )


# =====================================================
# RESTAURANT MANAGEMENT
# =====================================================

@admin.route("/restaurants")
@admin_required
def restaurants():
    status = request.args.get("status", "").strip().lower()

    query = RestaurantProfile.query

    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
    }

    if status in allowed_statuses:
        query = query.filter(
            RestaurantProfile.verification_status == status
        )

    restaurant_list = (
        query
        .order_by(RestaurantProfile.created_at.desc())
        .all()
    )

    return render_template(
        "admin/restaurants.html",
        restaurants=restaurant_list,
        selected_status=status,
    )


# =====================================================
# RESTAURANT DETAILS
# =====================================================

@admin.route("/restaurants/<int:restaurant_id>")
@admin_required
def restaurant_details(restaurant_id):
    profile = db.get_or_404(RestaurantProfile, restaurant_id)

    venues = Venue.query.filter_by(
        restaurant_id=profile.id
    ).order_by(Venue.created_at.desc()).all()

    venue_ids = [venue.id for venue in venues]

    booking_count = Booking.query.filter(
        Booking.venue_id.in_(venue_ids)
    ).count() if venue_ids else 0

    return render_template(
        "admin/restaurant_details.html",
        restaurant=profile,
        profile=profile,
        venues=venues,
        booking_count=booking_count,
    )


# =====================================================
# APPROVE OR REJECT RESTAURANT
# =====================================================

@admin.route(
    "/restaurants/<int:restaurant_id>/verification",
    methods=["POST"]
)
@admin_required
def update_restaurant_verification(restaurant_id):
    profile = db.get_or_404(RestaurantProfile, restaurant_id)

    new_status = request.form.get(
        "status", ""
    ).strip().lower()

    if new_status not in {"approved", "rejected"}:
        flash("Invalid verification action.", "danger")
        return redirect(
            url_for(
                "admin.restaurant_details",
                restaurant_id=profile.id,
            )
        )

    profile.verification_status = new_status

    # Rejected or pending restaurants must not have
    # publicly visible venues.
    if new_status == "rejected":
        Venue.query.filter_by(
            restaurant_id=profile.id
        ).update(
            {
                "is_published": False,
                "status": "draft",
            },
            synchronize_session=False,
        )

    if new_status == "approved":
        notification = Notification(
            user_id=profile.user_id,
            title="Restaurant verification approved",
            message=(
                "Your restaurant account has been approved. "
                "You can now publish eligible venues."
            ),
            category="account",
            is_read=False,
        )
        db.session.add(notification)

    elif new_status == "rejected":
        notification = Notification(
            user_id=profile.user_id,
            title="Restaurant verification update",
            message=(
                "Your restaurant verification was rejected. "
                "Please contact the PartyPilot administrator."
            ),
            category="account",
            is_read=False,
        )
        db.session.add(notification)

    db.session.commit()

    flash(
        f"Restaurant verification status changed to {new_status}.",
        "success",
    )

    return redirect(
        url_for(
            "admin.restaurant_details",
            restaurant_id=profile.id,
        )
    )


# =====================================================
# VENUE MANAGEMENT
# =====================================================

@admin.route("/venues")
@admin_required
def venue_management():
    status = request.args.get("status", "").strip().lower()
    search = request.args.get("search", "").strip()

    query = Venue.query.join(RestaurantProfile)
    if status == "published":
        query = query.filter(Venue.is_published.is_(True))
    elif status == "draft":
        query = query.filter(Venue.is_published.is_(False))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Venue.name.ilike(pattern),
            Venue.city.ilike(pattern),
            RestaurantProfile.business_name.ilike(pattern),
        ))

    venue_list = query.order_by(Venue.created_at.desc()).all()
    return render_template(
        "admin/venue_management.html",
        venues=venue_list,
        selected_status=status,
        search=search,
    )


# =====================================================
# PUBLISH OR HIDE VENUE
# =====================================================

@admin.route(
    "/venues/<int:venue_id>/visibility",
    methods=["POST"]
)
@admin_required
def update_venue_visibility(venue_id):
    venue = db.get_or_404(Venue, venue_id)

    action = request.form.get("action", "").strip().lower()

    profile = db.session.get(RestaurantProfile, venue.restaurant_id)

    if action == "publish":
        if not profile or profile.verification_status != "approved":
            flash(
                "Only venues belonging to approved restaurants "
                "can be published.",
                "warning",
            )
            return redirect(url_for("admin.venue_management"))

        venue.is_published = True
        venue.status = "published"

        message = f"{venue.name} has been published."

    elif action == "hide":
        venue.is_published = False
        venue.status = "draft"

        message = f"{venue.name} has been hidden."

    else:
        flash("Invalid venue action.", "danger")
        return redirect(url_for("admin.venue_management"))

    db.session.commit()

    flash(message, "success")
    return redirect(url_for("admin.venue_management"))


# =====================================================
# BOOKING MANAGEMENT
# =====================================================

@admin.route("/bookings")
@admin_required
def bookings():
    status = request.args.get("status", "").strip().lower()

    query = Booking.query

    allowed_statuses = {
        "pending",
        "confirmed",
        "rejected",
        "cancelled",
        "completed",
    }

    if status in allowed_statuses:
        query = query.filter(Booking.status == status)

    booking_list = (
        query
        .order_by(Booking.created_at.desc())
        .all()
    )

    return render_template(
        "admin/bookings.html",
        bookings=booking_list,
        selected_status=status,
    )


# =====================================================
# BOOKING DETAILS
# =====================================================

@admin.route("/bookings/<int:booking_id>")
@admin_required
def booking_details(booking_id):
    booking = db.get_or_404(Booking, booking_id)

    return render_template(
        "admin/booking_details.html",
        booking=booking,
    )


# =====================================================
# CUSTOMER MANAGEMENT
# =====================================================

@admin.route("/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    new_status = request.form.get("status", "").strip().lower()
    allowed = {
        "pending": {"confirmed", "rejected", "cancelled"},
        "confirmed": {"completed", "cancelled"},
    }
    if new_status not in allowed.get(booking.status, set()):
        flash("This booking status transition is not allowed.", "danger")
        return redirect(url_for("admin.booking_details", booking_id=booking.id))

    booking.status = new_status
    messages = {
        "confirmed": "Your booking request has been confirmed.",
        "rejected": "Your booking request has been declined.",
        "cancelled": "Your booking has been cancelled by the administrator.",
        "completed": "Your event has been marked as completed.",
    }
    db.session.add(Notification(
        user_id=booking.customer_id,
        title=f"Booking {new_status.title()}",
        message=f"{messages[new_status]} Reference: {booking.booking_reference}.",
        category="booking",
        is_read=False,
    ))
    db.session.commit()
    flash("Booking status updated.", "success")
    return redirect(url_for("admin.booking_details", booking_id=booking.id))


@admin.route("/customers")
@admin_required
def customers():
    search = request.args.get("search", "").strip()

    query = User.query.filter_by(role="customer")

    if search:
        search_pattern = f"%{search}%"

        query = query.filter(
            or_(
                User.full_name.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.phone.ilike(search_pattern),
            )
        )

    customer_list = (
        query
        .order_by(User.created_at.desc())
        .all()
    )

    return render_template(
        "admin/customers.html",
        customers=customer_list,
        search=search,
    )


# =====================================================
# ADMIN REPORTS
# =====================================================

@admin.route("/reports")
@admin_required
def reports():
    total_customers = User.query.filter_by(
        role="customer"
    ).count()

    total_restaurants = RestaurantProfile.query.count()

    approved_restaurants = RestaurantProfile.query.filter_by(
        verification_status="approved"
    ).count()

    pending_restaurants = RestaurantProfile.query.filter_by(
        verification_status="pending"
    ).count()

    total_venues = Venue.query.count()

    published_venues = Venue.query.filter_by(
        is_published=True
    ).count()

    total_bookings = Booking.query.count()

    pending_bookings = Booking.query.filter_by(
        status="pending"
    ).count()

    confirmed_bookings = Booking.query.filter_by(
        status="confirmed"
    ).count()

    completed_bookings = Booking.query.filter_by(
        status="completed"
    ).count()

    cancelled_bookings = Booking.query.filter_by(
        status="cancelled"
    ).count()

    # This is the sum of booking amounts, not collected revenue.
    completed_booking_value = (
        db.session.query(
            func.coalesce(func.sum(Booking.total_amount), 0)
        )
        .filter(Booking.status == "completed")
        .scalar()
    )

    return render_template(
        "admin/reports.html",
        total_customers=total_customers,
        total_restaurants=total_restaurants,
        approved_restaurants=approved_restaurants,
        pending_restaurants=pending_restaurants,
        total_venues=total_venues,
        published_venues=published_venues,
        total_bookings=total_bookings,
        pending_bookings=pending_bookings,
        confirmed_bookings=confirmed_bookings,
        completed_bookings=completed_bookings,
        cancelled_bookings=cancelled_bookings,
        completed_booking_value=completed_booking_value,
    )


# =====================================================
# ADMIN SETTINGS
# =====================================================

@admin.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        if action == "profile":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip() or None
            if not full_name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Enter a valid name and email address.", "danger")
                return redirect(url_for("admin.settings"))
            duplicate = User.query.filter(
                User.id != current_user.id,
                or_(func.lower(User.email) == email, User.phone == phone) if phone else func.lower(User.email) == email,
            ).first()
            if duplicate:
                flash("That email address or phone number is already in use.", "danger")
                return redirect(url_for("admin.settings"))
            current_user.full_name = full_name
            current_user.email = email
            current_user.phone = phone
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Profile could not be saved because the email or phone is already in use.", "danger")
                return redirect(url_for("admin.settings"))
            flash("Administrator profile updated.", "success")
        elif action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not current_user.check_password(current_password):
                flash("Your current password is incorrect.", "danger")
                return redirect(url_for("admin.settings"))
            if len(new_password) < 10 or new_password != confirm_password:
                flash("The new password must be at least 10 characters and both entries must match.", "danger")
                return redirect(url_for("admin.settings"))
            current_user.set_password(new_password)
            db.session.commit()
            flash("Administrator password updated.", "success")
        else:
            flash("Invalid settings action.", "danger")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", admin_user=current_user)
