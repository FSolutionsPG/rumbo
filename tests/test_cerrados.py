"""Productos cerrados: 0 unidades y 0 € (o «Archivado») se ocultan del panel, pero siguen contando."""
import copy
import unittest

from app import almacen
from tests.ayudas import Base, compra, producto


def cartera():
    return {
        "productos": [producto("vivo", slot=1), producto("vendido", slot=2), producto("viejo", slot=3),
                      producto("caja", fuente="manual", tipo="efectivo", slot=4),
                      producto("vacia", fuente="manual", tipo="efectivo", slot=5)],
        "movimientos": [compra("m1", "vivo", "2024-01-02", 10, 1000.0),
                        compra("m2", "vendido", "2024-01-02", 10, 1000.0),
                        {"id": "m3", "fecha": "2025-02-03", "producto": "vendido", "tipo": "venta",
                         "unidades": 10, "importe": 1300.0},
                        compra("m4", "viejo", "2024-03-01", 5, 500.0)],
        "valoraciones": [{"id": "v1", "fecha": "2025-03-01", "producto": "caja", "valor": 250.0},
                         {"id": "v2", "fecha": "2025-03-01", "producto": "vacia", "valor": 0.0}],
    }


class Cerrados(Base):
    PRECIOS = {"VIVOVIVOVIVO.T": 150.0, "VENDIDOVENDIDOVENDIDO.T": 100.0, "VIEJOVIEJOVIEJO.T": 70.0}

    def test_marca_cada_caso(self):
        cfg = cartera()
        almacen.guarda_producto(cfg, {**cfg["productos"][2], "archivado": True})
        D = self.construye(cfg)
        self.assertIs(self.prod(D, "vivo")["cerrado"], False)
        self.assertIs(self.prod(D, "vendido")["cerrado"], True)      # vendido entero
        self.assertIs(self.prod(D, "viejo")["cerrado"], True)        # archivado con unidades
        self.assertEqual(self.prod(D, "viejo")["participaciones"], 5.0)
        self.assertIs(self.prod(D, "caja")["cerrado"], False)
        self.assertIs(self.prod(D, "vacia")["cerrado"], True)        # cuenta a 0 €
        for p in D["productos"] + D["otrosActivos"]:
            self.assertIn(p["cerrado"], (True, False), p["id"])

    def test_los_cerrados_siguen_contando(self):
        sin = cartera()
        con = copy.deepcopy(sin)
        almacen.guarda_producto(con, {**con["productos"][2], "archivado": True})
        almacen.guarda_producto(con, {**con["productos"][0], "archivado": True})
        D0, D = self.construye(sin), self.construye(con)
        for k in ("patrimonio", "aportado", "plusvalia", "tir", "realizado", "serie", "serieAportado"):
            self.assertEqual(D["total"][k], D0["total"][k], k)
        self.assertEqual(self.prod(D, "vendido")["realizado"], 300.0)
        self.assertIn("vendido", [p["id"] for p in D["productos"]])   # sigue en los datos para el histórico

    def test_no_aparece_ningun_cerrado_falso(self):
        D = self.construye(cartera())
        self.assertEqual(sorted(p["id"] for p in D["productos"] if p["cerrado"]), ["vendido"])


class Archivado(unittest.TestCase):
    def base(self):
        cfg = {"productos": [], "movimientos": [], "valoraciones": []}
        almacen.guarda_producto(cfg, {"nombre": "Plan", "tipo": "pension", "fuente": "manual"})
        return cfg

    def test_se_guarda_y_se_conserva_al_editar_otros_campos(self):
        cfg = self.base()
        p = cfg["productos"][0]
        almacen.guarda_producto(cfg, {"id": p["id"], "nombre": "Plan", "tipo": "pension", "fuente": "manual",
                                      "archivado": True})
        self.assertIs(cfg["productos"][0]["archivado"], True)
        almacen.guarda_producto(cfg, {"id": p["id"], "nombre": "Plan 2", "tipo": "pension", "fuente": "manual"})
        self.assertIs(cfg["productos"][0]["archivado"], True)       # no enviado: se conserva
        self.assertEqual(cfg["productos"][0]["nombre"], "Plan 2")

    def test_se_puede_desarchivar(self):
        cfg = self.base()
        p = cfg["productos"][0]
        datos = {"id": p["id"], "nombre": "Plan", "tipo": "pension", "fuente": "manual"}
        almacen.guarda_producto(cfg, {**datos, "archivado": True})
        almacen.guarda_producto(cfg, {**datos, "archivado": False})
        self.assertNotIn("archivado", cfg["productos"][0])


if __name__ == "__main__":
    unittest.main()
