"""Lectura de números (0.123 no es 123) e importación/venta con decimales."""
import datetime as dt
import unittest

from app import almacen, importar, motor


def cartera(unidades=10.123456):
    return {
        "productos": [{"id": "fnd", "nombre": "Fondo de prueba", "corto": "Fondo", "tipo": "fondo",
                       "fuente": "morningstar", "identificador": "ES0000000001"}],
        "movimientos": [{"id": "m1", "fecha": "2024-01-10", "producto": "fnd", "tipo": "compra",
                         "unidades": unidades, "importe": 1000.0}] if unidades else [],
        "valoraciones": [], "comparador": [],
    }


def vende(cfg, unidades, **extra):
    return almacen.guarda_movimiento(cfg, {"producto": "fnd", "tipo": "venta", "fecha": "2024-06-01",
                                           "unidades": unidades, "importe": "100", **extra})


class NumEs(unittest.TestCase):
    def test_casos(self):
        casos = {
            "0.123": 0.123, "0,123": 0.123, "0.005": 0.005, "-0.5": -0.5,
            "1.234": 1234.0, "1.234,56": 1234.56, "12.3456": 12.3456, "1,250": 1.25,
            "1250": 1250.0, "1.000.000": 1000000.0, " 3352,6 €": 3352.6,
        }
        for txt, esperado in casos.items():
            with self.subTest(txt=txt):
                self.assertAlmostEqual(motor.num_es(txt), esperado, places=9)


FILAS = [(2, {"fecha": "2024-03-01", "tipo_movimiento": "compra", "identificador": "ES0000000001",
              "importe": "100.50", "unidades": "1.250"})]


def informe(filas):
    cfg = cartera(unidades=0)
    plan = importar.preparar_tabla(cfg, filas, ".")
    return plan, importar.vista_previa(cfg, plan)


class Importador(unittest.TestCase):
    def test_punto_decimal_si_no_hay_comas(self):
        plan, inf = informe(FILAS)
        self.assertEqual(plan.errores, [])
        mv = plan.movimientos[0]
        self.assertAlmostEqual(mv["unidades"], 1.25)
        self.assertAlmostEqual(mv["importe"], 100.5)
        self.assertEqual(len(inf["avisos"]), 1)
        self.assertIn("punto como decimal", inf["avisos"][0])

    def test_con_una_coma_el_punto_son_miles(self):
        filas = FILAS + [(3, {"fecha": "2024-03-02", "tipo_movimiento": "compra",
                              "identificador": "ES0000000001", "importe": "1.250,00", "unidades": "3"})]
        plan, inf = informe(filas)
        self.assertEqual(plan.errores, [])
        self.assertAlmostEqual(plan.movimientos[0]["unidades"], 1250.0)
        self.assertAlmostEqual(plan.movimientos[1]["importe"], 1250.0)
        self.assertEqual(inf["avisos"], [])

    def test_float_de_excel_no_cambia(self):
        filas = [(2, {**FILAS[0][1], "unidades": 1.25, "importe": 100.5})]
        plan, inf = informe(filas)
        self.assertAlmostEqual(plan.movimientos[0]["unidades"], 1.25)
        self.assertEqual(inf["avisos"], [])

    def test_sin_forma_de_millar_no_avisa(self):
        filas = [(2, {**FILAS[0][1], "unidades": "0.123", "importe": "100.5"})]
        plan, inf = informe(filas)
        self.assertAlmostEqual(plan.movimientos[0]["unidades"], 0.123)
        self.assertEqual(inf["avisos"], [])


class Venta(unittest.TestCase):
    def test_vende_todo_con_4_decimales(self):
        cfg = cartera()
        self.assertEqual(vende(cfg, "10,1235")["unidades"], 10.123456)

    def test_vende_todo_con_5_decimales(self):
        cfg = cartera()
        self.assertEqual(vende(cfg, "10,12345")["unidades"], 10.123456)

    def test_pasarse_de_verdad_da_error_con_6_decimales(self):
        cfg = cartera()
        with self.assertRaises(almacen.ErrorValidacion) as c:
            vende(cfg, "10,1236")
        msg = " ".join(c.exception.errores)
        self.assertIn("10,123456", msg)
        self.assertIn("10,1236", msg)

    def test_venta_parcial_no_se_toca(self):
        cfg = cartera()
        self.assertEqual(vende(cfg, 5)["unidades"], 5)

    def test_sin_unidades_no_se_inventa_nada(self):
        cfg = cartera(unidades=0)
        with self.assertRaises(almacen.ErrorValidacion):
            vende(cfg, "0,00003")


if __name__ == "__main__":
    unittest.main()
