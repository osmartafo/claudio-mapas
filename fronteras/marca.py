"""Nombre y lema del canal en un solo lugar. Se pueden cambiar con FRONTERAS_MARCA y FRONTERAS_LEMA."""
import os

_viejos = {"", "EL PORQUÉ", "EL PORQUE", "FRONTERAS"}
NOMBRE = os.environ.get("FRONTERAS_MARCA", "STORY")
NOMBRE = "STORY" if NOMBRE.strip().upper() in _viejos else NOMBRE
LEMA = os.environ.get("FRONTERAS_LEMA", "Detrás de todo hay una historia")
LEMA = "Detrás de todo hay una historia" if LEMA.strip() in ("", "Todo tiene una razón") else LEMA
