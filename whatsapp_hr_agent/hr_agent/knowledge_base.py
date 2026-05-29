"""Base de conocimiento de RR.HH.

Cada entrada (FAQ) representa una pregunta recurrente del personal de la empresa.
La estructura es deliberadamente simple (una lista de diccionarios) para que el
equipo de Recursos Humanos pueda mantenerla sin saber programar: basta con
agregar, editar o quitar diccionarios de esta lista.

Campos:
    id        Identificador único y estable de la pregunta.
    pregunta  Texto canónico de la pregunta frecuente.
    palabras  Palabras/frases clave que disparan esta respuesta (sinónimos,
              variaciones coloquiales, errores comunes, etc.).
    respuesta Respuesta concreta que recibirá el usuario por WhatsApp.

Para producción se recomienda mover esto a una base de datos o a un archivo
JSON/YAML editable por el área de RR.HH., pero para el prototipo vive en código.
"""

FAQS = [
    {
        "id": "vacaciones_solicitud",
        "pregunta": "¿Cómo solicito mis vacaciones?",
        "palabras": [
            "vacaciones",
            "solicitar vacaciones",
            "pedir vacaciones",
            "días libres",
            "tomar vacaciones",
        ],
        "respuesta": (
            "Para solicitar vacaciones ingresa al portal del empleado, ve a "
            "*Solicitudes > Vacaciones* y completa las fechas. Tu jefe directo "
            "debe aprobarlas. Recuerda solicitarlas con al menos 15 días de "
            "anticipación."
        ),
    },
    {
        "id": "vacaciones_saldo",
        "pregunta": "¿Cuántos días de vacaciones tengo disponibles?",
        "palabras": [
            "cuántos días",
            "saldo de vacaciones",
            "días disponibles",
            "días acumulados",
            "cuántas vacaciones tengo",
        ],
        "respuesta": (
            "Puedes consultar tu saldo de vacaciones en el portal del empleado, "
            "sección *Mi perfil > Vacaciones*. Si ves alguna inconsistencia, "
            "escríbele a nomina@empresa.com."
        ),
    },
    {
        "id": "certificado_laboral",
        "pregunta": "¿Cómo obtengo un certificado laboral?",
        "palabras": [
            "certificado laboral",
            "certificación laboral",
            "carta laboral",
            "constancia de trabajo",
            "certificado de ingresos",
        ],
        "respuesta": (
            "Solicita tu certificado laboral en el portal del empleado, opción "
            "*Documentos > Certificado laboral*. Se genera automáticamente en "
            "PDF en un máximo de 24 horas hábiles."
        ),
    },
    {
        "id": "incapacidad",
        "pregunta": "¿Cómo reporto una incapacidad médica?",
        "palabras": [
            "incapacidad",
            "incapacidad médica",
            "reportar incapacidad",
            "estoy enfermo",
            "licencia médica",
            "certificado médico",
        ],
        "respuesta": (
            "Para reportar una incapacidad, envía el certificado médico (PDF o "
            "foto legible) dentro de las primeras 48 horas a "
            "incapacidades@empresa.com e informa a tu jefe directo. RR.HH. "
            "confirmará la recepción."
        ),
    },
    {
        "id": "nomina_fecha_pago",
        "pregunta": "¿Cuándo se paga la nómina?",
        "palabras": [
            "cuándo pagan",
            "fecha de pago",
            "día de pago",
            "pago de nómina",
            "cuándo cae el sueldo",
            "salario",
        ],
        "respuesta": (
            "La nómina se paga el día 30 de cada mes (o el día hábil anterior si "
            "cae en fin de semana o festivo). El desprendible queda disponible "
            "en el portal del empleado."
        ),
    },
    {
        "id": "desprendible_pago",
        "pregunta": "¿Dónde descargo mi desprendible de pago?",
        "palabras": [
            "desprendible",
            "colilla de pago",
            "comprobante de pago",
            "recibo de nómina",
            "volante de pago",
        ],
        "respuesta": (
            "Descarga tu desprendible de pago en el portal del empleado, sección "
            "*Nómina > Desprendibles*. Están disponibles los últimos 24 meses."
        ),
    },
    {
        "id": "horario_laboral",
        "pregunta": "¿Cuál es el horario laboral?",
        "palabras": [
            "horario",
            "horario laboral",
            "hora de entrada",
            "hora de salida",
            "jornada",
        ],
        "respuesta": (
            "El horario general es de lunes a viernes de 8:00 a.m. a 5:00 p.m., "
            "con una hora de almuerzo. Algunas áreas tienen horario flexible; "
            "consúltalo con tu jefe directo."
        ),
    },
    {
        "id": "permiso_personal",
        "pregunta": "¿Cómo pido un permiso personal?",
        "palabras": [
            "permiso",
            "permiso personal",
            "pedir permiso",
            "salir temprano",
            "ausentarme",
        ],
        "respuesta": (
            "Los permisos personales se solicitan en el portal del empleado, "
            "*Solicitudes > Permisos*, indicando el motivo y las horas. Requieren "
            "aprobación de tu jefe directo."
        ),
    },
    {
        "id": "afiliacion_eps",
        "pregunta": "¿Cómo cambio mi EPS o consulto mi afiliación?",
        "palabras": [
            "eps",
            "cambiar eps",
            "afiliación",
            "seguridad social",
            "salud",
            "pensión",
        ],
        "respuesta": (
            "Para consultar o cambiar tu EPS, escribe a seguridadsocial@empresa.com "
            "con tu solicitud. Los cambios de EPS solo se pueden hacer si llevas "
            "más de 12 meses en la actual."
        ),
    },
    {
        "id": "contacto_rrhh",
        "pregunta": "¿Cómo contacto al área de Recursos Humanos?",
        "palabras": [
            "contacto",
            "hablar con recursos humanos",
            "contactar rrhh",
            "teléfono de rrhh",
            "hablar con una persona",
            "asesor",
        ],
        "respuesta": (
            "Puedes contactar a Recursos Humanos en el correo rrhh@empresa.com o "
            "en la extensión 100, de lunes a viernes de 8:00 a.m. a 5:00 p.m."
        ),
    },
]

# Mensaje cuando el agente no encuentra una respuesta con confianza suficiente.
FALLBACK = (
    "Por ahora no tengo una respuesta exacta a tu pregunta. 🤔\n"
    "Puedes reformularla o escribir directamente a Recursos Humanos: "
    "rrhh@empresa.com (ext. 100)."
)

# Mensaje de bienvenida (por ejemplo, ante un \"hola\").
SALUDO = (
    "¡Hola! 👋 Soy el asistente virtual de Recursos Humanos. "
    "Puedo ayudarte con preguntas sobre vacaciones, nómina, certificados, "
    "incapacidades, permisos y más.\n\n¿En qué puedo ayudarte?"
)
