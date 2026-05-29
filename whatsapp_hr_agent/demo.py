"""Demo de consola del agente de RR.HH. — SIN COSTO, sin WhatsApp, sin internet.

Sirve para demostrar que el agente funciona antes de invertir en un plan pago.
Tiene dos modos:

  1) Interactivo (por defecto): chateas con el agente desde la terminal.
         python demo.py

  2) Por lotes: le pasas preguntas y muestra las respuestas (útil para demos
     reproducibles o capturas de pantalla).
         python demo.py "como pido vacaciones" "cuando pagan la nomina"

Este demo simula exactamente el flujo que ocurriría en WhatsApp: usuario escribe
-> el agente responde. La única diferencia es el canal (terminal vs. WhatsApp).
"""

from __future__ import annotations

import sys

from hr_agent import responder

PREGUNTAS_EJEMPLO = [
    "Hola",
    "¿Cómo pido mis vacaciones?",
    "cuantos dias de vacaciones me quedan",
    "necesito un certificado laboral",
    "cuando pagan la nomina?",
    "como reporto una incapacidad",
    "quiero hablar con una persona de recursos humanos",
    "cual es la capital de francia",  # fuera de tema -> fallback
]


def _imprimir_intercambio(pregunta: str) -> None:
    r = responder(pregunta)
    etiqueta = "FALLBACK" if r.es_fallback else (r.faq_id or "saludo")
    print(f"\n👤 Usuario: {pregunta}")
    print(f"🤖 Agente: {r.texto}")
    print(f"   (match: {etiqueta} | confianza: {r.confianza})")


def modo_lotes(preguntas) -> None:
    for p in preguntas:
        _imprimir_intercambio(p)


def modo_demostracion() -> None:
    print("=" * 60)
    print(" DEMO automática del agente de RR.HH. (preguntas de ejemplo)")
    print("=" * 60)
    modo_lotes(PREGUNTAS_EJEMPLO)


def modo_interactivo() -> None:
    print("=" * 60)
    print(" Asistente virtual de Recursos Humanos (modo prueba)")
    print(" Escribe tu pregunta. Para salir: 'salir', 'exit' o Ctrl+C.")
    print("=" * 60)
    while True:
        try:
            pregunta = input("\n👤 Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego! 👋")
            return
        if pregunta.lower() in {"salir", "exit", "quit"}:
            print("¡Hasta luego! 👋")
            return
        if not pregunta:
            continue
        r = responder(pregunta)
        print(f"🤖 Agente: {r.texto}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        # Sin argumentos: si hay terminal interactiva, chatea; si no, demo.
        if sys.stdin.isatty():
            modo_interactivo()
        else:
            modo_demostracion()
    elif args == ["--demo"]:
        modo_demostracion()
    else:
        modo_lotes(args)


if __name__ == "__main__":
    main()
