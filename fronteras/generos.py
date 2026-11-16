"""Tipos de video apagados. Un tipo apagado no sale en los menús, ni en las ideas, ni en el piloto, y no se produce aunque lo pidan.
Para volver a prender los cortos de amor quita "amor" de la lista (o pon la variable FRONTERAS_APAGADOS vacía en Railway)."""
import os

APAGADOS = {g.strip() for g in os.environ.get("FRONTERAS_APAGADOS", "amor").split(",") if g.strip()}
AVISO = {"amor": "💘 Los cortos de amor están apagados por ahora. Pídeme otro tipo de video."}


def apagado(modo):
    return modo in APAGADOS


def aviso(modo):
    return AVISO.get(modo, "Ese tipo de video está apagado por ahora.")
