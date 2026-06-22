"""
agent_core.py
-------------
Motor principal del agente autónomo Córdoba Rock.

Este módulo NO tiene ninguna dependencia de Streamlit.
Puede ser invocado desde:
  - run_agent.py (CLI / GitHub Actions)
  - Cualquier agente externo que importe este módulo

Cada función pública devuelve un dict con la estructura:
  {
    "success": bool,
    "id": int | None,         # ID del post/evento creado/actualizado
    "url": str | None,        # URL del contenido en WordPress
    "message": str,           # Mensaje legible
    "ai_content": { ... }     # Contenido generado por IA (opcional)
  }
"""

import time
import html
import re
import requests
import google.generativeai as genai

from agent_config import (
    WP_URL, AUTH, HEADERS_GET,
    GEMINI_API_KEY, GEMINI_MODEL,
    DEFAULT_AI_TONE, AI_TONE_INSTRUCTIONS,
    EVENT_CATEGORIES, EVENT_CAT_MAP_INV,
)

# Inicializar cliente IA
genai.configure(api_key=GEMINI_API_KEY)


# ==========================================
# HELPERS IA
# ==========================================

def _get_tone_instructions(tono: str, instrucciones_custom: str = "") -> str:
    """Devuelve las instrucciones de tono para el prompt de IA."""
    if tono == "custom" and instrucciones_custom:
        return instrucciones_custom
    return AI_TONE_INSTRUCTIONS.get(tono, AI_TONE_INSTRUCTIONS[DEFAULT_AI_TONE])


def _run_ai_query(prompt: str, max_retries: int = 2) -> str:
    """Ejecuta una consulta a Gemini con reintentos en caso de rate limit."""
    model = genai.GenerativeModel(GEMINI_MODEL)
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt).text
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                print(f"  ⚠️  Rate limit (429), esperando 10s... (intento {attempt + 1})")
                time.sleep(10)
            else:
                raise RuntimeError(f"Error IA en intento {attempt + 1}: {e}") from e
    return ""


def _generar_texto_noticia(tipo: str, titulo: str, apuntes: str, tono: str) -> str:
    objetivo_map = {
        "content": "Redacta una noticia musical completa basada en el título y los apuntes proporcionados.",
        "excerpt": "Crea un EXTRACTO (Excerpt) corto y atractivo para SEO (máx 2 frases).",
        "social": "Crea un COPY PARA INSTAGRAM viral anunciando esta noticia.",
    }
    formato_map = {
        "content": "HTML. Usa <p>, <strong>, <h2> si es necesario, y <ul> para listas.",
        "excerpt": "Texto plano o HTML básico.",
        "social": "TEXTO PLANO con Emojis y Hashtags.",
    }
    prompt = f"""
Actúa como periodista de 'Córdoba Rock'.
TITULAR: "{titulo}"
APUNTES/CONTENIDO PREVIO: "{apuntes}"

OBJETIVO: {objetivo_map[tipo]}
TONO: {tono}
FORMATO OBLIGATORIO: {formato_map[tipo]}
"""
    return _run_ai_query(prompt)


def _generar_texto_grupo(tipo: str, nombre: str, estilos: list, ciudad: str,
                          propuesta: str, tono: str, borrador: str = "") -> str:
    estilos_txt = ", ".join(estilos) if estilos else "Rock/Metal"
    objetivo_map = {
        "bio": "Escribe una BIOGRAFÍA COMPLETA y atractiva para la web del grupo.",
        "resumen": "Escribe una INTRODUCCIÓN CORTA o resumen (2-3 frases) impactante.",
        "social": "Crea un POST PARA INSTAGRAM/FACEBOOK presentando a la banda.",
    }
    formato_map = {
        "bio": "HTML. Usa párrafos <p> y negritas <strong> para destacar nombres o discos.",
        "resumen": "Texto plano o HTML básico.",
        "social": "Texto plano con Emojis y Hashtags.",
    }
    prompt = f"""
Eres un redactor musical experto de 'Córdoba Rock'.
DATOS DEL GRUPO:
- Nombre: {nombre}
- Ciudad: {ciudad}
- Estilo: {estilos_txt}
- Propuesta: {propuesta}
- Info extra/Borrador: "{borrador}"

OBJETIVO: {objetivo_map[tipo]}
TONO: {tono}
FORMATO OBLIGATORIO: {formato_map[tipo]}
"""
    return _run_ai_query(prompt)


def _generar_texto_evento(tipo: str, titulo: str, fecha: str, sala: str,
                           precio: str, tono: str, borrador: str = "") -> str:
    datos_extra = f"Fecha: {fecha}. Sala: {sala}. Precio: {precio}."
    objetivo_map = {
        "descripcion": (
            "Redacta la DESCRIPCIÓN DETALLADA del evento para la web. "
            "Incluye biografía breve del artista si lo conoces."
        ),
        "excerpt": "Escribe un EXTRACTO CORTO (1 o 2 frases) para listados y SEO.",
        "social": (
            "Crea un COPY PARA INSTAGRAM/FACEBOOK muy atractivo para vender entradas. "
            "¡Usa emojis!"
        ),
    }
    formato_map = {
        "descripcion": "HTML. Usa <p>, <strong> y listas si hace falta.",
        "excerpt": "Texto plano.",
        "social": "Texto plano con Hashtags.",
    }
    prompt = f"""
Eres el community manager de 'Córdoba Rock'.
EVENTO: {titulo}
DATOS CLAVE: {datos_extra}
BORRADOR/NOTAS: "{borrador}"

OBJETIVO: {objetivo_map[tipo]}
TONO: {tono}
FORMATO OBLIGATORIO: {formato_map[tipo]}
"""
    return _run_ai_query(prompt)


# ==========================================
# HELPERS WORDPRESS
# ==========================================

def _clean_url(url: str) -> str | None:
    if not url:
        return None
    url = str(url).strip()
    if not url or url.lower() == "nan":
        return None
    if not url.startswith("http://") and not url.startswith("https://"):
        return "https://" + url
    return url


def _upload_image_from_url(img_url: str) -> int | None:
    """Descarga una imagen de una URL y la sube a WordPress Media Library."""
    if not img_url:
        return None
    try:
        r = requests.get(img_url, timeout=15)
        if r.status_code != 200:
            print(f"  ⚠️  No se pudo descargar imagen: HTTP {r.status_code}")
            return None

        filename = img_url.split("/")[-1].split("?")[0]
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            filename += ".jpg"

        media_url = f"{WP_URL}/wp/v2/media"
        headers = {
            "Content-Type": "image/jpeg",
            "Content-Disposition": f"attachment; filename={filename}",
        }
        res = requests.post(media_url, data=r.content, headers=headers, auth=AUTH)
        if res.status_code == 201:
            media_id = res.json()["id"]
            print(f"  ✅ Imagen subida a WP: ID={media_id}")
            return media_id
        else:
            print(f"  ⚠️  Error subiendo imagen: HTTP {res.status_code}")
    except Exception as e:
        print(f"  ⚠️  Excepción subiendo imagen: {e}")
    return None


def _ensure_tag_exists(tag_name: str) -> int | None:
    """Busca una etiqueta en WP por nombre; la crea si no existe. Devuelve el ID."""
    if not tag_name:
        return None
    try:
        res = requests.get(
            f"{WP_URL}/wp/v2/tags",
            params={"search": tag_name},
            auth=AUTH,
            headers=HEADERS_GET,
        )
        if res.status_code == 200:
            for tag in res.json():
                if html.unescape(tag["name"]).lower() == tag_name.lower():
                    return tag["id"]

        # No existe → crear
        res_create = requests.post(
            f"{WP_URL}/wp/v2/tags",
            json={"name": tag_name},
            auth=AUTH,
        )
        if res_create.status_code == 201:
            return res_create.json()["id"]
    except Exception as e:
        print(f"  ⚠️  Error con etiqueta '{tag_name}': {e}")
    return None


def _get_or_create_venue(venue_name: str) -> int | None:
    """Busca una sala en TEC por nombre; la crea si no existe. Devuelve el ID."""
    if not venue_name:
        return None
    try:
        res = requests.get(
            f"{WP_URL}/tribe/events/v1/venues",
            params={"search": venue_name, "per_page": 5},
            auth=AUTH,
            headers=HEADERS_GET,
        )
        if res.status_code == 200:
            for v in res.json().get("venues", []):
                if html.unescape(v.get("venue", "")).lower() == venue_name.lower():
                    return v["id"]

        # No existe → crear
        res_c = requests.post(
            f"{WP_URL}/tribe/events/v1/venues",
            json={"venue": venue_name},
            auth=AUTH,
        )
        if res_c.status_code in [200, 201]:
            return res_c.json().get("id")
    except Exception as e:
        print(f"  ⚠️  Error con venue '{venue_name}': {e}")
    return None


def _get_tax_terms(taxonomy: str) -> dict:
    """Obtiene los términos de una taxonomía WordPress (nombre → ID)."""
    name_to_id = {}
    page = 1
    while True:
        try:
            res = requests.get(
                f"{WP_URL}/wp/v2/{taxonomy}",
                params={"per_page": 100, "page": page},
                auth=AUTH,
                headers=HEADERS_GET,
            )
            if res.status_code == 200:
                data = res.json()
                if not data:
                    break
                for term in data:
                    name_to_id[term["name"].lower()] = term["id"]
                page += 1
            else:
                break
        except Exception:
            break
    return name_to_id


def _force_taxonomies_update(event_id: int, cat_ids: list, tag_ids: list):
    """Asigna taxonomías nativamente en WP para evitar bugs de TEC."""
    payload = {}
    if cat_ids:
        payload["tribe_events_cat"] = [int(c) for c in cat_ids]
    if tag_ids:
        payload["tags"] = [int(t) for t in tag_ids]
    if payload:
        try:
            requests.post(f"{WP_URL}/wp/v2/tribe_events/{event_id}", json=payload, auth=AUTH)
        except Exception:
            pass


def _attach_media_to_event(event_id: int, image_id: int | None):
    """Adjunta imagen y activa el mapa en un evento de TEC."""
    if not image_id:
        return
    payload = {
        "featured_media": int(image_id),
        "meta": {"_EventShowMap": "1", "_EventShowMapLink": "1"},
    }
    try:
        requests.post(f"{WP_URL}/wp/v2/tribe_events/{event_id}", json=payload, auth=AUTH)
    except Exception:
        pass


def _get_post_url(post_id: int, post_type: str = "posts") -> str | None:
    """Obtiene la URL pública de un post de WordPress."""
    try:
        res = requests.get(f"{WP_URL}/wp/v2/{post_type}/{post_id}", auth=AUTH, headers=HEADERS_GET)
        if res.status_code == 200:
            return res.json().get("link")
    except Exception:
        pass
    return None


# ==========================================
# ACCIONES PRINCIPALES DEL AGENTE
# ==========================================

def publicar_noticia(payload: dict) -> dict:
    """
    Crea o actualiza una noticia en WordPress.

    Campos obligatorios en payload:
      - titulo (str)

    Campos opcionales:
      - apuntes (str): Info base para que la IA redacte el contenido
      - contenido_manual (str): HTML del contenido (si no se usa IA)
      - excerpt_manual (str): Extracto manual
      - categoria_ids (list[int]): IDs de categorías WP
      - tono_ia (str): periodistico | rockero | social | custom
      - instrucciones_custom (str): Solo si tono_ia = "custom"
      - estado (str): publish | draft | future (default: publish)
      - fecha_publicacion (str): ISO 8601, p.ej. "2025-01-15T21:00:00"
      - imagen_url (str): URL de imagen a subir como destacada
      - generar_excerpt (bool): Si True, usa IA para crear extracto
      - generar_social (bool): Si True, genera copy para redes
      - wp_post_id (int): Si se proporciona, actualiza en lugar de crear
    """
    titulo = payload.get("titulo", "").strip()
    if not titulo:
        return {"success": False, "message": "❌ 'titulo' es obligatorio"}

    tono_key = payload.get("tono_ia", DEFAULT_AI_TONE)
    instrucciones_custom = payload.get("instrucciones_custom", "")
    tono = _get_tone_instructions(tono_key, instrucciones_custom)
    apuntes = payload.get("apuntes", "")
    ai_content = {}

    # 1. Generar contenido con IA
    if payload.get("contenido_manual"):
        content_html = payload["contenido_manual"]
        print("  📝 Usando contenido manual proporcionado.")
    else:
        print("  🤖 Generando contenido con IA...")
        content_html = _generar_texto_noticia("content", titulo, apuntes, tono)
        ai_content["content"] = content_html
        print("  ✅ Contenido generado.")

    # 2. Extracto
    if payload.get("excerpt_manual"):
        excerpt = payload["excerpt_manual"]
    elif payload.get("generar_excerpt", True):
        print("  🤖 Generando extracto con IA...")
        excerpt = _generar_texto_noticia("excerpt", titulo, apuntes, tono)
        ai_content["excerpt"] = excerpt
        print("  ✅ Extracto generado.")
    else:
        excerpt = ""

    # 3. Copy social (opcional)
    if payload.get("generar_social", False):
        print("  🤖 Generando copy para redes...")
        social_copy = _generar_texto_noticia("social", titulo, apuntes, tono)
        ai_content["social_copy"] = social_copy
        print("  ✅ Copy social generado.")

    # 4. Subir imagen (si se proporciona URL)
    img_id = None
    if payload.get("imagen_url"):
        print(f"  📷 Subiendo imagen: {payload['imagen_url']}")
        img_id = _upload_image_from_url(payload["imagen_url"])

    # 5. Construir payload WordPress
    wp_payload = {
        "title": titulo,
        "content": content_html,
        "excerpt": excerpt,
        "status": payload.get("estado", "publish"),
        "categories": payload.get("categoria_ids", []),
    }
    if payload.get("fecha_publicacion"):
        wp_payload["date"] = payload["fecha_publicacion"]
    if img_id:
        wp_payload["featured_media"] = img_id

    # 6. Publicar en WordPress
    post_id = payload.get("wp_post_id")
    try:
        if post_id:
            print(f"  📤 Actualizando noticia ID={post_id}...")
            res = requests.post(f"{WP_URL}/wp/v2/posts/{post_id}", json=wp_payload, auth=AUTH)
            action = "actualizada"
        else:
            print("  📤 Creando nueva noticia...")
            res = requests.post(f"{WP_URL}/wp/v2/posts", json=wp_payload, auth=AUTH)
            action = "creada"

        if res.status_code in [200, 201]:
            data = res.json()
            post_id = data.get("id")
            url = data.get("link")
            print(f"  ✅ Noticia {action}: ID={post_id}, URL={url}")
            return {
                "success": True,
                "id": post_id,
                "url": url,
                "message": f"✅ Noticia {action} correctamente",
                "ai_content": ai_content,
            }
        else:
            return {
                "success": False,
                "message": f"❌ Error WordPress: HTTP {res.status_code} — {res.text[:300]}",
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Excepción: {e}"}


def publicar_evento(payload: dict) -> dict:
    """
    Crea o actualiza un evento en The Events Calendar.

    Campos obligatorios:
      - titulo (str)
      - fecha_inicio (str): "YYYY-MM-DD HH:MM:SS"

    Campos opcionales:
      - fecha_fin (str): "YYYY-MM-DD HH:MM:SS" (default: misma fecha 23:59)
      - sala_nombre (str): Nombre de la sala (se crea si no existe)
      - precio (str)
      - url_entradas (str)
      - descripcion_apuntes (str): Info para que la IA redacte
      - descripcion_manual (str): HTML del contenido (si no se usa IA)
      - categoria_nombres (list[str]): ["Córdoba", "Festival", "Nacional"]
      - etiquetas (list[str]): Lista de etiquetas en texto
      - tono_ia (str)
      - instrucciones_custom (str)
      - imagen_url (str)
      - generar_excerpt (bool)
      - generar_social (bool)
      - wp_event_id (int): Si se proporciona, actualiza en lugar de crear
    """
    titulo = payload.get("titulo", "").strip()
    fecha_inicio = payload.get("fecha_inicio", "").strip()
    if not titulo:
        return {"success": False, "message": "❌ 'titulo' es obligatorio"}
    if not fecha_inicio:
        return {"success": False, "message": "❌ 'fecha_inicio' es obligatorio (formato: YYYY-MM-DD HH:MM:SS)"}

    # Fecha fin por defecto
    fecha_fin = payload.get("fecha_fin")
    if not fecha_fin:
        fecha_fin = fecha_inicio.split(" ")[0] + " 23:59:00"

    tono_key = payload.get("tono_ia", DEFAULT_AI_TONE)
    instrucciones_custom = payload.get("instrucciones_custom", "")
    tono = _get_tone_instructions(tono_key, instrucciones_custom)

    sala_nombre = payload.get("sala_nombre", "")
    precio = payload.get("precio", "")
    borrador = payload.get("descripcion_apuntes", "")
    fecha_display = fecha_inicio.split(" ")[0]
    ai_content = {}

    # 1. Generar descripción con IA
    if payload.get("descripcion_manual"):
        desc_html = payload["descripcion_manual"]
        print("  📝 Usando descripción manual.")
    else:
        print("  🤖 Generando descripción del evento con IA...")
        desc_html = _generar_texto_evento("descripcion", titulo, fecha_display, sala_nombre, precio, tono, borrador)
        ai_content["descripcion"] = desc_html
        print("  ✅ Descripción generada.")

    # 2. Extracto
    excerpt = ""
    if payload.get("generar_excerpt", True):
        print("  🤖 Generando extracto...")
        excerpt = _generar_texto_evento("excerpt", titulo, fecha_display, sala_nombre, precio, tono)
        ai_content["excerpt"] = excerpt

    # 3. Copy social
    if payload.get("generar_social", False):
        print("  🤖 Generando copy para redes...")
        social_copy = _generar_texto_evento("social", titulo, fecha_display, sala_nombre, precio, tono, borrador)
        ai_content["social_copy"] = social_copy

    # 4. Sala (venue)
    venue_id = None
    if sala_nombre:
        print(f"  🏢 Buscando/creando sala: {sala_nombre}")
        venue_id = _get_or_create_venue(sala_nombre)

    # 5. Categorías
    final_cats = []
    for cat_name in payload.get("categoria_nombres", []):
        cat_id = EVENT_CAT_MAP_INV.get(cat_name.lower())
        if cat_id:
            final_cats.append(cat_id)

    # 6. Etiquetas
    final_tag_ids = []
    for tag_name in payload.get("etiquetas", []):
        tid = _ensure_tag_exists(tag_name)
        if tid:
            final_tag_ids.append(tid)

    # 7. Imagen
    img_id = None
    if payload.get("imagen_url"):
        print(f"  📷 Subiendo imagen: {payload['imagen_url']}")
        img_id = _upload_image_from_url(payload["imagen_url"])

    # 8. Payload TEC
    tec_payload = {
        "title": titulo,
        "description": desc_html,
        "excerpt": excerpt,
        "start_date": fecha_inicio,
        "end_date": fecha_fin,
        "all_day": payload.get("all_day", False),
        "cost": precio,
        "website": _clean_url(payload.get("url_entradas", "")) or "",
        "status": "publish",
        "show_map": "true",
        "show_map_link": "true",
    }
    if venue_id:
        tec_payload["venue"] = venue_id

    # 9. Publicar en TEC
    event_id = payload.get("wp_event_id")
    try:
        if event_id:
            print(f"  📤 Actualizando evento ID={event_id}...")
            res = requests.post(f"{WP_URL}/tribe/events/v1/events/{event_id}", json=tec_payload, auth=AUTH)
            action = "actualizado"
            expected_status = 200
        else:
            print("  📤 Creando nuevo evento...")
            res = requests.post(f"{WP_URL}/tribe/events/v1/events", json=tec_payload, auth=AUTH)
            action = "creado"
            expected_status = 201

        if res.status_code == expected_status:
            data = res.json()
            event_id = data.get("id")
            url = data.get("url") or data.get("link")

            # Post-proceso: imagen y taxonomías
            _attach_media_to_event(event_id, img_id)
            _force_taxonomies_update(event_id, final_cats, final_tag_ids)

            print(f"  ✅ Evento {action}: ID={event_id}")
            return {
                "success": True,
                "id": event_id,
                "url": url,
                "message": f"✅ Evento {action} correctamente",
                "ai_content": ai_content,
            }
        else:
            return {
                "success": False,
                "message": f"❌ Error TEC: HTTP {res.status_code} — {res.text[:300]}",
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Excepción: {e}"}


def publicar_grupo(payload: dict) -> dict:
    """
    Crea o actualiza un grupo (Custom Post Type) en WordPress.

    Campos obligatorios:
      - nombre (str)
      - ciudad (str)

    Campos opcionales:
      - provincia (str): default "Córdoba"
      - estilos (list[str]): Nombres de estilos, p.ej. ["Rock", "Metal"]
      - tipo_propuesta (str): "original" | "tributo"
      - estado_grupo (str): "activo" | "inactivo"
      - bio_apuntes (str): Info para que la IA genere la biografía
      - bio_manual (str): HTML de biografía (si no se usa IA)
      - url_facebook, url_instagram, url_spotify, url_youtube, url_web (str)
      - telefono (str)
      - email (str)
      - mostrar_telefono (bool)
      - mostrar_email (bool)
      - imagen_url (str)
      - tono_ia (str)
      - instrucciones_custom (str)
      - wp_group_id (int): Si se proporciona, actualiza en lugar de crear
    """
    nombre = payload.get("nombre", "").strip()
    ciudad = payload.get("ciudad", "").strip()
    if not nombre:
        return {"success": False, "message": "❌ 'nombre' es obligatorio"}
    if not ciudad:
        return {"success": False, "message": "❌ 'ciudad' es obligatorio"}

    tono_key = payload.get("tono_ia", DEFAULT_AI_TONE)
    instrucciones_custom = payload.get("instrucciones_custom", "")
    tono = _get_tone_instructions(tono_key, instrucciones_custom)
    estilos_nombres = payload.get("estilos", [])
    propuesta = payload.get("tipo_propuesta", "original")
    ai_content = {}

    # 1. Generar bio con IA
    if payload.get("bio_manual"):
        bio_html = payload["bio_manual"]
        print("  📝 Usando biografía manual.")
    else:
        print("  🤖 Generando biografía con IA...")
        bio_html = _generar_texto_grupo(
            "bio", nombre, estilos_nombres, ciudad, propuesta, tono,
            payload.get("bio_apuntes", "")
        )
        ai_content["bio"] = bio_html
        print("  ✅ Biografía generada.")

    # 2. Resolver IDs de estilos musicales desde la taxonomía WP
    estilo_ids = []
    if estilos_nombres:
        print("  🎸 Resolviendo IDs de estilos musicales...")
        style_map = _get_tax_terms("estilo")
        for estilo_name in estilos_nombres:
            sid = style_map.get(estilo_name.lower())
            if sid:
                estilo_ids.append(sid)

    # 3. Etiqueta del grupo (el nombre del grupo como tag)
    tag_id = _ensure_tag_exists(nombre)
    final_tags = [tag_id] if tag_id else []

    # 4. Imagen
    img_id = None
    if payload.get("imagen_url"):
        print(f"  📷 Subiendo imagen: {payload['imagen_url']}")
        img_id = _upload_image_from_url(payload["imagen_url"])

    # 5. Payload WordPress
    wp_payload = {
        "title": nombre,
        "status": "publish",
        "estilo": estilo_ids,
        "tags": final_tags,
        "acf": {
            "descripcion": bio_html,
            "ciudad": ciudad,
            "provincia": payload.get("provincia", "Córdoba"),
            "estado_grupo": payload.get("estado_grupo", "activo"),
            "tipo_propuesta": propuesta if propuesta in ["original"] else "versiones",
            "formacion_actual": payload.get("formacion_actual", ""),
            "antiguos_miembros": payload.get("antiguos_miembros", ""),
            "url_facebook": _clean_url(payload.get("url_facebook", "")),
            "url_instagram": _clean_url(payload.get("url_instagram", "")),
            "url_spotify": _clean_url(payload.get("url_spotify", "")),
            "url_youtube": _clean_url(payload.get("url_youtube", "")),
            "url_web": _clean_url(payload.get("url_web", "")),
            "telefono": payload.get("telefono") or None,
            "email": payload.get("email") or None,
            "mostrar_telefono": payload.get("mostrar_telefono", False),
            "mostrar_email": payload.get("mostrar_email", False),
        },
    }
    if img_id:
        wp_payload["featured_media"] = int(img_id)

    # 6. Publicar
    group_id = payload.get("wp_group_id")
    headers = {"Content-Type": "application/json"}
    try:
        if group_id:
            print(f"  📤 Actualizando grupo ID={group_id}...")
            res = requests.post(f"{WP_URL}/wp/v2/grupo/{group_id}", json=wp_payload, auth=AUTH, headers=headers)
            action = "actualizado"
            expected_status = 200
        else:
            print("  📤 Creando nuevo grupo...")
            res = requests.post(f"{WP_URL}/wp/v2/grupo", json=wp_payload, auth=AUTH, headers=headers)
            action = "creado"
            expected_status = 201

        if res.status_code == expected_status:
            data = res.json()
            group_id = data.get("id")
            url = data.get("link")
            print(f"  ✅ Grupo {action}: ID={group_id}")
            return {
                "success": True,
                "id": group_id,
                "url": url,
                "message": f"✅ Grupo {action} correctamente",
                "ai_content": ai_content,
            }
        else:
            return {
                "success": False,
                "message": f"❌ Error WordPress: HTTP {res.status_code} — {res.text[:300]}",
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Excepción: {e}"}


def publicar_sala(payload: dict) -> dict:
    """
    Crea o actualiza una sala (venue) en The Events Calendar.

    Campos obligatorios:
      - nombre (str)

    Campos opcionales:
      - descripcion (str)
      - direccion (str)
      - ciudad (str)
      - provincia (str): default "Córdoba"
      - cp (str)
      - telefono (str)
      - web (str)
      - imagen_url (str)
      - wp_venue_id (int): Si se proporciona, actualiza en lugar de crear
    """
    nombre = payload.get("nombre", "").strip()
    if not nombre:
        return {"success": False, "message": "❌ 'nombre' es obligatorio"}

    # Imagen
    img_id = None
    if payload.get("imagen_url"):
        print(f"  📷 Subiendo imagen: {payload['imagen_url']}")
        img_id = _upload_image_from_url(payload["imagen_url"])

    tec_payload = {
        "venue": nombre,
        "description": payload.get("descripcion", ""),
        "address": payload.get("direccion", ""),
        "city": payload.get("ciudad", ""),
        "province": payload.get("provincia", "Córdoba"),
        "zip": payload.get("cp", ""),
        "phone": payload.get("telefono", ""),
        "website": _clean_url(payload.get("web", "")) or "",
        "show_map": "true",
        "show_map_link": "true",
        "status": "publish",
    }
    if img_id:
        tec_payload["image"] = img_id

    venue_id = payload.get("wp_venue_id")
    try:
        if venue_id:
            print(f"  📤 Actualizando sala ID={venue_id}...")
            res = requests.post(f"{WP_URL}/tribe/events/v1/venues/{venue_id}", json=tec_payload, auth=AUTH)
            action = "actualizada"
            expected_status = 200
        else:
            print("  📤 Creando nueva sala...")
            res = requests.post(f"{WP_URL}/tribe/events/v1/venues", json=tec_payload, auth=AUTH)
            action = "creada"
            expected_status = 201

        if res.status_code == expected_status:
            data = res.json()
            venue_id = data.get("id")
            url = data.get("url") or data.get("link")
            print(f"  ✅ Sala {action}: ID={venue_id}")
            return {
                "success": True,
                "id": venue_id,
                "url": url,
                "message": f"✅ Sala {action} correctamente",
            }
        else:
            return {
                "success": False,
                "message": f"❌ Error TEC: HTTP {res.status_code} — {res.text[:300]}",
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Excepción: {e}"}


def health_check() -> dict:
    """Verifica la conectividad con WordPress y Gemini AI."""
    results = {}

    # Test WordPress
    try:
        res = requests.get(f"{WP_URL}/wp/v2/posts?per_page=1", auth=AUTH, headers=HEADERS_GET, timeout=10)
        results["wordpress"] = "✅ OK" if res.status_code == 200 else f"❌ HTTP {res.status_code}"
    except Exception as e:
        results["wordpress"] = f"❌ Error: {e}"

    # Test TEC (The Events Calendar)
    try:
        res = requests.get(f"{WP_URL}/tribe/events/v1/events?per_page=1", auth=AUTH, headers=HEADERS_GET, timeout=10)
        results["tribe_events_calendar"] = "✅ OK" if res.status_code == 200 else f"❌ HTTP {res.status_code}"
    except Exception as e:
        results["tribe_events_calendar"] = f"❌ Error: {e}"

    # Test Gemini AI
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        model.generate_content("Di 'OK' en una sola palabra.")
        results["gemini_ai"] = "✅ OK"
    except Exception as e:
        results["gemini_ai"] = f"❌ Error: {e}"

    all_ok = all("✅" in v for v in results.values())
    return {
        "success": all_ok,
        "checks": results,
        "message": "✅ Todos los servicios operativos" if all_ok else "⚠️  Algunos servicios tienen problemas",
    }
