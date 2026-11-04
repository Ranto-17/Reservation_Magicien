from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Booking, Contract, Offer, User
from client.services.api import ApiService


def test_health() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_offers_are_seeded() -> None:
    with TestClient(app) as client:
        response = client.get("/offers")
        assert response.status_code == 200
        assert len(response.json()) == 2
        for offer in response.json():
            assert offer["image_url"].startswith("/uploads/offers/")
            assert client.get(offer["image_url"]).status_code == 200


def test_auth_me_requires_authentication() -> None:
    with TestClient(app) as client:
        assert client.get("/auth/me").status_code == 401


def test_client_booking_is_visible_to_admin() -> None:
    email = f"{uuid4().hex}@example.com"
    with TestClient(app) as client:
        registered = client.post(
            "/auth/register",
            json={"full_name": "Test Reservation", "email": email, "phone": "0612345678", "password": "Password123!"},
        )
        assert registered.status_code == 201
        token = client.post("/auth/login", data={"username": email, "password": "Password123!"}).json()["access_token"]
        offer = client.get("/offers").json()[0]
        booking = client.post(
            "/bookings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "offer_id": offer["id"],
                "client_name": "Test Reservation",
                "phone": "0612345678",
                "email": email,
                "event_type": "anniversaire",
                "event_date": str(date.today() + timedelta(days=90)),
                "event_time": "17:00",
                "location": "Paris",
                "participants": 20,
                "additional_message": "Test",
            },
        )
        assert booking.status_code == 201
        admin_token = client.post("/auth/login", data={"username": "admin@magicien.local", "password": "ChangeMe123!"}).json()["access_token"]
        response = client.get("/admin/bookings", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        found = next(item for item in response.json() if item["id"] == booking.json()["id"])
        assert found["status"] == "en_attente"
        assert found["offer_name"] == offer["name"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            booking_ids = list(db.scalars(select(Booking.id).where(Booking.client_id == user.id)))
            if booking_ids:
                db.execute(delete(Contract).where(Contract.booking_id.in_(booking_ids)))
            db.execute(delete(Booking).where(Booking.client_id == user.id))
            db.delete(user)
            db.commit()


def test_admin_image_upload_is_persisted_and_served() -> None:
    with TestClient(app) as client:
        admin_token = client.post(
            "/auth/login",
            data={"username": "admin@magicien.local", "password": "ChangeMe123!"},
        ).json()["access_token"]
        offer = client.get("/offers").json()[0]
        image = BytesIO()
        Image.new("RGB", (4, 4), "red").save(image, format="PNG")
        response = client.post(
            f"/admin/offers/{offer['id']}/image",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"image": ("new-offer.png", image.getvalue(), "image/png")},
        )
        assert response.status_code == 200
        image_url = response.json()["image_url"]
        assert image_url.startswith("/uploads/offers/")
        served = client.get(image_url)
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        with SessionLocal() as db:
            persisted_offer = db.get(Offer, offer["id"])
            assert persisted_offer is not None
            persisted_offer.image_url = offer["image_url"]
            db.commit()
        Path(image_url.removeprefix("/")).unlink(missing_ok=True)


def test_offer_update_does_not_clear_existing_image() -> None:
    with TestClient(app) as client:
        admin_token = client.post(
            "/auth/login",
            data={"username": "admin@magicien.local", "password": "ChangeMe123!"},
        ).json()["access_token"]
        headers = {"Authorization": "Bearer " + admin_token}
        offer = client.get("/offers").json()[0]
        image = BytesIO()
        Image.new("RGB", (4, 4), "blue").save(image, format="PNG")
        uploaded = client.post(
            f"/admin/offers/{offer['id']}/image",
            headers=headers,
            files={"image": ("preserve.png", image.getvalue(), "image/png")},
        )
        assert uploaded.status_code == 200
        image_url = uploaded.json()["image_url"]
        updated = client.put(
            f"/admin/offers/{offer['id']}",
            headers=headers,
            json={
                "name": offer["name"],
                "description": offer["description"],
                "price": offer["price"],
                "duration_minutes": offer["duration_minutes"],
            },
        )
        assert updated.status_code == 200
        assert updated.json()["image_url"] == image_url
        client.delete(f"/admin/offers/{offer['id']}/image", headers=headers)


def test_admin_can_update_offer_presentation_details() -> None:
    with TestClient(app) as client:
        admin_token = client.post(
            "/auth/login",
            data={"username": "admin@magicien.local", "password": "ChangeMe123!"},
        ).json()["access_token"]
        headers = {"Authorization": "Bearer " + admin_token}
        offer = client.get("/offers").json()[0]
        original = {
            "name": offer["name"],
            "description": offer["description"],
            "subtitle": offer.get("subtitle"),
            "detailed_description": offer.get("detailed_description"),
            "magic_tricks": offer.get("magic_tricks"),
            "conclusion": offer.get("conclusion"),
            "price": offer["price"],
            "duration_minutes": offer["duration_minutes"],
        }
        payload = {**original, "subtitle": "Sous-titre de test", "magic_tricks": "Carte\nMentalisme"}
        response = client.put(f"/admin/offers/{offer['id']}", headers=headers, json=payload)
        assert response.status_code == 200
        assert response.json()["subtitle"] == "Sous-titre de test"
        assert response.json()["magic_tricks"] == "Carte\nMentalisme"
        restored = client.put(f"/admin/offers/{offer['id']}", headers=headers, json=original)
        assert restored.status_code == 200


def test_logout_clears_client_session() -> None:
    service = ApiService()
    service.token = "temporary-token"
    service.user = {"id": 1, "role": "client"}
    service.logout()
    assert service.token is None
    assert service.user is None
    assert not service.is_authenticated


def test_client_can_sign_contract_and_admin_can_read_it() -> None:
    email = f"{uuid4().hex}@example.com"
    with TestClient(app) as client:
        assert client.post(
            "/auth/register",
            json={"full_name": "Signature Client", "email": email, "phone": "0612345678", "password": "Password123!"},
        ).status_code == 201
        token = client.post("/auth/login", data={"username": email, "password": "Password123!"}).json()["access_token"]
        auth_headers = {"Authorization": "Bearer " + token}
        offer = client.get("/offers").json()[0]
        booking_response = client.post(
            "/bookings",
            headers=auth_headers,
            json={
                "offer_id": offer["id"],
                "client_name": "Signature Client",
                "phone": "0612345678",
                "email": email,
                "event_type": "autre",
                "event_date": str(date.today() + timedelta(days=365)),
                "event_time": "12:00",
                "location": "Lyon",
                "participants": 10,
            },
        )
        assert booking_response.status_code == 201, booking_response.text
        booking = booking_response.json()
        contract = client.get(f"/bookings/{booking['id']}/contract", headers=auth_headers)
        assert contract.status_code == 200
        assert contract.json()["status"] == "a_signer"
        signed = client.post(
            f"/bookings/{booking['id']}/contract/sign",
            headers=auth_headers,
            json={"signature_name": "Signature Client"},
        )
        assert signed.status_code == 200
        assert signed.json()["status"] == "signe"
        payment = client.post(
            f"/bookings/{booking['id']}/payment",
            headers=auth_headers,
            json={"payment_method": "mvola", "payment_reference": "MV-2026-123456"},
        )
        assert payment.status_code == 200
        assert payment.json()["payment_status"] == "soumis"
        admin_token = client.post("/auth/login", data={"username": "admin@magicien.local", "password": "ChangeMe123!"}).json()["access_token"]
        admin_headers = {"Authorization": "Bearer " + admin_token}
        confirmed = client.patch(
            f"/admin/bookings/{booking['id']}/payment/confirm",
            headers=admin_headers,
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmee"
        assert confirmed.json()["payment_status"] == "confirme"
        admin_contract = client.get(
            f"/admin/bookings/{booking['id']}/contract",
            headers=admin_headers,
        )
        assert admin_contract.status_code == 200
        assert admin_contract.json()["signature_name"] == "Signature Client"
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            booking_ids = list(db.scalars(select(Booking.id).where(Booking.client_id == user.id)))
            db.execute(delete(Contract).where(Contract.booking_id.in_(booking_ids)))
            db.execute(delete(Booking).where(Booking.client_id == user.id))
            db.delete(user)
            db.commit()
