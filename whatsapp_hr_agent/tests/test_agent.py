"""Pruebas del motor del agente y de la integración con WhatsApp.

Se ejecutan sin dependencias externas:
    python -m unittest discover -s whatsapp_hr_agent/tests
o
    pytest whatsapp_hr_agent/tests
"""

import os
import sys
import unittest

# Permite importar el paquete hr_agent sin instalar nada.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hr_agent import responder  # noqa: E402
from hr_agent.agent import normalizar  # noqa: E402
from hr_agent.whatsapp import extraer_mensaje, verificar_webhook  # noqa: E402


class TestNormalizacion(unittest.TestCase):
    def test_quita_acentos_y_signos(self):
        self.assertEqual(normalizar("¿Cómo estás?"), "como estas")

    def test_colapsa_espacios_y_minusculas(self):
        self.assertEqual(normalizar("  HOLA   Mundo  "), "hola mundo")


class TestAgente(unittest.TestCase):
    def test_saludo(self):
        r = responder("Hola")
        self.assertFalse(r.es_fallback)
        self.assertIsNone(r.faq_id)
        self.assertIn("asistente virtual", r.texto.lower())

    def test_vacaciones_directo(self):
        r = responder("¿Cómo solicito mis vacaciones?")
        self.assertEqual(r.faq_id, "vacaciones_solicitud")
        self.assertFalse(r.es_fallback)

    def test_vacaciones_coloquial_con_typos(self):
        # Frase informal y con errores: debe seguir resolviendo.
        r = responder("como pido vacasiones")
        self.assertEqual(r.faq_id, "vacaciones_solicitud")

    def test_saldo_vacaciones_no_se_confunde_con_solicitud(self):
        r = responder("cuantos dias de vacaciones me quedan")
        self.assertEqual(r.faq_id, "vacaciones_saldo")

    def test_nomina_fecha(self):
        r = responder("cuando pagan la nomina")
        self.assertEqual(r.faq_id, "nomina_fecha_pago")

    def test_certificado(self):
        r = responder("necesito un certificado laboral")
        self.assertEqual(r.faq_id, "certificado_laboral")

    def test_incapacidad(self):
        r = responder("como reporto una incapacidad medica")
        self.assertEqual(r.faq_id, "incapacidad")

    def test_contacto_humano(self):
        r = responder("quiero hablar con una persona de recursos humanos")
        self.assertEqual(r.faq_id, "contacto_rrhh")

    def test_fuera_de_tema_es_fallback(self):
        r = responder("cual es la capital de francia")
        self.assertTrue(r.es_fallback)
        self.assertIsNone(r.faq_id)

    def test_vacio_es_fallback(self):
        r = responder("   ")
        self.assertTrue(r.es_fallback)


class TestWhatsAppHelpers(unittest.TestCase):
    def test_verificar_webhook_ok(self):
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "secreto123"
        cuerpo, codigo = verificar_webhook(
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "secreto123",
                "hub.challenge": "desafio",
            }
        )
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo, "desafio")

    def test_verificar_webhook_token_malo(self):
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "secreto123"
        _, codigo = verificar_webhook(
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "incorrecto",
                "hub.challenge": "desafio",
            }
        )
        self.assertEqual(codigo, 403)

    def test_extraer_mensaje_de_texto(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(extraer_mensaje(payload), ("573001112233", "Hola"))

    def test_extraer_mensaje_ignora_estados(self):
        # Evento de estado de entrega (sin 'messages') -> None.
        payload = {"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}
        self.assertIsNone(extraer_mensaje(payload))


if __name__ == "__main__":
    unittest.main()
