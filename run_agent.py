#!/usr/bin/env python3
"""
run_agent.py
------------
Entrypoint CLI del agente autónomo Córdoba Rock.

Uso básico:
  python run_agent.py --action health
  python run_agent.py --action noticia --input '{"titulo": "Concierto..."}'
  python run_agent.py --action lote_noticias --input-file noticias.json
  python run_agent.py --action evento --input-file evento.json
  python run_agent.py --action grupo --input-file grupo.json
  python run_agent.py --action sala --input-file sala.json

Modo prueba (limita cuántos items se procesan):
  python run_agent.py --action lote_noticias --input-file noticias.json --limite 2
  python run_agent.py --action lote_noticias --input-file noticias.json --limite -1  # todos

Control de publicación:
  python run_agent.py --action lote_noticias --input-file noticias.json \\
      --limite 3 --estado-defecto draft --auto-publish-first 1

GitHub Actions lo invoca con variables de entorno y argumentos pasados como inputs.

Salida:
  El resultado se imprime en stdout como JSON.
  Exit code 0 = éxito, 1 = error.
"""

import sys
import json
import argparse

# Carga dotenv si existe (para desarrollo local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(
        description="Agente autónomo Córdoba Rock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["health", "noticia", "lote_noticias", "evento", "grupo", "sala"],
        help="Acción a ejecutar",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Payload JSON como string",
    )
    parser.add_argument(
        "--input-file",
        default=None,
        dest="input_file",
        help="Ruta a un fichero JSON con el payload",
    )

    # ── Parámetros de modo prueba ───────────────────────────────────────────
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        dest="limite",
        help=(
            "Número de items a procesar. "
            "N > 0 = procesar los primeros N. -1 = todos. "
            "Sobreescribe PUBLISH_LIMIT del entorno."
        ),
    )
    parser.add_argument(
        "--estado-defecto",
        default=None,
        dest="estado_defecto",
        choices=["draft", "publish"],
        help=(
            "Estado WP por defecto para los posts: 'draft' (borrador) o 'publish'. "
            "Sobreescribe DEFAULT_WP_STATUS del entorno."
        ),
    )
    parser.add_argument(
        "--auto-publish-first",
        type=int,
        default=None,
        dest="auto_publish_first",
        help=(
            "Auto-publicar los primeros N items del lote; el resto quedan en borrador. "
            "0 = todos usan --estado-defecto. "
            "Sobreescribe AUTO_PUBLISH_FIRST del entorno."
        ),
    )

    args = parser.parse_args()

    # --- Cargar payload base ---
    payload = {}
    if args.input:
        try:
            payload = json.loads(args.input)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "message": f"❌ JSON inválido en --input: {e}"}))
            sys.exit(1)
    elif args.input_file:
        try:
            with open(args.input_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(json.dumps({"success": False, "message": f"❌ Error leyendo fichero: {e}"}))
            sys.exit(1)

    # --- Inyectar parámetros CLI en el payload (sobreescriben lo que venga del fichero) ---
    if args.limite is not None:
        payload["limite"] = args.limite
    if args.estado_defecto is not None:
        payload["estado_defecto"] = args.estado_defecto
        # Para acciones individuales (noticia, evento, grupo) el campo es "estado"
        if args.action in ("noticia", "evento", "grupo"):
            payload.setdefault("estado", args.estado_defecto)
    if args.auto_publish_first is not None:
        payload["auto_publish_first"] = args.auto_publish_first

    # --- Importar core ---
    try:
        import agent_core as core
    except EnvironmentError as e:
        print(json.dumps({"success": False, "message": str(e)}))
        sys.exit(1)

    # --- Mostrar cabecera ---
    limite_txt = str(payload.get("limite", "env")) if args.action in ("lote_noticias",) else ""
    estado_txt = payload.get("estado_defecto", payload.get("estado", "env"))
    auto_txt = str(payload.get("auto_publish_first", "env")) if args.action == "lote_noticias" else ""

    print(f"\n🚀 Córdoba Rock Agent | Acción: {args.action.upper()}")
    if limite_txt:
        print(f"   Límite: {limite_txt} | Estado: {estado_txt} | Auto-publish primeros: {auto_txt}")
    print("─" * 55)

    # --- Mapeo de acciones ---
    action_map = {
        "health": core.health_check,
        "noticia": core.publicar_noticia,
        "lote_noticias": core.publicar_lote_noticias,
        "evento": core.publicar_evento,
        "grupo": core.publicar_grupo,
        "sala": core.publicar_sala,
    }

    handler = action_map[args.action]

    try:
        if args.action == "health":
            result = handler()
        else:
            result = handler(payload)
    except Exception as e:
        result = {"success": False, "message": f"❌ Error no esperado: {e}"}

    # --- Salida ---
    print(f"\n{'─' * 55}")
    print("📊 RESULTADO:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Guardar resultado para GitHub Actions
    with open("agent_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n💾 Resultado guardado en agent_result.json")

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
