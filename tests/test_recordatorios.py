"""Pruebas de hugin/personal/recordatorios.py.

Portadas de diario/tests/test_recordatorios.py de midgaror: mismo cuerpo,
con `self.citas`/`self.avisados` (dos rutas sueltas) cambiados por
`self.inq` (un Inquilino de mentira: las dos viven en su carpeta) y
`agenda` por `citas`. El reloj se inyecta siempre: un recordatorio que
depende de la hora a la que corra la prueba es una prueba que falla sola
una vez al día.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import entorno  # noqa: E402,F401

from hugin import inquilino as hugin_inquilino
from hugin.personal import citas, recordatorios

MADRID = ZoneInfo("Europe/Madrid")
AHORA = datetime(2026, 9, 18, 9, 0, tzinfo=MADRID)


def _inq(ruta: Path) -> hugin_inquilino.Inquilino:
    ruta.mkdir(parents=True, exist_ok=True)
    return hugin_inquilino.Inquilino(
        nombre="prueba", ruta=ruta, capacidades=frozenset({"agenda"}), base=None)


class CasoRecordatorios(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.inq = _inq(Path(self._tmp.name) / "inquilino")

    def cita(self, hora: str | None, fecha: str = "2026-09-18", texto: str = "médico") -> dict:
        """Escribe una cita directamente, sin pasar por el parser de texto."""
        todas = citas.cargar(self.inq)
        nueva = {"id": len(todas) + 1, "texto": texto, "fecha": fecha,
                 "hora": hora, "duracion": 60, "creada": "2026-09-17 20:00"}
        todas.append(nueva)
        citas.guardar(todas, self.inq)
        return nueva

    def pendientes(self, ahora=AHORA):
        return recordatorios.pendientes(self.inq, ahora)


class TestQueSeAvisa(CasoRecordatorios):
    def test_una_cita_dentro_de_la_ventana_se_avisa(self):
        self.cita("09:20")            # dentro de los 30 minutos
        self.assertEqual([c["texto"] for c in self.pendientes()], ["médico"])

    def test_justo_en_el_borde_de_la_ventana_tambien(self):
        self.cita("09:30")
        self.assertEqual(len(self.pendientes()), 1)

    def test_una_cita_lejos_todavia_no(self):
        self.cita("13:00")
        self.assertEqual(self.pendientes(), [])

    def test_una_cita_que_ya_paso_no_se_avisa(self):
        # Si el bot estuvo parado, al arrancar no vomita lo que ya empezó.
        self.cita("08:00")
        self.assertEqual(self.pendientes(), [])

    def test_una_cita_sin_hora_no_se_avisa(self):
        # Todo el día: no hay momento del que avisar.
        self.cita(None)
        self.assertEqual(self.pendientes(), [])

    def test_una_cita_cancelada_no_se_avisa(self):
        cita = self.cita("09:20")
        citas.cancelar(cita["id"], self.inq)
        self.assertEqual(self.pendientes(), [])

    def test_salen_ordenadas_por_hora(self):
        self.cita("09:25", texto="segunda")
        self.cita("09:05", texto="primera")
        self.assertEqual([c["texto"] for c in self.pendientes()], ["primera", "segunda"])

    def test_otro_dia_dentro_de_30_minutos_de_reloj_no_cuenta(self):
        # 09:20 de mañana no está dentro de la ventana de hoy a las 9:00.
        self.cita("09:20", fecha="2026-09-19")
        self.assertEqual(self.pendientes(), [])


class TestNoSeAvisaDosVeces(CasoRecordatorios):
    def test_una_vez_anotada_ya_no_sale(self):
        self.cita("09:20")
        primera = self.pendientes()
        self.assertEqual(len(primera), 1)
        recordatorios.anotar(primera, self.inq, AHORA)
        self.assertEqual(self.pendientes(), [])

    def test_mirar_sin_anotar_la_deja_pendiente(self):
        # A propósito: si el mensaje a Telegram falla, la cita se reintenta.
        self.cita("09:20")
        self.assertEqual(len(self.pendientes()), 1)
        self.assertEqual(len(self.pendientes()), 1)

    def test_el_id_solo_no_basta_la_fecha_va_delante(self):
        # El id 1 de hoy, avisado; el id 1 de otro fichero/día tiene que
        # poder avisarse igual. Guardar solo el número lo silenciaría, y
        # ese fallo no salta: simplemente no llega el aviso.
        hoy = self.cita("09:20")
        recordatorios.anotar([hoy], self.inq, AHORA)
        guardadas = recordatorios.cargar_avisados(self.inq)
        self.assertEqual(guardadas, ["2026-09-18#1"])
        self.assertIn("#", guardadas[0])

    def test_lo_anterior_a_hoy_se_tira_al_anotar(self):
        recordatorios.guardar_avisados(["2026-01-01#9", "2026-09-18#4"], self.inq)
        cita = self.cita("09:20")
        recordatorios.anotar([cita], self.inq, AHORA)
        guardadas = recordatorios.cargar_avisados(self.inq)
        self.assertNotIn("2026-01-01#9", guardadas)
        self.assertIn("2026-09-18#4", guardadas)
        self.assertIn("2026-09-18#1", guardadas)


class TestLaVentana(CasoRecordatorios):
    def test_la_ventana_es_la_constante_del_modulo(self):
        # Cambiar VENTANA_MINUTOS tiene que cambiar el comportamiento, no
        # solo la documentación.
        self.cita("09:45")
        self.assertEqual(self.pendientes(), [])
        justo = AHORA + timedelta(minutes=45) - timedelta(minutes=recordatorios.VENTANA_MINUTOS)
        self.assertEqual(len(self.pendientes(ahora=justo)), 1)


if __name__ == "__main__":
    unittest.main()
