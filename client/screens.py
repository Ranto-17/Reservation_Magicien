from __future__ import annotations

from datetime import date
import re
from threading import Thread
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import Any

from kivy.clock import Clock
from kivy.cache import Cache
from kivy.logger import Logger
from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner

from .services.api import ApiError
from .theme import DANGER, GOLD, MUTED, NAVY, NAVY_LIGHT, SUCCESS, WHITE
from .widgets import Card, Field, GoldButton, MessageBar, OfferCard, PageLayout, PhotoPlaceholder, PrimaryButton, Sidebar, StatusBadge, elevated_background, parchment_background, rounded_background, wrapped_label


def title_label(text: str, size: int = 28) -> Label:
    return Label(text=text, color=WHITE, font_size=dp(size), bold=True, halign="left", valign="middle", text_size=(None, None), size_hint_y=None, height=dp(size + 18))


class BaseScreen(Screen):
    api = ObjectProperty(None)

    def content(self, spacing: int = 18) -> BoxLayout:
        page = PageLayout()
        page.main.spacing = dp(spacing)
        return page

    def run_async(self, work: Any, success: Any, error: Any) -> None:
        def execute() -> None:
            try:
                result = work()
            except ApiError as exc:
                message = str(exc)
                Clock.schedule_once(lambda dt, message=message: error(message))
            except Exception:
                Clock.schedule_once(lambda dt: error("Une erreur inattendue est survenue."))
            else:
                Clock.schedule_once(lambda dt: success(result))
        Thread(target=execute, daemon=True).start()

    def navigate(self, name: str, **kwargs: Any) -> None:
        try:
            screen = self.manager.get_screen(name)
            for key, value in kwargs.items():
                setattr(screen, key, value)
            already_current = self.manager.current == name
            self.manager.current = name
            if already_current and hasattr(screen, "refresh"):
                screen.refresh()
        except (KeyError, AttributeError, RuntimeError) as exc:
            Logger.exception("Navigation vers '%s' impossible", name)
            self._show_navigation_error(f"Impossible d'ouvrir cet écran : {exc}")

    def _show_navigation_error(self, message: str) -> None:
        if hasattr(self, "message"):
            self.message.show(message, DANGER)
            return
        self.clear_widgets()
        self.add_widget(MessageBar(text=message, color=DANGER))

    def nav_bar(self, active: str = "") -> BoxLayout:
        is_admin = bool(self.api.user and self.api.user.get("role") == "admin")
        return Sidebar(active, self.api.is_authenticated, is_admin, self.navigate, self.logout, self.go_back)

    def go_back(self) -> None:
        if self.manager is None:
            return
        previous = self.manager.previous()
        if previous and previous != self.manager.current:
            self.navigate(previous)
        else:
            self.navigate("home")

    def logout(self) -> None:
        self.api.logout()
        login = self.manager.get_screen("login")
        login.next_screen = "home"
        login.offer = {}
        self.navigate("login")

    @staticmethod
    def refresh_image(image: AsyncImage, source: str) -> None:
        for cache_name in ("kv.image", "kv.texture"):
            Cache.remove(cache_name, source)
        image.source = source
        image.reload()


class HomeScreen(BaseScreen):
    def on_pre_enter(self, *_: Any) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("home"))
        hero = BoxLayout(orientation="horizontal", padding=[dp(28), dp(24)], spacing=dp(24), size_hint_y=None, height=dp(330))
        rounded_background(hero, NAVY_LIGHT)
        left = BoxLayout(orientation="vertical", spacing=dp(14))
        left.add_widget(Label(text="L'ART DE L'ILLUSION", color=GOLD, font_size=dp(13), bold=True, halign="left", size_hint_y=None, height=dp(25)))
        left.add_widget(title_label("Vivez une expérience\nmagique inoubliable", 34))
        left.add_widget(wrapped_label("Des prestations élégantes et spectaculaires pour vos mariages, anniversaires, événements privés et soirées d'entreprise.", color=MUTED, font_size=dp(16), size_hint_y=None, height=dp(62)))
        discover = GoldButton("Découvrir nos offres", size_hint_x=None, width=dp(210))
        discover.bind(on_release=lambda *_: self.navigate("offers"))
        left.add_widget(discover)
        hero.add_widget(left)
        self.hero_photo = BoxLayout(orientation="vertical", size_hint_x=0.48)
        self.hero_photo.add_widget(PhotoPlaceholder("Ajoutez une image depuis l'espace administrateur"))
        hero.add_widget(self.hero_photo)
        root.add_widget(hero)
        root.add_widget(wrapped_label("Nos prestations", color=WHITE, font_size=dp(22), bold=True, size_hint_y=None, height=dp(38)))
        root.add_widget(wrapped_label("Deux formats, une même promesse : vous laisser un souvenir inoubliable.", color=MUTED, size_hint_y=None, height=dp(30)))
        self.add_widget(root)
        self.run_async(self.api.hero_image, self._show_hero_image, lambda _: None)

    def _show_hero_image(self, image_url: str | None) -> None:
        self.hero_photo.clear_widgets()
        if image_url:
            self.hero_photo.add_widget(AsyncImage(source=image_url, allow_stretch=True, keep_ratio=True, nocache=True))
        else:
            self.hero_photo.add_widget(PhotoPlaceholder("Ajoutez une image depuis l'espace administrateur"))


class OffersScreen(BaseScreen):
    offers: list[dict[str, Any]] = []

    def on_pre_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("offers"))
        root.add_widget(title_label("Nos offres", 30))
        root.add_widget(Label(text="Choisissez l'expérience qui correspond à votre événement.", color=MUTED, halign="left", size_hint_y=None, height=dp(25)))
        self.message = MessageBar()
        root.add_widget(self.message)
        scroll = ScrollView()
        self.cards = GridLayout(cols=2, spacing=dp(20), padding=[0, dp(8)], size_hint_y=None, size_hint_x=1)
        self.cards.bind(minimum_width=self.cards.setter("width"))
        self.cards.bind(minimum_height=self.cards.setter("height"))
        self.cards.bind(width=lambda _, width: setattr(self.cards, "cols", 1 if width < dp(720) else 2))
        scroll.add_widget(self.cards)
        root.add_widget(scroll)
        self.add_widget(root)
        self.message.show("Chargement des prestations...", MUTED)
        self.run_async(self.api.offers, self._show_offers, lambda error: self.message.show(error, DANGER))

    def _show_offers(self, offers: list[dict[str, Any]]) -> None:
        self.offers = offers
        self.cards.clear_widgets()
        for offer in offers:
            self.cards.add_widget(OfferCard(offer, self.show_details, self.reserve))
        self.message.show(f"{len(offers)} prestations disponibles", SUCCESS)

    def show_details(self, offer: dict[str, Any]) -> None:
        self.navigate("offer_detail", offer=offer)

    def reserve(self, offer: dict[str, Any]) -> None:
        if not self.api.is_authenticated:
            self.navigate("login", next_screen="reservation", offer=offer)
        else:
            self.navigate("reservation", offer=offer)


class OfferDetailScreen(BaseScreen):
    offer: dict[str, Any] = {}

    def refresh(self) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("offers"))
        scroll = ScrollView(do_scroll_x=False)
        card = BoxLayout(orientation="vertical", spacing=dp(12), padding=[dp(24), dp(22)], size_hint_y=None, opacity=0)
        card.bind(minimum_height=card.setter("height"))
        parchment_background(card)
        scroll.add_widget(card)
        root.add_widget(scroll)
        offer_name = self.offer.get("name", "Prestation de magie")
        defaults = {
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
        }.get(offer_name, {})
        subtitle = self.offer.get("subtitle") or defaults.get("subtitle") or "Une expérience magique unique"
        detailed = self.offer.get("detailed_description") or defaults.get("detailed_description") or self.offer.get("description", "")
        tricks = self.offer.get("magic_tricks") or defaults.get("magic_tricks", "")
        conclusion = self.offer.get("conclusion") or defaults.get("conclusion") or "Une prestation sur mesure pour votre événement."
        card.add_widget(Label(text="*   *   *   LE ROULEAU DES MERVEILLES   *   *   *", color=[0.35, 0.20, 0.08, 1], font_size=dp(13), bold=True, size_hint_y=None, height=dp(30)))
        if self.offer.get("image_url"):
            card.add_widget(AsyncImage(source=self.offer["image_url"], size_hint_y=None, height=dp(190), allow_stretch=True, keep_ratio=True, nocache=True))
        else:
            card.add_widget(PhotoPlaceholder("Image de présentation à venir", height=dp(150)))
        card.add_widget(Label(text=offer_name, color=[0.25, 0.13, 0.04, 1], font_size=dp(28), bold=True, size_hint_y=None, height=dp(42)))
        card.add_widget(Label(text=subtitle, color=[0.45, 0.26, 0.08, 1], italic=True, font_size=dp(18), size_hint_y=None, height=dp(32)))
        card.add_widget(wrapped_label(detailed, color=[0.20, 0.15, 0.10, 1], font_size=dp(15), size_hint_y=None, height=dp(92)))
        card.add_widget(Label(text="LES SECRETS DU PRESTIDIGITATEUR", color=[0.45, 0.26, 0.08, 1], font_size=dp(16), bold=True, size_hint_y=None, height=dp(30)))
        trick_text = "\n".join(f"*  {line.strip()}" for line in tricks.splitlines() if line.strip())
        card.add_widget(wrapped_label(trick_text, color=[0.20, 0.15, 0.10, 1], font_size=dp(14), size_hint_y=None, height=max(dp(100), dp(26) * max(1, len(trick_text.splitlines())))))
        card.add_widget(wrapped_label(conclusion, color=[0.25, 0.17, 0.08, 1], font_size=dp(14), italic=True, size_hint_y=None, height=dp(62)))
        card.add_widget(Label(text=f"{self.offer.get('price', 0):,.0f} Ar   •   {self.offer.get('duration_minutes', 0)} minutes", color=[0.45, 0.26, 0.08, 1], font_size=dp(19), bold=True, size_hint_y=None, height=dp(36)))
        reserve = GoldButton("Réserver maintenant")
        reserve.bind(on_release=lambda *_: self._reserve())
        card.add_widget(reserve)
        self.add_widget(root)
        Animation(opacity=1, duration=0.4, t="out_quad").start(card)

    def _reserve(self) -> None:
        if not self.api.is_authenticated:
            self.navigate("login", next_screen="reservation", offer=self.offer)
        else:
            self.navigate("reservation", offer=self.offer)


class LoginScreen(BaseScreen):
    next_screen = "home"
    offer: dict[str, Any] = {}

    def on_pre_enter(self, *_: Any) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("login"))
        holder = AnchorLayout(anchor_x="center", anchor_y="center")
        card = BoxLayout(orientation="vertical", size_hint=(None, None), width=dp(480), height=dp(438), padding=[dp(34), dp(28)], spacing=dp(10))
        elevated_background(card)
        holder.bind(width=lambda _, width: setattr(card, "width", min(dp(480), max(dp(280), width - dp(32)))))
        card.add_widget(Label(text="MAGIC RESERVATION", color=GOLD, font_size=dp(14), bold=True, size_hint_y=None, height=dp(24)))
        card.add_widget(title_label("Bienvenue", 30))
        card.add_widget(wrapped_label("Connectez-vous pour réserver votre prestation.", color=MUTED, font_size=dp(13), size_hint_y=None, height=dp(34)))
        self.email = Field("Adresse e-mail (ex. nom@domaine.com)")
        self.password = Field("Mot de passe", password=True)
        card.add_widget(self.email)
        card.add_widget(self.password)
        self.message = MessageBar()
        card.add_widget(self.message)
        login = GoldButton("Se connecter")
        login.bind(on_release=lambda *_: self.submit())
        card.add_widget(login)
        register = Button(text="Pas encore de compte ?  Créer un compte", background_normal="", background_color=[0, 0, 0, 0], color=GOLD, size_hint_y=None, height=dp(40))
        register.bind(on_release=lambda *_: self.navigate("register"))
        card.add_widget(register)
        holder.add_widget(card)
        root.add_widget(holder)
        self.add_widget(root)

    def submit(self) -> None:
        if not self.email.value or not self.password.value:
            self.message.show("Veuillez remplir tous les champs.", DANGER)
            return
        self.message.show("Connexion en cours...", MUTED)
        self.run_async(lambda: self.api.login(self.email.value, self.password.value), self._success, self._login_error)

    def _login_error(self, error: str) -> None:
        if "Impossible de contacter" in error:
            message = error
        elif "incorrect" in error.lower():
            message = "Mot de passe incorrect. Veuillez réessayer."
        elif "compte" in error.lower() or "e-mail" in error.lower():
            message = "Aucun compte associé à cette adresse email. Vérifiez votre adresse ou créez un compte."
        else:
            message = "Connexion impossible. Vérifiez vos identifiants."
        self.message.show(message, DANGER)

    def _success(self, user: dict[str, Any]) -> None:
        target = "admin" if user["role"] == "admin" else (self.next_screen if self.next_screen != "home" else "client")
        self.navigate(target, offer=self.offer)


class RegisterScreen(BaseScreen):
    def on_pre_enter(self, *_: Any) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("register"))
        scroll = ScrollView(do_scroll_x=False)
        holder = AnchorLayout(anchor_x="center", anchor_y="center", size_hint_y=None, height=dp(610))
        card = BoxLayout(orientation="vertical", size_hint=(None, None), width=dp(480), height=dp(610), padding=[dp(34), dp(28)], spacing=dp(10))
        elevated_background(card)
        holder.bind(width=lambda _, width: setattr(card, "width", min(dp(480), max(dp(280), width - dp(32)))))
        card.add_widget(Label(text="MAGIC RESERVATION", color=GOLD, font_size=dp(14), bold=True, size_hint_y=None, height=dp(24)))
        card.add_widget(title_label("Créer un compte", 30))
        card.add_widget(wrapped_label("Réservez vos prestations en quelques clics.", color=MUTED, font_size=dp(13), size_hint_y=None, height=dp(34)))
        self.full_name = Field("Nom complet")
        self.email = Field("Adresse e-mail (ex. nom@domaine.com)")
        self.phone = Field("Téléphone")
        self.password = Field("Mot de passe (8 caractères minimum)", password=True)
        for field in [self.full_name, self.email, self.phone, self.password]:
            card.add_widget(field)
        self.message = MessageBar()
        card.add_widget(self.message)
        submit = GoldButton("Créer mon compte")
        submit.bind(on_release=lambda *_: self.submit())
        card.add_widget(submit)
        back = Button(text="J'ai déjà un compte : me connecter", background_normal="", background_color=[0, 0, 0, 0], color=GOLD, size_hint_y=None, height=dp(40))
        back.bind(on_release=lambda *_: self.navigate("login"))
        card.add_widget(back)
        holder.add_widget(card)
        scroll.add_widget(holder)
        root.add_widget(scroll)
        self.add_widget(root)

    def submit(self) -> None:
        values = [self.full_name.value, self.email.value, self.phone.value, self.password.value]
        if not all(values) or len(self.password.value) < 8:
            self.message.show("Renseignez tous les champs et un mot de passe de 8 caractères.", DANGER)
            return
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.email.value) is None:
            self.message.show("Adresse e-mail invalide. Utilisez le format nom@domaine.com.", DANGER)
            return
        self.message.show("Création du compte...", MUTED)
        work = lambda: self.api.register(*values)
        self.run_async(work, lambda _: self._registered(), lambda error: self.message.show(error, DANGER))

    def _registered(self) -> None:
        self.navigate("login")
        self.manager.get_screen("login").message.show("Compte créé. Connectez-vous.", SUCCESS)


class ReservationScreen(BaseScreen):
    offer: dict[str, Any] = {}

    def on_pre_enter(self, *_: Any) -> None:
        if not self.offer or "id" not in self.offer:
            self._show_navigation_error("L'offre sélectionnée est introuvable. Revenez à la liste des offres.")
            return
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("offers"))
        root.add_widget(title_label("Réserver votre prestation", 28))
        root.add_widget(Label(text=f"Offre sélectionnée : {self.offer.get('name', '')}", color=GOLD, size_hint_y=None, height=dp(25)))
        scroll = ScrollView()
        form = GridLayout(cols=2, spacing=dp(12), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        self.fields: dict[str, Field] = {}
        for key, label in [("client_name", "Nom complet"), ("email", "Adresse e-mail"), ("phone", "Téléphone"), ("location", "Adresse de l'événement"), ("event_date", "Date (AAAA-MM-JJ)"), ("event_time", "Heure (HH:MM)"), ("participants", "Nombre de participants")]:
            field = Field(label)
            self.fields[key] = field
            form.add_widget(field)
        self.event_type = Spinner(text="Type d'événement", values=("mariage", "anniversaire", "entreprise", "fete_privee", "autre"), size_hint_y=None, height=dp(52), background_color=NAVY_LIGHT, color=WHITE)
        form.add_widget(self.event_type)
        self.message_field = Field("Message complémentaire")
        self.message_field.input.multiline = True
        self.message_field.input.height = dp(90)
        form.add_widget(self.message_field)
        scroll.add_widget(form)
        root.add_widget(scroll)
        self.message = MessageBar()
        root.add_widget(self.message)
        submit = GoldButton("Confirmer ma réservation")
        submit.bind(on_release=lambda *_: self.submit())
        root.add_widget(submit)
        self.add_widget(root)

    def submit(self) -> None:
        values = {key: field.value for key, field in self.fields.items()}
        if not all(values.values()) or self.event_type.text == "Type d'événement":
            self.message.show("Veuillez remplir tous les champs obligatoires.", DANGER)
            return
        try:
            date.fromisoformat(values["event_date"])
            participants = int(values["participants"])
        except ValueError:
            self.message.show("Date ou nombre de participants invalide.", DANGER)
            return
        payload = {**values, "offer_id": self.offer["id"], "event_type": self.event_type.text, "participants": participants, "additional_message": self.message_field.value}
        self.message.show("Envoi de la réservation...", MUTED)
        self.run_async(lambda: self.api.create_booking(payload), self._success, lambda error: self.message.show(error, DANGER))

    def _success(self, booking: dict[str, Any]) -> None:
        self.message.show("Réservation enregistrée. Ouverture du contrat...", SUCCESS)
        Clock.schedule_once(lambda _: self.navigate("contract", booking_id=booking["id"]), 0.8)


class ContractScreen(BaseScreen):
    booking_id: int = 0

    def on_pre_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("reservations"))
        root.add_widget(title_label("Votre contrat de prestation", 28))
        self.message = MessageBar()
        root.add_widget(self.message)
        self.contract_box = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        self.contract_box.bind(minimum_height=self.contract_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.contract_box)
        root.add_widget(scroll)
        self.add_widget(root)
        self.run_async(
            lambda: self.api.get_contract(self.booking_id),
            self._show_contract,
            lambda error: self.message.show(error, DANGER),
        )

    def _show_contract(self, contract: dict[str, Any]) -> None:
        self.contract = contract
        self.contract_box.clear_widgets()
        self.contract_box.add_widget(Label(text=contract["content"], color=WHITE, halign="left", valign="top", text_size=(None, None), size_hint_y=None, height=dp(330)))
        if contract["status"] == "signe":
            self.contract_box.add_widget(Label(text=f"Contrat signé par {contract['signature_name']} le {contract['signed_at']}.", color=SUCCESS, size_hint_y=None, height=dp(40)))
            payment = GoldButton("Continuer vers le paiement")
            payment.bind(on_release=lambda *_: self.navigate("payment", booking_id=self.booking_id))
            self.contract_box.add_widget(payment)
            self.message.show("Votre contrat est signé. Le paiement de l'avance est requis.", SUCCESS)
            return
        self.signature = Field("Saisissez votre nom complet pour signer")
        self.contract_box.add_widget(self.signature)
        sign = GoldButton("Signer et envoyer le contrat")
        sign.bind(on_release=lambda *_: self.sign())
        self.contract_box.add_widget(sign)
        self.message.show("Lisez le contrat puis saisissez exactement votre nom complet.", MUTED)

    def sign(self) -> None:
        if not self.signature.value:
            self.message.show("Votre signature est obligatoire.", DANGER)
            return
        self.message.show("Signature et envoi en cours...", MUTED)
        self.run_async(
            lambda: self.api.sign_contract(self.booking_id, self.signature.value),
            lambda _: self._signed(),
            lambda error: self.message.show(error, DANGER),
        )

    def _signed(self) -> None:
        self.message.show("Contrat signé. Paiement de l'avance requis.", SUCCESS)
        Clock.schedule_once(lambda _: self.navigate("payment", booking_id=self.booking_id), 0.8)


class PaymentScreen(BaseScreen):
    booking_id: int = 0

    def on_pre_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("reservations"))
        root.add_widget(title_label("Paiement de l'avance", 28))
        root.add_widget(Label(text="Choisissez votre opérateur puis saisissez la référence du paiement.", color=MUTED, size_hint_y=None, height=dp(30)))
        self.message = MessageBar()
        root.add_widget(self.message)
        self.method = Spinner(
            text="Choisir un moyen de paiement",
            values=("MVola", "Orange Money", "Airtel Money"),
            size_hint_y=None,
            height=dp(52),
            background_color=NAVY_LIGHT,
            color=WHITE,
        )
        self.reference = Field("Référence du paiement")
        root.add_widget(self.method)
        root.add_widget(self.reference)
        submit = GoldButton("Envoyer la référence")
        submit.bind(on_release=lambda *_: self.submit())
        root.add_widget(submit)
        self.add_widget(root)

    def submit(self) -> None:
        methods = {"MVola": "mvola", "Orange Money": "orange_money", "Airtel Money": "airtel_money"}
        if self.method.text not in methods or not self.reference.value:
            self.message.show("Sélectionnez un opérateur et renseignez la référence.", DANGER)
            return
        self.message.show("Envoi du paiement en cours...", MUTED)
        self.run_async(
            lambda: self.api.submit_payment(self.booking_id, methods[self.method.text], self.reference.value),
            self._submitted,
            lambda error: self.message.show(error, DANGER),
        )

    def _submitted(self, _: dict[str, Any]) -> None:
        self.message.show("Paiement transmis. En attente de confirmation de l'administrateur.", SUCCESS)
        Clock.schedule_once(lambda _: self.navigate("reservations"), 1.4)


class ClientDashboardScreen(BaseScreen):
    def on_pre_enter(self, *_: Any) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("home"))
        root.add_widget(title_label("Mon espace", 30))
        self.profile = Card(orientation="vertical", size_hint_y=None, height=dp(150))
        self.profile.add_widget(Label(text="Chargement de votre profil...", color=MUTED))
        root.add_widget(self.profile)
        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        reservations = PrimaryButton("Voir mes réservations")
        reservations.bind(on_release=lambda *_: self.navigate("reservations"))
        offers = GoldButton("Réserver une prestation")
        offers.bind(on_release=lambda *_: self.navigate("offers"))
        actions.add_widget(reservations)
        actions.add_widget(offers)
        root.add_widget(actions)
        self.add_widget(root)
        self.run_async(self.api.me, self._show_profile, lambda error: self.profile.children[0].__setattr__("text", error))

    def _show_profile(self, user: dict[str, Any]) -> None:
        self.profile.clear_widgets()
        self.profile.add_widget(Label(text=user["full_name"], color=GOLD, font_size=dp(20), bold=True))
        self.profile.add_widget(Label(text=f"{user['email']}  •  {user['phone']}", color=MUTED))


class MyReservationsScreen(BaseScreen):
    def on_pre_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar("reservations"))
        title = Label(text="Mes réservations", color=WHITE, font_size=dp(30), bold=True, halign="center", valign="middle", text_size=(None, dp(40)), size_hint_y=None, height=dp(42))
        root.add_widget(title)
        self.count_label = Label(text="Chargement des réservations...", color=MUTED, halign="center", valign="middle", text_size=(None, dp(24)), size_hint_y=None, height=dp(26))
        root.add_widget(self.count_label)
        self.message = MessageBar()
        root.add_widget(self.message)
        scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(12), padding=[dp(4), dp(8)], size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)
        self.add_widget(root)
        if not self.api.is_authenticated:
            self.message.show("Connectez-vous pour consulter vos réservations.", DANGER)
            return
        self.run_async(self.api.my_bookings, self._show, lambda error: self.message.show(error, DANGER))

    def _show(self, bookings: list[dict[str, Any]]) -> None:
        self.list_box.clear_widgets()
        self.count_label.text = f"{len(bookings)} réservation(s)"
        if not bookings:
            self.list_box.add_widget(Label(text="Aucune réservation pour le moment.", color=MUTED, size_hint_y=None, height=dp(50)))
        for booking in bookings:
            card = Card(orientation="vertical", size_hint_y=None, height=dp(190), padding=[dp(16), dp(12)], spacing=dp(7))
            header = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
            header.add_widget(wrapped_label(booking["offer_name"], color=GOLD, font_size=dp(16), bold=True))
            badge_holder = AnchorLayout(anchor_x="right", anchor_y="center", size_hint_x=None, width=dp(128))
            badge_holder.add_widget(StatusBadge(booking["status"], size_hint_x=None, width=dp(118)))
            header.add_widget(badge_holder)
            card.add_widget(header)
            content = BoxLayout(orientation="vertical", spacing=dp(3), size_hint_y=None, height=dp(82))
            content.add_widget(wrapped_label(f"Date : {booking['event_date']}    Heure : {booking['event_time']}", color=WHITE, font_size=dp(13), size_hint_y=None, height=dp(22)))
            content.add_widget(wrapped_label(f"Client : {booking['client_name']}    Événement : {booking['event_type']}", color=MUTED, font_size=dp(12), size_hint_y=None, height=dp(22)))
            content.add_widget(wrapped_label(f"Adresse : {booking['location']}", color=MUTED, font_size=dp(12), size_hint_y=None, height=dp(34)))
            card.add_widget(content)
            payment_label = {"a_payer": "À payer", "soumis": "Paiement soumis", "confirme": "Paiement confirmé"}.get(booking.get("payment_status"), "À payer")
            card.add_widget(wrapped_label(f"Paiement : {payment_label}", color=GOLD, font_size=dp(12), size_hint_y=None, height=dp(22)))
            actions = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
            if booking["status"] == "en_attente":
                cancel = Button(text="Annuler", background_normal="", background_color=[0, 0, 0, 0], color=DANGER, size_hint_x=None, width=dp(92))
                cancel.bind(on_release=lambda _, booking_id=booking["id"]: self.cancel(booking_id))
                actions.add_widget(cancel)
            details = PrimaryButton("Détails", size_hint_x=None, width=dp(100))
            details.bind(on_release=lambda _, item=booking: self.show_details(item))
            actions.add_widget(details)
            contract = GoldButton("Voir le contrat", size_hint_x=None, width=dp(142))
            contract.bind(on_release=lambda _, booking_id=booking["id"]: self.navigate("contract", booking_id=booking_id))
            actions.add_widget(contract)
            card.add_widget(actions)
            def adapt_card(_, width, action_row=actions, booking_card=card):
                compact = width < dp(560)
                action_row.orientation = "vertical" if compact else "horizontal"
                for action in action_row.children:
                    action.size_hint_x = 1 if compact else None
                    action.width = 0 if compact else action.width
                    action.height = dp(34)
                action_row.height = dp(118) if compact else dp(34)
                booking_card.height = dp(274) if compact else dp(190)
            card.bind(width=adapt_card)
            self.list_box.add_widget(card)
        self.message.show(f"{len(bookings)} réservation(s)", SUCCESS)

    def show_details(self, booking: dict[str, Any]) -> None:
        details = (
            f"Offre : {booking['offer_name']}\n"
            f"Date : {booking['event_date']} à {booking['event_time']}\n"
            f"Client : {booking['client_name']}\n"
            f"Adresse : {booking['location']}\n"
            f"Type : {booking['event_type']}\n"
            f"Participants : {booking['participants']}\n"
            f"Paiement : {booking.get('payment_method') or 'Non renseigné'}\n"
            f"Référence : {booking.get('payment_reference') or 'Non renseignée'}"
        )
        content = Card(orientation="vertical", padding=dp(20))
        content.add_widget(wrapped_label(details, color=WHITE, font_size=dp(14)))
        close = GoldButton("Fermer")
        popup = Popup(title="Détails de la réservation", content=content, size_hint=(0.82, 0.62), separator_color=GOLD, background_color=NAVY_LIGHT)
        close.bind(on_release=popup.dismiss)
        content.add_widget(close)
        popup.open()

    def cancel(self, booking_id: int) -> None:
        self.run_async(lambda: self.api.cancel_booking(booking_id), lambda _: self.refresh(), lambda error: self.message.show(error, DANGER))


class AdminDashboardScreen(BaseScreen):
    refresh_event: Any = None
    all_bookings: list[dict[str, Any]] = []
    booking_filter: str = "all"
    booking_filter_labels = {
        "Toutes": "all",
        "En attente": "en_attente",
        "Confirmées": "confirmee",
        "Refusées": "refusee",
        "Annulées": "annulee",
    }

    def on_pre_enter(self, *_: Any) -> None:
        if not self.api.is_authenticated or self.api.user is None or self.api.user.get("role") != "admin":
            self.navigate("login")
            return
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        root = self.content()
        root.add_widget(self.nav_bar())
        root.add_widget(title_label("Espace administrateur", 30))
        self.message = MessageBar()
        root.add_widget(self.message)
        self.stats_box = GridLayout(cols=4, spacing=dp(12), size_hint_y=None, height=dp(110))
        self.stats_box.bind(width=lambda _, width: setattr(self.stats_box, "cols", 2 if width < dp(760) else 4))
        root.add_widget(self.stats_box)
        filter_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        filter_row.add_widget(Label(text="Filtrer les réservations :", color=MUTED, size_hint_x=None, width=dp(180)))
        self.booking_filter_spinner = Spinner(
            text=next(label for label, code in self.booking_filter_labels.items() if code == self.booking_filter),
            values=tuple(self.booking_filter_labels),
            size_hint_x=None,
            width=dp(180),
            background_color=NAVY_LIGHT,
            color=WHITE,
        )
        self.booking_filter_spinner.bind(text=self._filter_bookings)
        filter_row.add_widget(self.booking_filter_spinner)
        root.add_widget(filter_row)
        scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(10), padding=[dp(4), dp(8)], size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)
        support_scroll = ScrollView()
        self.support_box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.support_box.bind(minimum_height=self.support_box.setter("height"))
        support_scroll.add_widget(self.support_box)
        root.add_widget(support_scroll)
        self.add_widget(root)
        self.refresh_bookings()
        self.run_async(lambda: (self.api.statistics(), self.api.offers(), self.api.clients()), self._show_supporting_data, lambda error: self.message.show(error, DANGER))
        if self.refresh_event is None:
            self.refresh_event = Clock.schedule_interval(lambda _: self.refresh_silent(), 30)

    def refresh_silent(self) -> None:
        if self.manager and self.manager.current == "admin":
            self.refresh_bookings()
            self.run_async(lambda: (self.api.statistics(), self.api.offers(), self.api.clients()), self._show_supporting_data, lambda error: self.message.show(error, DANGER))

    def refresh_bookings(self) -> None:
        self.run_async(self.api.admin_bookings, self._show_bookings, lambda error: self.message.show(f"Réservations : {error}", DANGER))

    def _show_supporting_data(self, result: tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]) -> None:
        stats, offers, clients = result
        self.stats_box.clear_widgets()
        statuses = stats.get("by_status", {})
        for label, value in [("Total", stats.get("total", 0)), ("En attente", statuses.get("en_attente", 0)), ("Confirmées", statuses.get("confirmee", 0)), ("Refusées", statuses.get("refusee", 0))]:
            card = Card(orientation="vertical", padding=dp(12))
            card.add_widget(Label(text=str(value), color=GOLD, font_size=dp(25), bold=True))
            card.add_widget(Label(text=label, color=MUTED))
            self.stats_box.add_widget(card)

        self._render_offers_and_clients(offers, clients)

    def _show_bookings(self, bookings: list[dict[str, Any]]) -> None:
        self.all_bookings = bookings
        self._render_bookings()

    def _filter_bookings(self, _, value: str) -> None:
        self.booking_filter = self.booking_filter_labels[value]
        self._render_bookings()

    def _render_bookings(self) -> None:
        self.list_box.clear_widgets()
        bookings = [
            booking
            for booking in self.all_bookings
            if self.booking_filter == "all" or booking["status"] == self.booking_filter
        ]
        for booking in bookings:
            card = Card(orientation="vertical", size_hint_y=None, height=dp(252), padding=[dp(16), dp(12)], spacing=dp(8))
            payment_status = booking.get("payment_status", "a_payer")
            payment_label = {
                "a_payer": "À payer",
                "soumis": "Paiement soumis",
                "confirme": "Paiement confirmé",
            }.get(payment_status, payment_status.replace("_", " ").title())
            header = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
            header.add_widget(wrapped_label(f"#{booking['id']}  {booking['offer_name']}", color=GOLD, font_size=dp(15), bold=True))
            badge_holder = AnchorLayout(anchor_x="right", anchor_y="center", size_hint_x=None, width=dp(128))
            badge_holder.add_widget(StatusBadge(booking["status"], size_hint_x=None, width=dp(118)))
            header.add_widget(badge_holder)
            card.add_widget(header)
            content = BoxLayout(orientation="vertical", spacing=dp(3), size_hint_y=None, height=dp(96))
            content.add_widget(wrapped_label(f"Client : {booking['client_name']}  •  {booking['event_type']}", color=WHITE, font_size=dp(12), size_hint_y=None, height=dp(22)))
            content.add_widget(wrapped_label(f"Date : {booking['event_date']}    Heure : {booking['event_time']}    Participants : {booking['participants']}", color=MUTED, font_size=dp(12), size_hint_y=None, height=dp(22)))
            content.add_widget(wrapped_label(f"Adresse : {booking['location']}", color=MUTED, font_size=dp(12), size_hint_y=None, height=dp(24)))
            payment_reference = booking.get("payment_reference") or "non transmise"
            payment_method = booking.get("payment_method") or "—"
            content.add_widget(
                wrapped_label(
                    f"Paiement : {payment_label}  •  {payment_method}\nRéférence : {payment_reference}",
                    color=GOLD,
                    font_size=dp(11),
                    size_hint_y=None,
                    height=dp(40),
                )
            )
            card.add_widget(content)
            actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
            accept = GoldButton("Accepter", size_hint_x=None, width=dp(100))
            accept.bind(on_release=lambda _, booking_id=booking["id"]: self.change_status(booking_id, "confirmee"))
            refuse = Button(text="Refuser", background_normal="", background_color=[0, 0, 0, 0], color=DANGER, size_hint_x=None, width=dp(82))
            refuse.bind(on_release=lambda _, booking_id=booking["id"]: self.change_status(booking_id, "refusee"))
            confirm_payment = GoldButton("Paiement", size_hint_x=None, width=dp(100))
            confirm_payment.disabled = payment_status != "soumis"
            confirm_payment.bind(on_release=lambda _, booking_id=booking["id"]: self.confirm_payment(booking_id))
            details = PrimaryButton("Détails", size_hint_x=None, width=dp(82))
            details.bind(on_release=lambda _, item=booking: self.show_booking_details(item))
            contract = PrimaryButton("Contrat", size_hint_x=None, width=dp(82))
            contract.bind(on_release=lambda _, booking_id=booking["id"]: self.show_contract(booking_id))
            actions.add_widget(accept)
            actions.add_widget(refuse)
            actions.add_widget(confirm_payment)
            actions.add_widget(details)
            actions.add_widget(contract)
            card.add_widget(actions)
            def adapt_admin_card(_, width, action_row=actions, booking_card=card):
                compact = width < dp(700)
                action_row.orientation = "vertical" if compact else "horizontal"
                for action in action_row.children:
                    action.size_hint_x = 1 if compact else None
                    action.width = 0 if compact else action.width
                    action.height = dp(34)
                action_row.height = dp(194) if compact else dp(42)
                booking_card.height = dp(404) if compact else dp(252)
            card.bind(width=adapt_admin_card)
            self.list_box.add_widget(card)
        refresh = PrimaryButton("Actualiser les réservations")
        refresh.bind(on_release=lambda *_: self.refresh_silent())
        self.list_box.add_widget(refresh)

        if not bookings:
            self.message.show("Aucune réservation enregistrée.", MUTED)
        else:
            self.message.show(f"{len(bookings)} réservation(s) administrée(s)", SUCCESS)

    def _render_offers_and_clients(self, offers: list[dict[str, Any]], clients: list[dict[str, Any]]) -> None:
        self.support_box.clear_widgets()
        self._render_hero_editor()
        self.support_box.add_widget(Label(text="Modifier les offres", color=GOLD, font_size=dp(20), bold=True, size_hint_y=None, height=dp(42)))
        self.offer_editors = {}
        for offer in offers:
            editor = Card(orientation="vertical", size_hint_y=None, spacing=dp(8))
            editor.bind(minimum_height=editor.setter("height"))
            name = Field("Nom", text=offer["name"])
            subtitle = Field("Sous-titre", text=offer.get("subtitle") or "")
            description = Field("Description principale", text=offer["description"])
            detailed = Field("Description détaillée", text=offer.get("detailed_description") or "")
            detailed.input.multiline = True
            detailed.input.height = dp(78)
            detailed.height = dp(106)
            tricks = Field("Tours de magie (un par ligne)", text=offer.get("magic_tricks") or "")
            tricks.input.multiline = True
            tricks.input.height = dp(78)
            tricks.height = dp(106)
            conclusion = Field("Texte de conclusion", text=offer.get("conclusion") or "")
            conclusion.input.multiline = True
            conclusion.input.height = dp(58)
            conclusion.height = dp(86)
            price = Field("Prix (Ar)")
            price.input.text = str(offer["price"])
            duration = Field("Durée en minutes")
            duration.input.text = str(offer["duration_minutes"])
            editor.add_widget(name)
            editor.add_widget(subtitle)
            editor.add_widget(description)
            editor.add_widget(detailed)
            editor.add_widget(tricks)
            editor.add_widget(conclusion)
            image_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(90))
            preview: Any = AsyncImage(source=offer.get("image_url") or "", size_hint_x=None, width=dp(120), allow_stretch=True, keep_ratio=True, nocache=True)
            if not offer.get("image_url"):
                preview = PhotoPlaceholder("Ajouter une image", size_hint_x=None, width=dp(120))
                image_row.add_widget(preview)
            else:
                image_row.add_widget(preview)
            choose = PrimaryButton("🖼  Choisir une image")
            choose.bind(on_release=lambda _, item=offer, image_preview=preview: self.choose_image(item, image_preview))
            remove = Button(text="Supprimer l'image", background_normal="", background_color=[0, 0, 0, 0], color=DANGER)
            remove.bind(on_release=lambda _, item=offer, image_preview=preview: self.remove_image(item, image_preview))
            image_row.add_widget(choose)
            image_row.add_widget(remove)
            editor.add_widget(image_row)
            self.offer_editors[offer["id"]] = {"image_path": None, "remove_image": False, "preview": preview}
            row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(72))
            row.add_widget(price)
            row.add_widget(duration)
            editor.add_widget(row)
            save = PrimaryButton("Enregistrer les modifications")
            save.bind(on_release=lambda _, item=offer, n=name, st=subtitle, d=description, dd=detailed, tr=tricks, co=conclusion, p=price, t=duration: self.save_offer(item, n, st, d, dd, tr, co, p, t))
            editor.add_widget(save)
            self.support_box.add_widget(editor)
        self.support_box.add_widget(Label(text="Clients inscrits", color=GOLD, font_size=dp(20), bold=True, size_hint_y=None, height=dp(42)))
        for client in clients:
            self.support_box.add_widget(Label(text=f"{client['full_name']}  •  {client['email']}  •  {client['phone']}", color=WHITE, halign="left", size_hint_y=None, height=dp(36)))

    def _render_hero_editor(self) -> None:
        editor = Card(orientation="vertical", size_hint_y=None, height=dp(245))
        editor.add_widget(Label(text="Image de la bannière d'accueil", color=GOLD, font_size=dp(20), bold=True, size_hint_y=None, height=dp(38)))
        preview: Any = PhotoPlaceholder("Ajouter une image", height=dp(110))
        editor.add_widget(preview)
        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        choose = PrimaryButton("Choisir une image")
        remove = Button(text="Supprimer l'image", background_normal="", background_color=[0, 0, 0, 0], color=DANGER)
        choose.bind(on_release=lambda *_: self.choose_hero_image(preview))
        remove.bind(on_release=lambda *_: self.remove_hero_image(preview))
        actions.add_widget(choose)
        actions.add_widget(remove)
        editor.add_widget(actions)
        self.hero_editor_preview = preview
        self.support_box.add_widget(editor)
        self.run_async(self.api.hero_image, lambda url: self._set_hero_preview(preview, url), lambda _: None)

    def _set_hero_preview(self, preview: AsyncImage, image_url: str | None) -> None:
        if isinstance(preview, PhotoPlaceholder):
            if image_url and preview.parent is not None:
                parent = preview.parent
                parent.remove_widget(preview)
                parent.add_widget(AsyncImage(source=image_url, allow_stretch=True, keep_ratio=True, nocache=True))
            return
        preview.source = image_url or ""
        if image_url:
            preview.reload()

    def choose_hero_image(self, preview: Any) -> None:
        path = self._choose_local_image()
        if not path:
            return
        if isinstance(preview, PhotoPlaceholder):
            parent = preview.parent
            if parent is not None:
                parent.remove_widget(preview)
                parent.add_widget(AsyncImage(source=path, allow_stretch=True, keep_ratio=True, nocache=True))
        else:
            self.refresh_image(preview, path)
        self.message.show("Enregistrement de la bannière...", MUTED)
        self.run_async(lambda: self.api.upload_hero_image(path), lambda _: self._hero_saved(), lambda error: self.message.show(error, DANGER))

    def remove_hero_image(self, preview: Any) -> None:
        self.run_async(self.api.delete_hero_image, lambda _: self._hero_saved(), lambda error: self.message.show(error, DANGER))

    def _hero_saved(self) -> None:
        self.message.show("Image de bannière mise à jour.", SUCCESS)
        self.refresh()

    def change_status(self, booking_id: int, value: str) -> None:
        self.run_async(lambda: self.api.update_booking_status(booking_id, value), lambda _: self.refresh(), lambda error: self.message.show(error, DANGER))

    def confirm_payment(self, booking_id: int) -> None:
        self.run_async(
            lambda: self.api.confirm_payment(booking_id),
            lambda _: self.refresh(),
            lambda error: self.message.show(error, DANGER),
        )

    def show_booking_details(self, booking: dict[str, Any]) -> None:
        details = "\n".join(f"{key}: {value}" for key, value in booking.items() if not key.startswith("_"))
        content = Card(orientation="vertical", padding=dp(24))
        content.add_widget(Label(text=details, color=WHITE, halign="left", valign="top", text_size=(None, None)))
        close = GoldButton("Fermer")
        popup = Popup(title=f"Réservation #{booking['id']}", content=content, size_hint=(0.8, 0.7), separator_color=GOLD, background_color=NAVY_LIGHT)
        close.bind(on_release=popup.dismiss)
        content.add_widget(close)
        popup.open()

    def show_contract(self, booking_id: int) -> None:
        self.message.show("Chargement du contrat...", MUTED)
        self.run_async(
            lambda: self.api.admin_contract(booking_id),
            lambda contract: self._show_contract_popup(contract),
            lambda error: self.message.show(error, DANGER),
        )

    def _show_contract_popup(self, contract: dict[str, Any]) -> None:
        signature = contract["signature_name"] or "Non signé"
        text = f"{contract['content']}\n\nStatut : {contract['status']}\nSignature : {signature}\nDate : {contract['signed_at'] or '—'}"
        content = Card(orientation="vertical", padding=dp(24))
        content.add_widget(Label(text=text, color=WHITE, halign="left", valign="top", text_size=(None, None)))
        close = GoldButton("Fermer")
        popup = Popup(title=f"Contrat de la réservation #{contract['booking_id']}", content=content, size_hint=(0.85, 0.8), separator_color=GOLD, background_color=NAVY_LIGHT)
        close.bind(on_release=popup.dismiss)
        content.add_widget(close)
        popup.open()

    def save_offer(self, offer: dict[str, Any], name: Field, subtitle: Field, description: Field, detailed: Field, tricks: Field, conclusion: Field, price: Field, duration: Field) -> None:
        try:
            payload = {
                "name": name.value,
                "subtitle": subtitle.value or None,
                "description": description.value,
                "detailed_description": detailed.value or None,
                "magic_tricks": tricks.value or None,
                "conclusion": conclusion.value or None,
                "price": float(price.value),
                "duration_minutes": int(duration.value),
            }
        except ValueError:
            self.message.show("Prix ou durée invalide.", DANGER)
            return
        editor_state = self.offer_editors[offer["id"]]

        def save() -> dict[str, Any]:
            updated = self.api.update_offer(offer["id"], payload)
            if editor_state["image_path"]:
                updated = self.api.upload_offer_image(offer["id"], editor_state["image_path"])
            elif editor_state["remove_image"]:
                updated = self.api.delete_offer_image(offer["id"])
            return updated

        self.run_async(save, self._saved_offer, lambda error: self.message.show(error, DANGER))

    def choose_image(self, offer: dict[str, Any], preview: Any) -> None:
        path = self._choose_local_image()
        if not path:
            return
        state = self.offer_editors[offer["id"]]
        state["image_path"] = path
        state["remove_image"] = False
        if isinstance(preview, PhotoPlaceholder):
            parent = preview.parent
            if parent is not None:
                parent.remove_widget(preview)
                replacement = AsyncImage(source=path, size_hint_x=None, width=dp(120), allow_stretch=True, keep_ratio=True, nocache=True)
                parent.add_widget(replacement, index=0)
                state["preview"] = replacement
        else:
            self.refresh_image(preview, path)

    @staticmethod
    def _choose_local_image() -> str | None:
        root = tk.Tk()
        try:
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Choisir une image",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("Tous les fichiers", "*.*")],
            )
        finally:
            root.destroy()
        if not path:
            return None
        if path.lower().rsplit(".", 1)[-1] not in {"jpg", "jpeg", "png", "webp"}:
            return None
        return path

    def remove_image(self, offer: dict[str, Any], preview: AsyncImage) -> None:
        state = self.offer_editors[offer["id"]]
        state["image_path"] = None
        state["remove_image"] = True
        if isinstance(preview, PhotoPlaceholder):
            return
        self.refresh_image(preview, "")

    def _saved_offer(self, _: dict[str, Any]) -> None:
        self.refresh()
        Clock.schedule_once(lambda _: self.message.show("Offre mise à jour avec succès.", SUCCESS), 0.1)
