"""Snapshot of the curated demo content, so a fresh database (e.g. the Vercel deploy)
starts with the same places, photos, reviews, events and translations.

``export_demo_data`` writes ``demo_data/snapshot.json`` plus the photos (1600 px WebP);
``load_demo_data`` recreates everything on a database that has no places yet. Personal
accounts are never exported: demo content is owned by a team account and reviews keep
their demo authors, all without usable passwords.
"""

import json
import shutil
from pathlib import Path

from django.core.files import File
from django.db import transaction

from apps.accounts.models import User
from apps.core.thumbnails import thumb_name, thumbnail_url
from apps.explore.models import Category, Place, PlaceImage, PlaceReview
from apps.news.models import News, NewsCategory

DATA_DIR = Path(__file__).resolve().parent / "demo_data"
SNAPSHOT = DATA_DIR / "snapshot.json"
MEDIA_DIR = DATA_DIR / "media"
OWNER = "equipe-maricacity"


def _photo(field):
    """Copy the 1600 px WebP of an upload into demo_data/media; return its file name."""
    thumbnail_url(field, 1600)  # make sure it exists
    source = Path(field.storage.path(thumb_name(field.name, 1600)))
    target = MEDIA_DIR / f"{Path(field.name).stem}.webp"
    shutil.copyfile(source, target)
    return target.name


def _stamp(value):
    return value.isoformat() if value else None


def export():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    places = Place.objects.public().prefetch_related(
        "categories", "images", "reviews__user"
    )
    events = News.objects.published().events()
    reviewers = User.objects.filter(place_reviews_written__place__in=places).distinct()
    data = {
        "users": [
            {
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
            }
            # Personal/staff accounts stay out; their reviews move to the team account
            for u in reviewers
            if not (u.is_staff or u.is_superuser)
        ],
        "categories": [
            {
                "slug": c.slug,
                "name": c.name,
                "description": c.description,
                "icon": c.icon,
                "display_order": c.display_order,
                "translations": c.translations,
            }
            for c in Category.objects.filter(is_active=True)
        ],
        "places": [
            {
                "name": p.name,
                "description": p.description,
                "address": p.address,
                "latitude": str(p.latitude) if p.latitude is not None else None,
                "longitude": str(p.longitude) if p.longitude is not None else None,
                "categories": [c.slug for c in p.categories.all()],
                "is_featured": p.is_featured,
                "translations": p.translations,
                "created_at": _stamp(p.created_at),
                "images": [
                    {
                        "file": _photo(i.image),
                        "caption": i.caption,
                        "is_primary": i.is_primary,
                        "display_order": i.display_order,
                    }
                    for i in p.images.all()
                ],
                "reviews": [
                    {
                        "user": (
                            OWNER
                            if r.user.is_staff or r.user.is_superuser
                            else r.user.username
                        ),
                        "rating": r.rating,
                        "comment": r.comment,
                        "translations": r.translations,
                        "created_at": _stamp(r.created_at),
                    }
                    for r in p.reviews.all()
                ],
            }
            for p in places
        ],
        "events": [
            {
                "title": e.title,
                "slug": e.slug,
                "excerpt": e.excerpt,
                "content": e.content,
                "image": _photo(e.featured_image) if e.featured_image else None,
                "image_caption": e.image_caption,
                "event_date": _stamp(e.event_date),
                "event_end_date": _stamp(e.event_end_date),
                "event_location": e.event_location,
                "source_name": e.source_name,
                "source_url": e.source_url,
                "is_featured": e.is_featured,
                "translations": e.translations,
                "publish_date": _stamp(e.publish_date),
            }
            for e in events
        ],
    }
    SNAPSHOT.write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return data


def _demo_user(username, **fields):
    user, created = User.objects.get_or_create(username=username, defaults=fields)
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _attach(field, name):
    with open(MEDIA_DIR / name, "rb") as fh:
        field.save(name, File(fh), save=False)


@transaction.atomic
def load():
    """Create the snapshot content; returns how many places were created."""
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    owner = _demo_user(OWNER, first_name="Equipe", last_name="MaricaCity")
    users = {
        u["username"]: _demo_user(
            u["username"], **{k: v for k, v in u.items() if k != "username"}
        )
        for u in data["users"]
    }

    categories = {}
    for c in data["categories"]:
        slug = c.pop("slug")
        categories[slug], _created = Category.objects.update_or_create(
            slug=slug, defaults=c
        )

    for p in data["places"]:
        place = Place.objects.create(
            name=p["name"],
            description=p["description"],
            address=p["address"],
            latitude=p["latitude"],
            longitude=p["longitude"],
            is_featured=p["is_featured"],
            translations=p["translations"],
            created_by=owner,
            is_approved=True,
        )
        place.categories.set([categories[s] for s in p["categories"]])
        for i in p["images"]:
            image = PlaceImage(
                place=place,
                caption=i["caption"],
                is_primary=i["is_primary"],
                display_order=i["display_order"],
            )
            _attach(image.image, i["file"])
            image.save()
        for r in p["reviews"]:
            review = PlaceReview.objects.create(
                place=place,
                user=users.get(r["user"], owner),
                rating=r["rating"],
                comment=r["comment"],
                translations=r["translations"],
            )
            PlaceReview.objects.filter(pk=review.pk).update(
                created_at=r["created_at"], updated_at=r["created_at"]
            )
        Place.objects.filter(pk=place.pk).update(created_at=p["created_at"])

    event_category = NewsCategory.objects.get(name=NewsCategory.EVENT)
    for e in data["events"]:
        image = e.pop("image")
        publish_date = e.pop("publish_date")
        event = News(**e, category=event_category, author=owner, status=News.PUBLISHED)
        if image:
            _attach(event.featured_image, image)
        event.save()
        News.objects.filter(pk=event.pk).update(publish_date=publish_date)

    return len(data["places"])


def restore_media():
    """Upload snapshot photos missing from storage (e.g. loaded before R2 was set up).

    Matches each stored image to ``demo_data/media/<same stem>.webp`` and saves it under
    its existing name; returns how many files were uploaded.
    """
    available = {path.stem: path for path in MEDIA_DIR.glob("*.webp")}
    fields = [image.image for image in PlaceImage.objects.all()]
    fields += [e.featured_image for e in News.objects.exclude(featured_image="")]
    uploaded = 0
    for field in fields:
        source = available.get(Path(field.name).stem)
        if source is None or field.storage.exists(field.name):
            continue
        with open(source, "rb") as fh:
            field.storage.save(field.name, File(fh))
        uploaded += 1
    return uploaded
