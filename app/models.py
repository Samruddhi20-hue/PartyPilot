
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint, Index, CheckConstraint

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


# =====================================================
# 1. USER MODEL
# =====================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default="customer")

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now
    )

    restaurant_profile = db.relationship(
        "RestaurantProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    bookings = db.relationship(
        "Booking",
        back_populates="customer",
        foreign_keys="Booking.customer_id"
    )

    notifications = db.relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, role):
        return self.role == role

    def __repr__(self):
        return f"<User {self.email}>"


# =====================================================
# 2. RESTAURANT PROFILE MODEL
# =====================================================

class RestaurantProfile(db.Model):
    __tablename__ = "restaurant_profiles"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    business_name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)

    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(20))

    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(12))

    verification_status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    user = db.relationship(
        "User",
        back_populates="restaurant_profile"
    )

    venues = db.relationship(
        "Venue",
        back_populates="restaurant",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<RestaurantProfile {self.business_name}>"


# =====================================================
# 3. VENUE MODEL
# =====================================================

class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.Integer, primary_key=True)

    restaurant_id = db.Column(
        db.Integer,
        db.ForeignKey("restaurant_profiles.id"),
        nullable=False
    )

    name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    venue_type = db.Column(db.String(100))

    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(12))

    min_capacity = db.Column(db.Integer, default=1)
    max_capacity = db.Column(db.Integer, nullable=False)

    price_per_person = db.Column(db.Numeric(12, 2), default=0)
    base_price = db.Column(db.Numeric(12, 2), default=0)

    status = db.Column(db.String(20), default="draft", nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now
    )

    restaurant = db.relationship(
        "RestaurantProfile",
        back_populates="venues"
    )

    images = db.relationship(
        "VenueImage",
        back_populates="venue",
        cascade="all, delete-orphan"
    )

    menus = db.relationship(
        "Menu",
        back_populates="venue",
        cascade="all, delete-orphan"
    )

    packages = db.relationship(
        "Package",
        back_populates="venue",
        cascade="all, delete-orphan"
    )

    availability_slots = db.relationship(
        "Availability",
        back_populates="venue",
        cascade="all, delete-orphan"
    )

    bookings = db.relationship(
        "Booking",
        back_populates="venue"
    )

    __table_args__ = (
        CheckConstraint("min_capacity >= 1", name="check_venue_min_capacity"),
        CheckConstraint(
            "max_capacity >= min_capacity",
            name="check_venue_max_capacity"
        ),
        CheckConstraint(
            "price_per_person >= 0 AND base_price >= 0",
            name="check_venue_prices"
        ),
    )

    def __repr__(self):
        return f"<Venue {self.name}>"


# =====================================================
# 4. VENUE IMAGE MODEL
# =====================================================

class VenueImage(db.Model):
    __tablename__ = "venue_images"

    id = db.Column(db.Integer, primary_key=True)

    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("venues.id"),
        nullable=False
    )

    image_path = db.Column(db.String(500), nullable=False)
    storage_path = db.Column(db.String(500))
    is_primary = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    venue = db.relationship(
        "Venue",
        back_populates="images"
    )


# =====================================================
# 5. MENU MODEL
# =====================================================

class Menu(db.Model):
    __tablename__ = "menus"

    id = db.Column(db.Integer, primary_key=True)

    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("venues.id"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    venue = db.relationship(
        "Venue",
        back_populates="menus"
    )

    items = db.relationship(
        "MenuItem",
        back_populates="menu",
        cascade="all, delete-orphan"
    )


# =====================================================
# 6. MENU ITEM MODEL
# =====================================================

class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)

    menu_id = db.Column(
        db.Integer,
        db.ForeignKey("menus.id"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    category = db.Column(db.String(100))
    price = db.Column(db.Numeric(12, 2), nullable=False)

    dietary_type = db.Column(db.String(30), default="veg")
    is_available = db.Column(db.Boolean, default=True, nullable=False)

    menu = db.relationship(
        "Menu",
        back_populates="items"
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="check_menu_item_price"),
    )


# =====================================================
# 7. PACKAGE MODEL
# =====================================================

class Package(db.Model):
    __tablename__ = "packages"

    id = db.Column(db.Integer, primary_key=True)

    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("venues.id"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    price_per_person = db.Column(db.Numeric(12, 2), nullable=False)

    min_guests = db.Column(db.Integer, default=1)
    max_guests = db.Column(db.Integer)

    inclusions = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    venue = db.relationship(
        "Venue",
        back_populates="packages"
    )

    bookings = db.relationship(
        "Booking",
        back_populates="package"
    )

    __table_args__ = (
        CheckConstraint(
            "price_per_person >= 0",
            name="check_package_price"
        ),
        CheckConstraint(
            "min_guests >= 1",
            name="check_package_min_guests"
        ),
        CheckConstraint(
            "max_guests IS NULL OR max_guests >= min_guests",
            name="check_package_max_guests"
        ),
    )


# =====================================================
# 8. VENUE AVAILABILITY MODEL
# =====================================================

class Availability(db.Model):
    __tablename__ = "availability"

    id = db.Column(db.Integer, primary_key=True)

    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("venues.id"),
        nullable=False
    )

    available_date = db.Column(db.Date, nullable=False)

    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    is_available = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.String(255))

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    venue = db.relationship(
        "Venue",
        back_populates="availability_slots"
    )

    __table_args__ = (
        UniqueConstraint(
            "venue_id",
            "available_date",
            "start_time",
            "end_time",
            name="unique_venue_availability"
        ),
        CheckConstraint(
            "end_time > start_time",
            name="check_availability_time"
        ),
        Index("idx_availability_date", "available_date"),
    )


# =====================================================
# 9. BOOKING MODEL
# =====================================================

class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)

    booking_reference = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
        index=True
    )

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("venues.id"),
        nullable=False
    )

    package_id = db.Column(
        db.Integer,
        db.ForeignKey("packages.id"),
        nullable=True
    )

    event_name = db.Column(db.String(180))
    event_type = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    duration = db.Column(db.String(30))
    organiser_name = db.Column(db.String(120))
    company_name = db.Column(db.String(180))
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(20))

    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)

    guest_count = db.Column(db.Integer, nullable=False)

    special_requests = db.Column(db.Text)

    total_amount = db.Column(db.Numeric(12, 2), default=0)

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now
    )

    customer = db.relationship(
        "User",
        back_populates="bookings",
        foreign_keys=[customer_id]
    )

    venue = db.relationship(
        "Venue",
        back_populates="bookings"
    )

    package = db.relationship(
        "Package",
        back_populates="bookings"
    )

    __table_args__ = (
        CheckConstraint("guest_count >= 1", name="check_booking_guests"),
        CheckConstraint("total_amount >= 0", name="check_booking_amount"),
    )


# =====================================================
# 10. NOTIFICATION MODEL
# =====================================================

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)

    category = db.Column(db.String(50), default="general")

    is_read = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    user = db.relationship(
        "User",
        back_populates="notifications"
    )

    def __repr__(self):
        return f"<Notification {self.title}>"
