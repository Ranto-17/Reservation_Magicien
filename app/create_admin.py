"""Create the first administrator interactively.

Run with: python -m app.create_admin
"""

from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import User, UserRole
from .security import hash_password


def ask_email() -> str:
    email = input("Adresse e-mail administrateur : ").strip().lower()
    try:
        return TypeAdapter(EmailStr).validate_python(email)
    except ValidationError as exc:
        raise SystemExit("Adresse e-mail invalide.") from exc


def ask_password() -> str:
    password = getpass("Mot de passe administrateur (8 caractères minimum) : ")
    confirmation = getpass("Confirmez le mot de passe : ")
    if len(password) < 8:
        raise SystemExit("Le mot de passe doit contenir au moins 8 caractères.")
    if password != confirmation:
        raise SystemExit("Les mots de passe ne correspondent pas.")
    return password


def main() -> None:
    Base.metadata.create_all(bind=engine)
    email = ask_email()
    password = ask_password()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role == UserRole.ADMIN:
                raise SystemExit("Un administrateur existe déjà avec cette adresse.")
            raise SystemExit("Cette adresse est déjà utilisée par un compte client.")
        db.add(
            User(
                full_name="Administrateur",
                email=email,
                phone="",
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    print(f"Administrateur créé : {email}")


if __name__ == "__main__":
    main()
