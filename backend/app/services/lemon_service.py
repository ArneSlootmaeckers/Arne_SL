"""Koppeling met het lobbysysteem van Lemon: de kiosk aan de experience.

Bezoekers scannen hun bandje aan de kiosk. Zodra de experience start, stelt
de kiosk de spelers van die sessie ter beschikking, op twee manieren:

- de kiosk stuurt ze zelf door (POST naar /api/lemon/session), de standaard;
- of deze server vraagt ze op bij de kiosk (GET http://<kiosk>:<poort>/players),
  als fallback; aan of uit te zetten in config.yaml.

Na het oordeel van de host (groen of rood) krijgt de kiosk een stopbericht
(POST http://<kiosk>:<poort>/scores) met de sessionId, gameModeCode en die
ene speler, zonder score en zonder resultaat (zie scores_payload).

Gegevensafspraak met IT van Sparkx: enkel de UUID van een speler mag
bewaard worden (als "bandje-ID" in de database en de logs). Naam en avatar
worden enkel in het geheugen gehouden, zolang de sessie loopt, om op het
hostscherm te tonen, en nergens weggeschreven: niet in de database, niet in
de logs, niet in logbestanden of foutmeldingen. Geboortedatum en de andere
velden worden bij het inlezen meteen weggelaten.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.services.common import now_utc
from app.services.errors import DomainServiceError

# Na zoveel tijd zonder nieuwe sessie verdwijnen naam en avatar ook uit het geheugen.
SESSION_TTL_SECONDS = 15 * 60
_NAME_MAX_LENGTH = 40
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class InvalidLemonDataError(DomainServiceError):
    """De kiosk stuurde iets dat geen geldige sessie is."""


@dataclass(frozen=True)
class LemonPlayer:
    id: str  # UUID van de speler, het enige dat bewaard mag worden
    first_name: str
    last_initial: str
    avatar_url: str | None
    avatar_color: str | None


@dataclass(frozen=True)
class LemonSession:
    key: str
    players: tuple[LemonPlayer, ...]
    received_at: datetime
    via: str
    received_monotonic: float


class _PlayerIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    firstName: str = ""
    lastName: str = ""
    avatarUrl: str | None = None
    avatarColor: str | None = None


class _SessionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    players: list[_PlayerIn] = []


def parse_session(payload: object) -> tuple[str, tuple[LemonPlayer, ...]]:
    """Leest een sessie van de kiosk in en houdt enkel over wat nodig is.
    De foutmelding herhaalt nooit de ontvangen gegevens."""
    try:
        session = _SessionIn.model_validate(payload)
    except ValidationError:
        raise InvalidLemonDataError("Ongeldige sessie van de kiosk.") from None

    players = tuple(
        LemonPlayer(
            id=str(player.id),
            first_name=player.firstName.strip()[:_NAME_MAX_LENGTH],
            last_initial=player.lastName.strip()[:1].upper(),
            # Enkel een gewone https-link mag als afbeelding getoond worden.
            avatar_url=player.avatarUrl if (player.avatarUrl or "").startswith("https://") else None,
            avatar_color=player.avatarColor if _COLOR.match(player.avatarColor or "") else None,
        )
        for player in session.players
    )
    return session.sessionId, players


class LemonInbox:
    """De laatst ontvangen sessie, enkel in het geheugen. Een sessie die
    zowel via POST als via GET binnenkomt, telt maar één keer."""

    def __init__(self, *, ttl_seconds: float = SESSION_TTL_SECONDS, clock=time.monotonic) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._session: LemonSession | None = None
        # Speler-UUID -> (sessionId, ontvangen), om na het oordeel het
        # stopbericht naar de juiste sessie te sturen, ook als er intussen
        # al een nieuwe sessie binnenkwam. Enkel in het geheugen.
        self._player_sessions: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self.poll_error: str | None = None
        self.scores_error: str | None = None

    def receive(self, payload: object, *, via: str) -> LemonSession | None:
        """Geeft de sessie terug als ze nieuw is, None als ze al gekend was
        of geen spelers heeft."""
        key, players = parse_session(payload)
        if not players:
            return None
        with self._lock:
            current = self._current_locked()
            if current is not None and current.key == key:
                return None
            self._session = LemonSession(
                key=key, players=players, received_at=now_utc(), via=via, received_monotonic=self._clock()
            )
            if via != "test":  # een testspeler bestaat niet bij de kiosk
                for player in players:
                    self._player_sessions[player.id] = (key, self._session.received_monotonic)
            return self._session

    def current(self) -> LemonSession | None:
        with self._lock:
            return self._current_locked()

    def take_session_id(self, player_id: str) -> str | None:
        """De sessionId waarin deze speler van de kiosk kwam, of None als hij
        niet (meer) van de kiosk komt. Eén keer op te vragen: daarna is de
        speler afgehandeld."""
        with self._lock:
            self._current_locked()
            entry = self._player_sessions.pop(player_id, None)
            return None if entry is None else entry[0]

    def _current_locked(self) -> LemonSession | None:
        if self._session is not None and self._clock() - self._session.received_monotonic > self._ttl_seconds:
            self._session = None  # naam en avatar weg uit het geheugen
        now = self._clock()
        for player_id, (_, received) in list(self._player_sessions.items()):
            if now - received > self._ttl_seconds:
                del self._player_sessions[player_id]
        return self._session

    def age_seconds(self, session: LemonSession) -> float:
        return self._clock() - session.received_monotonic


def fetch_players(client: httpx.Client, *, host: str, port: int) -> object:
    """Vraagt de spelers op bij de kiosk (GET-fallback). Gooit
    InvalidLemonDataError met een algemene melding als dat niet lukt; de
    inhoud van het antwoord komt nooit in een foutmelding."""
    try:
        response = client.get(f"http://{host}:{port}/players")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        raise InvalidLemonDataError("Kiosk niet bereikbaar.") from None
    except ValueError:
        raise InvalidLemonDataError("Onverwacht antwoord van de kiosk.") from None


def scores_payload(session_id: str, player_id: str, *, game_mode_code: str) -> dict:
    """Stopbericht voor de kiosk na het oordeel (groen of rood): de sessie
    en één speler. Bewust zonder score en zonder resultaat: of iemand mag
    springen, gaat nooit naar Lemon. Lemon gebruikt dit enkel om het spel
    van die speler te stoppen."""
    return {"sessionId": session_id, "gameModeCode": game_mode_code, "players": [{"id": player_id}]}


def send_scores(client: httpx.Client, *, host: str, port: int, payload: dict) -> None:
    """POST http://<kiosk>:<poort>/scores. Gooit InvalidLemonDataError met
    een algemene melding; de inhoud komt nooit in een foutmelding."""
    try:
        client.post(f"http://{host}:{port}/scores", json=payload).raise_for_status()
    except httpx.HTTPError:
        raise InvalidLemonDataError("Stopbericht naar de kiosk mislukt.") from None


def test_session_payload() -> dict:
    """Een verzonnen sessie met één testspeler, om het hostscherm te testen
    zonder kiosk (knop op Beheer -> Systeem)."""
    return {
        "sessionId": f"test-{uuid.uuid4()}",
        "players": [{"id": str(uuid.uuid4()), "firstName": "Testspeler", "lastName": "", "avatarColor": "#facb0d"}],
    }
