from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine, get_db
from .models import Booking, BookingStatus, Contract, Offer, SiteSetting, User, UserRole
from .schemas import (
    BookingCreate,
    BookingRead,
    BookingStatusUpdate,
    ContractRead,
    ContractSignature,
    PaymentSubmission,
    OfferBase,
    OfferRead,
    Token,
    UserCreate,
    UserRead,
)
from .security import create_access_token, get_current_user, hash_password, require_admin, verify_password

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads" / "offers"
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
BUILTIN_IMAGE_NAMES = {"close-up.png", "stage-show.png", "hero.png"}
DEFAULT_OFFER_DETAILS = {
    "Magie Close-up": {
        "subtitle": "Le Mystère à portée de main",
        "detailed_description": "Une expérience magique rapprochée où les spectateurs découvrent des illusions extraordinaires à quelques centimètres de leurs yeux.",
        "magic_tricks": "Apparitions et disparitions de cartes.\nPrédictions impossibles.\nTransformations de cartes.\nTours avec des pièces.\nMentalisme.\nExpériences interactives avec les invités.",
        "conclusion": "Une magie élégante, intime et participative, idéale pour créer des souvenirs autour de chaque table.",
    },
    "Spectacle de magie professionnel": {
        "subtitle": "Le Grand Spectacle des Illusions",
        "detailed_description": "Un spectacle de magie captivant mêlant illusions visuelles, mentalisme, participation du public et surprises extraordinaires.",
        "magic_tricks": "Grandes illusions visuelles.\nMentalisme et prédictions.\nApparitions et disparitions.\nExpériences participatives.\nMoments comiques.\nSurprises et effets spectaculaires.",
        "conclusion": "Un grand moment de scène pensé pour émerveiller tous les publics et donner une dimension inoubliable à votre événement.",
    },
}


def seed_database(db: Session) -> None:
    local_images = {
        "Magie Close-up": "/uploads/offers/close-up.png",
        "Spectacle de magie professionnel": "/uploads/offers/stage-show.png",
    }
    if db.scalar(select(func.count(Offer.id))) == 0:
        db.add_all(
            [
                Offer(name="Magie Close-up", description="Spectacle de magie rapprochée avec des cartes, des pièces et des illusions interactives.", price=500, duration_minutes=120, image_url=None, **DEFAULT_OFFER_DETAILS["Magie Close-up"]),
                Offer(name="Spectacle de magie professionnel", description="Spectacle de magie et d'illusion avec mentalisme et interactions avec les spectateurs.", price=1200, duration_minutes=90, image_url=None, **DEFAULT_OFFER_DETAILS["Spectacle de magie professionnel"]),
            ]
        )
    else:
        for offer in db.scalars(select(Offer)):
            if offer.name in local_images and (
                not offer.image_url or offer.image_url.startswith("http://") or offer.image_url.startswith("https://")
                or (
                    offer.image_url.startswith("/uploads/offers/")
                    and not (UPLOAD_DIR / Path(offer.image_url).name).is_file()
                )
            ):
                offer.image_url = local_images[offer.name]
            defaults = DEFAULT_OFFER_DETAILS.get(offer.name, {})
            for key, value in defaults.items():
                if not getattr(offer, key):
                    setattr(offer, key, value)
    db.commit()


def migrate_offer_data() -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("offers")}
    additions = {
        "subtitle": "VARCHAR(255)",
        "detailed_description": "TEXT",
        "magic_tricks": "TEXT",
        "conclusion": "TEXT",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE offers ADD COLUMN {name} {definition}"))


def contract_content(booking: Booking) -> str:
    return (
        "CONTRAT DE PRESTATION DE MAGIE\n\n"
        f"Client : {booking.client_name}\n"
        f"Email : {booking.email}\n"
        f"Événement : {booking.event_type.value}\n"
        f"Date : {booking.event_date} à {booking.event_time}\n"
        f"Lieu : {booking.location}\n"
        f"Participants : {booking.participants}\n"
        f"Prestation : {booking.offer.name}\n"
        f"Prix convenu : {booking.price_at_booking:,.0f} Ar\n\n"
        "Le client confirme les informations ci-dessus et accepte les "
        "conditions de la prestation. La signature électronique est "
        "enregistrée avec la date et l'heure de validation."
    )


def migrate_booking_data() -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("bookings")}
    additions = {
        "payment_method": "VARCHAR(30)",
        "payment_reference": "VARCHAR(120)",
        "payment_status": "VARCHAR(20) NOT NULL DEFAULT 'a_payer'",
        "payment_submitted_at": "DATETIME",
        "payment_confirmed_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE bookings ADD COLUMN {name} {definition}"))
        connection.execute(text("UPDATE bookings SET payment_status = 'a_payer' WHERE payment_status IS NULL OR payment_status = ''"))
    with SessionLocal() as db:
        for booking in db.scalars(select(Booking)):
            if db.scalar(select(Contract).where(Contract.booking_id == booking.id)) is None:
                db.add(Contract(booking_id=booking.id, content=contract_content(booking)))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_offer_data()
    migrate_booking_data()
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="Réservation Magicien", version="1.0.0", lifespan=lifespan)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR.parent), name="uploads")


@app.get("/settings/hero-image")
def get_hero_image() -> dict[str, str | None]:
    with SessionLocal() as db:
        setting = db.scalar(select(SiteSetting).where(SiteSetting.key == "hero_image"))
        return {"image_url": setting.value if setting else None}


@app.post("/admin/settings/hero-image")
def upload_hero_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, str]:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Format accepté : JPG, JPEG, PNG ou WEBP")
    temporary_path = UPLOAD_DIR / f".hero-{uuid4().hex}.upload"
    size = 0
    try:
        with temporary_path.open("wb") as target:
            while chunk := image.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_SIZE:
                    raise HTTPException(413, "L'image ne doit pas dépasser 5 Mo")
                target.write(chunk)
        try:
            with Image.open(temporary_path) as validated:
                validated.verify()
                image_format = validated.format
        except (UnidentifiedImageError, OSError):
            raise HTTPException(415, "Le fichier n'est pas une image valide") from None
        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise HTTPException(415, "Format accepté : JPG, JPEG, PNG ou WEBP")
        filename = f"hero-{uuid4().hex}{ALLOWED_IMAGE_FORMATS[image_format]}"
        final_path = UPLOAD_DIR / filename
        temporary_path.replace(final_path)
        setting = db.scalar(select(SiteSetting).where(SiteSetting.key == "hero_image"))
        previous_url = setting.value if setting else None
        if setting is None:
            setting = SiteSetting(key="hero_image", value=f"/uploads/offers/{filename}")
            db.add(setting)
        else:
            setting.value = f"/uploads/offers/{filename}"
        try:
            db.commit()
        except Exception:
            db.rollback()
            final_path.unlink(missing_ok=True)
            raise
        if previous_url:
            remove_local_image(previous_url)
        return {"image_url": setting.value}
    finally:
        temporary_path.unlink(missing_ok=True)


@app.delete("/admin/settings/hero-image")
def delete_hero_image(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, None]:
    setting = db.scalar(select(SiteSetting).where(SiteSetting.key == "hero_image"))
    if setting is not None:
        previous_url = setting.value
        setting.value = None
        db.commit()
        remove_local_image(previous_url)
    return {"image_url": None}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=UserRead, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Cette adresse e-mail est déjà utilisée")
    user_data = payload.model_dump(exclude={"password"})
    user_data["email"] = email
    user = User(**user_data, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Aucun compte associé à cette adresse email")
    if not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mot de passe incorrect")
    return Token(access_token=create_access_token(user))


@app.get("/auth/me", response_model=UserRead)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


@app.get("/offers", response_model=list[OfferRead])
def list_offers(db: Session = Depends(get_db)) -> list[Offer]:
    return list(db.scalars(select(Offer).where(Offer.is_active.is_(True)).order_by(Offer.id)))


@app.post("/admin/offers", response_model=OfferRead, status_code=201)
def create_offer(payload: OfferBase, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Offer:
    if db.scalar(select(func.count(Offer.id))) >= 2:
        raise HTTPException(400, "L'application doit conserver exactement deux offres")
    offer = Offer(**payload.model_dump())
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


@app.put("/admin/offers/{offer_id}", response_model=OfferRead)
def update_offer(offer_id: int, payload: OfferBase, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Offre introuvable")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(offer, key, value)
    db.commit()
    db.refresh(offer)
    return offer


def remove_local_image(image_url: str | None) -> None:
    if not image_url or not image_url.startswith("/uploads/offers/"):
        return
    if Path(image_url).name in BUILTIN_IMAGE_NAMES:
        return
    candidate = (UPLOAD_DIR / Path(image_url).name).resolve()
    if candidate.parent == UPLOAD_DIR.resolve() and candidate.exists():
        candidate.unlink()


@app.post("/admin/offers/{offer_id}/image", response_model=OfferRead)
def upload_offer_image(
    offer_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Offre introuvable")
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Format accepté : JPG, JPEG, PNG ou WEBP")

    temporary_path = UPLOAD_DIR / f".{uuid4().hex}.upload"
    size = 0
    try:
        with temporary_path.open("wb") as target:
            while chunk := image.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_SIZE:
                    raise HTTPException(413, "L'image ne doit pas dépasser 5 Mo")
                target.write(chunk)
        try:
            with Image.open(temporary_path) as validated:
                validated.verify()
                image_format = validated.format
        except (UnidentifiedImageError, OSError):
            raise HTTPException(415, "Le fichier n'est pas une image valide") from None
        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise HTTPException(415, "Format accepté : JPG, JPEG, PNG ou WEBP")

        filename = f"{uuid4().hex}{ALLOWED_IMAGE_FORMATS[image_format]}"
        final_path = UPLOAD_DIR / filename
        temporary_path.replace(final_path)
        previous_url = offer.image_url
        offer.image_url = f"/uploads/offers/{filename}"
        try:
            db.commit()
        except Exception:
            db.rollback()
            final_path.unlink(missing_ok=True)
            raise
        db.refresh(offer)
        remove_local_image(previous_url)
        return offer
    finally:
        temporary_path.unlink(missing_ok=True)


@app.delete("/admin/offers/{offer_id}/image", response_model=OfferRead)
def delete_offer_image(offer_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Offre introuvable")
    previous_url = offer.image_url
    offer.image_url = None
    db.commit()
    db.refresh(offer)
    remove_local_image(previous_url)
    return offer


@app.delete("/admin/offers/{offer_id}", status_code=204)
def delete_offer(offer_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> None:
    if db.scalar(select(func.count(Offer.id))) <= 2:
        raise HTTPException(400, "Les deux offres obligatoires ne peuvent pas être supprimées")
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "Offre introuvable")
    previous_url = offer.image_url
    db.delete(offer)
    db.commit()
    remove_local_image(previous_url)


@app.post("/bookings", response_model=BookingRead, status_code=201)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Booking:
    offer = db.scalar(select(Offer).where(Offer.id == payload.offer_id, Offer.is_active.is_(True)))
    if offer is None:
        raise HTTPException(404, "Offre introuvable")
    start = datetime.combine(payload.event_date, payload.event_time)
    end = start + timedelta(minutes=offer.duration_minutes)
    existing_bookings = db.scalars(
        select(Booking)
        .join(Offer)
        .where(
            Booking.event_date == payload.event_date,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
        )
    )
    for existing in existing_bookings:
        existing_start = datetime.combine(existing.event_date, existing.event_time)
        existing_end = existing_start + timedelta(minutes=existing.offer.duration_minutes)
        if start < existing_end and existing_start < end:
            raise HTTPException(409, "Le magicien est déjà réservé sur ce créneau")
    booking = Booking(**payload.model_dump(), client_id=user.id, price_at_booking=offer.price, status=BookingStatus.PENDING)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    contract = Contract(booking_id=booking.id, content=contract_content(booking))
    db.add(contract)
    db.commit()
    return booking


@app.get("/bookings/me", response_model=list[BookingRead])
def my_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Booking]:
    return list(db.scalars(select(Booking).where(Booking.client_id == user.id).order_by(Booking.event_date)))


@app.get("/bookings/{booking_id}/contract", response_model=ContractRead)
def get_contract(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Contract:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.client_id != user.id:
        raise HTTPException(404, "Réservation introuvable")
    contract = db.scalar(select(Contract).where(Contract.booking_id == booking_id))
    if contract is None:
        raise HTTPException(404, "Contrat introuvable")
    return contract


@app.post("/bookings/{booking_id}/contract/sign", response_model=ContractRead)
def sign_contract(
    booking_id: int,
    payload: ContractSignature,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Contract:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.client_id != user.id:
        raise HTTPException(404, "Réservation introuvable")
    contract = db.scalar(select(Contract).where(Contract.booking_id == booking_id))
    if contract is None:
        raise HTTPException(404, "Contrat introuvable")
    if contract.status == "signe":
        raise HTTPException(409, "Ce contrat est déjà signé")
    if payload.signature_name.strip().casefold() != booking.client_name.strip().casefold():
        raise HTTPException(400, "La signature doit correspondre au nom du client")
    contract.signature_name = payload.signature_name.strip()
    contract.signed_at = datetime.utcnow()
    contract.status = "signe"
    db.commit()
    db.refresh(contract)
    return contract


@app.post("/bookings/{booking_id}/payment", response_model=BookingRead)
def submit_payment(
    booking_id: int,
    payload: PaymentSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.client_id != user.id:
        raise HTTPException(404, "Réservation introuvable")
    contract = db.scalar(select(Contract).where(Contract.booking_id == booking_id))
    if contract is None or contract.status != "signe":
        raise HTTPException(400, "Le contrat doit être signé avant le paiement")
    if booking.payment_status == "confirme":
        raise HTTPException(409, "Le paiement est déjà confirmé")
    booking.payment_method = payload.payment_method
    booking.payment_reference = payload.payment_reference.strip()
    booking.payment_status = "soumis"
    booking.payment_submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(booking)
    return booking


@app.patch("/bookings/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.client_id != user.id:
        raise HTTPException(404, "Réservation introuvable")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(400, "Seule une réservation en attente peut être annulée")
    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return booking


@app.get("/admin/clients", response_model=list[UserRead])
def clients(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User).where(User.role == UserRole.CLIENT).order_by(User.id)))


@app.get("/admin/bookings", response_model=list[BookingRead])
def all_bookings(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[Booking]:
    return list(db.scalars(select(Booking).order_by(Booking.event_date, Booking.event_time)))


@app.get("/admin/bookings/{booking_id}/contract", response_model=ContractRead)
def admin_get_contract(booking_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Contract:
    contract = db.scalar(select(Contract).where(Contract.booking_id == booking_id))
    if contract is None:
        raise HTTPException(404, "Contrat introuvable")
    return contract


@app.patch("/admin/bookings/{booking_id}/payment/confirm", response_model=BookingRead)
def confirm_payment(booking_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Réservation introuvable")
    if booking.payment_status != "soumis":
        raise HTTPException(400, "Aucun paiement soumis à confirmer")
    booking.payment_status = "confirme"
    booking.payment_confirmed_at = datetime.utcnow()
    booking.status = BookingStatus.CONFIRMED
    db.commit()
    db.refresh(booking)
    return booking


@app.patch("/admin/bookings/{booking_id}/status", response_model=BookingRead)
def update_booking_status(booking_id: int, payload: BookingStatusUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Réservation introuvable")
    if payload.status == BookingStatus.CONFIRMED and booking.payment_status != "confirme":
        raise HTTPException(400, "Le paiement doit être confirmé avant d'accepter la réservation")
    booking.status = payload.status
    db.commit()
    db.refresh(booking)
    return booking


@app.get("/admin/statistics")
def statistics(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    rows = db.execute(select(Booking.status, func.count(Booking.id)).group_by(Booking.status)).all()
    return {"total": sum(count for _, count in rows), "by_status": {status.value: count for status, count in rows}}
