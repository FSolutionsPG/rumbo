"""Importador del CSV de transacciones de Trade Republic. CSV sintético (nada real), sin red."""
import copy
import csv
import io
import json
import tempfile
import unittest
from decimal import Decimal
from unittest import mock

from app import almacen, importar

CABECERA = ["datetime", "date", "account_type", "category", "type", "asset_class", "name", "symbol", "shares",
            "price", "amount", "fee", "tax", "currency", "original_amount", "original_currency", "fx_rate",
            "description", "transaction_id", "counterparty_name", "counterparty_iban", "payment_reference",
            "mcc_code"]
A, B, ETF, VIEJO = "IE00BYX5NX33", "IE00BYX5P602", "IE00B4L5Y983", "IE00B3RBWM25"
# Textos que NO pueden acabar en la cartera guardada.
PRIVADOS = ("COMERCIO-PRUEBA", "NOMBRE-PRUEBA", "ES0000000000000000000000", "REF-PRUEBA", "DESC-PRUEBA")


def fila(tipo, fecha, categoria="TRADING", clase="", nombre="", simbolo="", shares="", price="",
         amount="", fee="", tax="", n=[0]):
    n[0] += 1
    r = dict.fromkeys(CABECERA, "")
    r.update(datetime=f"{fecha}T10:00:00.000000Z", date=fecha, account_type="DEFAULT", category=categoria,
             type=tipo, asset_class=clase, name=nombre, symbol=simbolo, shares=shares, price=price,
             amount=amount, fee=fee, tax=tax, currency="EUR", transaction_id=f"tx-{n[0]}",
             description="DESC-PRUEBA", counterparty_name="NOMBRE-PRUEBA",
             counterparty_iban="ES0000000000000000000000", payment_reference="REF-PRUEBA")
    return r


def csv_de(filas, cabecera=CABECERA):
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=cabecera, quoting=csv.QUOTE_ALL, extrasaction="ignore")
    w.writeheader()
    w.writerows(filas)
    return s.getvalue().encode("utf-8")


def filas_base():
    return [
        fila("TRANSFER_INBOUND", "2026-01-05", "CASH", amount="1000.00"),
        fila("BUY", "2026-01-10", clase="MUTUAL_FUND", nombre="Fondo A", simbolo=A, shares="4.0000000000",
             price="14.7500000000", amount="-59.00", fee="-1.00"),
        fila("BUY", "2026-01-11", clase="FUND", nombre="ETF Mundo", simbolo=ETF, shares="2.0000000000",
             price="100.0000000000", amount="-200.00"),
        fila("SELL", "2026-02-01", clase="MUTUAL_FUND", nombre="Fondo A", simbolo=A, shares="-2.0000000000",
             price="168.9500000000", amount="337.90", fee="-1.00", tax="-1.89"),
        fila("INTEREST_PAYMENT", "2026-02-15", "CASH", amount="0.09", tax="-0.02"),
        fila("MIGRATION", "2026-02-20", "DELIVERY", clase="MUTUAL_FUND", nombre="Viejo", simbolo=VIEJO,
             shares="3.0000000000"),
        fila("MIGRATION", "2026-02-20", "DELIVERY", clase="MUTUAL_FUND", nombre="Viejo", simbolo=VIEJO,
             shares="-3.0000000000"),
        fila("CARD_TRANSACTION", "2026-02-21", "CASH", amount="-25.50"),
        fila("TRANSFER_INSTANT_OUTBOUND", "2026-02-22", "CASH", amount="-100.00"),
        fila("BENEFITS_SAVEBACK", "2026-02-23", "CASH", amount="1.00"),
        fila("BUY", "2026-02-24", clase="CRYPTO", nombre="Bitcoin", simbolo="BTC", shares="0.0010000000",
             price="60000.0000000000", amount="-60.00"),
        # Cambio entre fondos: venta y compra sin amount, del mismo valor (80,00 y 80,10).
        fila("SELL", "2026-03-01", clase="MUTUAL_FUND", nombre="Fondo A", simbolo=A, shares="-0.5000000000",
             price="160.0000000000"),
        fila("BUY", "2026-03-03", clase="MUTUAL_FUND", nombre="Fondo B", simbolo=B, shares="6.0000000000",
             price="13.3500000000"),
    ]
SALDO_BASE = Decimal("890.58")   # 1000 - 60 - 200 + 335,01 + 0,07 - 25,50 - 100 + 1 - 60


def falso_buscar(texto):
    """Sustituye al buscador de internet: nada sale de la máquina."""
    tipos = {A: "fondo", B: "fondo", ETF: "otro", "BTC": "cripto"}      # el ETF llega mal clasificado a propósito
    if texto not in tipos:
        return []
    if texto == "BTC":      # como el buscador real: un ETF con el mismo ticker sale antes que la cripto
        return [{"codigo": "BTC", "nombre": "ETF BTC", "tipo": "etf", "fuente": "yahoo", "moneda": "USD",
                 "vivo": "", "precio": 30.0, "fecha": "2026-01-01", "mercado": None},
                {"codigo": "BTC-EUR", "nombre": "Bitcoin", "tipo": "cripto", "fuente": "yahoo", "moneda": "EUR",
                 "vivo": "bitcoin", "precio": 60000.0, "fecha": "2026-01-01", "mercado": None}]
    return [{"codigo": f"COD-{texto}", "nombre": f"Producto {texto}", "tipo": tipos[texto], "fuente": "yahoo",
             "moneda": "EUR", "vivo": "bitcoin" if texto == "BTC" else "", "precio": 10.0,
             "fecha": "2026-01-01", "mercado": None}]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        p = mock.patch.object(importar.buscar, "buscar", falso_buscar)
        p.start()
        self.addCleanup(p.stop)
        self.cfg = copy.deepcopy(almacen.CARTERA_VACIA)

    def plan(self, filas=None, cfg=None, cabecera=CABECERA):
        contenido = csv_de(filas if filas is not None else filas_base(), cabecera)
        return importar.preparar_traderepublic(cfg if cfg is not None else self.cfg,
                                               [("transactions.csv", contenido)], self._tmp.name)

    def importa(self, filas=None, cfg=None):
        cfg = cfg if cfg is not None else self.cfg
        plan = self.plan(filas, cfg)
        informe = importar.aplicar(cfg, plan)
        return plan, informe

    def movs(self, tipo):
        return [m for m in self.cfg["movimientos"] if m["tipo"] == tipo]

    def prod(self, ident):
        return next(p for p in self.cfg["productos"] if p.get("identificador") == ident)


class Movimientos(Base):
    def test_compra_con_comision_importe_es_lo_que_salio(self):
        self.importa()
        a = self.prod(A)["id"]
        c = next(m for m in self.movs("compra") if m["producto"] == a)
        self.assertEqual((c["importe"], c["comision"], c["unidades"], c["fecha"]), (60.0, 1.0, 4.0, "2026-01-10"))

    def test_compra_sin_comision_no_lleva_comision(self):
        self.importa()
        e = next(m for m in self.movs("compra") if m["producto"] == self.prod(ETF)["id"])
        self.assertEqual((e["importe"], e.get("comision")), (200.0, None))

    def test_venta_con_comision_y_retencion(self):
        self.importa()
        v = self.movs("venta")[0]
        self.assertEqual((v["importe"], v["comision"], v["unidades"]), (335.01, 1.0, 2.0))
        self.assertIn("retención 1,89 €", v["nota"])

    def test_interes_neto_en_la_cuenta_de_efectivo(self):
        self.importa()
        i = self.movs("interes")
        self.assertEqual([(m["importe"], m["fecha"]) for m in i], [(0.07, "2026-02-15")])
        cuenta = next(p for p in self.cfg["productos"] if p["nombre"] == importar.NOMBRE_CUENTA_TR)
        self.assertEqual((i[0]["producto"], cuenta["tipo"]), (cuenta["id"], "efectivo"))

    def test_tipos_de_producto_segun_trade_republic(self):
        self.importa()
        self.assertEqual([self.prod(x)["tipo"] for x in (A, ETF, "BTC")], ["fondo", "etf", "cripto"])
        self.assertEqual((self.prod("BTC")["codigo"], self.prod("BTC")["vivo"]), ("BTC-EUR", "bitcoin"))

    def test_migration_no_crea_movimientos_ni_producto(self):
        self.importa()
        self.assertNotIn(VIEJO, [p.get("identificador") for p in self.cfg["productos"]])
        self.assertEqual(len(self.cfg["movimientos"]), 6)
        self.assertEqual(sorted(m["tipo"] for m in self.cfg["movimientos"]),
                         ["compra", "compra", "compra", "interes", "traspaso", "venta"])

    def test_nada_privado_acaba_en_la_cartera(self):
        self.importa()
        guardado = json.dumps(self.cfg, ensure_ascii=False)
        for texto in PRIVADOS:
            self.assertNotIn(texto, guardado)
        for texto in PRIVADOS:
            self.assertNotIn(texto, json.dumps(importar.vista_previa(copy.deepcopy(self.cfg), self.plan(cfg=copy.deepcopy(self.cfg))),
                                               ensure_ascii=False))


class Efectivo(Base):
    def test_saldo_exacto_con_tarjeta_y_transferencias_dentro(self):
        plan = self.plan()
        self.assertEqual(plan.resumen["saldo"], float(SALDO_BASE))
        self.assertEqual(plan.valoraciones[0]["valor"], 890.58)
        self.assertEqual(plan.valoraciones[0]["fecha"], "2026-03-03")

    def test_funcion_del_saldo_suma_amount_fee_tax(self):
        filas = [{"amount": "-59.00", "fee": "-1.00", "tax": ""}, {"amount": "337.90", "fee": "-1.00", "tax": "-1.89"},
                 {"amount": "", "fee": "", "tax": ""}]
        self.assertEqual(importar.saldo_efectivo_tr(filas), Decimal("275.01"))

    def test_la_vista_previa_avisa_del_saldo(self):
        informe = importar.vista_previa(self.cfg, self.plan())
        self.assertTrue(any("Saldo calculado: 890,58 €" in a and "abriste la cuenta" in a for a in informe["avisos"]))
        self.assertEqual(informe["saldos"], 1)

    def test_recuentos_de_la_vista_previa(self):
        r = importar.vista_previa(self.cfg, self.plan())["resumen"]
        self.assertEqual((r["compras"], r["ventas"], r["intereses"], r["traspasos"]), (3, 1, 1, 1))
        self.assertEqual(r["ignoradas"], {"MIGRATION": 2, "CARD_TRANSACTION": 1, "TRANSFER_INBOUND": 1,
                                          "TRANSFER_INSTANT_OUTBOUND": 1, "BENEFITS_SAVEBACK": 1})
        self.assertEqual(r["filas"], 13)

    def test_ningun_tipo_ignorado_sale_como_desconocido(self):
        informe = importar.vista_previa(self.cfg, self.plan())
        self.assertFalse([a for a in informe["avisos"] if "desconocido" in a])
        self.assertEqual(informe["errores"], [])


class Traspasos(Base):
    def test_cambio_entre_fondos_es_un_traspaso_marcado(self):
        self.importa()
        t = self.movs("traspaso")
        self.assertEqual(len(t), 1)
        self.assertEqual((t[0]["producto"], t[0]["destino"]), (self.prod(A)["id"], self.prod(B)["id"]))
        self.assertEqual((t[0]["unidades"], t[0]["unidadesDestino"], t[0]["importe"], t[0]["fecha"]),
                         (0.5, 6.0, 80.0, "2026-03-01"))

    def test_la_vista_previa_marca_el_traspaso_para_revisar(self):
        informe = importar.vista_previa(self.cfg, self.plan())
        f = next(f for f in informe["filas"] if f["tipo"] == "traspaso")
        self.assertEqual(f["marcas"], [importar.MARCA_TRASPASO])
        self.assertTrue(f["destinoNombre"])

    def test_venta_sin_importe_y_sin_pareja_es_error(self):
        filas = [fila("TRANSFER_INBOUND", "2026-01-05", "CASH", amount="1000.00"),
                 fila("BUY", "2026-01-10", clase="MUTUAL_FUND", nombre="A", simbolo=A, shares="4", price="15",
                      amount="-60"),
                 fila("SELL", "2026-02-01", clase="MUTUAL_FUND", nombre="A", simbolo=A, shares="-1", price="15")]
        informe = importar.vista_previa(self.cfg, self.plan(filas))
        self.assertEqual(len(informe["errores"]), 1)
        self.assertEqual(informe["errores"][0]["fila"], 4)
        self.assertEqual([f["tipo"] for f in informe["filas"] if f["tipo"] != "saldo"], ["compra"])

    def test_valor_distinto_o_demasiado_lejos_no_empareja(self):
        for dias, precio in (("2026-03-09", "13.35"), ("2026-03-03", "14.50")):
            filas = [fila("SELL", "2026-03-01", clase="MUTUAL_FUND", nombre="A", simbolo=A, shares="-0.5",
                          price="160"),
                     fila("BUY", dias, clase="MUTUAL_FUND", nombre="B", simbolo=B, shares="6", price=precio)]
            informe = importar.vista_previa(self.cfg, self.plan(filas))
            self.assertEqual(len(informe["errores"]), 2, (dias, precio))
            self.assertEqual(informe["resumen"]["traspasos"], 0)


class Reimportar(Base):
    def test_el_mismo_fichero_dos_veces_no_duplica(self):
        _, primero = self.importa()
        antes = copy.deepcopy(self.cfg["movimientos"])
        _, segundo = self.importa()
        self.assertEqual((primero["añadidos"], segundo["añadidos"], segundo["repetidos"]), (6, 0, 6))
        self.assertEqual(self.cfg["movimientos"], antes)
        self.assertEqual(len(self.cfg["valoraciones"]), 1)           # el saldo de la misma fecha se sustituye
        self.assertEqual(len([p for p in self.cfg["productos"] if p["nombre"] == importar.NOMBRE_CUENTA_TR]), 1)

    def test_un_fichero_que_se_solapa_solo_anade_lo_nuevo(self):
        self.importa(filas_base()[:5])
        self.assertEqual(len(self.cfg["movimientos"]), 4)
        _, segundo = self.importa()
        self.assertEqual((segundo["añadidos"], segundo["repetidos"]), (2, 4))

    def test_dos_archivos_solapados_no_cuentan_dos_veces_en_el_saldo(self):
        filas = filas_base()
        plan = importar.preparar_traderepublic(self.cfg, [("a.csv", csv_de(filas)), ("b.csv", csv_de(filas[3:]))],
                                               self._tmp.name)
        self.assertEqual(plan.resumen["saldo"], float(SALDO_BASE))


class Formato(Base):
    def test_fichero_sin_la_cabecera_de_trade_republic(self):
        informe = importar.vista_previa(self.cfg, self.plan(cabecera=["fecha", "importe", "tipo"]))
        self.assertEqual(len(informe["errores"]), 1)
        self.assertIn("Trade Republic", informe["errores"][0]["mensaje"])
        self.assertEqual((informe["añadidos"], informe["saldos"]), (0, 0))

    def test_archivo_vacio_solo_cabecera(self):
        informe = importar.vista_previa(self.cfg, self.plan(filas=[]))
        self.assertEqual(len(informe["errores"]), 1)
        self.assertEqual(informe["añadidos"], 0)


if __name__ == "__main__":
    unittest.main()
