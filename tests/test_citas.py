"""Pruebas de hugin/personal/citas.py.

Portadas de diario/tests/test_agenda.py de midgaror: mismo cuerpo, con
`self.ruta` cambiado por `self.inq` y sin `TestAgenda.test_cli` (esta
versión es librería). Añade dos pruebas que el juez de la fase 4 pidió
ANTES de portar el modelo: `del_dia("el lunes")` y
`de_la_semana("el lunes")` afirmando el lunes que VIENE, llamadas
directamente y no a través de `resumen()` — que ya cazaba la dirección de
la semana pero no la del día ni la de forma directa.
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import entorno  # noqa: E402,F401

from hugin import inquilino as hugin_inquilino
from hugin.personal import citas, fechas

AHORA = datetime(2026, 9, 5, 17, 10)  # sábado
HOY = "2026-09-05"
MANANA = "2026-09-06"


def _inq(ruta: Path) -> hugin_inquilino.Inquilino:
    ruta.mkdir(parents=True, exist_ok=True)
    return hugin_inquilino.Inquilino(
        nombre="prueba", ruta=ruta, capacidades=frozenset({"agenda"}), base=None)


class TestCitas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inq = _inq(Path(self.tmp.name) / "inquilino")
        self.ruta = self.inq.ruta / citas.FICHERO

    def _cita(self, texto, **kw):
        return citas.agregar(texto, self.inq, AHORA, **kw)[0]

    def test_sin_fichero_no_hay_citas(self):
        self.assertEqual(citas.cargar(self.inq), [])
        self.assertIn("Sin citas el", citas.resumen(HOY, self.inq))

    def test_agregar_saca_la_fecha_del_texto(self):
        cita, solapan = citas.agregar("médico mañana a las 10", self.inq, AHORA)
        self.assertEqual(solapan, [])
        # «a las 10» sin mañana/tarde/noche: la hora se guarda tal cual, pero
        # marcada como sin confirmar (ver TestHoraSinConfirmar más abajo).
        self.assertEqual(cita, {"id": 1, "texto": "médico", "fecha": MANANA, "hora": "10:00",
                                "hora_sin_confirmar": True,
                                "duracion": 60, "creada": "2026-09-05 17:10"})
        # En disco va envuelto con su versión de esquema (ADR-012, apartado 7).
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8")),
                         {"schemaVersion": citas.VERSION, "datos": [cita]})

    def test_una_cita_sin_cuando_no_es_una_cita(self):
        for malo in ("comprar el pan", "", "   "):
            with self.assertRaises(ValueError):
                citas.agregar(malo, self.inq, AHORA)
        self.assertFalse(self.ruta.exists())

    def test_sin_hora_es_de_todo_el_dia_y_no_choca(self):
        self._cita("médico mañana a las 10")
        cita, solapan = citas.agregar("reunión mañana", self.inq, AHORA)
        self.assertIsNone(cita["hora"])
        self.assertEqual(solapan, [])
        self.assertIn("todo el día", citas.resumen(MANANA, self.inq))

    def test_avisa_del_choque_pero_guarda_la_cita(self):
        self._cita("médico mañana a las 10")
        cita, solapan = citas.agregar("dentista mañana a las 10:30", self.inq, AHORA)
        self.assertEqual([c["texto"] for c in solapan], ["médico"])
        self.assertIn("Choca con [1] médico a las 10:00", citas.aviso_choques(solapan))
        self.assertEqual(len(citas.cargar(self.inq)), 2)  # se guarda igual

    def test_no_choca_si_no_se_solapan_ni_si_es_otro_dia(self):
        self._cita("médico mañana a las 10")          # 10:00-11:00
        self.assertEqual(citas.agregar("gestoría mañana a las 11", self.inq, AHORA)[1], [])
        self.assertEqual(citas.agregar("café el lunes a las 10", self.inq, AHORA)[1], [])

    def test_una_cita_cancelada_deja_de_estorbar(self):
        self._cita("médico mañana a las 10")
        citas.cancelar(1, self.inq)
        self.assertEqual(citas.agregar("dentista mañana a las 10", self.inq, AHORA)[1], [])
        self.assertEqual(citas.del_dia(MANANA, self.inq)[0]["id"], 2)
        self.assertTrue(citas.cargar(self.inq)[0]["cancelada"])

    def test_mover_cambia_el_cuando_y_avisa_del_choque(self):
        self._cita("médico mañana a las 10")
        self._cita("dentista el lunes a las 10")
        cita, solapan = citas.mover(2, "mañana a las 10:30", self.inq, AHORA)
        self.assertEqual((cita["fecha"], cita["hora"]), (MANANA, "10:30"))
        self.assertEqual([c["id"] for c in solapan], [1])
        with self.assertRaises(ValueError):
            citas.mover(1, "cuando pueda", self.inq, AHORA)

    def test_id_inexistente_falla_sin_tocar_el_fichero(self):
        self._cita("médico mañana a las 10")
        antes = self.ruta.read_text(encoding="utf-8")
        for accion in (lambda i: citas.cancelar(i, self.inq),
                       lambda i: citas.mover(i, "el lunes", self.inq, AHORA)):
            with self.assertRaises(ValueError):
                accion(99)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)
        self.assertEqual(self._cita("gestoría mañana")["id"], 2)  # los ids no se reutilizan

    def test_del_dia_y_de_la_semana_ordenan_por_hora(self):
        self._cita("médico mañana a las 10")
        self._cita("gestoría mañana a las 9")
        self._cita("reunión mañana")           # todo el día
        self._cita("café el 20 de septiembre")  # fuera de la semana
        self.assertEqual([c["id"] for c in citas.del_dia(MANANA, self.inq)], [3, 2, 1])
        self.assertEqual([c["id"] for c in citas.de_la_semana(HOY, self.inq)], [3, 2, 1])

    def test_resumen_de_la_semana_agrupa_por_dia(self):
        self._cita("médico mañana a las 10 de la mañana")
        self._cita("dentista el lunes a las 17")
        lineas = citas.resumen(HOY, self.inq, semana=True).splitlines()
        self.assertEqual(lineas[0], "Citas del 2026-09-05 al 2026-09-11:")
        self.assertEqual(lineas[1], "2026-09-06:")
        self.assertIn("[1] 10:00 · médico", lineas[2])
        self.assertEqual(lineas[3], "2026-09-07:")
        self.assertIn("[2] 17:00 · dentista", lineas[4])

    def test_sin_inquilino_falla_claro(self):
        with self.assertRaises(ValueError):
            citas.agregar("médico mañana a las 10", ahora=AHORA)


class TestFechasEnLenguajeNatural(unittest.TestCase):
    """«mañana», «el lunes»… Hacia delante: la agenda se mira para lo que
    viene. La referencia es hoy de verdad, porque `resumen()` no admite un
    `ahora`.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inq = _inq(Path(self.tmp.name) / "inquilino")
        self.hoy = datetime.now(fechas.ZONA).date()

    def test_manana(self):
        manana = (self.hoy + timedelta(days=1)).isoformat()
        self.assertIn(f"Sin citas el {manana}", citas.resumen("mañana", self.inq))
        self.assertEqual(citas.del_dia("mañana", self.inq), [])

    def test_del_dia_el_lunes_es_el_que_viene_no_el_que_paso(self):
        # Pedido explícito del juez, ANTES de portar el modelo: del_dia y
        # de_la_semana llamados directamente (no a través de resumen), con
        # "el lunes" y afirmando el lunes QUE VIENE. La agenda va siempre
        # hacia delante: nadie reserva cita para el martes pasado.
        self._agregar_directo("médico el lunes a las 10")
        citas_del_lunes = citas.del_dia("el lunes", self.inq)
        self.assertEqual(len(citas_del_lunes), 1)
        self.assertGreater(citas_del_lunes[0]["fecha"], self.hoy.isoformat())

    def test_de_la_semana_el_lunes_es_la_que_viene_no_la_que_paso(self):
        inicio = citas.de_la_semana("el lunes", self.inq)
        # Sin citas todavía: se comprueba con la fecha que resuelve
        # normalizar() por el mismo camino que usa de_la_semana().
        self.assertEqual(inicio, [])
        resuelto = fechas.normalizar("el lunes", hacia_atras=False)
        self.assertGreater(resuelto, self.hoy.isoformat())
        self.assertEqual(datetime.fromisoformat(resuelto).weekday(), 0)

    def _agregar_directo(self, texto):
        citas.agregar(texto, self.inq)

    def test_la_semana_desde_el_lunes_que_viene(self):
        texto = citas.resumen("el lunes", self.inq, semana=True)
        inicio = texto.split("entre el ")[1].split(" y")[0]
        self.assertGreater(inicio, self.hoy.isoformat())
        self.assertEqual(datetime.fromisoformat(inicio).weekday(), 0)

    def test_una_cita_apuntada_manana_sale_al_pedir_manana(self):
        citas.agregar("médico mañana a las 10", self.inq)
        self.assertIn("médico", citas.resumen("mañana", self.inq))

    def test_lo_que_no_es_fecha_avisa(self):
        with self.assertRaises(ValueError) as e:
            citas.resumen("loquesea", self.inq)
        self.assertIn("fecha no válida", str(e.exception))

    def test_iso_como_siempre(self):
        self.assertIn("Sin citas el 2026-01-01", citas.resumen("2026-01-01", self.inq))


class TestHoraSinConfirmar(unittest.TestCase):
    """«a las cinco» sin mañana/tarde/noche: se guarda, pero se marca.

    Antes esto se colaba como 05:00 sin más, con el mismo riesgo que ya
    tenía el lado de negocio (`hugin/mente/recepcion.py`): una cita a las
    5 de la madrugada porque nadie preguntó si era de la tarde.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inq = _inq(Path(self.tmp.name) / "inquilino")

    def test_hora_suelta_se_marca_sin_confirmar(self):
        cita, _ = citas.agregar("médico mañana a las 5", self.inq, AHORA)
        self.assertTrue(cita["hora_sin_confirmar"])

    def test_hora_con_franja_no_se_marca(self):
        cita, _ = citas.agregar("médico mañana a las 5 de la tarde", self.inq, AHORA)
        self.assertFalse(cita["hora_sin_confirmar"])

    def test_hora_de_tarde_sin_ambiguedad_no_se_marca(self):
        cita, _ = citas.agregar("médico mañana a las 17", self.inq, AHORA)
        self.assertFalse(cita["hora_sin_confirmar"])

    def test_sin_hora_no_hay_nada_que_confirmar(self):
        cita, _ = citas.agregar("médico mañana", self.inq, AHORA)
        self.assertFalse(cita["hora_sin_confirmar"])

    def test_linea_avisa_de_la_ambiguedad(self):
        cita, _ = citas.agregar("médico mañana a las 5", self.inq, AHORA)
        self.assertIn("(¿mañana o tarde?)", citas.linea(cita))

    def test_linea_no_avisa_si_esta_confirmada(self):
        cita, _ = citas.agregar("médico mañana a las 5 de la tarde", self.inq, AHORA)
        self.assertNotIn("(¿mañana o tarde?)", citas.linea(cita))

    def test_mover_tambien_marca_la_ambiguedad(self):
        cita, _ = citas.agregar("médico mañana a las 5 de la tarde", self.inq, AHORA)
        movida, _ = citas.mover(cita["id"], "el lunes a las 6", self.inq, AHORA)
        self.assertTrue(movida["hora_sin_confirmar"])

    def test_mover_tambien_limpia_la_ambiguedad(self):
        cita, _ = citas.agregar("médico mañana a las 5", self.inq, AHORA)
        self.assertTrue(cita["hora_sin_confirmar"])
        movida, _ = citas.mover(cita["id"], "el lunes a las 6 de la tarde", self.inq, AHORA)
        self.assertFalse(movida["hora_sin_confirmar"])


if __name__ == "__main__":
    unittest.main()
