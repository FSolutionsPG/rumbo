"""Intereses de cuentas remuneradas: movimiento «interes» solo en cuentas; cuentan aparte, sin tocar el valor."""
import copy
import datetime as dt
import unittest
from unittest import mock

from app import almacen, importar, motor
from tests.ayudas import Base, compra, producto

HOY = dt.date(2026, 10, 11)


def interes(mid, pid, fecha, importe):
    return {"id": mid, "fecha": fecha, "producto": pid, "tipo": "interes", "unidades": 0, "importe": importe}


def cartera(con_intereses=True):
    cfg = {
        "productos": [producto("fon", slot=1), producto("caja", fuente="manual", tipo="efectivo", slot=2)],
        "movimientos": [compra("m1", "fon", "2025-01-02", 10, 1000.0)],
        "valoraciones": [{"id": "v1", "fecha": "2025-01-01", "producto": "caja", "valor": 1000.0},
                         {"id": "v2", "fecha": "2025-07-01", "producto": "caja", "valor": 1010.0}],
    }
    if con_intereses:
        cfg["movimientos"] += [interes("i1", "caja", "2025-03-31", 5.0), interes("i2", "caja", "2025-06-30", 5.0),
                               interes("i3", "caja", "2026-03-31", 3.0)]
    return cfg


class Motor(Base):
    PRECIOS = {"FONFONFON.T": 150.0}

    def setUp(self):
        super().setUp()
        p = mock.patch.object(motor, "hoy", lambda: HOY)
        p.start()
        self.addCleanup(p.stop)
        largo = {}
        x = dt.date(2024, 1, 1)
        while x <= HOY:
            largo[x.isoformat()] = 150.0
            x += dt.timedelta(days=1)
        self.escribe_serie("FONFONFON.T", largo)
        for cod in ("IWDA.AS", "SXR8.DE", "EUNA.DE", "XEON.DE"):
            self.escribe_serie(cod, {k: 100.0 for k in largo})

    def test_totales_por_cuenta_y_por_ano(self):
        D = self.construye(cartera())
        caja = self.prod(D, "caja")
        self.assertEqual(caja["intereses"], 13.0)
        self.assertEqual(caja["interesesPorAno"], {"2025": 10.0, "2026": 3.0})
        self.assertEqual(D["total"]["intereses"], 13.0)
        self.assertEqual(D["total"]["interesesAno"], 3.0)      # año de fechaExtracto
        self.assertEqual(D["fechaExtracto"][:4], "2026")
        self.assertEqual(self.prod(D, "fon").get("intereses"), None)    # un fondo no tiene

    def test_sin_intereses_salen_a_cero(self):
        D = self.construye(cartera(False))
        self.assertEqual(self.prod(D, "caja")["intereses"], 0.0)
        self.assertEqual(self.prod(D, "caja")["interesesPorAno"], {})
        self.assertEqual((D["total"]["intereses"], D["total"]["interesesAno"]), (0.0, 0.0))

    def test_no_cambian_valor_serie_ni_patrimonio(self):
        con, sin = self.construye(cartera()), self.construye(cartera(False))
        self.assertEqual(self.prod(con, "caja")["valor"], 1010.0)
        self.assertEqual(self.prod(con, "caja")["valor"], self.prod(sin, "caja")["valor"])
        self.assertEqual(self.prod(con, "caja")["serie"], self.prod(sin, "caja")["serie"])
        self.assertEqual(con["total"]["patrimonio"], sin["total"]["patrimonio"])
        self.assertEqual(con["total"]["serie"], sin["total"]["serie"])

    def test_no_tocan_tir_ni_aportado_ni_flujos(self):
        con, sin = self.construye(cartera()), self.construye(cartera(False))
        for k in ("aportado", "tir", "plusvalia", "rentabilidad", "realizado", "serieAportado"):
            self.assertEqual(con["total"][k], sin["total"][k], k)
        self.assertEqual(con["aportacionesMensuales"], sin["aportacionesMensuales"])
        self.assertEqual(self.prod(con, "fon")["tir"], self.prod(sin, "fon")["tir"])

    def test_resumen_mensual_solo_los_meses_con_intereses(self):
        D = self.construye(cartera())
        por_mes = {r["mes"]: r.get("intereses") for r in D["resumenMensual"]}
        self.assertEqual(por_mes["2025-03"], 5.0)
        self.assertEqual(por_mes["2025-06"], 5.0)
        self.assertEqual(por_mes["2026-03"], 3.0)
        self.assertNotIn("intereses", next(r for r in D["resumenMensual"] if r["mes"] == "2025-04"))
        self.assertEqual(round(sum(v for v in por_mes.values() if v), 2), 13.0)

    def test_dos_intereses_el_mismo_mes_se_suman(self):
        cfg = cartera(False)
        cfg["movimientos"] += [interes("i1", "caja", "2025-03-10", 1.25), interes("i2", "caja", "2025-03-31", 2.5)]
        D = self.construye(cfg)
        self.assertEqual(next(r for r in D["resumenMensual"] if r["mes"] == "2025-03")["intereses"], 3.75)
        self.assertEqual(self.prod(D, "caja")["interesesPorAno"], {"2025": 3.75})


class Validacion(unittest.TestCase):
    def cfg(self):
        c = cartera(False)
        c["productos"].append(producto("deu", fuente="manual", tipo="deuda", slot=3))
        return c

    def mov(self, pid, **kw):
        return {"producto": pid, "tipo": "interes", "fecha": "2025-03-31", "importe": "5,5", **kw}

    def test_en_una_cuenta_se_guarda_neto_y_sin_unidades_ni_comision(self):
        cfg = self.cfg()
        m = almacen.guarda_movimiento(cfg, self.mov("caja", unidades="3", comision="1", nota="T1"))
        self.assertEqual((m["tipo"], m["importe"], m["unidades"], m["nota"]), ("interes", 5.5, 0.0, "T1"))
        self.assertNotIn("comision", m)

    def test_en_un_fondo_o_una_deuda_da_error(self):
        for pid in ("fon", "deu"):
            with self.assertRaises(almacen.ErrorValidacion, msg=pid) as cm:
                almacen.guarda_movimiento(self.cfg(), self.mov(pid))
            self.assertIn("intereses son de cuentas", " ".join(cm.exception.errores))

    def test_el_resto_de_tipos_en_una_cuenta_sigue_dando_error(self):
        for tipo in ("compra", "venta", "dividendo", "comision"):
            with self.assertRaises(almacen.ErrorValidacion, msg=tipo) as cm:
                almacen.guarda_movimiento(self.cfg(), self.mov("caja", tipo=tipo, unidades="1"))
            self.assertIn("se sigue con saldos", " ".join(cm.exception.errores))

    def test_importe_cero_negativo_o_vacio_da_error(self):
        for imp in ("0", "-3", ""):
            with self.assertRaises(almacen.ErrorValidacion, msg=imp):
                almacen.guarda_movimiento(self.cfg(), self.mov("caja", importe=imp))


class Importador(unittest.TestCase):
    def cfg(self):
        c = cartera(False)
        c["productos"][0]["identificador"] = "ES0000000001"
        return c

    def plan(self, **fila):
        base = {"fecha": "2025-03-31", "importe": "5,50"}
        plan = importar.preparar_tabla(self.cfg(), [(2, {**base, **fila})], ".")
        self.assertEqual(plan.errores, [])
        return plan

    def test_interes_con_tipo_producto_efectivo_es_interes(self):
        for texto in ("interés", "interes", "Intereses", "INTERÉS"):
            plan = self.plan(tipo_movimiento=texto, tipo_producto="efectivo", nombre="Cuenta nueva")
            self.assertEqual([m["tipo"] for m in plan.movimientos], ["interes"], texto)

    def test_interes_sobre_una_cuenta_existente_o_sin_identificador_es_interes(self):
        plan = self.plan(tipo_movimiento="intereses", nombre="Producto CAJA")     # nombre de una cuenta ya creada
        self.assertEqual(plan.movimientos[0]["tipo"], "interes")
        plan = self.plan(tipo_movimiento="interes", nombre="Otra cuenta")        # sin identificador ni tipo
        self.assertEqual(plan.movimientos[0]["tipo"], "interes")
        self.assertEqual(plan.productos_nuevos[0]["datos"]["tipo"], "efectivo")

    def test_intereses_de_un_fondo_siguen_siendo_dividendo(self):
        for texto in ("intereses", "interés", "cupón", "dividendo"):
            plan = self.plan(tipo_movimiento=texto, identificador="ES0000000001")
            self.assertEqual([m["tipo"] for m in plan.movimientos], ["dividendo"], texto)

    def test_aplicar_guarda_el_interes_en_la_cuenta(self):
        cfg = self.cfg()
        plan = importar.preparar_tabla(cfg, [(2, {"fecha": "2025-03-31", "importe": "5,50",
                                                  "tipo_movimiento": "interes", "nombre": "Producto CAJA"})], ".")
        informe = importar.aplicar(cfg, plan)
        self.assertEqual(informe["errores"], [])
        self.assertEqual([(m["producto"], m["tipo"], m["importe"]) for m in cfg["movimientos"][-1:]],
                         [("caja", "interes", 5.5)])


if __name__ == "__main__":
    unittest.main()
