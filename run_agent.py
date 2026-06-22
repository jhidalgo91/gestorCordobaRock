#!/usr/bin/env python3
"""
run_agent.py
------------
Entrypoint CLI del agente autónomo Córdoba Rock.

Uso:
  python run_agent.py --action health
  python run_agent.py --action noticia --input '{"titulo": "Concierto..."}'
  python run_agent.py --action evento --input-file evento.json
  python run_agent.py --action grupo --input-file grupo.json
  python run_agent.py --action sala --input-file sala.json

GitHub Actions lo invoca con:
  python run_agent.py --action ${{ inputs.action }} --input '${{ inputs.payload }}'

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
    pass  # En GitHub Actions las vars vienen de Secrets, no hace falta dotenv


def main():
    parser = argparse.ArgumentParser(description="Agente autónomo Córdoba Rock")
    parser.add_argument(
        "--action",
        required=True,
        choices=["health", "noticia", "evento", "grupo", "sala"],
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

    args = parser.parse_args()

    # --- Cargar payload ---
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

    # --- Importar core (aquí para que los errores de config sean claros) ---
    try:
        import agent_core as core
    except EnvironmentError as e:
        print(json.dumps({"success": False, "message": str(e)}))
        sys.exit(1)

    # --- Ejecutar acción ---
    print(f"\n🚀 Córdoba Rock Agent | Acción: {args.action.upper()}\n{'─' * 50}")

    action_map = {
        "health": core.health_check,
        "noticia": core.publicar_noticia,
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
    print(f"\n{'─' * 50}")
    print("📊 RESULTADO:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Escribir resultado a fichero para que el workflow de GitHub Actions pueda leerlo
    with open("agent_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n💾 Resultado guardado en agent_result.json")

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
