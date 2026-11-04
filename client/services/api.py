from __future__ import annotations

from typing import Any

import httpx
import mimetypes
from pathlib import Path
from uuid import uuid4


class ApiError(Exception):
    """A user-readable error returned by the REST API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApiService:
    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.user: dict[str, Any] | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.token is not None

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = httpx.request(method, f"{self.base_url}{path}", headers=headers, timeout=12, **kwargs)
        except httpx.RequestError as exc:
            raise ApiError("Impossible de contacter le serveur. Vérifiez votre connexion.") from exc
        if response.is_error:
            if response.status_code >= 500:
                raise ApiError("Le serveur rencontre un problème. Réessayez dans quelques instants.", response.status_code)
            try:
                detail = response.json().get("detail", "Une erreur est survenue.")
            except ValueError:
                detail = "Une erreur est survenue."
            raise ApiError(str(detail), response.status_code)
        if response.status_code == 204:
            return None
        return response.json()

    def login(self, email: str, password: str) -> dict[str, Any]:
        data = self._request("POST", "/auth/login", data={"username": email.strip().lower(), "password": password})
        self.token = data["access_token"]
        self.user = self.me()
        return self.user

    def register(self, full_name: str, email: str, phone: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/auth/register",
            json={"full_name": full_name, "email": email, "phone": phone, "password": password},
        )

    def logout(self) -> None:
        self.token = None
        self.user = None

    def me(self) -> dict[str, Any]:
        self.user = self._request("GET", "/auth/me")
        return self.user

    def offers(self) -> list[dict[str, Any]]:
        return [self._with_media_url(offer) for offer in self._request("GET", "/offers")]

    def _with_media_url(self, item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item)
        image_url = result.get("image_url")
        result["_image_path"] = image_url
        if image_url and image_url.startswith("/"):
            result["image_url"] = f"{self.base_url}{image_url}?v={uuid4().hex}"
        return result

    def create_booking(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._request("POST", "/bookings", json=payload)
        except ApiError as exc:
            raise ApiError(f"Création de la réservation impossible : {exc}", exc.status_code) from exc

    def my_bookings(self) -> list[dict[str, Any]]:
        return self._request("GET", "/bookings/me")

    def cancel_booking(self, booking_id: int) -> dict[str, Any]:
        return self._request("PATCH", f"/bookings/{booking_id}/cancel")

    def get_contract(self, booking_id: int) -> dict[str, Any]:
        return self._request("GET", f"/bookings/{booking_id}/contract")

    def sign_contract(self, booking_id: int, signature_name: str) -> dict[str, Any]:
        try:
            return self._request("POST", f"/bookings/{booking_id}/contract/sign", json={"signature_name": signature_name})
        except ApiError as exc:
            raise ApiError(f"Signature du contrat impossible : {exc}", exc.status_code) from exc

    def submit_payment(self, booking_id: int, payment_method: str, payment_reference: str) -> dict[str, Any]:
        try:
            return self._request(
                "POST",
                f"/bookings/{booking_id}/payment",
                json={"payment_method": payment_method, "payment_reference": payment_reference},
            )
        except ApiError as exc:
            raise ApiError(f"Envoi du paiement impossible : {exc}", exc.status_code) from exc

    def statistics(self) -> dict[str, Any]:
        return self._request("GET", "/admin/statistics")

    def admin_bookings(self) -> list[dict[str, Any]]:
        return self._request("GET", "/admin/bookings")

    def clients(self) -> list[dict[str, Any]]:
        return self._request("GET", "/admin/clients")

    def update_booking_status(self, booking_id: int, status: str) -> dict[str, Any]:
        return self._request("PATCH", f"/admin/bookings/{booking_id}/status", json={"status": status})

    def admin_contract(self, booking_id: int) -> dict[str, Any]:
        return self._request("GET", f"/admin/bookings/{booking_id}/contract")

    def confirm_payment(self, booking_id: int) -> dict[str, Any]:
        return self._request("PATCH", f"/admin/bookings/{booking_id}/payment/confirm")

    def update_offer(self, offer_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._with_media_url(self._request("PUT", f"/admin/offers/{offer_id}", json=payload))

    def upload_offer_image(self, offer_id: int, image_path: str) -> dict[str, Any]:
        with open(image_path, "rb") as image_file:
            result = self._request(
                "POST",
                f"/admin/offers/{offer_id}/image",
                files={"image": (Path(image_path).name, image_file, mimetypes.guess_type(image_path)[0] or "application/octet-stream")},
            )
        return self._with_media_url(result)

    def delete_offer_image(self, offer_id: int) -> dict[str, Any]:
        return self._with_media_url(self._request("DELETE", f"/admin/offers/{offer_id}/image"))

    def hero_image(self) -> str | None:
        result = self._request("GET", "/settings/hero-image")
        image_url = result.get("image_url")
        return f"{self.base_url}{image_url}?v={uuid4().hex}" if image_url else None

    def upload_hero_image(self, image_path: str) -> str | None:
        with open(image_path, "rb") as image_file:
            result = self._request(
                "POST",
                "/admin/settings/hero-image",
                files={"image": (Path(image_path).name, image_file, mimetypes.guess_type(image_path)[0] or "application/octet-stream")},
            )
        image_url = result.get("image_url")
        return f"{self.base_url}{image_url}?v={uuid4().hex}" if image_url else None

    def delete_hero_image(self) -> None:
        self._request("DELETE", "/admin/settings/hero-image")
