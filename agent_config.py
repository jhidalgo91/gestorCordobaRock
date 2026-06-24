"""
agent_config.py
---------------
Configuración centralizada del agente.
Lee TODAS las credenciales y parámetros desde variables de entorno.
NUNCA escribas credenciales directamente en este fichero.
"""

import os

# ==========================================
# WORDPRESS
# ==========================================
WP_URL = os.environ.get("WP_URL", "https://cordobarock.es/wp-json")
WP_USER = os.environ.get("WP_USER", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

if not WP_USER or not WP_APP_PASSWORD:
    raise EnvironmentError(
        "❌ Faltan variables de entorno: WP_USER y WP_APP_PASSWORD son obligatorias.\n"
        "Añádelas como GitHub Secrets o en tu fichero .env local."
    )

AUTH = (WP_USER, WP_APP_PASSWORD)

HEADERS_GET = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ==========================================
# IA (Gemini, OpenAI, Anthropic)
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.5-flash")
API_DELAY_SECONDS = int(os.environ.get("API_DELAY_SECONDS", "120"))

if not (GEMINI_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY):
    raise EnvironmentError(
        "❌ Falta variable de entorno: Es obligatoria al menos una API_KEY (GEMINI_API_KEY, OPENAI_API_KEY o ANTHROPIC_API_KEY).\n"
        "Añádela como GitHub Secret o en tu fichero .env local."
    )

# ==========================================
# SEGURIDAD DEL AGENTE (opcional)
# ==========================================
AGENT_SECRET_TOKEN = os.environ.get("AGENT_SECRET_TOKEN", "")

# ==========================================
# CONFIGURACIÓN DE TONO IA
# ==========================================
DEFAULT_AI_TONE = os.environ.get("DEFAULT_AI_TONE", "periodistico")

AI_TONE_INSTRUCTIONS = {
    "periodistico": (
        "Usa un tono periodístico, objetivo, informativo y serio. "
        "Evita adjetivos exagerados."
    ),
    "rockero": (
        "Usa un tono apasionado, enérgico y 'rockero'. "
        "Usa palabras como 'potente', 'descarga', 'brutal'."
    ),
    "social": (
        "Usa un tono muy cercano, corto y directo. "
        "Incluye emojis musicales."
    ),
}

# ==========================================
# CATEGORÍAS DE EVENTOS (The Events Calendar)
# ==========================================
EVENT_CATEGORIES = {
    8: "Córdoba",
    19: "Festival",
    16: "Nacional",
}
EVENT_CAT_MAP_INV = {v.lower(): k for k, v in EVENT_CATEGORIES.items()}

# ==========================================
# MODO PRUEBAS Y CONTROL DE PUBLICACIÓN
# ==========================================

# --- Límite de items a procesar ---
# Número de noticias/eventos/grupos a procesar en cada ejecución.
#   N  > 0 → procesa exactamente N items
#  -1      → procesa TODOS los items disponibles
# Se puede sobreescribir desde el payload de cada llamada.
PUBLISH_LIMIT = int(os.environ.get("PUBLISH_LIMIT", "-1"))

# --- Estado de publicación por defecto ---
# "draft"   → Los posts quedan como BORRADOR. El usuario los revisa y publica manualmente.
# "publish" → Los posts se publican directamente en WordPress.
DEFAULT_WP_STATUS = os.environ.get("DEFAULT_WP_STATUS", "draft")

# --- Auto-publicar los N primeros, el resto como borrador ---
# Si AUTO_PUBLISH_FIRST > 0, los primeros N items del lote se publican automáticamente
# y el resto queda en borrador para revisión.
#   0 → Todos los items usan DEFAULT_WP_STATUS
#   N → Los primeros N se publican, el resto van a borrador
AUTO_PUBLISH_FIRST = int(os.environ.get("AUTO_PUBLISH_FIRST", "0"))
