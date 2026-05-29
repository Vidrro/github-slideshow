"""Motor del agente de RR.HH.

Implementa la lógica para, dado un mensaje de texto del usuario, encontrar la
pregunta frecuente más parecida y devolver una respuesta concreta.

El emparejamiento es 100% local (no requiere internet ni servicios de pago), lo
que lo hace ideal para el prototipo. Combina dos señales:

1. Coincidencia de palabras clave (las definidas en cada FAQ).
2. Similitud difusa (difflib) entre el mensaje y la pregunta/keywords, que
   tolera errores de tipeo y frases incompletas.

Cuando llegue el momento de escalar, este motor se puede reemplazar o complementar
con un modelo de lenguaje (p. ej. la API de Claude) manteniendo la misma interfaz
`responder(texto) -> Respuesta`. Ver README para la ruta de escalamiento.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional

from .knowledge_base import FAQS, FALLBACK, SALUDO

# Umbral mínimo de confianza para dar una respuesta de la base de conocimiento.
# Por debajo de esto, el agente prefiere derivar a una persona (fallback).
UMBRAL_CONFIANZA = 0.45

# Palabras vacías que no aportan a la coincidencia y solo añaden ruido.
STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a",
    "al", "y", "o", "que", "como", "cómo", "para", "por", "con", "en", "mi",
    "mis", "me", "se", "su", "sus", "es", "son", "tengo", "puedo", "quiero",
    "necesito", "hacer", "donde", "dónde", "cuando", "cuándo", "cual", "cuál",
    "cuanto", "cuánto", "cuanta", "cuánta", "cuantos", "cuántos", "le", "lo",
    "este", "esta", "porfa", "favor", "hola", "buenas", "dias", "días",
}

SALUDOS = {"hola", "buenas", "buenos", "saludos", "hey", "ola", "holi"}


@dataclass
class Respuesta:
    """Resultado de una consulta al agente."""

    texto: str
    faq_id: Optional[str]  # id de la FAQ encontrada, o None si fue fallback/saludo
    confianza: float  # 0.0 a 1.0
    es_fallback: bool


def normalizar(texto: str) -> str:
    """Pasa a minúsculas, quita acentos y signos, y colapsa espacios."""
    texto = texto.lower().strip()
    # Quitar acentos/diacríticos.
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Reemplazar todo lo que no sea alfanumérico por espacio.
    texto = re.sub(r"[^a-z0-9ñ\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _tokens(texto: str) -> List[str]:
    return [t for t in normalizar(texto).split() if t and t not in STOPWORDS]


def _es_saludo(texto: str) -> bool:
    tokens = normalizar(texto).split()
    return bool(tokens) and all(t in SALUDOS for t in tokens)


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# Una palabra de la consulta cuenta como coincidencia de una palabra clave si su
# similitud supera este valor. Tolera errores de tipeo (p. ej. "vacasiones").
UMBRAL_TOKEN = 0.82


def _tokens_coinciden(a: str, b: str) -> bool:
    """True si dos palabras son iguales o muy parecidas (tolera typos)."""
    return a == b or _similitud(a, b) >= UMBRAL_TOKEN


def _puntuar_faq(consulta: str, faq: dict) -> float:
    """Devuelve un puntaje de 0.0 a 1.0 de qué tanto la consulta calza con la FAQ."""
    consulta_norm = normalizar(consulta)
    tokens_consulta = set(_tokens(consulta))

    # Señal 1: coincidencia de palabras clave (incluida la pregunta canónica).
    candidatos = list(faq["palabras"]) + [faq["pregunta"]]
    mejor_kw = 0.0
    for frase in candidatos:
        frase_norm = normalizar(frase)
        # Coincidencia exacta de la frase clave dentro de la consulta -> muy fuerte.
        if frase_norm and frase_norm in consulta_norm:
            mejor_kw = max(mejor_kw, 0.95)
        # Solapamiento de tokens (Jaccard sobre palabras significativas), pero
        # tolerando typos: dos tokens "coinciden" si son muy parecidos.
        tokens_frase = set(_tokens(frase))
        if tokens_frase:
            coincidencias = sum(
                1
                for tf in tokens_frase
                if any(_tokens_coinciden(tc, tf) for tc in tokens_consulta)
            )
            union = len(tokens_consulta | tokens_frase)
            jaccard = coincidencias / union if union else 0.0
            # Cobertura: qué proporción de la frase clave aparece en la consulta.
            # Es más tolerante a palabras de relleno (p. ej. "pido", "necesito")
            # que el Jaccard, pero la atenuamos para que no domine la decisión
            # entre FAQs que comparten una palabra (p. ej. "vacaciones").
            cobertura = 0.7 * (coincidencias / len(tokens_frase))
            mejor_kw = max(mejor_kw, jaccard, cobertura)

    # Señal 2: similitud difusa contra la pregunta canónica (tolera typos).
    sim = _similitud(consulta_norm, normalizar(faq["pregunta"]))

    # Combinación ponderada: damos más peso a las palabras clave.
    return 0.7 * mejor_kw + 0.3 * sim


def responder(texto: str) -> Respuesta:
    """Punto de entrada principal: convierte un mensaje en una Respuesta."""
    if not texto or not texto.strip():
        return Respuesta(texto=FALLBACK, faq_id=None, confianza=0.0, es_fallback=True)

    if _es_saludo(texto):
        return Respuesta(texto=SALUDO, faq_id=None, confianza=1.0, es_fallback=False)

    mejor_faq = None
    mejor_puntaje = 0.0
    for faq in FAQS:
        puntaje = _puntuar_faq(texto, faq)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_faq = faq

    if mejor_faq is not None and mejor_puntaje >= UMBRAL_CONFIANZA:
        return Respuesta(
            texto=mejor_faq["respuesta"],
            faq_id=mejor_faq["id"],
            confianza=round(mejor_puntaje, 3),
            es_fallback=False,
        )

    return Respuesta(
        texto=FALLBACK,
        faq_id=None,
        confianza=round(mejor_puntaje, 3),
        es_fallback=True,
    )
