"""Prueba rápida de ENVÍO por WhatsApp Cloud API.

Sirve para demostrar en minutos que la integración con WhatsApp funciona, SIN
necesidad de configurar el webhook ni un túnel. Envía un mensaje de texto a un
número que tú indiques.

Requisitos:
    1. pip install -r requirements.txt
    2. Copiar .env.example a .env y completar WHATSAPP_PHONE_NUMBER_ID y
       WHATSAPP_ACCESS_TOKEN (del panel de Meta).
    3. El número destino debe estar agregado como "destinatario de prueba" en el
       panel de Meta (mientras uses el número de prueba gratuito).

Uso:
    python enviar_prueba.py 573001112233
    python enviar_prueba.py 573001112233 "Hola, este es un mensaje de prueba"

El número va en formato internacional, solo dígitos (sin +, sin espacios).
"""

from __future__ import annotations

import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from hr_agent.whatsapp import enviar_mensaje

MENSAJE_POR_DEFECTO = (
    "✅ ¡Hola! Soy el asistente virtual de Recursos Humanos. "
    "Esta es una prueba de conexión y está funcionando correctamente."
)


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python enviar_prueba.py <numero_destino> [mensaje]")
        print('Ejemplo: python enviar_prueba.py 573001112233 "Hola"')
        sys.exit(1)

    numero = sys.argv[1].strip().lstrip("+").replace(" ", "")
    mensaje = sys.argv[2] if len(sys.argv) > 2 else MENSAJE_POR_DEFECTO

    print(f"Enviando mensaje a +{numero} ...")
    try:
        respuesta = enviar_mensaje(numero, mensaje)
    except Exception as exc:
        print(f"❌ Error al enviar: {exc}")
        sys.exit(1)

    print("✅ Enviado. Respuesta de la API:")
    print(respuesta)


if __name__ == "__main__":
    main()
