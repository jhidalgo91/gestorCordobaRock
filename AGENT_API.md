# 🎸 Córdoba Rock Agent — Contrato de API

> Referencia completa de todas las acciones, campos de entrada y salidas del agente.
> Para la guía de puesta en marcha, consulta [IMPLEMENTACION.md](./IMPLEMENTACION.md).

---

## Índice

1. [Arquitectura](#1-arquitectura)
2. [GitHub Secrets requeridos](#2-github-secrets-requeridos)
3. [Cómo invocar el agente](#3-cómo-invocar-el-agente)
4. [Parámetros de control de publicación](#4-parámetros-de-control-de-publicación)
5. [Acciones disponibles](#5-acciones-disponibles)
   - [health](#health)
   - [noticia](#noticia)
   - [lote_noticias](#lote_noticias) ⭐
   - [evento](#evento)
   - [grupo](#grupo)
   - [sala](#sala)
6. [Outputs del agente](#6-outputs-del-agente)
7. [Tonos de redacción IA](#7-tonos-de-redacción-ia)
8. [Códigos de error y exit codes](#8-códigos-de-error-y-exit-codes)
9. [Ficheros de prueba](#9-ficheros-de-prueba)

---

## 1. Arquitectura

```
┌──────────────────────────────────────┐
│  AGENTE 1 (repo CordobaRock)         │
│  Recopila noticias/eventos           │
│  Genera JSON de datos                │
└─────────────────┬────────────────────┘
                  │ workflow_call / repository_dispatch
                  │ with: action, payload, limite, estado_defecto
                  ▼
┌──────────────────────────────────────┐
│  CÓRDOBA ROCK AGENT (este repo)      │
│                                      │
│  1. Valida payload de entrada        │
│  2. Aplica límite de items           │
│  3. Genera texto con Gemini AI       │
│  4. Calcula estado WP por posición   │
│  5. Publica en WordPress / TEC       │
│  6. Devuelve resultado JSON          │
└─────────────────┬────────────────────┘
                  │ outputs: success, publicados, borradores, post_url
                  ▼
┌──────────────────────────────────────┐
│  WordPress (cordobarock.es)          │
│  Posts/Eventos/Grupos en             │
│  estado "publish" o "draft"          │
└──────────────────────────────────────┘
```

### Flujo de decisión de estado WP

```
¿El item trae "estado" explícito en su JSON?
         │
        SÍ ──────────────────→ Usa ese estado (publish | draft | future)
         │
        NO
         │
         ▼
¿auto_publish_first > 0 y posición <= auto_publish_first?
         │
        SÍ ──────────────────→ "publish"
         │
        NO
         │
         ▼
         Usa DEFAULT_WP_STATUS (draft por defecto)
```

---

## 2. GitHub Secrets requeridos

Configura en **Settings → Secrets and variables → Actions**:

| Secret | Descripción | Obligatorio |
|--------|-------------|-------------|
| `WP_URL` | URL base de la API REST de WordPress, ej. `https://cordobarock.es/wp-json` | ✅ |
| `WP_USER` | Nombre de usuario de WordPress | ✅ |
| `WP_APP_PASSWORD` | Contraseña de Aplicación de WP (no la de login) | ✅ |
| `GEMINI_API_KEY` | API Key de Google Gemini | ✅ |

Variables opcionales (no sensibles, pueden ir como *Variables* en lugar de Secrets):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DEFAULT_WP_STATUS` | `draft` | Estado WP por defecto |
| `PUBLISH_LIMIT` | `-1` | Items a procesar por ejecución |
| `AUTO_PUBLISH_FIRST` | `0` | Primeros N publicados automáticamente |
| `DEFAULT_AI_TONE` | `periodistico` | Tono de redacción por defecto |

---

## 3. Cómo invocar el agente

### Opción A — `workflow_call` (mismo org, recomendada)

```yaml
jobs:
  publicar:
    uses: TU_ORG/gestor-cordoba-rock/.github/workflows/cordoba_rock_agent.yml@main
    with:
      action: lote_noticias
      payload: ${{ needs.mi-job.outputs.noticias_json }}
      limite: -1
      estado_defecto: draft
      auto_publish_first: 1
    secrets: inherit
```

### Opción B — `repository_dispatch` (repos distintos)

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/TU_ORG/gestor-cordoba-rock/dispatches \
  -d '{
    "event_type": "cordoba-rock-agent",
    "client_payload": {
      "action": "lote_noticias",
      "limite": -1,
      "estado_defecto": "draft",
      "auto_publish_first": 1,
      "payload": { "noticias": [...] }
    }
  }'
```

### Opción C — Manual (UI de GitHub Actions)

**Actions → 🤖 Córdoba Rock Agent → Run workflow**

Rellena los campos: `action`, `payload` (JSON), `limite`, `estado_defecto`, `auto_publish_first`.

### Opción D — CLI local (desarrollo/pruebas)

```bash
# Acción individual
python run_agent.py --action noticia \
  --input '{"titulo": "Mi Noticia"}' \
  --estado-defecto draft

# Lote desde fichero
python run_agent.py --action lote_noticias \
  --input-file tests/inputs/test_lote_noticias.json \
  --limite 2 \
  --estado-defecto draft \
  --auto-publish-first 1
```

---

## 4. Parámetros de control de publicación

Estos parámetros se pueden pasar en tres lugares (el primero tiene mayor prioridad):

1. **Campo `estado` dentro de cada JSON individual** — solo afecta a ese item
2. **Argumento CLI** (`--limite`, `--estado-defecto`, `--auto-publish-first`)
3. **Input del workflow** (`limite`, `estado_defecto`, `auto_publish_first`)
4. **Variable de entorno** (`PUBLISH_LIMIT`, `DEFAULT_WP_STATUS`, `AUTO_PUBLISH_FIRST`)

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `limite` | int | Cuántos items procesar. `-1` = todos. `N` = solo los primeros N |
| `estado_defecto` | string | `draft` (borrador) o `publish` (publicar directo) |
| `auto_publish_first` | int | Los primeros N items se publican, el resto van a borrador. `0` = desactivado |

### Ejemplos de combinaciones

```yaml
# Modo prueba: solo 2 items, todos borradores
limite: 2
estado_defecto: draft
auto_publish_first: 0

# Modo validación: todos, primero publicado el resto borrador
limite: -1
estado_defecto: draft
auto_publish_first: 1

# Modo producción: todos publicados directamente
limite: -1
estado_defecto: publish
auto_publish_first: 0
```

---

## 5. Acciones disponibles

---

### `health`

Verifica la conectividad con WordPress, The Events Calendar y Gemini AI.
No requiere payload ni parámetros adicionales.

**Respuesta:**
```json
{
  "success": true,
  "checks": {
    "wordpress": "✅ OK",
    "tribe_events_calendar": "✅ OK",
    "gemini_ai": "✅ OK"
  },
  "message": "✅ Todos los servicios operativos"
}
```

---

### `noticia`

Crea o actualiza una noticia en WordPress (post estándar). La IA genera el contenido completo a partir de los apuntes.

#### Campos

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `titulo` | string | ✅ | Título de la noticia |
| `apuntes` | string | ✅* | Información base para que la IA redacte el contenido |
| `contenido_manual` | string (HTML) | ❌ | Si se proporciona, reemplaza la generación por IA |
| `excerpt_manual` | string | ❌ | Extracto manual (si no se usa IA) |
| `categoria_ids` | array[int] | ❌ | IDs de categorías de WordPress |
| `tono_ia` | string | ❌ | `periodistico` \| `rockero` \| `social` \| `custom` |
| `instrucciones_custom` | string | ❌ | Solo si `tono_ia = "custom"` |
| `estado` | string | ❌ | `publish` \| `draft` \| `future`. Si se omite, lo calcula el agente según `auto_publish_first` y `DEFAULT_WP_STATUS` |
| `fecha_publicacion` | string | ❌ | ISO 8601: `"2025-01-15T21:00:00"`. Necesario si `estado = "future"` |
| `imagen_url` | string | ❌ | URL pública de la imagen destacada |
| `generar_excerpt` | bool | ❌ | Si `true`, la IA genera el extracto SEO (default: `true`) |
| `generar_social` | bool | ❌ | Si `true`, la IA genera copy para redes (default: `false`) |
| `wp_post_id` | int | ❌ | Si se proporciona, **actualiza** la noticia existente |

> *`apuntes` es obligatorio si no se proporciona `contenido_manual`

#### Ejemplo mínimo
```json
{
  "titulo": "Los Reyes del Metal vuelven a Córdoba"
}
```

#### Ejemplo completo
```json
{
  "titulo": "Los Reyes del Metal vuelven a Córdoba con su gira 'Fuego y Acero'",
  "apuntes": "Concierto el 15 de enero en la Sala Fanatic. 15 años en activo. Entradas a 18 euros.",
  "categoria_ids": [5, 12],
  "tono_ia": "rockero",
  "estado": "draft",
  "imagen_url": "https://example.com/cartel.jpg",
  "generar_excerpt": true,
  "generar_social": false
}
```

#### Respuesta
```json
{
  "success": true,
  "id": 1234,
  "url": "https://cordobarock.es/?p=1234",
  "wp_status": "draft",
  "message": "✅ Noticia creada como draft",
  "ai_content": {
    "content": "<p>Texto generado...</p>",
    "excerpt": "Extracto SEO generado..."
  }
}
```

---

### `lote_noticias`

Procesa un **lote de noticias** en una sola llamada, aplicando los parámetros de control de publicación por posición.

#### Campos del payload

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `noticias` | array[dict] | ✅ | Lista de payloads de noticia individual |
| `limite` | int | ❌ | Cuántos items procesar (`-1` = todos). Sobreescribe env `PUBLISH_LIMIT` |
| `estado_defecto` | string | ❌ | `draft` o `publish` por defecto. Sobreescribe `DEFAULT_WP_STATUS` |
| `auto_publish_first` | int | ❌ | Primeros N publicados, resto borradores. Sobreescribe `AUTO_PUBLISH_FIRST` |
| `tono_ia` | string | ❌ | Tono por defecto para todas (se puede sobreescribir item a item) |
| `generar_excerpt` | bool | ❌ | Por defecto `true` para todas |
| `generar_social` | bool | ❌ | Por defecto `false` para todas |

Cada item en `noticias` sigue el mismo formato que la acción `noticia`.
Los campos globales del lote son los defaults; el item individual los puede sobreescribir.

#### Ejemplo — lote con 3 noticias, procesar 2, todas en borrador

```json
{
  "limite": 2,
  "estado_defecto": "draft",
  "auto_publish_first": 0,
  "tono_ia": "periodistico",
  "generar_excerpt": true,
  "noticias": [
    {
      "titulo": "Noticia 1 — procesada y en borrador",
      "apuntes": "Información de la primera noticia..."
    },
    {
      "titulo": "Noticia 2 — procesada y en borrador",
      "apuntes": "Información de la segunda noticia..."
    },
    {
      "titulo": "Noticia 3 — NO procesada (fuera del límite)",
      "apuntes": "Esta no se procesará porque limite=2"
    }
  ]
}
```

#### Ejemplo — lote con auto-publicación de la primera

```json
{
  "limite": -1,
  "estado_defecto": "draft",
  "auto_publish_first": 1,
  "noticias": [
    {
      "titulo": "Noticia 1 — se publicará automáticamente",
      "apuntes": "..."
    },
    {
      "titulo": "Noticia 2 — quedará como borrador",
      "apuntes": "..."
    },
    {
      "titulo": "Noticia 3 — quedará como borrador",
      "apuntes": "..."
    }
  ]
}
```

#### Respuesta de lote

```json
{
  "success": true,
  "total_recibidas": 3,
  "total_procesadas": 2,
  "publicados": 0,
  "borradores": 2,
  "errores": 0,
  "message": "✅ Lote procesado: 0 publicadas, 2 borradores, 0 errores",
  "items": [
    {
      "success": true,
      "id": 101,
      "url": "https://cordobarock.es/?p=101",
      "wp_status": "draft",
      "titulo": "Noticia 1",
      "posicion": 1
    },
    {
      "success": true,
      "id": 102,
      "url": "https://cordobarock.es/?p=102",
      "wp_status": "draft",
      "titulo": "Noticia 2",
      "posicion": 2
    }
  ]
}
```

---

### `evento`

Crea o actualiza un evento en **The Events Calendar** (plugin de WordPress).

#### Campos

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `titulo` | string | ✅ | Título del evento |
| `fecha_inicio` | string | ✅ | Formato: `"YYYY-MM-DD HH:MM:SS"` |
| `fecha_fin` | string | ❌ | Default: misma fecha a las `23:59:00` |
| `sala_nombre` | string | ❌ | Nombre de la sala (se crea en TEC si no existe) |
| `precio` | string | ❌ | Ej. `"18€"` |
| `url_entradas` | string | ❌ | URL de venta de entradas |
| `descripcion_apuntes` | string | ❌ | Información para que la IA redacte la descripción |
| `descripcion_manual` | string (HTML) | ❌ | Reemplaza la generación IA |
| `categoria_nombres` | array[string] | ❌ | `"Córdoba"` \| `"Festival"` \| `"Nacional"` |
| `etiquetas` | array[string] | ❌ | Se crean automáticamente si no existen |
| `tono_ia` | string | ❌ | `periodistico` \| `rockero` \| `social` \| `custom` |
| `instrucciones_custom` | string | ❌ | Solo si `tono_ia = "custom"` |
| `imagen_url` | string | ❌ | URL del cartel del evento |
| `all_day` | bool | ❌ | `true` = evento de todo el día (default: `false`) |
| `estado` | string | ❌ | `publish` \| `draft` (calculado automáticamente si se omite) |
| `generar_excerpt` | bool | ❌ | Default: `true` |
| `generar_social` | bool | ❌ | Default: `false` |
| `wp_event_id` | int | ❌ | Si se proporciona, **actualiza** el evento |

#### Ejemplo mínimo
```json
{
  "titulo": "Los Reyes del Metal — Sala Fanatic",
  "fecha_inicio": "2025-01-15 21:30:00"
}
```

#### Ejemplo completo
```json
{
  "titulo": "Los Reyes del Metal — Sala Fanatic Córdoba",
  "fecha_inicio": "2025-01-15 21:30:00",
  "fecha_fin": "2025-01-15 23:59:00",
  "sala_nombre": "Sala Fanatic",
  "precio": "18€",
  "url_entradas": "https://www.entradas.com/evento/reyes-metal",
  "descripcion_apuntes": "La banda regresa tras 3 años. Thrash y heavy clásico. Teloneros: Distrito Sur.",
  "categoria_nombres": ["Córdoba"],
  "etiquetas": ["Metal", "Heavy Metal", "Sala Fanatic"],
  "tono_ia": "rockero",
  "estado": "draft",
  "imagen_url": "https://example.com/cartel.jpg",
  "generar_excerpt": true,
  "generar_social": false
}
```

---

### `grupo`

Crea o actualiza un grupo musical (Custom Post Type `grupo` con campos ACF).

#### Campos

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `nombre` | string | ✅ | Nombre del grupo |
| `ciudad` | string | ✅ | Ciudad de origen |
| `provincia` | string | ❌ | Default: `"Córdoba"` |
| `estilos` | array[string] | ❌ | Deben existir como términos de la taxonomía `estilo` en WP |
| `tipo_propuesta` | string | ❌ | `"original"` \| `"tributo"` |
| `estado_grupo` | string | ❌ | `"activo"` \| `"inactivo"` |
| `bio_apuntes` | string | ❌ | Información para que la IA genere la biografía |
| `bio_manual` | string (HTML) | ❌ | Reemplaza la generación IA |
| `formacion_actual` | string | ❌ | Miembros actuales |
| `antiguos_miembros` | string | ❌ | Ex-miembros |
| `url_facebook` | string | ❌ | — |
| `url_instagram` | string | ❌ | — |
| `url_spotify` | string | ❌ | — |
| `url_youtube` | string | ❌ | — |
| `url_web` | string | ❌ | Web oficial |
| `telefono` | string | ❌ | — |
| `email` | string | ❌ | — |
| `mostrar_telefono` | bool | ❌ | Default: `false` |
| `mostrar_email` | bool | ❌ | Default: `false` |
| `imagen_url` | string | ❌ | URL de la foto/logo del grupo |
| `tono_ia` | string | ❌ | `periodistico` \| `rockero` \| `social` \| `custom` |
| `estado` | string | ❌ | `publish` \| `draft` (calculado automáticamente si se omite) |
| `wp_group_id` | int | ❌ | Si se proporciona, **actualiza** el grupo |

#### Ejemplo
```json
{
  "nombre": "Los Reyes del Metal",
  "ciudad": "Córdoba",
  "estilos": ["Metal", "Rock"],
  "bio_apuntes": "Banda formada en 2010. Influencias: Metallica, Iron Maiden. Tres discos publicados.",
  "url_instagram": "https://instagram.com/losreyesdelmetal",
  "estado": "draft",
  "tono_ia": "rockero"
}
```

---

### `sala`

Crea o actualiza una sala/venue en The Events Calendar.

#### Campos

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `nombre` | string | ✅ | Nombre de la sala |
| `descripcion` | string | ❌ | Descripción |
| `direccion` | string | ❌ | Dirección postal |
| `ciudad` | string | ❌ | — |
| `provincia` | string | ❌ | Default: `"Córdoba"` |
| `cp` | string | ❌ | Código postal |
| `telefono` | string | ❌ | — |
| `web` | string | ❌ | URL de la sala |
| `imagen_url` | string | ❌ | — |
| `wp_venue_id` | int | ❌ | Si se proporciona, **actualiza** la sala |

#### Ejemplo
```json
{
  "nombre": "Sala Fanatic",
  "descripcion": "Sala de conciertos de referencia en Córdoba.",
  "direccion": "Calle Pintor Espinosa, 2",
  "ciudad": "Córdoba",
  "cp": "14004",
  "telefono": "957000000",
  "web": "https://salafanatic.com"
}
```

---

## 6. Outputs del agente

### Acciones individuales (`noticia`, `evento`, `grupo`, `sala`)

| Output del workflow | Tipo | Descripción |
|--------------------|------|-------------|
| `success` | `"true"` / `"false"` | Si la operación fue exitosa |
| `post_url` | string | URL del post en WordPress |
| `result` | JSON string | Resultado completo |

### Acción `lote_noticias`

| Output del workflow | Tipo | Descripción |
|--------------------|------|-------------|
| `success` | `"true"` / `"false"` | Sin errores en el lote |
| `publicados` | int | Número de items publicados directamente |
| `borradores` | int | Número de items guardados como borrador |
| `result` | JSON string | Resultado completo con detalle por item |

---

## 7. Tonos de redacción IA

| Valor | Descripción |
|-------|-------------|
| `periodistico` | Objetivo, informativo y serio. Sin adjetivos exagerados. |
| `rockero` | Apasionado, enérgico. Palabras como "brutal", "descarga", "potente". |
| `social` | Cercano, corto, con emojis musicales. Ideal para Instagram. |
| `custom` | Define tus propias instrucciones en `instrucciones_custom`. |

---

## 8. Códigos de error y exit codes

| Código | Situación |
|--------|-----------|
| Exit 0 | Éxito completo |
| Exit 1 | Error (ver campo `message` en el JSON) |
| HTTP 401 | Credenciales WP incorrectas |
| HTTP 403 | El usuario WP no tiene permisos de Editor/Admin |
| HTTP 404 | El post/evento a actualizar no existe |
| HTTP 429 | Rate limit Gemini AI (el agente reintenta automáticamente 2 veces) |
| HTTP 500 | Error interno de WordPress |

---

## 9. Ficheros de prueba

```
tests/inputs/
  test_noticia.json        ← Noticia individual
  test_evento.json         ← Evento en The Events Calendar
  test_grupo.json          ← Grupo musical con campos ACF
  test_lote_noticias.json  ← Lote de 3 noticias (limite=2 en el JSON)
```

### Comandos de prueba local

```bash
# Health check
python run_agent.py --action health

# Noticia individual en borrador
python run_agent.py --action noticia \
  --input-file tests/inputs/test_noticia.json \
  --estado-defecto draft

# Lote: solo 2, todos borradores
python run_agent.py --action lote_noticias \
  --input-file tests/inputs/test_lote_noticias.json \
  --limite 2 \
  --estado-defecto draft

# Lote: todos, primera publicada
python run_agent.py --action lote_noticias \
  --input-file tests/inputs/test_lote_noticias.json \
  --limite -1 \
  --estado-defecto draft \
  --auto-publish-first 1

# Evento en borrador
python run_agent.py --action evento \
  --input-file tests/inputs/test_evento.json \
  --estado-defecto draft

# Grupo en borrador
python run_agent.py --action grupo \
  --input-file tests/inputs/test_grupo.json \
  --estado-defecto draft
```
