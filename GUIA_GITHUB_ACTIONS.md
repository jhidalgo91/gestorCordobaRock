# Guía Rápida: Actualización de GitHub Actions para Multi-Modelo IA

Con la nueva actualización, el agente y el tracker soportan múltiples proveedores de IA (Gemini, OpenAI y Anthropic) y aplican un retraso estratégico de 2 minutos (120s) entre peticiones para evitar bloqueos por *Rate Limit*.

Para asegurar que todo funciona correctamente en GitHub Actions tras estos cambios, debes revisar los siguientes puntos en la configuración de tus repositorios.

---

## 1. Configuración de API Keys (Secrets)

Ya no es estrictamente obligatorio usar Gemini. El sistema permite usar ChatGPT o Claude configurando sus respectivas variables de entorno. 

Ve a **Settings → Secrets and variables → Actions** en ambos repositorios (`CordobaRock` y `gestorCordobaRock`).

Asegúrate de que exista **AL MENOS UNA** de las siguientes *Repository Secrets*:

| Secret | Descripción | Requerido si usas... |
|---|---|---|
| `GEMINI_API_KEY` | Clave de Google AI Studio | Modelos `gemini-*` (por defecto) |
| `OPENAI_API_KEY` | Clave de OpenAI | Modelos `gpt-*` (ej. `gpt-4o`) |
| `ANTHROPIC_API_KEY` | Clave de Anthropic | Modelos `claude-*` (ej. `claude-3-5-sonnet`) |

*Nota: Puedes tener las tres configuradas a la vez e ir alternando de modelo.*

## 2. Configuración del Modelo (Variables)

Para decirle al sistema qué IA debe usar, hemos reemplazado la variable `GEMINI_MODEL` por `AI_MODEL`.

Ve a la pestaña **Variables** (misma sección que los Secrets):
- Si tenías definida la variable `GEMINI_MODEL`, elimínala o cámbiale el nombre a `AI_MODEL`.
- Si no la defines, el sistema usará `gemini-3.5-flash` por defecto.

Ejemplos de valores válidos para `AI_MODEL`:
- `gemini-3.5-flash`
- `gpt-4o`
- `claude-3-5-sonnet-20240620`

## 3. Tiempos de Ejecución (¡Muy Importante!)

Hemos introducido un retraso fijo de **2 minutos (`time.sleep(120)`)** antes de cada llamada a la API.

**Consecuencias para GitHub Actions:**
- Si un flujo procesa 5 noticias de forma secuencial, tardará **al menos 10 minutos**.
- GitHub Actions tiene un límite de tiempo global (usualmente 6 horas por job en repositorios gratuitos), pero no deberías acercarte a este límite a menos que proceses más de 150 noticias de golpe.
- Notarás que en la pestaña de "Actions", el estado del workflow permanecerá "In progress" durante bastante más tiempo del habitual. Esto es el comportamiento esperado.

### Recomendación de timeouts:
Si por seguridad prefieres asegurar que el workflow no se quede "colgado" indefinidamente, puedes editar los archivos YAML en `.github/workflows/` y añadir un `timeout-minutes`:

```yaml
jobs:
  run-tracker:
    runs-on: ubuntu-latest
    timeout-minutes: 60  # Cancela el proceso si dura más de 1 hora
    steps:
      ...
```

## Resumen de Pasos a realizar ahora mismo

1. Ir a GitHub > Settings > Secrets and Variables en `CordobaRock`.
2. Añadir la API Key del modelo que quieras usar (si vas a seguir usando Gemini, ya la tienes).
3. (Opcional) Modificar/crear la Variable `AI_MODEL` indicando el modelo.
4. Repetir pasos 1, 2 y 3 en el repositorio `gestorCordobaRock`.
5. ¡Listo! La próxima ejecución programada aplicará la pausa de 2 minutos automáticamente.
