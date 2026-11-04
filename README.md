# Réservation Magicien

Application de réservation de prestations de magie avec API FastAPI/SQLite et
client Kivy.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Important : le chemin correct commence par `.\.venv` (un seul point pour le
répertoire courant). `..venv` est un chemin différent et n'existe pas dans ce
projet.

Si PowerShell bloque l'activation des scripts, utilisez directement
`.\.venv\Scripts\python.exe` sans activer l'environnement.

Modifiez `JWT_SECRET_KEY` dans `.env` avant un déploiement.

## Lancer l'API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

La documentation interactive est disponible sur <http://127.0.0.1:8000/docs>.
Pour créer un administrateur manuellement, sans mot de passe codé dans le
projet :

```powershell
.\.venv\Scripts\python.exe -m app.create_admin
```

La commande demande l'e-mail et le mot de passe, le hache avant l'enregistrement
et refuse les doublons. Les comptes déjà présents dans la base sont conservés.
Le compte historique `admin@magicien.local` reste compatible avec la connexion
de l'application, même si les nouveaux comptes doivent utiliser une adresse
e-mail standard.

## Lancer le client Kivy

Avec l'API démarrée dans un autre terminal :

```powershell
.\.venv\Scripts\python.exe -m client.kivy_app
```

Le lancement direct reste également possible :

```powershell
.\.venv\Scripts\python.exe .\client\kivy_app.py
```

Les clients s'inscrivent via `POST /auth/register`, puis se connectent via
OAuth2 (`POST /auth/login`). Les routes `/admin/*` nécessitent un JWT
administrateur. Les offres sont initialisées avec exactement deux offres et
leur prix est copié dans chaque réservation afin de conserver l'historique.
Le client propose les écrans d'accueil, offres, détails, connexion,
inscription, réservation, réservations client et tableau de bord
administrateur. Le backend doit être démarré avant le client Kivy.
Dans l'espace administrateur, les images d'offres se sélectionnent depuis
l'explorateur Windows. Elles sont validées (JPG, PNG ou WEBP, 5 Mo maximum),
stockées dans `uploads/offers/` et servies par `/uploads`.
Les offres et la bannière disposent d'emplacements photo personnalisables.
Une image absente affiche un cadre « Ajouter une image » plutôt qu'une image
fictive. L'administrateur peut choisir, remplacer ou supprimer les images
depuis l'explorateur Windows ; la bannière est enregistrée dans SQLite via
`site_settings`.
Après un enregistrement, l'image est rechargée sans cache dans Kivy et les
offres sont rafraîchies. La déconnexion efface la session et revient à
l'écran de connexion sans fermer la fenêtre.
Le tableau administrateur charge les réservations depuis SQLite et propose les
filtres Toutes, En attente, Confirmées, Refusées et Annulées, ainsi que les
actions de détail, acceptation, refus et actualisation.
Après chaque réservation, un contrat est généré. Le client le signe avec son
nom complet depuis l'écran dédié ; la signature et sa date sont conservées dans
SQLite et le contrat est consultable depuis l'espace administrateur.
Après la signature, le client est redirigé vers le paiement de l'avance par
MVola, Orange Money ou Airtel Money. Il transmet la référence de transaction ;
la réservation reste en attente jusqu'à confirmation du paiement par
l'administrateur. Une fois confirmé, son statut devient `confirmee`.
La page « Voir les détails » présente chaque prestation sur un parchemin
magique responsive avec son sous-titre, sa description détaillée, ses tours
proposés, sa conclusion, son image, son prix en Ariary et sa durée. Les champs
éditoriaux sont modifiables depuis la gestion administrateur ; leur migration
est additive et conserve les offres et réservations existantes.
Au démarrage, les colonnes de paiement manquantes sont ajoutées à SQLite sans
supprimer de réservation. Les anciennes réservations reçoivent le statut
`a_payer` et un contrat uniquement si elles n'en possèdent pas déjà un.

## Tests

```powershell
python -m pytest
```