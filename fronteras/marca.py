"""Nombre y lema del canal en un solo lugar. Se cambian con las variables FRONTERAS_MARCA y FRONTERAS_LEMA."""
import os

NOMBRE = os.environ.get("FRONTERAS_MARCA", "EL PORQUÉ")
LEMA = os.environ.get("FRONTERAS_LEMA", "Todo tiene una razón")
