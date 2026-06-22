# 🎸 Córdoba Rock Agent — Guía de Implementación

> Pasos completos para poner en marcha el agente autónomo, desde cero hasta producción.

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Configuración inicial (entorno local)](#3-configuración-inicial-entorno-local)
4. [Obtener credenciales](#4-obtener-credenciales)
5. [Configurar GitHub Secrets](#5-configurar-github-secrets)
6. [Verificar conectividad (health check)](#6-verificar-conectividad-health-check)
7. [Pruebas en modo borrador](#7-pruebas-en-modo-borrador)
8. [Conectar con el Agente 1 (CordobaRock)](#8-conectar-con-el-agente-1-cordobarock)
9. [Puesta en producción](#9-puesta-en-producción)
10. [Control de publicación paso a paso](#10-control-de-publicación-paso-a-paso)
11. [Parámetros de configuración rápida](#11-parámetros-de-configuración-rápida)
12. [Resolución de problemas](#12-resolución-de-problemas)

---

## 1. Requisitos previos

Antes de empezar asegúrate de tener:

| Requisito | Versión mínima | Comprobación |
|-----------|---------------|--------------|
| Python | 3.11+ | `python --version` |
| pip | Cualquiera | `pip --version` |
| Git | Cualquiera | `git --version` |
| Cuenta GitHub | — | Con acceso a GitHub Actions |
| WordPress | 5.8+ | Con REST API activada |
| Plugin **The Events Calendar** | Cualquiera | Instalado y activo en WP |
| Plugin **ACF (Advanced Custom Fields)** | Cualquiera | Instalado y activo en WP |
| Cuenta Google AI Studio | — | Para obtener la API Key de Gemini |

---

## 2. Estructura del proyecto

```
gestor-cordoba-rock/
│
├── .github/
│   └── workflows/
│       └── cordoba_rock_agent.yml   ← Workflow principal de GitHub Actions
│
├── tests/
│   └── inputs/
│       ├── test_noticia.json        ← JSON de prueba para noticia individual
│       ├── test_evento.json         ← JSON de prueba para evento
│       ├── test_grupo.json          ← JSON de prueba para grupo musical
│       └── test_lote_noticias.json  ← JSON de prueba para lote de noticias
│
├── agent_config.py     ← Toda la configuración leída desde variables de entorno
├── agent_core.py       ← Motor del agente (IA + WordPress, sin Streamlit)
├── run_agent.py        ← CLI entrypoint que invoca GitHub Actions
├── requirements.txt    ← Dependencias Python
│
├── .env.example        ← Plantilla de variables de entorno (copia a .env)
├── .gitignore          ← Excluye .env, venv, temporales
├── AGENT_API.md        ← Contrato de API (campos, ejemplos, outputs)
└── IMPLEMENTACION.md   ← Este fichero
```

---

## 3. Configuración inicial (entorno local)

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/TU_ORG/gestor-cordoba-rock.git
cd gestor-cordoba-rock
```

### Paso 2 — Crear entorno virtual Python

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### Paso 3 — Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4 — Crear el fichero `.env`

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales reales (ver sección siguiente).

> **NUNCA** subas el fichero `.env` a GitHub. Ya está incluido en `.gitignore`.

---

## 4. Obtener credenciales

### WordPress — Contraseña de Aplicación

La **Contraseña de Aplicación** es diferente a tu contraseña de login de WordPress:

1. Accede al panel de WordPress: `https://cordobarock.es/wp-admin`
2. Ve a **Usuarios → Tu Perfil** (o directamente a `/wp-admin/profile.php`)
3. Baja hasta la sección **Contraseñas de Aplicación**
4. En el campo *Nombre de la nueva contraseña de aplicación*, escribe `GitHub Agent`
5. Haz clic en **Añadir nueva contraseña de aplicación**
6. WordPress genera una clave con formato `xxxx xxxx xxxx xxxx xxxx xxxx`
7. **Cópiala ahora** — no podrás verla de nuevo

> ⚠️ Si las credenciales anteriores estaban en el código fuente, **revócalas** desde este mismo panel antes de continuar.

### Google Gemini API Key

1. Ve a [Google AI Studio](https://aistudio.google.com/apikey)
2. Haz clic en **Create API key**
3. Copia la clave generada (empieza por `AIzaSy...`)

> ⚠️ Si la API Key anterior estaba en el código fuente, **elimínala** desde AI Studio y genera una nueva.

### Rellenar `.env`

```bash
# Editar con tu editor favorito
nano .env    # o code .env / vim .env
```

Contenido mínimo obligatorio:

```dotenv
WP_URL=https://cordobarock.es/wp-json
WP_USER=admin_mh
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx

GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash
```

---

## 5. Configurar GitHub Secrets

Los Secrets son las variables de entorno seguras de GitHub Actions.

### Pasos

1. Ve al repositorio en GitHub
2. Haz clic en **Settings** → **Secrets and variables** → **Actions**
3. Haz clic en **New repository secret** para cada uno:

| Nombre del Secret | Valor | Obligatorio |
|-------------------|-------|-------------|
| `WP_URL` | `https://cordobarock.es/wp-json` | ✅ |
| `WP_USER` | Tu usuario de WordPress | ✅ |
| `WP_APP_PASSWORD` | La contraseña de aplicación generada | ✅ |
| `GEMINI_API_KEY` | Tu API Key de Google Gemini | ✅ |

### Variables de control (opcionales pero recomendadas)

Estas variables controlan el comportamiento del agente y se pueden definir como **Variables** (no Secrets) en la misma pantalla, ya que no son sensibles:

| Nombre | Valor recomendado inicial | Descripción |
|--------|--------------------------|-------------|
| `DEFAULT_WP_STATUS` | `draft` | Todos los posts como borrador hasta validar |
| `PUBLISH_LIMIT` | `2` | Procesar solo 2 items por ejecución durante pruebas |
| `AUTO_PUBLISH_FIRST` | `0` | Desactivado — todos van a borrador |

---

## 6. Verificar conectividad (health check)

### Local

```bash
# Asegúrate de que el .env está relleno
source venv/bin/activate
python run_agent.py --action health
```

Salida esperada:
```
🚀 Córdoba Rock Agent | Acción: HEALTH
───────────────────────────────────────────────────────
📊 RESULTADO:
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

### Desde GitHub Actions (manual)

1. Ve a **Actions → 🤖 Córdoba Rock Agent → Run workflow**
2. Selecciona `health` en el campo *Acción*
3. Haz clic en **Run workflow**
4. Verifica que todos los checks aparecen en verde en el resumen del job

---

## 7. Pruebas en modo borrador

Antes de publicar nada en producción, ejecuta pruebas con `estado_defecto: draft`. Los posts quedarán como borradores en WordPress para que los revises manualmente.

### Prueba 1 — Noticia individual (local)

```bash
python run_agent.py \
  --action noticia \
  --input-file tests/inputs/test_noticia.json \
  --estado-defecto draft
```

Verifica en WordPress Admin → Entradas → Borradores que apareció el post.

### Prueba 2 — Lote de 2 noticias (local)

```bash
python run_agent.py \
  --action lote_noticias \
  --input-file tests/inputs/test_lote_noticias.json \
  --limite 2 \
  --estado-defecto draft
```

Salida esperada:
```
📦 Lote de 3 noticias → procesando las primeras 2
  📋 Estado por defecto para todas: draft
──────────────────────────────────────────────────
  📰 [1/2] Los Reyes del Metal vuelven...
  🤖 Generando contenido con IA...
  ✅ Contenido generado.
  📝 borrador Noticia creada: ID=101

  📰 [2/2] Nuevo disco de Distrito Sur...
  🤖 Generando contenido con IA...
  📝 borrador Noticia creada: ID=102

📊 LOTE COMPLETADO: 0 publicadas | 2 borradores | 0 errores
```

### Prueba 3 — Evento (local)

```bash
python run_agent.py \
  --action evento \
  --input-file tests/inputs/test_evento.json \
  --estado-defecto draft
```

### Prueba 4 — Desde GitHub Actions (manual)

1. Ve a **Actions → 🤖 Córdoba Rock Agent → Run workflow**
2. Rellena:
   - **Acción:** `lote_noticias`
   - **Payload:** pega el contenido de `tests/inputs/test_lote_noticias.json`
   - **Límite:** `2`
   - **Estado por defecto:** `draft`
   - **Auto-publish primeros:** `0`
3. Ejecuta y verifica el resumen

---

## 8. Conectar con el Agente 1 (CordobaRock)

El Agente 1 (en el repo CordobaRock) debe llamar a este workflow cuando termine su ejecución.

### Opción A — `workflow_call` (mismo org, recomendada)

Añade este job al final del workflow del Agente 1:

```yaml
# En el workflow del Agente 1 (repo: CordobaRock)
jobs:

  # ... tus jobs existentes del Agente 1 ...
  generar-contenido:
    runs-on: ubuntu-latest
    outputs:
      noticias_json: ${{ steps.build.outputs.noticias_json }}
    steps:
      - id: build
        run: |
          # Aquí el Agente 1 genera el JSON de noticias
          NOTICIAS=$(cat <<'EOF'
          {
            "noticias": [
              {
                "titulo": "Título generado por el Agente 1",
                "apuntes": "Información recopilada automáticamente..."
              }
            ]
          }
          EOF
          )
          echo "noticias_json=$NOTICIAS" >> $GITHUB_OUTPUT

  # Job que dispara el Gestor al terminar el Agente 1
  publicar-en-wordpress:
    needs: generar-contenido          # ← espera a que el Agente 1 acabe
    uses: TU_ORG/gestor-cordoba-rock/.github/workflows/cordoba_rock_agent.yml@main
    with:
      action: lote_noticias
      payload: ${{ needs.generar-contenido.outputs.noticias_json }}
      limite: -1               # procesar todas
      estado_defecto: draft    # borrador hasta validar
      auto_publish_first: 0    # todos a borrador
    secrets: inherit           # hereda WP_URL, WP_USER, GEMINI_API_KEY, etc.

  # Job opcional: notificar o loguear el resultado
  notificar-resultado:
    needs: publicar-en-wordpress
    runs-on: ubuntu-latest
    steps:
      - name: "📊 Ver resultado"
        run: |
          echo "Éxito:      ${{ needs.publicar-en-wordpress.outputs.success }}"
          echo "Publicados: ${{ needs.publicar-en-wordpress.outputs.publicados }}"
          echo "Borradores: ${{ needs.publicar-en-wordpress.outputs.borradores }}"
```

### Opción B — `repository_dispatch` (repos distintos)

Si el Agente 1 está en un repositorio diferente sin acceso de llamada directa:

```yaml
# En el workflow del Agente 1
- name: "🚀 Disparar Córdoba Rock Agent"
  run: |
    curl -s -X POST \
      -H "Authorization: Bearer ${{ secrets.GESTOR_REPO_TOKEN }}" \
      -H "Content-Type: application/json" \
      https://api.github.com/repos/TU_ORG/gestor-cordoba-rock/dispatches \
      -d '{
        "event_type": "cordoba-rock-agent",
        "client_payload": {
          "action": "lote_noticias",
          "limite": -1,
          "estado_defecto": "draft",
          "auto_publish_first": 0,
          "payload": ${{ toJson(steps.build.outputs.noticias_json) }}
        }
      }'
```

> **Requisito:** Crear un PAT (Personal Access Token) en GitHub con permisos `repo` y guardarlo como Secret `GESTOR_REPO_TOKEN` en el repo del Agente 1.

---

## 9. Puesta en producción

Una vez validadas las pruebas en borrador, sigue estos pasos para activar la publicación automática:

### Paso 1 — Aprobar borradores manualmente (primera vez)

1. Entra en WordPress Admin → Entradas → Borradores
2. Revisa cada post generado por la IA
3. Ajusta el texto si hace falta
4. Publica los que sean correctos

### Paso 2 — Activar auto-publicación parcial

Cuando confíes en la calidad de la IA, cambia a este modo: **la primera noticia se publica, el resto van a borrador**.

Modifica el job en el Agente 1:
```yaml
with:
  estado_defecto: draft
  auto_publish_first: 1    # ← la primera se publica automáticamente
```

O localmente:
```bash
python run_agent.py --action lote_noticias \
  --input-file tests/inputs/test_lote_noticias.json \
  --estado-defecto draft \
  --auto-publish-first 1
```

### Paso 3 — Publicación total automática

Cuando el sistema sea completamente fiable:
```yaml
with:
  estado_defecto: publish    # ← todo se publica directamente
  auto_publish_first: 0
```

> ⚠️ **Recomendación:** Mantén `estado_defecto: draft` durante al menos las primeras 2-3 semanas en producción hasta validar la calidad de los textos generados.

---

## 10. Control de publicación paso a paso

El sistema tiene **tres niveles de control**, del más seguro al más automático:

```
NIVEL 1 — Todo borrador (modo prueba / inicio)
─────────────────────────────────────────────────
  estado_defecto: draft
  auto_publish_first: 0
  → Todos los items van a WP como borrador
  → El usuario revisa y publica manualmente

NIVEL 2 — Publicación parcial (modo validación)
─────────────────────────────────────────────────
  estado_defecto: draft
  auto_publish_first: 1   (o 2)
  → Los primeros N items se publican solos
  → El resto van a borrador para revisión

NIVEL 3 — Publicación total (modo producción)
─────────────────────────────────────────────────
  estado_defecto: publish
  auto_publish_first: 0
  → Todo se publica directamente en WP
  → Sin intervención humana
```

### Prioridad de los parámetros

Los parámetros se pueden definir en tres lugares. El orden de **mayor a menor prioridad** es:

```
1. Campo individual en el JSON de cada noticia   ← mayor prioridad
2. Argumento CLI (--estado-defecto, etc.)
3. Input del workflow de GitHub Actions
4. Variable de entorno (.env / GitHub Secret)    ← menor prioridad
```

---

## 11. Parámetros de configuración rápida

### Variables de entorno (`.env` / GitHub Secrets)

| Variable | Valores | Descripción |
|----------|---------|-------------|
| `DEFAULT_WP_STATUS` | `draft` / `publish` | Estado por defecto de todos los posts |
| `PUBLISH_LIMIT` | `-1` / `N` | `-1` = todos, `N` = procesar solo los primeros N |
| `AUTO_PUBLISH_FIRST` | `0` / `N` | Primeros N items se publican, resto son borradores |
| `DEFAULT_AI_TONE` | `periodistico` / `rockero` / `social` | Tono de redacción por defecto |

### Argumentos CLI (`run_agent.py`)

| Argumento | Ejemplo | Descripción |
|-----------|---------|-------------|
| `--limite` | `--limite 2` | Procesar solo 2 items |
| `--limite -1` | `--limite -1` | Procesar todos |
| `--estado-defecto` | `--estado-defecto draft` | Todos como borrador |
| `--auto-publish-first` | `--auto-publish-first 1` | Primera publicada, resto borrador |

### Inputs del workflow (GitHub Actions UI)

| Input | Descripción |
|-------|-------------|
| `action` | `health` / `noticia` / `lote_noticias` / `evento` / `grupo` / `sala` |
| `payload` | JSON con los datos |
| `limite` | Número de items (−1 = todos) |
| `estado_defecto` | `draft` o `publish` |
| `auto_publish_first` | Primeros N publicados automáticamente |

---

## 12. Resolución de problemas

### ❌ `WP_USER y WP_APP_PASSWORD son obligatorias`

El fichero `.env` no está cargado o las variables están vacías.

```bash
# Verifica que el .env existe y tiene las variables
cat .env | grep WP_
# Recarga el entorno
source venv/bin/activate && python run_agent.py --action health
```

### ❌ `HTTP 401` al publicar en WordPress

La contraseña de aplicación es incorrecta o el usuario no existe.

1. En WP Admin → Usuarios → Tu Perfil → Contraseñas de Aplicación
2. Revoca la clave actual y genera una nueva
3. Actualiza `.env` y el GitHub Secret `WP_APP_PASSWORD`

### ❌ `HTTP 403` al publicar en WordPress

El usuario de WordPress no tiene permisos de `Editor` o `Administrador`.

1. En WP Admin → Usuarios → busca tu usuario
2. Cambia el Rol a **Editor** o **Administrador**

### ❌ `Error IA: 429`

Has alcanzado el límite de peticiones de la API de Gemini. El agente reintenta automáticamente tras 10 segundos. Si persiste:

- Usa el tier de pago de Google AI Studio
- Reduce `PUBLISH_LIMIT` para procesar menos items por ejecución

### ❌ Los eventos no aparecen en The Events Calendar

La API de TEC requiere que el plugin esté activo y la REST API de WP habilitada.

```bash
# Verifica el endpoint TEC
curl -u "usuario:password_app" https://cordobarock.es/wp-json/tribe/events/v1/events
```

Si responde `404`, el plugin no está activo o la versión no soporta la REST API.

### ❌ GitHub Actions no encuentra el workflow del gestor (`workflow_call`)

Asegúrate de que:
1. El fichero `.github/workflows/cordoba_rock_agent.yml` está en la rama `main`
2. El repo gestor-cordoba-rock es público o el Agente 1 tiene acceso como colaborador
3. La referencia al workflow usa exactamente `@main` (o el nombre de tu rama principal)

---

## Checklist de puesta en marcha

```
[ ] 1. Repositorio clonado y entorno virtual creado
[ ] 2. Dependencias instaladas (pip install -r requirements.txt)
[ ] 3. .env creado con credenciales válidas
[ ] 4. Contraseña de Aplicación WP generada (la anterior revocada si existía)
[ ] 5. API Key Gemini generada (la anterior revocada si estaba en el código)
[ ] 6. Health check local correcto (todos los checks en ✅)
[ ] 7. GitHub Secrets configurados (WP_URL, WP_USER, WP_APP_PASSWORD, GEMINI_API_KEY)
[ ] 8. Health check en GitHub Actions correcto
[ ] 9. Prueba de noticia en borrador (local) ✓
[ ] 10. Prueba de lote en borrador (local con --limite 2) ✓
[ ] 11. Prueba de lote en GitHub Actions (manual, estado: draft) ✓
[ ] 12. Integración con Agente 1 configurada
[ ] 13. Primeros items revisados en WP → aprobados o ajustados
[ ] 14. (Opcional) Activar auto_publish_first: 1 tras validar calidad
```
