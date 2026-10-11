"""Ayudas comunes de los tests de cálculo: cartera sintética, precios en una caché temporal y fecha fija."""
import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

from app import motor

DESDE, HASTA = dt.date(2024, 1, 1), dt.date(2025, 6, 30)
# ETF de referencia del comparador: sin sus series no hay comparación.
REFERENCIAS = ("IWDA.AS", "SXR8.DE", "EUNA.DE", "XEON.DE")


def serie_const(valor, desde=DESDE, hasta=HASTA):
    out, x = {}, desde
    while x <= hasta:
        out[x.isoformat()] = float(valor)
        x += dt.timedelta(days=1)
    return out


def producto(pid, codigo=None, fuente="yahoo", tipo="fondo", slot=1):
    p = {"id": pid, "nombre": f"Producto {pid.upper()}", "corto": f"Fondo {pid.upper()}", "tipo": tipo,
         "fuente": fuente, "moneda": "EUR", "slot": slot, "largoPlazo": True}
    if fuente != "manual":
        p["codigo"] = codigo or f"{pid.upper()}{pid.upper()}{pid.upper()}.T"
    return p


def compra(mid, pid, fecha, unidades, importe):
    return {"id": mid, "fecha": fecha, "producto": pid, "tipo": "compra", "unidades": unidades,
            "importe": importe}


class Base(unittest.TestCase):
    """Cada test tiene su carpeta de datos y 'hoy' fijado a 30/06/2025."""

    PRECIOS = {"AAA.T": 150.0, "BBB.T": 100.0, "CCC.T": 50.0}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = self._tmp.name
        p = mock.patch.object(motor, "hoy", lambda: HASTA)
        p.start()
        self.addCleanup(p.stop)
        os.makedirs(os.path.join(self.carpeta, "cache"))
        for cod, v in self.PRECIOS.items():
            self.escribe_serie(cod, serie_const(v))
        for cod in REFERENCIAS:
            self.escribe_serie(cod, serie_const(100))

    def escribe_serie(self, codigo, serie):
        with open(os.path.join(self.carpeta, "cache", f"{codigo}.json"), "w", encoding="utf-8") as f:
            json.dump(serie, f)

    def construye(self, cfg):
        cfg = copy.deepcopy(cfg)
        cfg.setdefault("valoraciones", [])
        cfg.setdefault("comparador", [{"id": "real", "nombre": "Mi cartera real", "real": True}])
        with mock.patch("builtins.print"):
            return motor.construir(cfg, self.carpeta, descargar=False)

    @staticmethod
    def prod(D, pid):
        return next(p for p in D["productos"] + D["otrosActivos"] + D["pasivos"] if p["id"] == pid)

    @staticmethod
    def dia(D, fecha, serie):
        return serie[D["fechas"].index(fecha)]
