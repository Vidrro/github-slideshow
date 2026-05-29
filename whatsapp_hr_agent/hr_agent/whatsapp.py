"""Utilitarios para integrar con la WhatsApp Cloud API (Meta).

Este módulo NO se necesita para el prototipo/demo local, pero deja todo listo
para el momento de escalar a un plan productivo. Encapsula:

* La verificación del webhook (handshake que exige Meta al registrar la URL).
* La extracción del texto y el remitente de los eventos entrantes.
* El envío de respuestas de texto a través de la Graph API.

Requisitos para producción (todos gratuitos de crear en Meta):
    - Una app en https://developers.facebook.com con el producto WhatsApp.
    - Un número de teléfono de WhatsApp Business.
    - Las variables de entorno descritas en .env.example.

Recuerda: responder DENTRO de la ventana de 24h a mensajes iniciados por el
usuario NO tiene costo de mensajería. El costo aparece con plantillas que tú
inicias. Ver README para el detalle de precios.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import requests

GRAPH_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v21.0")


def verificar_webhook(params: dict) -> Tuple[Optional[str], int]:
    """Maneja el handshake GET de verificación del webhook de Meta.

    Meta envía hub.mode, hub.verify_token y hub.challenge. Si el token coincide
    con el configurado, debemos devolver el challenge en texto plano.

    Devuelve (cuerpo_respuesta, codigo_http).
    """
    modo = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    token_esperado = os.environ.get("WHATSAPP_VERIFY_TOKEN")

    if modo == "subscribe" and token and token == token_esperado:
        return challenge, 200
    return "Token de verificación inválido", 403


def extraer_mensaje(payload: dict) -> Optional[Tuple[str, str]]:
    """Extrae (numero_remitente, texto) de un evento entrante del webhook.

    Devuelve None si el evento no contiene un mensaje de texto procesable
    (por ejemplo, notificaciones de estado de entrega).
    """
    try:
        entry = payload["entry"][0]
        cambio = entry["changes"][0]["value"]
        mensajes = cambio.get("messages")
        if not mensajes:
            return None
        mensaje = mensajes[0]
        if mensaje.get("type") != "text":
            return None
        numero = mensaje["from"]
        texto = mensaje["text"]["body"]
        return numero, texto
    except (KeyError, IndexError, TypeError):
        return None


def enviar_mensaje(numero_destino: str, texto: str) -> dict:
    """Envía un mensaje de texto al usuario vía la Graph API de WhatsApp.

    Lee el phone number id y el token de acceso desde variables de entorno.
    Lanza una excepción si las credenciales no están configuradas.
    """
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    if not phone_number_id or not token:
        raise RuntimeError(
            "Faltan credenciales: define WHATSAPP_PHONE_NUMBER_ID y "
            "WHATSAPP_ACCESS_TOKEN (ver .env.example)."
        )

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    cuerpo = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto},
    }
    respuesta = requests.post(url, headers=headers, json=cuerpo, timeout=15)
    respuesta.raise_for_status()
    return respuesta.json()
