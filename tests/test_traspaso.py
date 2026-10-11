"""Traspaso entre fondos y planes: el coste y la fecha de cada lote viajan con las unidades."""
import copy
import unittest

from app import almacen, importar
from tests.ayudas import Base, compra, producto

TRASPASO = "2025-01-02"


def cartera_base():
    """A: 10 u por 1.000 € (02/01/2024) y 10 u por 1.500 € (03/06/2024). B y C sin nada."""
    return {
        "productos": [producto("a", slot=1), producto("b", slot=2), producto("c", slot=3)],
        "movimientos": [compra("m1", "a", "2024-01-02", 10, 1000.0),
                        compra("m2", "a", "2024-06-03", 10, 1500.0)],
        "valoraciones": [],
    }


def traspasa(cfg, origen, destino, fecha, uA, uB, importe, **extra):
    return almacen.guarda_movimiento(cfg, {"producto": origen, "tipo": "traspaso", "fecha": fecha,
                                           "destino": destino, "unidades": uA, "unidadesDestino": uB,
                                           "importe": importe, **extra})


def vende(cfg, pid, fecha, unidades, importe):
    return almacen.guarda_movimiento(cfg, {"producto": pid, "tipo": "venta", "fecha": fecha,
                                           "unidades": unidades, "importe": importe})


class Total(Base):
    def setUp(self):
        super().setUp()
        self.cfg0 = cartera_base()
        self.cfg = copy.deepcopy(self.cfg0)
        traspasa(self.cfg, "a", "b", TRASPASO, 20, 30, 3000)
        self.D0 = self.construye(self.cfg0)
        self.D = self.construye(self.cfg)

    def test_el_coste_viaja_a_b_y_a_queda_cerrado(self):
        a, b = self.prod(self.D, "a"), self.prod(self.D, "b")
        self.assertEqual(b["aportado"], 2500.0)
        self.assertEqual(b["participaciones"], 30.0)
        self.assertEqual(b["valor"], 3000.0)
        self.assertEqual(a["realizado"], 0)
        self.assertEqual(a["participaciones"], 0)
        self.assertIs(a["cerrado"], True)
        self.assertIs(b["cerrado"], False)
        self.assertEqual(b["plusvalia"], 500.0)

    def test_el_patrimonio_aportado_y_tir_no_se_mueven(self):
        T, T0 = self.D["total"], self.D0["total"]
        self.assertEqual(T["aportado"], 2500.0)
        self.assertEqual(T["aportado"], T0["aportado"])
        self.assertEqual(T["serieAportado"], T0["serieAportado"])
        self.assertEqual(T["serie"], T0["serie"])          # precios constantes: ni un salto el día del traspaso
        self.assertEqual(T["realizado"], 0)
        self.assertIsNotNone(T["tir"])
        self.assertEqual(T["tir"], T0["tir"])

    def test_ningun_flujo_de_bolsillo_el_dia_del_traspaso(self):
        for p in self.D["productos"]:
            self.assertNotIn(TRASPASO, [f for f, _ in p["flujos"]], p["id"])
        C, C0 = self.D["comparacion"], self.D0["comparacion"]
        self.assertIsNotNone(C)
        # flujo_dia alimenta el aportado del comparador: una pata del traspaso lo haría saltar.
        self.assertEqual(C["aportado"], C0["aportado"])
        self.assertEqual(C["aportado"][self.D["fechas"].index(TRASPASO)],
                         C["aportado"][self.D["fechas"].index(TRASPASO) - 1])
        # La serie «tuya» incluye a B, que solo recibe el traspaso.
        self.assertEqual(C["tuya"], C0["tuya"])
        self.assertEqual(C["tuTir"], C0["tuTir"])
        self.assertEqual(C["tuValor"], 3000.0)

    def test_las_dos_patas_estan_en_flujos_propios(self):
        a, b = self.prod(self.D, "a"), self.prod(self.D, "b")
        self.assertIn([TRASPASO, 3000.0], a["flujosPropios"])
        self.assertIn([TRASPASO, -3000.0], b["flujosPropios"])
        self.assertEqual(b["flujos"], [])
        self.assertEqual(b["traspasos"][0]["sentido"], "entra")
        self.assertEqual(a["traspasos"][0]["contra"], "b")

    def test_lo_que_entra_por_traspaso_no_es_una_aportacion(self):
        b = self.prod(self.D, "b")
        self.assertEqual(b["aportaciones"], [])
        am = self.D["aportacionesMensuales"]
        self.assertEqual(am["porProducto"]["b"], [0.0] * len(am["meses"]))
        self.assertEqual(self.D["total"]["numAportaciones"], self.D0["total"]["numAportaciones"])
        self.assertEqual(self.D["total"]["racha"], self.D0["total"]["racha"])
        self.assertEqual(self.D["total"]["ritmoMensual"], self.D0["total"]["ritmoMensual"])

    def test_b_entra_en_la_tir_de_la_cartera(self):
        # Si B no sumara su valor, la TIR de cartera perdería 3.000 € de valor final.
        self.assertEqual(self.D["total"]["tir"], self.D0["total"]["tir"])
        self.assertIsNotNone(self.prod(self.D, "b")["tir"])


class Parcial(Base):
    def test_hereda_los_lotes_mas_antiguos(self):
        cfg = cartera_base()
        traspasa(cfg, "a", "b", TRASPASO, 15, 22.5, 2250)
        D = self.construye(cfg)
        a, b = self.prod(D, "a"), self.prod(D, "b")
        self.assertEqual(b["aportado"], 1750.0)      # 10 u de 1.000 € + 5 u de 1.500 € / 2
        self.assertEqual(b["participaciones"], 22.5)
        self.assertEqual(a["aportado"], 750.0)
        self.assertEqual(a["participaciones"], 5.0)
        self.assertIs(a["cerrado"], False)
        self.assertEqual(a["realizado"], 0)
        self.assertEqual(D["total"]["aportado"], 2500.0)


class VentaPosterior(Base):
    def test_b_vende_primero_el_lote_heredado_mas_antiguo(self):
        cfg = cartera_base()
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        almacen.guarda_movimiento(cfg, {"producto": "b", "tipo": "compra", "fecha": "2025-02-03",
                                        "unidades": 5, "importe": 400})
        vende(cfg, "b", "2025-03-03", 15, 1800)       # = el primer lote heredado (10 u de A x 1,5)
        D = self.construye(cfg)
        b = self.prod(D, "b")
        self.assertEqual(b["realizado"], 800.0)        # 1.800 - 1.000 (el lote de 2024-01-02)
        self.assertEqual(b["aportado"], 1900.0)        # 1.500 + 400
        self.assertEqual(b["participaciones"], 20.0)

    def test_el_orden_fifo_es_por_fecha_original_no_por_llegada(self):
        # B ya tenía una compra de dic-2024: los lotes de ene y jun-2024 que llegan después
        # son más antiguos y se venden antes.
        cfg = cartera_base()
        almacen.guarda_movimiento(cfg, {"producto": "b", "tipo": "compra", "fecha": "2024-12-01",
                                        "unidades": 10, "importe": 900})
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        vende(cfg, "b", "2025-03-03", 15, 1800)
        b = self.prod(self.construye(cfg), "b")
        self.assertEqual(b["realizado"], 800.0)
        self.assertEqual(b["aportado"], 2400.0)        # 1.500 + 900


class Cadenas(Base):
    def test_ida_y_vuelta_conserva_costes_y_fechas(self):
        cfg = cartera_base()
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        traspasa(cfg, "b", "a", "2025-03-03", 30, 20, 3000)
        vende(cfg, "a", "2025-04-01", 10, 1700)        # sigue saliendo primero el lote de ene-2024
        D = self.construye(cfg)
        a, b = self.prod(D, "a"), self.prod(D, "b")
        self.assertEqual(a["realizado"], 700.0)        # 1.700 - 1.000
        self.assertEqual(a["aportado"], 1500.0)
        self.assertIs(b["cerrado"], True)
        self.assertEqual((b["aportado"] or 0) + a["aportado"], 1500.0)
        # sin la venta: la suma de aportados es la de las compras
        cfg2 = cartera_base()
        traspasa(cfg2, "a", "b", TRASPASO, 20, 30, 3000)
        traspasa(cfg2, "b", "a", "2025-03-03", 30, 20, 3000)
        D2 = self.construye(cfg2)
        self.assertEqual((self.prod(D2, "a")["aportado"] or 0) + (self.prod(D2, "b")["aportado"] or 0), 2500.0)
        self.assertEqual(D2["total"]["aportado"], 2500.0)
        self.assertEqual(self.prod(D2, "a")["participaciones"], 20.0)

    def test_cadena_a_b_c(self):
        cfg = cartera_base()
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        traspasa(cfg, "b", "c", "2025-03-03", 15, 30, 1500)
        vende(cfg, "c", "2025-04-01", 30, 1800)
        D = self.construye(cfg)
        a, b, c = (self.prod(D, x) for x in "abc")
        self.assertEqual(b["aportado"], 1500.0)
        self.assertEqual(c["realizado"], 800.0)        # 1.800 - 1.000 del lote de ene-2024
        self.assertIs(c["cerrado"], True)
        self.assertEqual(D["total"]["aportado"], 1500.0)
        self.assertIs(a["cerrado"], True)


class ManualSinUnidades(Base):
    def test_traspaso_total_entre_planes_a_mano(self):
        cfg = {
            "productos": [producto("a", fuente="manual", tipo="pension"),
                          producto("b", fuente="manual", tipo="pension", slot=2),
                          producto("caja", fuente="manual", tipo="efectivo", slot=3)],
            "movimientos": [compra("m1", "a", "2024-01-02", 0, 1000.0),
                            compra("m2", "a", "2024-06-03", 0, 1500.0)],
            "valoraciones": [{"id": "v1", "fecha": "2024-12-01", "producto": "a", "valor": 3000.0},
                             {"id": "v2", "fecha": "2025-03-01", "producto": "caja", "valor": 500.0}],
        }
        traspasa(cfg, "a", "b", TRASPASO, 0, 0, 3000)
        D = self.construye(cfg)
        a, b = self.prod(D, "a"), self.prod(D, "b")
        f = D["fechas"]
        self.assertEqual(self.dia(D, "2025-01-01", a["serie"]), 3000.0)
        self.assertEqual(self.dia(D, TRASPASO, a["serie"]), 0.0)
        self.assertEqual(a["valor"], 0.0)
        self.assertIs(a["cerrado"], True)
        self.assertIsNone(self.dia(D, "2025-01-01", b["serie"]))
        self.assertEqual(self.dia(D, TRASPASO, b["serie"]), 3000.0)
        self.assertEqual(b["valor"], 3000.0)
        self.assertEqual(b["aportado"], 2500.0)       # el coste de A viaja
        self.assertIs(b["cerrado"], False)
        self.assertEqual(D["total"]["aportado"], 2500.0)
        # el patrimonio total no salta el día del traspaso
        s = D["total"]["serie"]
        self.assertEqual(s[f.index(TRASPASO)], s[f.index("2025-01-01")])

    def test_una_valoracion_anotada_ese_dia_manda(self):
        cfg = {
            "productos": [producto("a", fuente="manual", tipo="pension"),
                          producto("b", fuente="manual", tipo="pension", slot=2)],
            "movimientos": [compra("m1", "a", "2024-01-02", 0, 1000.0)],
            "valoraciones": [{"id": "v1", "fecha": "2024-12-01", "producto": "a", "valor": 1200.0},
                             {"id": "v2", "fecha": TRASPASO, "producto": "b", "valor": 1234.0}],
        }
        traspasa(cfg, "a", "b", TRASPASO, 0, 0, 1200)
        D = self.construye(cfg)
        self.assertEqual(self.dia(D, TRASPASO, self.prod(D, "b")["serie"]), 1234.0)


class PatasQueNoSeAnulan(Base):
    """Las dos patas de un traspaso se anulan entre sí en las sumas de la cartera, salvo si
    una de ellas queda fuera del conjunto que se suma."""

    def test_destino_sin_precio_no_convierte_el_traspaso_en_dinero_cobrado(self):
        cfg0 = cartera_base()
        cfg = cartera_base()
        cfg["productos"][1]["codigo"] = "SINPRECIO.T"          # B no tiene serie en la caché: se descarta
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        D0, D = self.construye(cfg0), self.construye(cfg)
        self.assertNotIn("b", [p["id"] for p in D["productos"]])
        ap, ap0 = D["comparacion"]["aportado"], D0["comparacion"]["aportado"]
        self.assertEqual(ap, ap0)                              # ni una salida de 3.000 € ese día
        self.assertEqual(ap[D["fechas"].index(TRASPASO)], 2500.0)

    def test_traspaso_a_un_plan_a_mano_no_hunde_el_indice_de_la_cartera(self):
        cfg0 = cartera_base()
        cfg = cartera_base()
        cfg["productos"][1] = producto("b", fuente="manual", tipo="pension", slot=2)
        traspasa(cfg, "a", "b", TRASPASO, 20, 0, 3000)
        D0, D = self.construye(cfg0), self.construye(cfg)
        self.assertEqual(D["indiceCartera"], D0["indiceCartera"])      # sale dinero de lo cotizado: no es una pérdida
        self.assertEqual(D["total"]["serie"], D0["total"]["serie"])
        self.assertEqual(self.prod(D, "b")["aportado"], 2500.0)


class Validaciones(Base):
    def cfg(self):
        cfg = cartera_base()
        cfg["productos"].append(producto("caja", fuente="manual", tipo="efectivo", slot=4))
        cfg["productos"].append(producto("m", fuente="manual", tipo="pension", slot=5))
        return cfg

    def error(self, cfg, **datos):
        base = {"producto": "a", "tipo": "traspaso", "fecha": TRASPASO, "destino": "b",
                "unidades": 20, "unidadesDestino": 30, "importe": 3000}
        with self.assertRaises(almacen.ErrorValidacion) as c:
            almacen.guarda_movimiento(cfg, {**base, **datos})
        return " ".join(c.exception.errores)

    def test_destino_igual_al_origen(self):
        self.assertIn("otro producto", self.error(self.cfg(), destino="a"))

    def test_mas_unidades_de_las_que_tenias(self):
        self.assertIn("solo tenías", self.error(self.cfg(), unidades=25))

    def test_destino_obligatorio_existente_y_no_saldo(self):
        cfg = self.cfg()
        self.error(cfg, destino="")
        self.error(cfg, destino="no_existe")
        self.assertIn("saldos", self.error(cfg, destino="caja"))

    def test_importe_y_unidades_de_entrada(self):
        cfg = self.cfg()
        self.error(cfg, importe=0)
        self.error(cfg, unidadesDestino="")      # B cotiza: hacen falta
        self.error(cfg, unidadesDestino=0)
        self.assertEqual(cfg["movimientos"][-1]["tipo"], "compra")      # nada se guardó

    def test_destino_a_mano_no_pide_unidades_de_entrada(self):
        cfg = self.cfg()
        mov = almacen.guarda_movimiento(cfg, {"producto": "a", "tipo": "traspaso", "fecha": TRASPASO,
                                              "destino": "m", "unidades": 20, "importe": 3000})
        self.assertEqual((mov["destino"], mov["unidadesDestino"], mov["unidades"]), ("m", 0.0, 20.0))

    def test_traspasar_todo_ajusta_los_decimales_como_vender_todo(self):
        mov = traspasa(self.cfg(), "a", "b", TRASPASO, "19,99998", 30, 3000)
        self.assertEqual(mov["unidades"], 20.0)

    def test_origen_a_mano_guarda_cero_unidades(self):
        cfg = self.cfg()
        mov = traspasa(cfg, "m", "b", TRASPASO, 7, 5, 100)
        self.assertEqual(mov["unidades"], 0.0)

    def test_lo_recibido_se_puede_vender_y_no_mas(self):
        cfg = self.cfg()
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        vende(cfg, "b", "2025-02-01", 30, 3100)
        with self.assertRaises(almacen.ErrorValidacion):
            vende(cfg, "b", "2025-02-02", 1, 100)

    def test_borrar_el_destino_nombra_el_origen(self):
        cfg = self.cfg()
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        with self.assertRaises(almacen.ErrorValidacion) as c:
            almacen.borra_producto(cfg, "b")
        msg = " ".join(c.exception.errores)
        self.assertIn("«Fondo A»", msg)
        self.assertIn("recibe un traspaso", msg)
        self.assertIsNotNone(almacen.producto(cfg, "b"))

    def test_borrar_el_origen_borra_el_traspaso(self):
        cfg = self.cfg()
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        almacen.borra_producto(cfg, "a")
        self.assertEqual([m for m in cfg["movimientos"] if m["tipo"] == "traspaso"], [])
        almacen.borra_producto(cfg, "b")       # ya no recibe nada: se deja borrar
        self.assertIsNone(almacen.producto(cfg, "b"))

    def test_editar_un_traspaso_no_se_cuenta_a_si_mismo(self):
        cfg = self.cfg()
        mov = traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)
        mov2 = traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3100, id=mov["id"])
        self.assertEqual(mov2["importe"], 3100.0)
        self.assertEqual(len([m for m in cfg["movimientos"] if m["tipo"] == "traspaso"]), 1)


class Importador(Base):
    def cfg_con_traspasos(self):
        cfg = cartera_base()
        for p, ident in zip(cfg["productos"], ("ES0000000001", "ES0000000002", "ES0000000003")):
            p["identificador"] = ident
        for m in cfg["movimientos"]:
            m["origen"] = "myinvestor"
        almacen.guarda_movimiento(cfg, {"producto": "b", "tipo": "compra", "fecha": "2024-03-01",
                                        "unidades": 10, "importe": 900})["origen"] = "myinvestor"
        traspasa(cfg, "a", "b", TRASPASO, 20, 30, 3000)       # sale de A y entra en B
        traspasa(cfg, "b", "a", "2025-03-03", 5, 3, 500)      # sale de B y entra en A
        return cfg

    def test_una_fila_traspaso_se_rechaza(self):
        for texto in ("traspaso", "Traspaso", "TRASPASOS"):
            filas = [(2, {"fecha": "2025-01-02", "tipo_movimiento": texto, "identificador": "ES0000000001",
                          "importe": "3000", "unidades": "20"})]
            plan = importar.preparar_tabla(cartera_base(), filas, self.carpeta)
            self.assertEqual([e["mensaje"] for e in plan.errores],
                             ["Los traspasos se anotan en Mis datos → Movimientos."], texto)
            self.assertEqual(plan.movimientos, [])

    def test_reimportar_myinvestor_conserva_los_traspasos(self):
        cfg = self.cfg_con_traspasos()
        traspasos = [copy.deepcopy(m) for m in cfg["movimientos"] if m["tipo"] == "traspaso"]
        self.assertEqual(len(traspasos), 2)
        csv = "Fecha fiscal;Inversión;Valor de mercado\n02/01/2024;1000,00;1100,00\n".encode("utf-8")
        for isin in ("ES0000000001", "ES0000000002"):        # el que sale y el que recibe
            plan = importar.preparar_myinvestor(cfg, [(f"{isin}.csv", csv)], self.carpeta)
            self.assertEqual(plan.errores, [], isin)
            self.assertEqual(plan.reemplazar and len(plan.reemplazar), 1)
            informe = importar.aplicar(cfg, plan)
            self.assertEqual(informe["errores"], [], isin)
            self.assertGreater(informe["sustituidos"], 0, isin)     # sí borra sus importados...
            ahora = [m for m in cfg["movimientos"] if m["tipo"] == "traspaso"]
            self.assertEqual(ahora, traspasos, isin)                # ...pero ningún traspaso


if __name__ == "__main__":
    unittest.main()
