"""Servidor webhook para conectar el agente de RR.HH. con la WhatsApp Cloud API.

Este es el componente que usarás al ESCALAR a un plan productivo. Expone:

    GET  /webhook  -> verificación del webhook que exige Meta.
    POST /webhook  -> recibe mensajes entrantes y responde automáticamente.
    GET  /health   -> chequeo de salud simple.

Para el prototipo SIN costo no necesitas levantar esto: usa `demo.py`.

Ejecución local (cuando tengas credenciales):
    pip install -r requirements.txt
    export $(cat .env | xargs)   # o usa python-dotenv
    python app.py
    # Expón el puerto 5000 con un túnel (p. ej. ngrok) y registra la URL en Meta.
"""

from __future__ import annotations

import os

from flask import Flask, request

# Carga automática del archivo .env (si python-dotenv está instalado).
# Así no hay que exportar variables a mano en Windows/PowerShell.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - opcional
    pass

from hr_agent import responder
from hr_agent.whatsapp import enviar_mensaje, extraer_mensaje, verificar_webhook

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.get("/webhook")
def verificar():
    cuerpo, codigo = verificar_webhook(request.args.to_dict())
    return cuerpo, codigo


@app.post("/webhook")
def recibir():
    payload = request.get_json(force=True, silent=True) or {}
    mensaje = extraer_mensaje(payload)

    # Si no es un mensaje de texto procesable (p. ej. un estado de entrega),
    # respondemos 200 para que Meta no reintente el envío.
    if mensaje is None:
        return {"status": "ignorado"}, 200

    numero, texto = mensaje
    respuesta = responder(texto)

    try:
        enviar_mensaje(numero, respuesta.texto)
    except Exception as exc:  # pragma: no cover - depende de credenciales reales
        app.logger.error("No se pudo enviar la respuesta a WhatsApp: %s", exc)
        return {"status": "error", "detalle": str(exc)}, 500

    return {"status": "ok", "faq_id": respuesta.faq_id}, 200


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=puerto)
