# Agente de WhatsApp para Recursos Humanos (prototipo)

Asistente virtual que responde **automáticamente** las preguntas recurrentes del
personal de la empresa sobre temas de RR.HH. (vacaciones, nómina, certificados,
incapacidades, permisos, etc.).

Está pensado en **dos etapas**:

1. **Prototipo SIN costo** (lo que hay aquí): el agente funciona y se demuestra
   100% en local, sin WhatsApp, sin servidores y sin servicios de pago.
2. **Escalamiento a producción**: se conecta a la **WhatsApp Cloud API** oficial
   de Meta a través del webhook ya incluido (`app.py`).

---

## 1. Probarlo ahora (gratis, sin instalar nada)

Solo necesitas Python 3.9+ (no requiere dependencias externas para el demo).

```bash
cd whatsapp_hr_agent

# Modo interactivo: chatea con el agente desde la terminal
python demo.py

# Demo automática con preguntas de ejemplo (ideal para mostrar/capturar)
python demo.py --demo

# Preguntas sueltas por línea de comandos
python demo.py "como pido vacaciones" "cuando pagan la nomina"
```

Ejecutar las pruebas:

```bash
python -m unittest discover -s tests
```

---

## 2. Estructura

```
whatsapp_hr_agent/
├── demo.py                  # Demo de consola (SIN costo, simula el flujo de chat)
├── app.py                   # Webhook Flask para la WhatsApp Cloud API (producción)
├── requirements.txt         # Dependencias (solo para app.py)
├── .env.example             # Variables de entorno para producción
├── hr_agent/
│   ├── agent.py             # Motor: convierte un mensaje en una respuesta
│   ├── knowledge_base.py    # Preguntas frecuentes y respuestas (editable por RR.HH.)
│   └── whatsapp.py          # Helpers de la WhatsApp Cloud API (envío/webhook)
└── tests/
    └── test_agent.py        # Pruebas del motor y de la integración
```

### ¿Cómo responde el agente?

El motor (`hr_agent/agent.py`) compara el mensaje del usuario contra la base de
conocimiento usando coincidencia de palabras clave + similitud difusa (tolera
errores de tipeo y frases informales). Si la confianza supera un umbral,
responde con la información concreta; si no, deriva amablemente a una persona de
RR.HH. (mensaje de *fallback*).

**Para editar las respuestas no se necesita programar**: basta con modificar la
lista `FAQS` en `hr_agent/knowledge_base.py` (agregar/editar/quitar preguntas).

---

## 3. ¿Tiene costo? Resumen rápido

| Componente | Costo |
|---|---|
| Este prototipo / demo local | **Gratis** |
| Crear la app y el número en Meta (WhatsApp Cloud API) | **Gratis** |
| Hosting del API (lo aloja Meta) | **Gratis** |
| Responder a mensajes que **inicia el usuario** (ventana de 24 h) | **Gratis** |
| Plantillas que **inicia la empresa** (marketing/utilidad/auth) | **Costo por mensaje** según país y categoría |
| Servidor donde corre `app.py` | Bajo (hay capas gratuitas) |
| IA generativa opcional (ver abajo) | Costo por uso del modelo |

Como este agente **responde solicitudes que el usuario envía primero**, la
mensajería es prácticamente gratis. El costo real al escalar es el servidor (muy
bajo) y, si decides usar IA generativa, el costo del modelo.

---

## 4. Escalar a producción (WhatsApp Cloud API)

1. Crea una app en <https://developers.facebook.com> y agrega el producto
   **WhatsApp**. Obtendrás un *phone number id* y un *access token*.
2. Copia `.env.example` a `.env` y complétalo.
3. Instala dependencias y levanta el webhook:
   ```bash
   pip install -r requirements.txt
   python app.py
   ```
4. Expón el puerto con un túnel (p. ej. `ngrok http 5000`) o despliégalo en un
   servidor con HTTPS.
5. En el panel de Meta, registra la URL `https://TU-DOMINIO/webhook` y el
   `WHATSAPP_VERIFY_TOKEN` que definiste. Suscríbete al evento `messages`.
6. ¡Listo! Los mensajes entrantes se responderán automáticamente con el mismo
   motor que ya probaste en el demo.

### Ruta opcional: respuestas con IA generativa

El motor actual es determinista (rápido, gratis y predecible). Si en el futuro
quieres respuestas más conversacionales, puedes reemplazar/complementar la
función `responder()` con un modelo de lenguaje (por ejemplo la API de Claude),
manteniendo la misma interfaz. Una arquitectura recomendada es **RAG**: el
modelo redacta la respuesta usando como contexto los documentos oficiales de
RR.HH., lo que reduce errores y mantiene las respuestas alineadas a las
políticas de la empresa.

---

## 5. Notas

- Las respuestas de ejemplo (correos, extensiones, plazos) son **ficticias**;
  reemplázalas por la información real de tu empresa en `knowledge_base.py`.
- Para producción conviene mover la base de conocimiento a una base de datos o a
  un archivo editable por RR.HH., y agregar registro/analítica de las preguntas
  más frecuentes.
