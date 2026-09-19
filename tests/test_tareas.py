"""Pruebas de hugin/personal/tareas.py.

Portadas de diario/tests/test_tareas.py de midgaror: mismo cuerpo, con
`self.ruta` (un `Path`) cambiado por `self.inq` (un Inquilino de mentira,
sin backend Postgres) y sin `TestTareas.test_cli`, porque esta versión es
librería — no tiene `main()` de terminal.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import entorno  # noqa: E402,F401

from hugin import inquilino as hugin_inquilino
from hugin.personal import tareas

AHORA = datetime(2026, 9, 5, 17, 10)  # sábado
HOY = "2026-09-05"


def _inq(ruta: Path) -> hugin_inquilino.Inquilino:
    ruta.mkdir(parents=True, exist_ok=True)
    return hugin_inquilino.Inquilino(
        nombre="prueba", ruta=ruta, capacidades=frozenset({"tareas"}), base=None)


class TestTareas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inq = _inq(Path(self.tmp.name) / "inquilino")
        self.ruta = self.inq.ruta / tareas.FICHERO

    def test_sin_fichero_no_hay_tareas(self):
        self.assertEqual(tareas.cargar(self.inq), [])
        self.assertIn("No hay tareas", tareas.resumen(self.inq, hoy=HOY))

    def test_agregar_crea_el_fichero_y_numera_desde_uno(self):
        t = tareas.agregar("Comprar el pan", self.inq, AHORA)
        self.assertEqual(t, {"id": 1, "texto": "Comprar el pan", "estado": "pendiente",
                             "fecha": None, "hora": None,
                             "creada": "2026-09-05 17:10", "hecha_el": None})
        # En disco va envuelto con su versión de esquema (ADR-012, apartado 7).
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8")),
                         {"schemaVersion": tareas.VERSION, "datos": [t]})

    def test_la_fecha_sale_del_texto(self):
        t = tareas.agregar("médico mañana a las 10", self.inq, AHORA)
        self.assertEqual((t["texto"], t["fecha"], t["hora"]), ("médico", "2026-09-06", "10:00"))
        t = tareas.agregar("llamar a Ana el 15 de octubre", self.inq, AHORA)
        self.assertEqual((t["texto"], t["fecha"], t["hora"]), ("llamar a Ana", "2026-10-15", None))

    def test_si_el_texto_es_solo_la_fecha_se_conserva(self):
        t = tareas.agregar("mañana", self.inq, AHORA)
        self.assertEqual(t["texto"], "mañana")
        self.assertEqual(t["fecha"], "2026-09-06")

    def test_estados(self):
        tareas.agregar("una", self.inq, AHORA)
        self.assertEqual(tareas.empezar(1, self.inq)["estado"], "en_proceso")
        t = tareas.hecha(1, self.inq, datetime(2026, 9, 6, 9, 0))
        self.assertEqual((t["estado"], t["hecha_el"]), ("hecha", "2026-09-06 09:00"))
        t = tareas.reabrir(1, self.inq)
        self.assertEqual((t["estado"], t["hecha_el"]), ("pendiente", None))

    def test_editar_y_aplazar(self):
        tareas.agregar("comprar pan", self.inq, AHORA)
        self.assertEqual(tareas.editar(1, "comprar pan y leche", self.inq, AHORA)["texto"], "comprar pan y leche")
        t = tareas.editar(1, "comprar pan el lunes", self.inq, AHORA)
        self.assertEqual((t["texto"], t["fecha"]), ("comprar pan", "2026-09-07"))
        t = tareas.aplazar(1, "pasado mañana por la tarde", self.inq, AHORA)
        self.assertEqual((t["fecha"], t["hora"]), ("2026-09-07", "16:00"))
        with self.assertRaises(ValueError):
            tareas.aplazar(1, "cuando pueda", self.inq, AHORA)
        with self.assertRaises(ValueError):
            tareas.editar(1, "   ", self.inq)

    def test_borrar_oculta_sin_perder_y_no_reutiliza_ids(self):
        tareas.agregar("una", self.inq, AHORA)
        tareas.agregar("dos", self.inq, AHORA)
        tareas.borrar(2, self.inq)
        self.assertEqual(tareas.agregar("tres", self.inq, AHORA)["id"], 3)
        self.assertNotIn("[2] dos", tareas.resumen(self.inq, hoy=HOY))
        self.assertTrue(tareas.cargar(self.inq)[1]["borrada"])
        with self.assertRaises(ValueError):
            tareas.hecha(2, self.inq)

    def test_id_inexistente_falla_sin_tocar_el_fichero(self):
        tareas.agregar("una", self.inq, AHORA)
        antes = self.ruta.read_text(encoding="utf-8")
        for accion in (tareas.hecha, tareas.empezar, tareas.borrar, tareas.reabrir):
            with self.assertRaises(ValueError):
                accion(99, self.inq)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)

    def test_resumen_ordena_por_estado_y_fecha_y_marca_vencidas(self):
        tareas.agregar("sin fecha", self.inq, AHORA)
        tareas.agregar("pagar el recibo", self.inq, AHORA)
        tareas.aplazar(2, "ayer", self.inq, AHORA)
        tareas.agregar("hoy a las 18", self.inq, AHORA)
        tareas.agregar("en marcha", self.inq, AHORA)
        tareas.empezar(4, self.inq)
        tareas.agregar("terminada", self.inq, AHORA)
        tareas.hecha(5, self.inq, AHORA)
        texto = tareas.resumen(self.inq, hoy=HOY)
        lineas = texto.splitlines()
        self.assertEqual(lineas[0], "◐ En proceso (1):")
        self.assertIn("[4] en marcha", lineas[1])
        self.assertEqual(lineas[2], "○ Pendientes (3):")
        self.assertIn("[2] pagar el recibo · 2026-09-04 ⚠️ vencida", lineas[3])
        self.assertIn("[3] hoy a las 18 · hoy 18:00", lineas[4])
        self.assertIn("[1] sin fecha", lineas[5])
        self.assertIn("● Hechas (1)", texto)

    def test_del_dia_trae_lo_de_hoy_y_lo_vencido(self):
        tareas.agregar("hoy", self.inq, AHORA)
        tareas.aplazar(1, "hoy", self.inq, AHORA)
        tareas.agregar("mañana", self.inq, AHORA)
        tareas.agregar("ayer", self.inq, AHORA)
        tareas.agregar("sin fecha", self.inq, AHORA)
        ids = [t["id"] for t in tareas.del_dia(HOY, self.inq)]
        self.assertEqual(ids, [3, 1])

    def test_lee_el_formato_viejo_sin_estados(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps([
            {"id": 1, "texto": "vieja abierta", "hecha": False,
             "creada": "2026-09-04 23:30", "hecha_el": None},
            {"id": 2, "texto": "vieja cerrada", "hecha": True,
             "creada": "2026-09-04 23:30", "hecha_el": "2026-09-04 23:40"},
        ]), encoding="utf-8")
        estados = [t["estado"] for t in tareas.cargar(self.inq)]
        self.assertEqual(estados, ["pendiente", "hecha"])
        self.assertIn("[1] vieja abierta", tareas.resumen(self.inq, hoy=HOY))
        self.assertEqual(tareas.agregar("nueva", self.inq, AHORA)["id"], 3)

    def test_sin_inquilino_falla_claro(self):
        with self.assertRaises(ValueError):
            tareas.agregar("una", ahora=AHORA)

    def test_hora_sin_franja_se_marca(self):
        t = tareas.agregar("médico mañana a las 5", self.inq, AHORA)
        self.assertTrue(t["sin_franja"])
        self.assertIn("(¿mañana o tarde?)", tareas.resumen(self.inq, hoy=HOY))

    def test_hora_acotada_no_se_marca(self):
        t = tareas.agregar("médico mañana a las 17", self.inq, AHORA)
        self.assertNotIn("sin_franja", t)

    def test_confirmar_hora_fija_la_hora_y_quita_la_marca(self):
        t = tareas.agregar("médico mañana a las 5", self.inq, AHORA)
        confirmada = tareas.confirmar_hora(t["id"], "17:00", self.inq)
        self.assertEqual(confirmada["hora"], "17:00")
        self.assertFalse(confirmada.get("sin_franja"))
        self.assertNotIn("(¿mañana o tarde?)", tareas.resumen(self.inq, hoy=HOY))

    def test_confirmar_hora_con_formato_invalido_falla_claro(self):
        t = tareas.agregar("médico mañana a las 5", self.inq, AHORA)
        for mala in ("cinco de la tarde", "25:00", "10:70", "10"):
            with self.assertRaises(ValueError):
                tareas.confirmar_hora(t["id"], mala, self.inq)

    def test_confirmar_hora_de_tarea_inexistente_falla_claro(self):
        with self.assertRaises(ValueError):
            tareas.confirmar_hora(99, "17:00", self.inq)


if __name__ == "__main__":
    unittest.main()
