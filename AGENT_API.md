# 🎸 Córdoba Rock Agent — Contrato de API

> Documentación completa de los campos que debe enviar el agente orquestador
> para que este agente ejecute cada acción de forma autónoma.

---

## Índice

1. [Arquitectura de integración](#arquitectura-de-integración)
2. [Variables de entorno / GitHub Secrets](#variables-de-entorno--github-secrets)
3. [Cómo invocar el agente desde otro workflow](#cómo-invocar-el-agente-desde-otro-workflow)
4. [Acciones disponibles](#acciones-disponibles)
   - [health — Verificar conectividad](#health)
   - [noticia — Publicar noticia](#noticia)
   - [evento — Publicar evento](#evento)
   - [grupo — Publicar grupo musical](#grupo)
   - [sala — Publicar sala/venue](#sala)
5. [Outputs del agente](#outputs-del-agente)
6. [Tonos de redacción IA disponibles](#tonos-de-redacción-ia-disponibles)
7. [Códigos de error](#códigos-de-error)

---

## Arquitectura de integración

```
┌─────────────────────────────────┐
│  AGENTE 1 (otro repo / workflow) │
│  Genera datos del evento/noticia │
└──────────────┬──────────────────┘
               │ uses: TU_ORG/gestor-cordoba-rock/.github/workflows/cordoba_rock_agent.yml@main
               │ with: action: evento, payload: '{...}'
               ▼
┌─────────────────────────────────┐
│  CÓRDOBA ROCK AGENT             │
│  1. Recibe payload JSON         │
│  2. Llama a Gemini AI           │
│  3. Publica en WordPress        │
│  4. Devuelve result + URL       │
└──────────────┬──────────────────┘
               │ outputs: success, post_url, result
               ▼
┌─────────────────────────────────┐
│  AGENTE 1 usa el resultado      │
│  (notificación, log, etc.)      │
└─────────────────────────────────┘
```

---

## Variables de entorno / GitHub Secrets

Configura estos secrets en **Settings → Secrets and variables → Actions** del repositorio:

| Secret | Descripción | Dónde obtenerlo |
|--------|-------------|-----------------|
| `WP_URL` | URL base API WordPress | `https://cordobarock.es/wp-json` |
| `WP_USER` | Usuario WordPress | Panel WP → Perfil |
| `WP_APP_PASSWORD` | Contraseña de Aplicación WP | Panel WP → Perfil → Contraseñas de Aplicación |
| `GEMINI_API_KEY` | API Key Google Gemini | https://aistudio.google.com/apikey |
| `GEMINI_MODEL` | Modelo Gemini (opcional) | Default: `gemini-2.0-flash` |

> ⚠️ **IMPORTANTE:** Las claves que estaban hardcodeadas en el código original (`utils.py`) deben ser **rotadas** antes de subir el repositorio a GitHub. La contraseña de aplicación WordPress se genera desde *WP Admin → Tu Perfil → Contraseñas de Aplicación*.

---

## Cómo invocar el agente desde otro workflow

### Opción A: `workflow_call` (recomendada — mismo repositorio o reusable)

```yaml
# En el workflow del AGENTE ORQUESTADOR (otro repo o mismo repo):
jobs:
  publicar-en-wordpress:
    uses: TU_ORG/gestor-cordoba-rock/.github/workflows/cordoba_rock_agent.yml@main
    with:
      action: noticia
      payload: |
        {
          "titulo": "Festival de Rock en Córdoba",
          "apuntes": "Evento el 15 de marzo en el Auditorio...",
          "tono_ia": "rockero",
          "generar_excerpt": true
        }
    secrets:
      WP_URL: ${{ secrets.WP_URL }}
      WP_USER: ${{ secrets.WP_USER }}
      WP_APP_PASSWORD: ${{ secrets.WP_APP_PASSWORD }}
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

  # Usar el resultado en un paso posterior
  notificar:
    needs: publicar-en-wordpress
    runs-on: ubuntu-latest
    steps:
      - name: "Ver resultado"
        run: |
          echo "Success: ${{ needs.publicar-en-wordpress.outputs.success }}"
          echo "URL: ${{ needs.publicar-en-wordpress.outputs.post_url }}"
```

### Opción B: `repository_dispatch` (desde sistema externo / otro agente)

```bash
# Desde cualquier sistema con un GitHub Token
curl -X POST \
  -H "Authorization: Bearer TU_GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/TU_ORG/gestor-cordoba-rock/dispatches \
  -d '{
    "event_type": "cordoba-rock-agent",
    "client_payload": {
      "action": "evento",
      "payload": {
        "titulo": "Concierto de Prueba",
        "fecha_inicio": "2025-03-15 21:00:00",
        "sala_nombre": "Sala Fanatic"
      }
    }
  }'
```

### Opción C: Manual desde la UI de GitHub

Ve a **Actions → 🤖 Córdoba Rock Agent → Run workflow** y rellena los campos `action` y `payload`.

---

## Acciones disponibles

---

### `health`

Verifica la conectividad con WordPress y Gemini AI. No necesita payload.

```json
{}
```

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

Crea o actualiza una noticia en WordPress (post estándar).

#### Campos

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `titulo` | string | ✅ | Título de la noticia |
| `apuntes` | string | ✅* | Información base que la IA usará para redactar el contenido completo |
| `contenido_manual` | string (HTML) | ❌ | Si se proporciona, se usa en lugar de la IA |
| `excerpt_manual` | string | ❌ | Extracto manual (si no se usa IA) |
| `categoria_ids` | array[int] | ❌ | IDs de categorías WordPress |
| `tono_ia` | string | ❌ | `periodistico` \| `rockero` \| `social` \| `custom` (default: `periodistico`) |
| `instrucciones_custom` | string | ❌ | Solo si `tono_ia = "custom"` |
| `estado` | string | ❌ | `publish` \| `draft` \| `future` (default: `publish`) |
| `fecha_publicacion` | string | ❌ | ISO 8601: `"2025-01-15T21:00:00"`. Necesario si `estado = "future"` |
| `imagen_url` | string | ❌ | URL pública de la imagen destacada |
| `generar_excerpt` | bool | ❌ | Si `true`, la IA genera el extracto SEO (default: `true`) |
| `generar_social` | bool | ❌ | Si `true`, la IA genera copy para Instagram (default: `false`) |
| `wp_post_id` | int | ❌ | Si se proporciona, **actualiza** la noticia en lugar de crear una nueva |

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
  "apuntes": "Concierto el 15 de enero en la Sala Fanatic. 15 años en activo. Entradas a 18 euros. Puertas a las 20:30h. Teloneros: Distrito Sur.",
  "categoria_ids": [5, 12],
  "tono_ia": "rockero",
  "estado": "publish",
  "imagen_url": "https://example.com/cartel.jpg",
  "generar_excerpt": true,
  "generar_social": true
}
```

---

### `evento`

Crea o actualiza un evento en **The Events Calendar** (plugin WordPress).

#### Campos

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `titulo` | string | ✅ | Título del evento |
| `fecha_inicio` | string | ✅ | Formato: `"YYYY-MM-DD HH:MM:SS"` |
| `fecha_fin` | string | ❌ | Formato: `"YYYY-MM-DD HH:MM:SS"` (default: misma fecha a las 23:59) |
| `sala_nombre` | string | ❌ | Nombre de la sala. Se crea automáticamente si no existe en TEC |
| `precio` | string | ❌ | Precio de las entradas, p.ej. `"15€"` |
| `url_entradas` | string | ❌ | URL de venta de entradas |
| `descripcion_apuntes` | string | ❌ | Información base para que la IA redacte la descripción |
| `descripcion_manual` | string (HTML) | ❌ | Si se proporciona, se usa en lugar de la IA |
| `categoria_nombres` | array[string] | ❌ | Valores posibles: `"Córdoba"`, `"Festival"`, `"Nacional"` |
| `etiquetas` | array[string] | ❌ | Lista de etiquetas en texto. Se crean si no existen |
| `tono_ia` | string | ❌ | `periodistico` \| `rockero` \| `social` \| `custom` |
| `instrucciones_custom` | string | ❌ | Solo si `tono_ia = "custom"` |
| `imagen_url` | string | ❌ | URL del cartel del evento |
| `all_day` | bool | ❌ | Si `true`, evento de todo el día (default: `false`) |
| `generar_excerpt` | bool | ❌ | Si `true`, genera extracto SEO (default: `true`) |
| `generar_social` | bool | ❌ | Si `true`, genera copy para redes (default: `false`) |
| `wp_event_id` | int | ❌ | Si se proporciona, **actualiza** el evento existente |

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
  "descripcion_apuntes": "La banda regresa tras 3 años. 15 años en activo. Thrash y heavy clásico. Disco 'Fuego y Acero'. Teloneros: Distrito Sur.",
  "categoria_nombres": ["Córdoba"],
  "etiquetas": ["Metal", "Heavy Metal", "Sala Fanatic"],
  "tono_ia": "rockero",
  "imagen_url": "https://example.com/cartel-reyes-metal.jpg",
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
| `provincia` | string | ❌ | Provincia (default: `"Córdoba"`) |
| `estilos` | array[string] | ❌ | Estilos musicales. Deben existir como términos de la taxonomía `estilo` en WP |
| `tipo_propuesta` | string | ❌ | `"original"` \| `"tributo"` (default: `"original"`) |
| `estado_grupo` | string | ❌ | `"activo"` \| `"inactivo"` (default: `"activo"`) |
| `bio_apuntes` | string | ❌ | Info para que la IA genere la biografía |
| `bio_manual` | string (HTML) | ❌ | Biografía manual (si no se usa IA) |
| `formacion_actual` | string | ❌ | Miembros actuales |
| `antiguos_miembros` | string | ❌ | Ex-miembros |
| `url_facebook` | string | ❌ | URL de Facebook |
| `url_instagram` | string | ❌ | URL de Instagram |
| `url_spotify` | string | ❌ | URL de Spotify |
| `url_youtube` | string | ❌ | URL de YouTube |
| `url_web` | string | ❌ | Web oficial |
| `telefono` | string | ❌ | Teléfono de contacto |
| `email` | string | ❌ | Email de contacto |
| `mostrar_telefono` | bool | ❌ | Si `true`, muestra el teléfono en la web (default: `false`) |
| `mostrar_email` | bool | ❌ | Si `true`, muestra el email en la web (default: `false`) |
| `imagen_url` | string | ❌ | URL de la foto/logo del grupo |
| `tono_ia` | string | ❌ | `periodistico` \| `rockero` \| `social` \| `custom` |
| `instrucciones_custom` | string | ❌ | Solo si `tono_ia = "custom"` |
| `wp_group_id` | int | ❌ | Si se proporciona, **actualiza** el grupo existente |

#### Ejemplo mínimo
```json
{
  "nombre": "Los Reyes del Metal",
  "ciudad": "Córdoba"
}
```

#### Ejemplo completo
```json
{
  "nombre": "Los Reyes del Metal",
  "ciudad": "Córdoba",
  "provincia": "Córdoba",
  "estilos": ["Metal", "Rock"],
  "tipo_propuesta": "original",
  "estado_grupo": "activo",
  "bio_apuntes": "Banda formada en 2010. Influencias: Metallica, Iron Maiden. Tres discos. Han tocado en ViñaRock.",
  "url_facebook": "https://facebook.com/losreyesdelmetal",
  "url_instagram": "https://instagram.com/losreyesdelmetal",
  "email": "contacto@losreyesdelmetal.com",
  "mostrar_email": true,
  "imagen_url": "https://example.com/foto-banda.jpg",
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
| `descripcion` | string | ❌ | Descripción de la sala |
| `direccion` | string | ❌ | Dirección postal |
| `ciudad` | string | ❌ | Ciudad |
| `provincia` | string | ❌ | Provincia (default: `"Córdoba"`) |
| `cp` | string | ❌ | Código postal |
| `telefono` | string | ❌ | Teléfono |
| `web` | string | ❌ | Web de la sala |
| `imagen_url` | string | ❌ | URL de la foto de la sala |
| `wp_venue_id` | int | ❌ | Si se proporciona, **actualiza** la sala existente |

#### Ejemplo
```json
{
  "nombre": "Sala Fanatic",
  "descripcion": "Sala de conciertos de referencia en Córdoba.",
  "direccion": "Calle Pintor Espinosa, 2",
  "ciudad": "Córdoba",
  "provincia": "Córdoba",
  "cp": "14004",
  "telefono": "957000000",
  "web": "https://salafanatic.com"
}
```

---

## Outputs del agente

Cuando el agente finaliza, el workflow devuelve estos outputs disponibles para el paso `needs.*`:

| Output | Tipo | Descripción |
|--------|------|-------------|
| `success` | string (`"true"` / `"false"`) | Si la operación fue exitosa |
| `post_url` | string | URL del post/evento/grupo publicado en WordPress |
| `result` | string (JSON) | Resultado completo en formato JSON |

El JSON completo tiene esta estructura:

```json
{
  "success": true,
  "id": 1234,
  "url": "https://cordobarock.es/noticias/concierto-ejemplo/",
  "message": "✅ Noticia creada correctamente",
  "ai_content": {
    "content": "<p>Texto generado por IA...</p>",
    "excerpt": "Resumen SEO generado por IA...",
    "social_copy": "🤘 ¡Atención rockeros!..."
  }
}
```

---

## Tonos de redacción IA disponibles

| Valor | Descripción |
|-------|-------------|
| `periodistico` | Tono objetivo, informativo y serio. Sin adjetivos exagerados. |
| `rockero` | Apasionado, enérgico. Palabras como "brutal", "descarga", "potente". |
| `social` | Cercano, corto, con emojis musicales. Ideal para Instagram/Facebook. |
| `custom` | Instrucciones personalizadas vía el campo `instrucciones_custom`. |

---

## Códigos de error

| Código HTTP | Situación |
|-------------|-----------|
| Exit 0 | Operación completada con éxito |
| Exit 1 | Error en la operación (ver `message` en el JSON) |
| HTTP 401 | Credenciales WordPress incorrectas |
| HTTP 403 | El usuario WP no tiene permisos suficientes |
| HTTP 404 | El post/evento a actualizar no existe |
| HTTP 429 | Rate limit de Gemini AI (el agente reintenta automáticamente) |

---

## Archivo de ejemplos de prueba

Los JSONs de prueba están en `tests/inputs/`:

```
tests/inputs/
  test_noticia.json
  test_evento.json
  test_grupo.json
```

Para ejecutar localmente:
```bash
# Copiar .env.example a .env y rellenar credenciales
cp .env.example .env

# Instalar dependencias
pip install -r requirements.txt

# Test de conectividad
python run_agent.py --action health

# Test de noticia
python run_agent.py --action noticia --input-file tests/inputs/test_noticia.json

# Test de evento
python run_agent.py --action evento --input-file tests/inputs/test_evento.json
```
