
from functools import wraps
import re

from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.models import (
    User,
    RestaurantProfile,
    Venue,
    Menu,
    MenuItem,
    Package,
    Booking,
    Notification,
)

from app.customer import customer


# ==================================================
# CUSTOMER ACCESS CONTROL
# ==================================================

def customer_required(view_function):
    @wraps(view_function)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "customer":
            flash(
                "You do not have permission to access this page.",
                "danger",
            )
            return redirect(url_for("home"))

        return view_function(*args, **kwargs)

    return decorated_function


# ==================================================
# PUBLIC VENUE QUERY
# Only published venues of approved restaurants
# are visible to customers and visitors.
# ==================================================

def public_venues_query():
    return (
        Venue.query
        .join(
            RestaurantProfile,
            Venue.restaurant_id == RestaurantProfile.id,
        )
        .filter(
            Venue.is_published.is_(True),
            Venue.status == "published",
            RestaurantProfile.verification_status == "approved",
        )
    )


# ==================================================
# CUSTOMER DASHBOARD
# ==================================================

@customer.route("/dashboard")
@customer_required
def dashboard():
    recent_bookings = (
        Booking.query
        .filter_by(customer_id=current_user.id)
        .order_by(Booking.created_at.desc())
        .limit(5)
        .all()
    )

    total_bookings = Booking.query.filter_by(
        customer_id=current_user.id
    ).count()

    pending_bookings = Booking.query.filter_by(
        customer_id=current_user.id,
        status="pending",
    ).count()

    confirmed_bookings = Booking.query.filter_by(
        customer_id=current_user.id,
        status="confirmed",
    ).count()

    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).count()

    return render_template(
        "customer/dashboard.html",
        bookings=recent_bookings,
        total_bookings=total_bookings,
        pending_bookings=pending_bookings,
        confirmed_bookings=confirmed_bookings,
        unread_notifications=unread_notifications,
    )


# ==================================================
# EXPLORE VENUES
# ==================================================

@customer.route("/explore")
def explore():
    # Keep one canonical discovery implementation and one set of filter parameters.
    return redirect(url_for("venues.explore", **request.args))


@customer.route("/venue/<int:venue_id>")
def venue_details(venue_id):
    venue = (
        public_venues_query()
        .filter(Venue.id == venue_id)
        .first_or_404()
    )

    images = venue.images

    menus = (
        Menu.query
        .filter_by(
            venue_id=venue.id,
            is_active=True,
        )
        .order_by(Menu.name.asc())
        .all()
    )

    packages = (
        Package.query
        .filter_by(
            venue_id=venue.id,
            is_active=True,
        )
        .order_by(Package.price_per_person.asc())
        .all()
    )

    return render_template(
        "customer/venue_details.html",
        venue=venue,
        images=images,
        menus=menus,
        packages=packages,
    )


# ==================================================
# VENUE MENUS
# ==================================================

@customer.route("/venue/<int:venue_id>/menu")
def venue_menu(venue_id):
    venue = (
        public_venues_query()
        .filter(Venue.id == venue_id)
        .first_or_404()
    )

    menus = (
        Menu.query
        .filter_by(
            venue_id=venue.id,
            is_active=True,
        )
        .order_by(Menu.name.asc())
        .all()
    )

    menu_items = (
        MenuItem.query
        .join(Menu, MenuItem.menu_id == Menu.id)
        .filter(
            Menu.venue_id == venue.id,
            Menu.is_active.is_(True),
            MenuItem.is_available.is_(True),
        )
        .order_by(
            MenuItem.category.asc(),
            MenuItem.name.asc(),
        )
        .all()
    )

    return render_template(
        "customer/menu_selection.html",
        venue=venue,
        menus=menus,
        menu_items=menu_items,
    )


# ==================================================
# VENUE PACKAGES
# ==================================================

@customer.route("/venue/<int:venue_id>/packages")
def venue_packages(venue_id):
    venue = (
        public_venues_query()
        .filter(Venue.id == venue_id)
        .first_or_404()
    )

    packages = (
        Package.query
        .filter_by(
            venue_id=venue.id,
            is_active=True,
        )
        .order_by(Package.price_per_person.asc())
        .all()
    )

    return render_template(
        "customer/packages.html",
        venue=venue,
        packages=packages,
    )


# ==================================================
# CUSTOMER PROFILE
# ==================================================

@customer.route("/profile", methods=["GET", "POST"])
@customer_required
def profile():
    if request.method == "POST":
        full_name = request.form.get(
            "full_name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        phone = request.form.get(
            "phone", ""
        ).strip()

        # Required field validation.
        if not full_name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("customer.profile"))

        # Basic email format validation.
        email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.match(email_pattern, email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("customer.profile"))

        # Check whether another user already has this email.
        existing_email = User.query.filter(
            User.email == email,
            User.id != current_user.id,
        ).first()

        if existing_email:
            flash("This email address is already registered.", "danger")
            return redirect(url_for("customer.profile"))

        # Check whether another user already has this phone number.
        if phone:
            existing_phone = User.query.filter(
                User.phone == phone,
                User.id != current_user.id,
            ).first()

            if existing_phone:
                flash("This phone number is already registered.", "danger")
                return redirect(url_for("customer.profile"))

        current_user.full_name = full_name
        current_user.email = email
        current_user.phone = phone or None

        try:
            db.session.commit()
            flash("Your profile has been updated successfully.", "success")

        except IntegrityError:
            db.session.rollback()
            flash(
                "This email or phone number is already in use.",
                "danger",
            )

        except SQLAlchemyError:
            db.session.rollback()
            flash(
                "Unable to update your profile. Please try again.",
                "danger",
            )

        return redirect(url_for("customer.profile"))

    return render_template(
        "customer/profile.html",
        user=current_user,
    )


# ==================================================
# CUSTOMER BOOKINGS
# ==================================================

@customer.route("/bookings")
@customer_required
def my_bookings():
    status = request.args.get(
        "status", ""
    ).strip().lower()

    allowed_statuses = {
        "pending",
        "confirmed",
        "rejected",
        "cancelled",
        "completed",
    }

    query = Booking.query.filter_by(
        customer_id=current_user.id
    )

    if status:
        if status not in allowed_statuses:
            flash("Invalid booking status filter.", "warning")
            return redirect(url_for("customer.my_bookings"))

        query = query.filter(
            Booking.status == status
        )

    customer_bookings = (
        query
        .order_by(Booking.created_at.desc())
        .all()
    )

    return render_template(
        "customer/my_bookings.html",
        bookings=customer_bookings,
        selected_status=status,
    )


# ==================================================
# CUSTOMER BOOKING DETAILS
# Customers can only view their own bookings.
# ==================================================

@customer.route("/bookings/<int:booking_id>")
@customer_required
def booking_details(booking_id):
    booking = Booking.query.filter_by(
        id=booking_id,
        customer_id=current_user.id,
    ).first_or_404()

    return render_template(
        "customer/booking_details.html",
        booking=booking,
    )


# ==================================================
# CUSTOMER NOTIFICATIONS
# ==================================================

@customer.route("/notifications")
@customer_required
def notifications():
    user_notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    return render_template(
        "customer/notifications.html",
        notifications=user_notifications,
    )


# ==================================================
# MARK ONE NOTIFICATION AS READ
# ==================================================

@customer.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"],
)
@customer_required
def mark_notification_read(notification_id):
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id,
    ).first_or_404()

    notification.is_read = True

    try:
        db.session.commit()
        flash("Notification marked as read.", "success")

    except SQLAlchemyError:
        db.session.rollback()
        flash("Unable to update the notification.", "danger")

    return redirect(url_for("customer.notifications"))


# ==================================================
# MARK ALL NOTIFICATIONS AS READ
# ==================================================

@customer.route(
    "/notifications/read-all",
    methods=["POST"],
)
@customer_required
def mark_all_notifications_read():
    try:
        Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False,
        ).update(
            {"is_read": True},
            synchronize_session=False,
        )

        db.session.commit()
        flash("All notifications marked as read.", "success")

    except SQLAlchemyError:
        db.session.rollback()
        flash("Unable to update your notifications.", "danger")

    return redirect(url_for("customer.notifications"))
