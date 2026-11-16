
from functools import wraps
import os
import re
from datetime import datetime, date, time

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    flash,
    abort,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.storage import upload_venue_image, delete_venue_image
from app.models import (
    User,
    RestaurantProfile,
    Venue,
    VenueImage,
    Menu,
    MenuItem,
    Package,
    Availability,
    Booking,
    Notification,
)

from app.restaurant import restaurant


# =========================================================
# ACCESS CONTROL AND HELPERS
# =========================================================

def restaurant_required(view_function):
    @wraps(view_function)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "restaurant":
            flash("Please log in with a restaurant account.", "warning")
            return redirect(url_for("auth.restaurant_login"))

        return view_function(*args, **kwargs)

    return decorated_function


def get_profile():
    return RestaurantProfile.query.filter_by(
        user_id=current_user.id
    ).first()


def require_profile():
    profile = get_profile()

    if not profile:
        flash("Please complete your restaurant profile first.", "warning")
        return None

    return profile


def get_owned_venue(venue_id):
    profile = require_profile()

    if not profile:
        return None

    return Venue.query.filter_by(
        id=venue_id,
        restaurant_id=profile.id
    ).first_or_404()


def get_owned_menu(menu_id):
    profile = require_profile()

    if not profile:
        return None

    return (
        Menu.query
        .join(Venue, Menu.venue_id == Venue.id)
        .filter(
            Menu.id == menu_id,
            Venue.restaurant_id == profile.id
        )
        .first_or_404()
    )


def get_owned_package(package_id):
    profile = require_profile()

    if not profile:
        return None

    return (
        Package.query
        .join(Venue, Package.venue_id == Venue.id)
        .filter(
            Package.id == package_id,
            Venue.restaurant_id == profile.id
        )
        .first_or_404()
    )


def parse_decimal(value):
    try:
        from decimal import Decimal, InvalidOperation
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            return None
        return number
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_integer(value):
    try:
        number = int(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def restaurant_can_publish(profile):
    return profile.verification_status == "approved"


def notify_customer(booking, title, message):
    notification = Notification(
        user_id=booking.customer_id,
        title=title,
        message=message,
        category="booking",
        is_read=False,
    )
    db.session.add(notification)


# =========================================================
# RESTAURANT HOME AND DASHBOARD
# =========================================================

@restaurant.route("/")
@restaurant_required
def dashboard():
    profile = get_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_ids = [
        venue.id for venue in profile.venues
    ]

    total_venues = len(venue_ids)

    total_bookings = Booking.query.filter(
        Booking.venue_id.in_(venue_ids)
    ).count() if venue_ids else 0

    pending_bookings = Booking.query.filter(
        Booking.venue_id.in_(venue_ids),
        Booking.status == "pending"
    ).count() if venue_ids else 0

    confirmed_bookings = Booking.query.filter(
        Booking.venue_id.in_(venue_ids),
        Booking.status == "confirmed"
    ).count() if venue_ids else 0

    recent_bookings = (
        Booking.query
        .filter(Booking.venue_id.in_(venue_ids))
        .order_by(Booking.created_at.desc())
        .limit(5)
        .all()
    ) if venue_ids else []

    return render_template(
        "restaurant/dashboard.html",
        profile=profile,
        total_venues=total_venues,
        total_bookings=total_bookings,
        pending_bookings=pending_bookings,
        confirmed_bookings=confirmed_bookings,
        recent_bookings=recent_bookings,
    )


# =========================================================
# RESTAURANT ONBOARDING
# Registration already creates a profile.
# This route updates it instead of creating another one.
# =========================================================

@restaurant.route("/onboarding", methods=["GET", "POST"])
@restaurant_required
def onboarding():
    profile = get_profile()

    if not profile:
        flash(
            "Your restaurant profile was not found. "
            "Please contact the administrator.",
            "danger"
        )
        return redirect(url_for("restaurant.dashboard"))

    if request.method == "POST":
        business_name = request.form.get(
            "business_name", ""
        ).strip()

        business_email = request.form.get(
            "business_email", ""
        ).strip().lower()

        business_phone = request.form.get(
            "business_phone", ""
        ).strip()

        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        description = request.form.get("description", "").strip()

        state = request.form.get("state", "").strip()
        pincode = request.form.get("pincode", "").strip()

        if not all([
            business_name,
            business_email,
            business_phone,
            city,
            address,
        ]):
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("restaurant.onboarding"))

        profile.business_name = business_name
        profile.contact_email = business_email
        profile.contact_phone = business_phone
        profile.city = city
        profile.address = address
        profile.description = description
        profile.state = state or None
        profile.pincode = pincode or None

        db.session.commit()

        flash("Restaurant profile saved successfully.", "success")
        return redirect(url_for("restaurant.dashboard"))

    return render_template(
        "restaurant/onboarding.html",
        profile=profile,
    )


# =========================================================
# RESTAURANT PROFILE
# =========================================================

@restaurant.route("/profile", methods=["GET", "POST"])
@restaurant_required
def profile():
    restaurant_profile = require_profile()

    if not restaurant_profile:
        return redirect(url_for("restaurant.onboarding"))

    if request.method == "POST":
        restaurant_profile.business_name = request.form.get(
            "business_name", ""
        ).strip()

        restaurant_profile.description = request.form.get(
            "description", ""
        ).strip()

        restaurant_profile.contact_email = request.form.get(
            "contact_email", ""
        ).strip().lower()

        restaurant_profile.contact_phone = request.form.get(
            "contact_phone", ""
        ).strip()

        restaurant_profile.address = request.form.get(
            "address", ""
        ).strip()

        restaurant_profile.city = request.form.get(
            "city", ""
        ).strip()

        restaurant_profile.state = request.form.get(
            "state", ""
        ).strip() or None

        restaurant_profile.pincode = request.form.get(
            "pincode", ""
        ).strip() or None

        if not restaurant_profile.business_name:
            flash("Business name is required.", "danger")
            return redirect(url_for("restaurant.profile"))

        db.session.commit()

        flash("Restaurant profile updated.", "success")
        return redirect(url_for("restaurant.profile"))

    return render_template(
        "restaurant/profile.html",
        profile=restaurant_profile,
    )


# =========================================================
# VENUE LIST
# =========================================================

@restaurant.route("/venues")
@restaurant_required
def venues():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_list = (
        Venue.query
        .filter_by(restaurant_id=profile.id)
        .order_by(Venue.created_at.desc())
        .all()
    )

    return render_template(
        "restaurant/venues.html",
        venues=venue_list,
        profile=profile,
    )


# =========================================================
# ADD VENUE
# =========================================================

@restaurant.route("/venues/add", methods=["GET", "POST"])
@restaurant_required
def add_venue():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        venue_type = request.form.get("venue_type", "").strip()
        description = request.form.get("description", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        state = request.form.get("state", "").strip()
        pincode = request.form.get("pincode", "").strip()

        min_capacity = parse_integer(
            request.form.get("min_capacity", "1")
        )

        max_capacity = parse_integer(
            request.form.get("capacity", "")
        )

        price_per_person = parse_decimal(
            request.form.get("price_per_person", "")
        )

        base_price = parse_decimal(
            request.form.get("base_price", "0")
        )

        action = request.form.get("action", "draft").strip()

        if not all([name, venue_type, city, address]):
            flash("Please complete the required venue fields.", "danger")
            return redirect(url_for("restaurant.add_venue"))

        if (
            min_capacity is None
            or max_capacity is None
            or max_capacity < min_capacity
        ):
            flash("Please enter valid venue capacity limits.", "danger")
            return redirect(url_for("restaurant.add_venue"))

        if price_per_person is None or base_price is None:
            flash("Please enter valid venue prices.", "danger")
            return redirect(url_for("restaurant.add_venue"))

        publish_requested = action == "publish"
        can_publish = (
            publish_requested
            and restaurant_can_publish(profile)
        )

        venue = Venue(
            restaurant_id=profile.id,
            name=name,
            venue_type=venue_type,
            description=description,
            city=city,
            address=address,
            state=state or None,
            pincode=pincode or None,
            min_capacity=min_capacity,
            max_capacity=max_capacity,
            price_per_person=price_per_person,
            base_price=base_price,
            status="published" if can_publish else "draft",
            is_published=can_publish,
        )

        db.session.add(venue)
        db.session.commit()

        if publish_requested and not can_publish:
            flash(
                "Venue saved as a draft. Your restaurant must be approved "
                "before venues can be published.",
                "warning",
            )
        else:
            flash("Venue added successfully.", "success")

        return redirect(url_for("restaurant.venues"))

    return render_template("restaurant/add_venue.html")


# =========================================================
# EDIT VENUE
# =========================================================

@restaurant.route(
    "/venues/<int:venue_id>/edit",
    methods=["GET", "POST"]
)
@restaurant_required
def edit_venue(venue_id):
    venue = get_owned_venue(venue_id)

    if not venue:
        return redirect(url_for("restaurant.venues"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        venue_type = request.form.get("venue_type", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()

        min_capacity = parse_integer(
            request.form.get("min_capacity", "1")
        )

        max_capacity = parse_integer(
            request.form.get("capacity", "")
        )

        price_per_person = parse_decimal(
            request.form.get("price_per_person", "")
        )

        base_price = parse_decimal(
            request.form.get("base_price", "0")
        )

        if not all([name, venue_type, city, address]):
            flash("Please complete the required fields.", "danger")
            return redirect(
                url_for("restaurant.edit_venue", venue_id=venue.id)
            )

        if (
            min_capacity is None
            or max_capacity is None
            or max_capacity < min_capacity
            or price_per_person is None
            or base_price is None
        ):
            flash("Please check the capacity and price values.", "danger")
            return redirect(
                url_for("restaurant.edit_venue", venue_id=venue.id)
            )

        venue.name = name
        venue.venue_type = venue_type
        venue.description = request.form.get(
            "description", ""
        ).strip()
        venue.city = city
        venue.address = address
        venue.state = request.form.get("state", "").strip() or None
        venue.pincode = request.form.get("pincode", "").strip() or None
        venue.min_capacity = min_capacity
        venue.max_capacity = max_capacity
        venue.price_per_person = price_per_person
        venue.base_price = base_price

        db.session.commit()

        flash("Venue updated successfully.", "success")
        return redirect(url_for("restaurant.venues"))

    return render_template(
        "restaurant/edit_venue.html",
        venue=venue,
    )


# =========================================================
# MENUS
# =========================================================

@restaurant.route("/menus")
@restaurant_required
def menus():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    menu_list = (
        Menu.query
        .join(Venue, Menu.venue_id == Venue.id)
        .filter(Venue.restaurant_id == profile.id)
        .order_by(Menu.created_at.desc())
        .all()
    )

    return render_template(
        "restaurant/menus.html",
        menus=menu_list,
    )


@restaurant.route("/menus/add", methods=["GET", "POST"])
@restaurant_required
def add_menu():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_list = Venue.query.filter_by(
        restaurant_id=profile.id
    ).all()

    if request.method == "POST":
        venue_id = request.form.get("venue_id", type=int)
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_active = request.form.get("status", "active") == "active"

        venue = Venue.query.filter_by(
            id=venue_id,
            restaurant_id=profile.id
        ).first()

        if not venue or not name:
            flash("Please select a valid venue and menu name.", "danger")
            return redirect(url_for("restaurant.add_menu"))

        menu = Menu(
            venue_id=venue.id,
            name=name,
            description=description,
            is_active=is_active,
        )

        db.session.add(menu)
        db.session.commit()

        flash("Menu created successfully.", "success")
        return redirect(url_for("restaurant.menus"))

    return render_template(
        "restaurant/add_menu.html",
        venues=venue_list,
    )


# =========================================================
# MENU ITEMS
# =========================================================

@restaurant.route("/menus/<int:menu_id>/items")
@restaurant_required
def menu_items(menu_id):
    menu = get_owned_menu(menu_id)

    if not menu:
        return redirect(url_for("restaurant.menus"))

    items = MenuItem.query.filter_by(
        menu_id=menu.id
    ).order_by(MenuItem.category, MenuItem.name).all()

    return render_template(
        "restaurant/menu_items.html",
        menu=menu,
        items=items,
    )


@restaurant.route(
    "/menus/<int:menu_id>/items/add",
    methods=["POST"]
)
@restaurant_required
def add_menu_item(menu_id):
    menu = get_owned_menu(menu_id)

    if not menu:
        return redirect(url_for("restaurant.menus"))

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    dietary_type = request.form.get("dietary_type", "").strip()
    price = parse_decimal(request.form.get("price", ""))

    if not name or price is None:
        flash("Please enter a valid item name and price.", "danger")
        return redirect(
            url_for("restaurant.menu_items", menu_id=menu.id)
        )

    item = MenuItem(
        menu_id=menu.id,
        name=name,
        description=description,
        category=category or None,
        dietary_type=dietary_type or None,
        price=price,
        is_available=True,
    )

    db.session.add(item)
    db.session.commit()

    flash("Menu item added.", "success")
    return redirect(url_for("restaurant.menu_items", menu_id=menu.id))


@restaurant.route(
    "/menu-items/<int:item_id>/toggle",
    methods=["POST"]
)
@restaurant_required
def toggle_menu_item(item_id):
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    item = (
        MenuItem.query
        .join(Menu, MenuItem.menu_id == Menu.id)
        .join(Venue, Menu.venue_id == Venue.id)
        .filter(
            MenuItem.id == item_id,
            Venue.restaurant_id == profile.id
        )
        .first_or_404()
    )

    item.is_available = not item.is_available
    db.session.commit()

    flash("Menu item availability updated.", "success")
    return redirect(
        url_for("restaurant.menu_items", menu_id=item.menu_id)
    )


# =========================================================
# PACKAGES
# =========================================================

@restaurant.route("/packages")
@restaurant_required
def packages():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    package_list = (
        Package.query
        .join(Venue, Package.venue_id == Venue.id)
        .filter(Venue.restaurant_id == profile.id)
        .order_by(Package.created_at.desc())
        .all()
    )

    return render_template(
        "restaurant/packages.html",
        packages=package_list,
    )


@restaurant.route("/packages/add", methods=["GET", "POST"])
@restaurant_required
def add_package():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_list = Venue.query.filter_by(
        restaurant_id=profile.id
    ).all()

    if request.method == "POST":
        venue_id = request.form.get("venue_id", type=int)
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        inclusions = ", ".join(
            value.strip() for value in request.form.getlist("inclusions") if value.strip()
        ) or request.form.get("inclusions_text", "").strip()

        price = parse_decimal(
            request.form.get("price_per_person", "")
        )

        min_guests = parse_integer(
            request.form.get("min_guests", "1")
        )

        max_guests = parse_integer(
            request.form.get("max_guests", "")
        )

        venue = Venue.query.filter_by(
            id=venue_id,
            restaurant_id=profile.id
        ).first()

        if (
            not venue
            or not name
            or price is None
            or min_guests is None
            or max_guests is None
            or min_guests < 1
            or max_guests < min_guests
        ):
            flash("Please check the package details.", "danger")
            return redirect(url_for("restaurant.add_package"))

        package = Package(
            venue_id=venue.id,
            name=name,
            description=description,
            inclusions=inclusions,
            price_per_person=price,
            min_guests=min_guests,
            max_guests=max_guests,
            is_active=request.form.get("status", "active") == "active",
        )

        db.session.add(package)
        db.session.commit()

        flash("Package created successfully.", "success")
        return redirect(url_for("restaurant.packages"))

    return render_template(
        "restaurant/add_package.html",
        venues=venue_list,
    )


@restaurant.route(
    "/packages/<int:package_id>/edit",
    methods=["GET", "POST"]
)
@restaurant_required
def edit_package(package_id):
    package = get_owned_package(package_id)

    if not package:
        return redirect(url_for("restaurant.packages"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = parse_decimal(
            request.form.get("price_per_person", "")
        )
        min_guests = parse_integer(
            request.form.get("min_guests", "1")
        )
        max_guests = parse_integer(
            request.form.get("max_guests", "")
        )

        if (
            not name
            or price is None
            or min_guests is None
            or max_guests is None
            or min_guests < 1
            or max_guests < min_guests
        ):
            flash("Please check the package details.", "danger")
            return redirect(
                url_for("restaurant.edit_package", package_id=package.id)
            )

        package.name = name
        package.description = request.form.get(
            "description", ""
        ).strip()
        package.inclusions = ", ".join(
            value.strip() for value in request.form.getlist("inclusions") if value.strip()
        ) or request.form.get("inclusions_text", "").strip()
        package.price_per_person = price
        package.min_guests = min_guests
        package.max_guests = max_guests
        package.is_active = request.form.get("status", "active") == "active"

        db.session.commit()

        flash("Package updated successfully.", "success")
        return redirect(url_for("restaurant.packages"))

    return render_template(
        "restaurant/add_package.html",
        package=package,
        venues=[package.venue],
        editing=True,
    )


@restaurant.route(
    "/packages/<int:package_id>/toggle",
    methods=["POST"]
)
@restaurant_required
def toggle_package(package_id):
    package = get_owned_package(package_id)

    if not package:
        return redirect(url_for("restaurant.packages"))

    package.is_active = not package.is_active
    db.session.commit()

    flash("Package availability updated.", "success")
    return redirect(url_for("restaurant.packages"))


# =========================================================
# AVAILABILITY
# =========================================================

@restaurant.route("/availability")
@restaurant_required
def availability():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_list = Venue.query.filter_by(
        restaurant_id=profile.id
    ).all()

    venue_ids = [venue.id for venue in venue_list]

    slots = (
        Availability.query
        .filter(Availability.venue_id.in_(venue_ids))
        .order_by(Availability.available_date.asc())
        .all()
    ) if venue_ids else []

    return render_template(
        "restaurant/availability.html",
        venues=venue_list,
        availability=slots,
        now_date=date.today().isoformat(),
    )


@restaurant.route("/availability/add", methods=["POST"])
@restaurant_required
def add_availability():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_id = request.form.get("venue_id", type=int)
    date_value = request.form.get("available_date", "").strip()
    start_value = request.form.get("start_time", "").strip()
    end_value = request.form.get("end_time", "").strip()
    notes = request.form.get("notes", "").strip()

    venue = Venue.query.filter_by(
        id=venue_id,
        restaurant_id=profile.id
    ).first()

    try:
        available_date = datetime.strptime(
            date_value, "%Y-%m-%d"
        ).date()

        start_time = datetime.strptime(
            start_value, "%H:%M"
        ).time()

        end_time = datetime.strptime(
            end_value, "%H:%M"
        ).time()
    except (ValueError, TypeError):
        venue = None
        available_date = None
        start_time = None
        end_time = None

    if (
        not venue
        or not available_date
        or not start_time
        or not end_time
        or end_time <= start_time
    ):
        flash("Please enter valid availability details.", "danger")
        return redirect(url_for("restaurant.availability"))

    if available_date < date.today():
        flash("Availability cannot be added for a past date.", "danger")
        return redirect(url_for("restaurant.availability"))

    overlapping_slot = Availability.query.filter(
        Availability.venue_id == venue.id,
        Availability.available_date == available_date,
        Availability.start_time < end_time,
        Availability.end_time > start_time,
    ).first()
    if overlapping_slot:
        flash("This time range overlaps an existing availability slot.", "warning")
        return redirect(url_for("restaurant.availability"))

    slot = Availability(
        venue_id=venue.id,
        available_date=available_date,
        start_time=start_time,
        end_time=end_time,
        is_available=True,
        notes=notes,
    )

    db.session.add(slot)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(
            "This availability slot may already exist. "
            "Please check your calendar.",
            "warning",
        )
        return redirect(url_for("restaurant.availability"))

    flash("Availability added successfully.", "success")
    return redirect(url_for("restaurant.availability"))


@restaurant.route(
    "/availability/<int:slot_id>/toggle",
    methods=["POST"]
)
@restaurant_required
def toggle_availability(slot_id):
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    slot = (
        Availability.query
        .join(Venue, Availability.venue_id == Venue.id)
        .filter(
            Availability.id == slot_id,
            Venue.restaurant_id == profile.id
        )
        .first_or_404()
    )

    if slot.is_available:
        blocking_booking = Booking.query.filter(
            Booking.venue_id == slot.venue_id,
            Booking.event_date == slot.available_date,
            Booking.status.in_(("pending", "confirmed")),
            Booking.start_time < slot.end_time,
            Booking.end_time > slot.start_time,
        ).first()
        if blocking_booking:
            flash("This slot has a pending or confirmed booking and cannot be blocked.", "warning")
            return redirect(url_for("restaurant.availability"))

    slot.is_available = not slot.is_available
    db.session.commit()

    flash("Availability updated.", "success")
    return redirect(url_for("restaurant.availability"))


# =========================================================
# BOOKING REQUESTS
# =========================================================

@restaurant.route("/booking-requests")
@restaurant_required
def booking_requests():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_ids = [venue.id for venue in profile.venues]

    requests_list = (
        Booking.query
        .filter(Booking.venue_id.in_(venue_ids))
        .order_by(Booking.created_at.desc())
        .all()
    ) if venue_ids else []

    return render_template(
        "restaurant/booking_requests.html",
        bookings=requests_list,
    )


# =========================================================
# UPCOMING EVENTS
# =========================================================

@restaurant.route("/upcoming-events")
@restaurant_required
def upcoming_events():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_ids = [venue.id for venue in profile.venues]

    events = (
        Booking.query
        .filter(
            Booking.venue_id.in_(venue_ids),
            Booking.status == "confirmed",
            Booking.event_date >= date.today(),
        )
        .order_by(Booking.event_date.asc())
        .all()
    ) if venue_ids else []

    return render_template(
        "restaurant/upcoming_events.html",
        events=events,
    )


# =========================================================
# BOOKING DETAILS
# =========================================================

@restaurant.route("/bookings/<int:booking_id>")
@restaurant_required
def booking_details(booking_id):
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_ids = [venue.id for venue in profile.venues]

    booking = Booking.query.filter(
        Booking.id == booking_id,
        Booking.venue_id.in_(venue_ids),
    ).first_or_404()

    return render_template(
        "restaurant/booking_details.html",
        booking=booking,
    )


# =========================================================
# UPDATE BOOKING STATUS
# =========================================================

@restaurant.route(
    "/bookings/<int:booking_id>/status",
    methods=["POST"]
)
@restaurant_required
def update_booking_status(booking_id):
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    venue_ids = [venue.id for venue in profile.venues]

    booking = Booking.query.filter(
        Booking.id == booking_id,
        Booking.venue_id.in_(venue_ids),
    ).first_or_404()

    new_status = request.form.get("status", "").strip().lower()

    allowed_transitions = {
        "pending": {"confirmed", "rejected"},
        "confirmed": {"completed"},
    }

    permitted = allowed_transitions.get(booking.status, set())

    if new_status not in permitted:
        flash("This booking status change is not allowed.", "danger")
        return redirect(
            url_for(
                "restaurant.booking_details",
                booking_id=booking.id
            )
        )

    booking.status = new_status

    if new_status == "confirmed":
        notify_customer(
            booking,
            "Booking confirmed",
            f"Your booking {booking.booking_reference} "
            f"has been confirmed by the restaurant.",
        )
    elif new_status == "rejected":
        notify_customer(
            booking,
            "Booking request declined",
            f"Your booking request {booking.booking_reference} "
            f"was declined by the restaurant.",
        )
    elif new_status == "completed":
        notify_customer(
            booking,
            "Event completed",
            f"Your event for booking {booking.booking_reference} "
            f"has been marked as completed.",
        )

    db.session.commit()

    flash("Booking status updated successfully.", "success")

    return redirect(
        url_for(
            "restaurant.booking_details",
            booking_id=booking.id
        )
    )


# =========================================================
# RESTAURANT SETTINGS
# =========================================================

@restaurant.route("/settings", methods=["GET", "POST"])
@restaurant_required
def settings():
    profile = require_profile()

    if not profile:
        return redirect(url_for("restaurant.onboarding"))

    if request.method == "POST":
        profile.business_name = request.form.get(
            "business_name", profile.business_name
        ).strip() or profile.business_name
        profile.contact_email = contact_email
        profile.contact_phone = contact_phone

        db.session.commit()

        flash("Settings updated successfully.", "success")
        return redirect(url_for("restaurant.settings"))

    return render_template(
        "restaurant/settings.html",
        profile=profile,
    )


# =========================================================
# VENUE PHOTOS — Supabase Storage
# =========================================================

@restaurant.route("/venues/<int:venue_id>/photos")
@restaurant_required
def venue_photos(venue_id):
    venue = get_owned_venue(venue_id)
    if not venue:
        abort(404)
    photos = VenueImage.query.filter_by(
        venue_id=venue.id
    ).order_by(VenueImage.is_primary.desc(), VenueImage.created_at.desc()).all()
    return render_template("restaurant/venue_photos.html", venue=venue, photos=photos)


@restaurant.route("/venues/<int:venue_id>/photos/upload", methods=["POST"])
@restaurant_required
def upload_venue_photos(venue_id):
    venue = get_owned_venue(venue_id)
    if not venue:
        abort(404)
    files = request.files.getlist("photos")
    files = [item for item in files if item and item.filename]
    if not files:
        flash("Choose at least one image to upload.", "warning")
        return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))
    if len(files) > 4:
        flash("Upload a maximum of four images at a time.", "warning")
        return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))

    profile = require_profile()
    uploaded = 0
    try:
        for item in files:
            if not item or not item.filename:
                continue
            object_path, public_url = upload_venue_image(
                item, profile.id, venue.id
            )
            image = VenueImage(
                venue_id=venue.id,
                image_path=public_url,
                storage_path=object_path,
                is_primary=(VenueImage.query.filter_by(venue_id=venue.id).count() == 0),
            )
            db.session.add(image)
            uploaded += 1
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "Image upload failed. Check storage configuration.", "danger")
        return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))

    flash(f"{uploaded} image(s) uploaded successfully.", "success")
    return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))


@restaurant.route("/venues/<int:venue_id>/photos/<int:photo_id>/delete", methods=["POST"])
@restaurant_required
def delete_venue_photo(venue_id, photo_id):
    venue = get_owned_venue(venue_id)
    if not venue:
        abort(404)
    photo = VenueImage.query.filter_by(id=photo_id, venue_id=venue.id).first_or_404()
    # Only objects under the current venue's storage prefix can be deleted.
    profile = require_profile()
    prefix = f"restaurants/{profile.id}/venues/{venue.id}/"
    object_path = photo.storage_path
    if object_path and object_path.startswith(prefix):
        try:
            delete_venue_image(object_path)
        except Exception:
            flash("The image could not be removed from storage.", "danger")
            return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))
    db.session.delete(photo)
    db.session.commit()
    flash("Venue photo removed.", "success")
    return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))


@restaurant.route("/venues/<int:venue_id>/photos/<int:photo_id>/primary", methods=["POST"])
@restaurant_required
def set_primary_venue_photo(venue_id, photo_id):
    venue = get_owned_venue(venue_id)
    if not venue:
        abort(404)
    photo = VenueImage.query.filter_by(id=photo_id, venue_id=venue.id).first_or_404()
    VenueImage.query.filter_by(venue_id=venue.id).update({"is_primary": False})
    photo.is_primary = True
    db.session.commit()
    flash("Cover photo updated.", "success")
    return redirect(url_for("restaurant.venue_photos", venue_id=venue.id))
