from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

from .theme import CARD_RADIUS, DANGER, GOLD, MUTED, NAVY, NAVY_LIGHT, PURPLE, PURPLE_LIGHT, SUCCESS, WHITE


def rounded_background(widget: Any, color: list[float] = NAVY_LIGHT) -> None:
    panel_color = [color[0], color[1], color[2], 0.72]
    with widget.canvas.before:
        Color(*panel_color)
        shape = RoundedRectangle(pos=widget.pos, size=widget.size, radius=CARD_RADIUS)
    widget.bind(pos=lambda *_: setattr(shape, "pos", widget.pos), size=lambda *_: setattr(shape, "size", widget.size))


def elevated_background(widget: Any, color: list[float] = NAVY_LIGHT) -> None:
    panel_color = [color[0], color[1], color[2], 0.42]
    with widget.canvas.before:
        Color(*panel_color)
        shape = RoundedRectangle(pos=widget.pos, size=widget.size, radius=CARD_RADIUS)
    widget.bind(
        pos=lambda *_: setattr(shape, "pos", widget.pos),
        size=lambda *_: setattr(shape, "size", widget.size),
    )


def image_background(widget: Any, source: str) -> None:
    texture = CoreImage(source).texture
    with widget.canvas.before:
        background = Rectangle(pos=widget.pos, size=widget.size, texture=texture)
        Color(0.03, 0.02, 0.10, 0.38)
        overlay = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *_: (
            setattr(background, "pos", widget.pos),
            setattr(overlay, "pos", widget.pos),
        ),
        size=lambda *_: (
            setattr(background, "size", widget.size),
            setattr(overlay, "size", widget.size),
        ),
    )


def parchment_background(widget: Any) -> None:
    with widget.canvas.before:
        Color(0.62, 0.40, 0.16, 1)
        border = RoundedRectangle(
            pos=(widget.x - dp(3), widget.y - dp(3)),
            size=(widget.width + dp(6), widget.height + dp(6)),
            radius=[dp(14)],
        )
        Color(0.91, 0.82, 0.64, 1)
        paper = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(12)])
    widget.bind(
        pos=lambda *_: (
            setattr(paper, "pos", widget.pos),
            setattr(border, "pos", (widget.x - dp(3), widget.y - dp(3))),
        ),
        size=lambda *_: (
            setattr(paper, "size", widget.size),
            setattr(border, "size", (widget.width + dp(6), widget.height + dp(6))),
        ),
    )


def wrapped_label(text: str, color: list[float] = WHITE, font_size: float = dp(14), **kwargs: Any) -> Label:
    kwargs.setdefault("color", color)
    kwargs.setdefault("font_size", font_size)
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "top")
    label = Label(text=text, **kwargs)
    label.bind(width=lambda instance, width: setattr(instance, "text_size", (max(width, 1), None)))
    return label


class PageLayout(BoxLayout):
    """Responsive application shell: a fixed rail and a flexible content area."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "horizontal")
        super().__init__(**kwargs)
        background_path = Path(__file__).resolve().parent / "assets" / "app-background.png"
        image_background(self, str(background_path))
        self.sidebar = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(224), padding=[dp(14), dp(18)], spacing=dp(8))
        self.main = BoxLayout(orientation="vertical", padding=[dp(30), dp(24)], spacing=dp(14))
        rounded_background(self.sidebar, NAVY_LIGHT)
        self.add_widget(self.sidebar)
        self.add_widget(self.main)
        self.bind(width=self._adapt_layout)

    def _adapt_layout(self, *_: Any) -> None:
        self.sidebar.width = dp(176) if self.width < dp(900) else dp(224)
        self.main.padding = [dp(18), dp(18)] if self.width < dp(900) else [dp(30), dp(24)]

    def add_widget(self, widget: Widget, *args: Any, **kwargs: Any) -> None:
        if isinstance(widget, Sidebar):
            self.sidebar.clear_widgets()
            self.sidebar.add_widget(widget, *args, **kwargs)
            return
        if hasattr(self, "main") and widget not in (self.sidebar, self.main):
            self.main.add_widget(widget, *args, **kwargs)
            return
        super().add_widget(widget, *args, **kwargs)


class Sidebar(BoxLayout):
    def __init__(self, active: str, authenticated: bool, is_admin: bool, navigate: Callable[[str], None], logout: Callable[[], None], go_back: Callable[[], None], **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", 1)
        super().__init__(**kwargs)
        if active != "home":
            back = Button(text="<  Retour", background_normal="", background_color=[0, 0, 0, 0], color=GOLD, font_size=dp(12), halign="left", text_size=(None, None), padding=[dp(10), 0], size_hint_y=None, height=dp(38))
            back.bind(on_release=lambda *_: go_back())
            self.add_widget(back)
        self.add_widget(Label(text="MAGIC\nRESERVATION", color=GOLD, font_size=dp(18), bold=True, halign="left", valign="middle", text_size=(None, dp(58)), padding=[dp(8), 0], size_hint_y=None, height=dp(68)))
        self.add_widget(Label(text="L'art de l'illusion", color=MUTED, font_size=dp(11), halign="left", text_size=(None, None), size_hint_y=None, height=dp(24)))
        self.add_widget(Widget())
        links = [("HOME", "Accueil", "home"), ("OFFRES", "Nos offres", "offers")]
        if authenticated:
            links.append(("RES", "Mes réservations", "reservations"))
        if is_admin:
            links = [("HOME", "Dashboard", "admin"), ("RES", "Réservations", "admin"), ("OFFRES", "Gestion des offres", "admin")]
        for icon, label, target in links:
            button = Button(text=f"{icon}   {label}", background_normal="", background_color=PURPLE if active == target else [0, 0, 0, 0], color=WHITE if active == target else MUTED, font_size=dp(12), halign="left", text_size=(None, None), padding=[dp(10), 0], size_hint_y=None, height=dp(46))
            button.bind(on_release=lambda _, screen=target: navigate(screen))
            self.add_widget(button)
        self.add_widget(Widget())
        if authenticated:
            logout_button = Button(text="SORTIR   Déconnexion", background_normal="", background_color=[0, 0, 0, 0], color=MUTED, font_size=dp(12), halign="left", text_size=(None, None), padding=[dp(10), 0], size_hint_y=None, height=dp(46))
            logout_button.bind(on_release=lambda *_: logout())
            self.add_widget(logout_button)
        else:
            login_button = Button(text="LOGIN   Connexion", background_normal="", background_color=GOLD, color=NAVY, bold=True, font_size=dp(12), halign="left", text_size=(None, None), padding=[dp(10), 0], size_hint_y=None, height=dp(46))
            login_button.bind(on_release=lambda *_: navigate("login"))
            self.add_widget(login_button)


STATUS_STYLE = {
    "en_attente": ("En attente", GOLD),
    "confirmee": ("Confirmée", SUCCESS),
    "refusee": ("Refusée", DANGER),
    "annulee": ("Annulée", get_color_from_hex("#8D91A3")),
    "a_signer": ("À signer", GOLD),
    "a_payer": ("À payer", PURPLE_LIGHT),
    "soumis": ("Paiement soumis", get_color_from_hex("#66B7FF")),
    "confirme": ("Paiement confirmé", SUCCESS),
}


class StatusBadge(Label):
    def __init__(self, status: str, **kwargs: Any) -> None:
        text, color = STATUS_STYLE.get(status, (status.replace("_", " ").title(), MUTED))
        kwargs.setdefault("text", f"  {text}  ")
        kwargs.setdefault("color", color)
        kwargs.setdefault("font_size", dp(12))
        kwargs.setdefault("bold", True)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(28))
        super().__init__(**kwargs)
        rounded_background(self, [color[0] * 0.25, color[1] * 0.25, color[2] * 0.25, 1])


class PhotoPlaceholder(BoxLayout):
    def __init__(self, text: str = "Ajouter une image", **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(155))
        super().__init__(**kwargs)
        rounded_background(self, [0.12, 0.1, 0.22, 1])
        self.add_widget(Label(text="[ IMAGE ]", color=GOLD, font_size=dp(18), bold=True, size_hint_y=None, height=dp(34)))
        self.add_widget(Label(text=text, color=MUTED, font_size=dp(13), size_hint_y=None, height=dp(28)))


class Card(BoxLayout):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("padding", dp(18))
        kwargs.setdefault("spacing", dp(10))
        super().__init__(**kwargs)
        rounded_background(self)


class PrimaryButton(Button):
    normal_color = PURPLE
    pressed_color = PURPLE_LIGHT
    text_color = WHITE

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("text", text)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", [0, 0, 0, 0])
        kwargs.setdefault("color", self.text_color)
        kwargs.setdefault("font_size", dp(14))
        kwargs.setdefault("bold", True)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        super().__init__(**kwargs)
        with self.canvas.before:
            self._button_color = Color(self.normal_color[0], self.normal_color[1], self.normal_color[2], 0.84)
            self._button_shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(
            pos=lambda *_: setattr(self._button_shape, "pos", self.pos),
            size=lambda *_: setattr(self._button_shape, "size", self.size),
        )
        self.bind(state=self._state_changed)

    def _state_changed(self, *_: Any) -> None:
        self._button_color.rgb = (self.pressed_color if self.state == "down" else self.normal_color)[:3]


class GoldButton(PrimaryButton):
    normal_color = GOLD
    pressed_color = GOLD
    text_color = NAVY_LIGHT


class PurpleButton(PrimaryButton):
    normal_color = PURPLE
    pressed_color = PURPLE_LIGHT


class Field(BoxLayout):
    def __init__(self, hint: str, password: bool = False, text: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(5))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(72))
        super().__init__(**kwargs)
        self.add_widget(Label(text=hint, color=MUTED, font_size=dp(12), halign="left", text_size=(None, None), size_hint_y=None, height=dp(20)))
        self.input = TextInput(text=text, hint_text=hint, multiline=False, password=password, padding=[dp(12), dp(12)], background_normal="", background_color=[0.1, 0.11, 0.2, 1], foreground_color=WHITE, cursor_color=GOLD, size_hint_y=None, height=dp(44))
        self.add_widget(self.input)

    @property
    def value(self) -> str:
        return self.input.text.strip()


class MessageBar(Label):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("text", "")
        kwargs.setdefault("color", WHITE)
        kwargs.setdefault("font_size", dp(13))
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(36))
        super().__init__(**kwargs)
        self.text_size = (None, dp(36))

    def show(self, message: str, color: list[float]) -> None:
        self.text = message
        self.color = color


class OfferCard(Card):
    def __init__(self, offer: dict[str, Any], on_details: Callable[[dict[str, Any]], None], on_book: Callable[[dict[str, Any]], None], **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(430))
        super().__init__(**kwargs)
        image_url = offer.get("image_url")
        if image_url:
            image = AsyncImage(source=image_url, size_hint_y=None, height=dp(155), allow_stretch=True, keep_ratio=True, nocache=True)
            image.bind(on_error=lambda *_: self._use_local_image(image, offer.get("name", "")))
            self.add_widget(image)
        else:
            self.add_widget(PhotoPlaceholder())
        self.add_widget(wrapped_label(offer["name"].upper(), color=GOLD, font_size=dp(18), bold=True, size_hint_y=None, height=dp(34)))
        description = wrapped_label(offer["description"], color=MUTED, font_size=dp(13), size_hint_y=None, height=dp(80))
        self.add_widget(description)
        self.add_widget(Label(text=f"{offer['price']:,.0f} Ar  •  {offer['duration_minutes']} min", color=WHITE, font_size=dp(16), bold=True, halign="left", size_hint_y=None, height=dp(32)))
        actions = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(46))
        details = Button(text="Voir les détails", background_normal="", background_color=[0, 0, 0, 0], color=GOLD, font_size=dp(13))
        details.bind(on_release=lambda *_: on_details(offer))
        actions.add_widget(details)
        book = PrimaryButton("Réserver maintenant")
        book.bind(on_release=lambda *_: on_book(offer))
        actions.add_widget(book)
        self.add_widget(actions)

    @staticmethod
    def _use_local_image(image: AsyncImage, offer_name: str) -> None:
        filename = "close-up.png" if "close" in offer_name.lower() else "stage-show.png"
        local_path = Path(__file__).resolve().parent.parent / "uploads" / "offers" / filename
        if image.source != str(local_path):
            image.source = str(local_path)
            image.reload()
