
import secrets
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    RestaurantProfile,
    Venue,
    Package,
    Availability,
    Booking,
    Notification,
)
from app.bookings import bookings


# =====================================================
# CUSTOMER ACCESS
# =====================================================

def customer_required(view_function):
    from functools import wraps

    @wraps(view_function)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "customer":
            flash("Please log in with a customer account.", "warning")
            return redirect(url_for("auth.login"))

        return view_function(*args, **kwargs)

    return decorated_function


# =====================================================
# HELPERS
# =====================================================

def get_public_venue(venue_id):
    return (
        Venue.query
        .join(
            RestaurantProfile,
            Venue.restaurant_id == RestaurantProfile.id
        )
        .filter(
            Venue.id == venue_id,
            Venue.is_published.is_(True),
            Venue.status == "published",
            RestaurantProfile.verification_status == "approved",
        )
        .first()
    )


def calculate_total(venue, package, guests):
    if package:
        per_person_price = Decimal(str(package.price_per_person or 0))
    else:
        per_person_price = Decimal(str(venue.price_per_person or 0))

    base_price = Decimal(str(venue.base_price or 0))

    return (
        per_person_price * Decimal(guests) + base_price
    ).quantize(Decimal("0.01"))


def get_selected_package(package_id, venue_id):
    if not package_id:
        return None

    try:
        package_id = int(package_id)
    except (ValueError, TypeError):
        return None

    return Package.query.filter_by(
        id=package_id,
        venue_id=venue_id,
        is_active=True,
    ).first()


def booking_end_time(start_time, duration_label):
    duration_hours = {
        "2 hours": 2, "3 hours": 3, "4 hours": 4,
        "5 hours": 5, "Full day": 12,
    }.get(duration_label)
    if not duration_hours:
        raise ValueError("Unsupported event duration")
    start_dt = datetime.combine(date.today(), start_time)
    end_dt = start_dt + timedelta(hours=duration_hours)
    if end_dt.date() != start_dt.date():
        raise ValueError("Event duration cannot extend past midnight")
    return end_dt.time()


def validate_booking_slot(venue_id, event_date, start_time, end_time):
    # A restaurant must explicitly publish an available slot.
    available_slot = Availability.query.filter(
        Availability.venue_id == venue_id,
        Availability.available_date == event_date,
        Availability.is_available.is_(True),
        Availability.start_time <= start_time,
        Availability.end_time >= end_time,
    ).first()
    if not available_slot:
        return False, "This venue has not marked the requested time as available."

    blocking_statuses = ("pending", "confirmed")
    conflict = Booking.query.filter(
        Booking.venue_id == venue_id,
        Booking.event_date == event_date,
        Booking.status.in_(blocking_statuses),
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    ).first()
    if conflict:
        return False, "This venue already has a booking that overlaps your requested time."
    return True, None


def create_booking_notification(booking):
    profile = RestaurantProfile.query.filter_by(
        id=booking.venue.restaurant_id
    ).first()

    if not profile:
        return

    notification = Notification(
        user_id=profile.user_id,
        title="New booking request",
        message=(
            f"New booking request {booking.booking_reference} "
            f"received for {booking.venue.name}."
        ),
        category="booking",
        is_read=False,
    )

    db.session.add(notification)


def generate_booking_reference():
    # Retry if the randomly generated reference already exists.
    for _ in range(5):
        reference = "PP-" + secrets.token_hex(4).upper()

        exists = Booking.query.filter_by(
            booking_reference=reference
        ).first()

        if not exists:
            return reference

    raise RuntimeError("Could not generate a unique booking reference.")


# =====================================================
# 1. CREATE BOOKING REQUEST
# =====================================================

@bookings.route(
    "/customer/venue/<int:venue_id>/book",
    methods=["GET", "POST"]
)
@customer_required
def create_booking(venue_id):
    venue = get_public_venue(venue_id)

    if not venue:
        flash("This venue is currently unavailable.", "warning")
        return redirect(url_for("customer.explore"))

    packages = Package.query.filter_by(
        venue_id=venue.id,
        is_active=True,
    ).order_by(Package.name.asc()).all()

    if request.method == "GET":
        selected_package = get_selected_package(
            request.args.get("package_id"), venue.id
        ) if request.args.get("package_id") else None
        return render_template(
            "customer/booking_form.html",
            venue=venue,
            packages=packages,
            selected_package=selected_package,
        )

    event_name = request.form.get("event_name", "").strip()
    event_type = request.form.get("event_type", "").strip()
    duration = request.form.get("duration", "").strip()
    organiser_name = request.form.get("organiser_name", "").strip()
    company_name = request.form.get("company_name", "").strip()
    contact_email = request.form.get("email", "").strip().lower()
    contact_phone = request.form.get("phone", "").strip()
    event_date_text = request.form.get("event_date", "").strip()
    event_time_text = request.form.get("event_time", "").strip()
    guests_text = request.form.get("guests", "").strip()
    special_requests = request.form.get(
        "special_requests", ""
    ).strip()
    package_id_text = request.form.get("package_id", "").strip()

    if not all([
        event_type,
        event_date_text,
        event_time_text,
        guests_text,
        organiser_name,
        contact_email,
        contact_phone,
    ]):
        flash("Please complete all required booking fields.", "danger")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    try:
        event_date = datetime.strptime(
            event_date_text, "%Y-%m-%d"
        ).date()

        event_time = datetime.strptime(
            event_time_text, "%H:%M"
        ).time()

        guests = int(guests_text)

    except (ValueError, TypeError):
        flash("Please enter a valid date, time and guest count.", "danger")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    if event_date < date.today():
        flash("Please select a future event date.", "danger")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    if guests < 1:
        flash("Guest count must be at least one.", "danger")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    if guests < (venue.min_capacity or 1):
        flash(
            f"This venue requires at least {venue.min_capacity} guests.",
            "danger",
        )
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    if venue.max_capacity and guests > venue.max_capacity:
        flash(
            f"This venue can accommodate at most "
            f"{venue.max_capacity} guests.",
            "danger",
        )
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    allowed_durations = {
        "2 hours": 2, "3 hours": 3, "4 hours": 4,
        "5 hours": 5, "Full day": 12,
    }
    if duration not in allowed_durations:
        flash("Please select a valid event duration.", "danger")
        return redirect(url_for("bookings.create_booking", venue_id=venue.id))

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact_email):
        flash("Please enter a valid contact email.", "danger")
        return redirect(url_for("bookings.create_booking", venue_id=venue.id))

    if not re.fullmatch(r"[6-9]\d{9}", contact_phone):
        flash("Please enter a valid 10-digit contact number.", "danger")
        return redirect(url_for("bookings.create_booking", venue_id=venue.id))

    package = None

    if package_id_text:
        package = get_selected_package(package_id_text, venue.id)

        if not package:
            flash("The selected package is invalid or unavailable.", "danger")
            return redirect(
                url_for("bookings.create_booking", venue_id=venue.id)
            )

        if package.min_guests and guests < package.min_guests:
            flash("Guest count is below the package minimum.", "danger")
            return redirect(
                url_for("bookings.create_booking", venue_id=venue.id)
            )

        if package.max_guests and guests > package.max_guests:
            flash("Guest count exceeds the package maximum.", "danger")
            return redirect(
                url_for("bookings.create_booking", venue_id=venue.id)
            )

    session["booking_draft"] = {
        "customer_id": current_user.id,
        "venue_id": venue.id,
        "package_id": package.id if package else None,
        "event_name": event_name or event_type,
        "event_type": event_type,
        "event_date": event_date.isoformat(),
        "start_time": event_time.strftime("%H:%M"),
        "duration": duration,
        "organiser_name": organiser_name,
        "company_name": company_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "guest_count": guests,
        "special_requests": special_requests,
    }

    return redirect(url_for("bookings.booking_summary"))


# =====================================================
# 2. BOOKING SUMMARY
# =====================================================

@bookings.route("/customer/booking/summary")
@customer_required
def booking_summary():
    draft = session.get("booking_draft")

    if not draft or draft.get("customer_id") != current_user.id:
        flash("Please enter your booking details first.", "warning")
        return redirect(url_for("customer.explore"))

    venue = get_public_venue(draft["venue_id"])

    if not venue:
        session.pop("booking_draft", None)
        flash("This venue is no longer available.", "warning")
        return redirect(url_for("customer.explore"))

    package = None

    if draft.get("package_id"):
        package = get_selected_package(
            draft["package_id"],
            venue.id,
        )

        if not package:
            session.pop("booking_draft", None)
            flash("The selected package is no longer available.", "warning")
            return redirect(
                url_for("bookings.create_booking", venue_id=venue.id)
            )

    total_amount = calculate_total(
        venue,
        package,
        int(draft["guest_count"]),
    )

    return render_template(
        "customer/booking_summary.html",
        venue=venue,
        package=package,
        draft=draft,
        total_amount=total_amount,
        customer=current_user,
    )


# =====================================================
# 3. CONFIRM BOOKING
# =====================================================

@bookings.route(
    "/customer/booking/confirm",
    methods=["POST"]
)
@customer_required
def confirm_booking():
    draft = session.get("booking_draft")

    if not draft or draft.get("customer_id") != current_user.id:
        flash("Your booking session has expired. Please try again.", "warning")
        return redirect(url_for("customer.explore"))

    # Serialize confirmations for this venue while availability is checked.
    venue = (
        Venue.query.filter_by(id=draft["venue_id"])
        .with_for_update()
        .first()
    )
    if venue:
        venue = get_public_venue(venue.id)

    if not venue:
        session.pop("booking_draft", None)
        flash("This venue is no longer available.", "warning")
        return redirect(url_for("customer.explore"))

    package = None

    if draft.get("package_id"):
        package = get_selected_package(
            draft["package_id"],
            venue.id,
        )

        if not package:
            session.pop("booking_draft", None)
            flash("The selected package is no longer available.", "warning")
            return redirect(
                url_for("bookings.create_booking", venue_id=venue.id)
            )

    guests = int(draft["guest_count"])

    # Recheck venue capacity before saving.
    if guests < (venue.min_capacity or 1) or (
        venue.max_capacity and guests > venue.max_capacity
    ):
        session.pop("booking_draft", None)
        flash("The guest count is no longer valid for this venue.", "warning")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    if package and (
        (package.min_guests and guests < package.min_guests)
        or (package.max_guests and guests > package.max_guests)
    ):
        session.pop("booking_draft", None)
        flash("The package guest limits are no longer valid.", "warning")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    event_date = datetime.strptime(
        draft["event_date"], "%Y-%m-%d"
    ).date()

    if event_date < date.today():
        session.pop("booking_draft", None)
        flash("The event date has passed. Please book again.", "warning")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    start_time = datetime.strptime(
        draft["start_time"], "%H:%M"
    ).time()
    try:
        end_time = booking_end_time(start_time, draft["duration"])
    except ValueError:
        flash("The selected event duration is invalid for this start time.", "danger")
        return redirect(url_for("bookings.create_booking", venue_id=venue.id))

    is_available, availability_error = validate_booking_slot(
        venue.id, event_date, start_time, end_time
    )
    if not is_available:
        flash(availability_error, "warning")
        return redirect(url_for("bookings.create_booking", venue_id=venue.id))

    total_amount = calculate_total(venue, package, guests)

    booking = Booking(
        booking_reference=generate_booking_reference(),
        customer_id=current_user.id,
        venue_id=venue.id,
        package_id=package.id if package else None,
        event_name=draft.get("event_name"),
        event_type=draft["event_type"],
        event_date=event_date,
        duration=draft.get("duration"),
        organiser_name=draft.get("organiser_name"),
        company_name=draft.get("company_name"),
        contact_email=draft.get("contact_email"),
        contact_phone=draft.get("contact_phone"),
        start_time=start_time,
        end_time=end_time,
        guest_count=guests,
        special_requests=draft["special_requests"],
        total_amount=total_amount,
        status="pending",
    )

    try:
        db.session.add(booking)
        db.session.flush()

        create_booking_notification(booking)
        db.session.add(Notification(
            user_id=current_user.id,
            title="Booking request received",
            message=(
                f"Your booking request {booking.booking_reference} "
                f"for {booking.venue.name} has been submitted."
            ),
            category="booking",
            is_read=False,
        ))

        db.session.commit()

    except Exception:
        db.session.rollback()
        flash("We could not save your booking. Please try again.", "danger")
        return redirect(
            url_for("bookings.create_booking", venue_id=venue.id)
        )

    session.pop("booking_draft", None)

    return redirect(
        url_for(
            "bookings.booking_success",
            booking_id=booking.id,
        )
    )


# =====================================================
# 4. BOOKING SUCCESS
# =====================================================

@bookings.route("/customer/booking/success/<int:booking_id>")
@customer_required
def booking_success(booking_id):
    booking = Booking.query.filter_by(
        id=booking_id,
        customer_id=current_user.id,
    ).first_or_404()

    return render_template(
        "customer/booking_success.html",
        booking=booking,
    )


# =====================================================
# 5. CANCEL CUSTOMER BOOKING
# =====================================================

@bookings.route(
    "/customer/bookings/<int:booking_id>/cancel",
    methods=["POST"]
)
@customer_required
def cancel_booking(booking_id):
    booking = Booking.query.filter_by(
        id=booking_id,
        customer_id=current_user.id,
    ).first_or_404()

    if booking.status != "pending":
        flash(
            "Only pending bookings can be cancelled through this page.",
            "warning",
        )
        return redirect(
            url_for(
                "customer.booking_details",
                booking_id=booking.id,
            )
        )

    booking.status = "cancelled"

    profile = RestaurantProfile.query.filter_by(
        id=booking.venue.restaurant_id
    ).first()

    if profile:
        notification = Notification(
            user_id=profile.user_id,
            title="Booking cancelled",
            message=(
                f"Booking {booking.booking_reference} "
                f"has been cancelled by the customer."
            ),
            category="booking",
            is_read=False,
        )
        db.session.add(notification)

    db.session.commit()

    flash("Your booking has been cancelled.", "success")

    return redirect(url_for("customer.my_bookings"))
