"""Agente de RR.HH. para WhatsApp.

Paquete con el motor de respuestas (`agent`), la base de conocimiento
(`knowledge_base`) y los utilitarios para integrar la WhatsApp Cloud API
(`whatsapp`).
"""

from .agent import Respuesta, responder

__all__ = ["responder", "Respuesta"]
