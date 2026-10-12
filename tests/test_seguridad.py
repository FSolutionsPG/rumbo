# -*- coding: utf-8 -*-
"""Guarda de peticiones ajenas (incidencia #8): XSSI, DNS rebinding y CSRF."""

import os
import tempfile
import unittest

# DATOS se calcula al importar: se fija antes, para no tocar mis_datos/.
_TMP = tempfile.TemporaryDirectory()
os.environ["PATRIMONIO_DATOS"] = _TMP.name

from app import servidor  # noqa: E402

AVISO = servidor.AVISO_AJENA


def tearDownModule():
    _TMP.cleanup()


class GuardaAjenas(unittest.TestCase):
    def setUp(self):
        self.c = servidor.app.test_client()

    def rechazada(self, r):
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json(), {"ok": False, "errores": [AVISO]})

    def admitida(self, r):
        self.assertNotEqual(r.status_code, 403, r.get_data(as_text=True)[:200])

    # ---- deben pasar
    def test_pasa_raiz_same_origin(self):
        r = self.c.get("/", headers={"Host": "127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"})
        self.admitida(r)
        self.assertEqual(r.status_code, 200)

    def test_pasa_datos_con_none(self):
        self.admitida(self.c.get("/datos.js", headers={"Sec-Fetch-Site": "none"}))

    def test_pasa_sin_sec_fetch(self):
        r = self.c.get("/datos.js", headers={"Host": "127.0.0.1:8765"})
        self.assertEqual(r.status_code, 200)

    def test_pasa_localhost(self):
        r = self.c.get("/api/ping", headers={"Host": "localhost:8766"})
        self.assertEqual(r.status_code, 200)

    def test_pasa_post_mismo_origen(self):
        r = self.c.post("/api/reiniciar", headers={"Host": "127.0.0.1:8765",
                                                   "Origin": "http://127.0.0.1:8765",
                                                   "Sec-Fetch-Site": "same-origin"})
        self.admitida(r)   # 400 «sin cartera propia», pero no la guarda

    # ---- deben dar 403 de la guarda
    def test_rechaza_cross_site(self):
        self.rechazada(self.c.get("/datos.js", headers={"Sec-Fetch-Site": "cross-site"}))

    def test_rechaza_same_site(self):
        self.rechazada(self.c.get("/datos.js", headers={"Sec-Fetch-Site": "same-site"}))

    def test_rechaza_host_ajeno(self):
        self.rechazada(self.c.get("/datos.js", headers={"Host": "evil.example:8765"}))

    def test_rechaza_host_con_prefijo_propio(self):
        self.rechazada(self.c.get("/datos.js", headers={"Host": "127.0.0.1.evil.example"}))

    def test_rechaza_post_origen_ajeno(self):
        self.rechazada(self.c.post("/api/reiniciar", headers={"Host": "127.0.0.1:8765",
                                                              "Origin": "https://evil.example"}))

    def test_rechaza_post_origen_null(self):
        self.rechazada(self.c.post("/api/reiniciar", headers={"Host": "127.0.0.1:8765",
                                                              "Origin": "null"}))

    def test_rechaza_descarga_con_host_ajeno(self):
        self.rechazada(self.c.get("/api/copia/descargar", headers={"Host": "evil.example:8765"}))

    # ---- cabeceras
    def test_cabeceras_en_respuesta_normal(self):
        r = self.c.get("/api/ping", headers={"Host": "127.0.0.1:8765"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["Content-Security-Policy"], "frame-ancestors 'none'")


if __name__ == "__main__":
    unittest.main()
