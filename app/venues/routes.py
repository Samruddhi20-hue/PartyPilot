
from flask import render_template, redirect, url_for, request
from sqlalchemy.orm import selectinload
from sqlalchemy import or_

from app.venues import venues
from app.extensions import db
from app.models import Venue, RestaurantProfile


@venues.route("/explore")
def explore():
    # Only show published venues belonging to approved partners.
    query = (
        Venue.query
        .join(Venue.restaurant)
        .options(
            selectinload(Venue.images),
            selectinload(Venue.restaurant)
        )
        .filter(
            Venue.is_published.is_(True),
            Venue.status == "published",
            RestaurantProfile.verification_status == "approved"
        )
    )

    # Location filter
    location = request.args.get("location", "").strip()
    if location:
        search_term = f"%{location}%"
        query = query.filter(
            or_(
                Venue.city.ilike(search_term),
                Venue.address.ilike(search_term)
            )
        )

    # Event type filter
    event_type = request.args.get("venue_type", request.args.get("event_type", "")).strip()
    if event_type:
        query = query.filter(
            Venue.venue_type.ilike(f"%{event_type}%")
        )

    # Guest capacity filter
    guests = request.args.get("guests", type=int)
    if guests and guests > 0:
        query = query.filter(
            Venue.max_capacity >= guests,
            or_(Venue.min_capacity.is_(None), Venue.min_capacity <= guests)
        )

    # Maximum budget per person
    budget = request.args.get("budget", type=float)
    if budget is not None and budget >= 0:
        query = query.filter(
            Venue.price_per_person <= budget
        )

    # Sorting
    sort = request.args.get("sort", "recommended")

    if sort == "low":
        query = query.order_by(Venue.price_per_person.asc())
    elif sort == "high":
        query = query.order_by(Venue.price_per_person.desc())
    else:
        query = query.order_by(Venue.created_at.desc())

    venues_list = query.all()

    return render_template(
        "customer/explore.html",
        venues=venues_list,
        venue_count=len(venues_list),
        selected_location=location,
        selected_event=event_type,
        selected_guests=guests or "",
        selected_budget=budget or "",
        selected_sort=sort
    )


@venues.route("/venue/<int:venue_id>")
def venue_details(venue_id):
    venue = (
        Venue.query
        .join(Venue.restaurant)
        .options(
            selectinload(Venue.images),
            selectinload(Venue.restaurant),
            selectinload(Venue.packages),
            selectinload(Venue.menus)
        )
        .filter(
            Venue.id == venue_id,
            Venue.is_published.is_(True),
            Venue.status == "published",
            RestaurantProfile.verification_status == "approved"
        )
        .first_or_404()
    )

    images = venue.images
    menus = [menu for menu in venue.menus if menu.is_active]
    packages = [package for package in venue.packages if package.is_active]
    return render_template(
        "customer/venue_details.html",
        venue=venue,
        images=images,
        menus=menus,
        packages=packages,
    )


@venues.route("/restaurant")
def restaurant_landing():
    return redirect(url_for("auth.restaurant_register"))
