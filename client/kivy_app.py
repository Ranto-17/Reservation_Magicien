"""Modern Kivy client for the Magic Reservation API."""

import sys
from pathlib import Path

# Running this file directly puts ``client`` rather than the project root on
# sys.path. Add the root so the package imports work in both launch modes.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.screenmanager import FadeTransition, ScreenManager

from client.screens import (
    AdminDashboardScreen,
    ClientDashboardScreen,
    ContractScreen,
    PaymentScreen,
    HomeScreen,
    LoginScreen,
    MyReservationsScreen,
    OfferDetailScreen,
    OffersScreen,
    RegisterScreen,
    ReservationScreen,
)
from client.services.api import ApiService
from client.theme import NAVY


class MagicReservationApp(App):
    title = "Magic Reservation"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api = ApiService()

    def build(self) -> ScreenManager:
        Window.clearcolor = NAVY
        Window.size = (1280, 760)
        Window.minimum_size = (960, 620)
        manager = ScreenManager(transition=FadeTransition(duration=0.18))
        screens = [
            HomeScreen(name="home"),
            LoginScreen(name="login"),
            RegisterScreen(name="register"),
            OffersScreen(name="offers"),
            OfferDetailScreen(name="offer_detail"),
            ReservationScreen(name="reservation"),
            ContractScreen(name="contract"),
            PaymentScreen(name="payment"),
            ClientDashboardScreen(name="client"),
            MyReservationsScreen(name="reservations"),
            AdminDashboardScreen(name="admin"),
        ]
        for screen in screens:
            screen.api = self.api
            manager.add_widget(screen)
        return manager


if __name__ == "__main__":
    MagicReservationApp().run()
