"""CLI Runner for NarrativeForge."""

import argparse
import sys
from pathlib import Path

from src.cli import commands
from src.cli.exceptions import CLIError
from src.cli.logger import logger


def main() -> None:
    """Entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="narrative",
        description="NarrativeForge - CLI de generación de relatos de terror",
        epilog="Usa --help después de un comando para ver más detalles.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output_stories/"),
        help="Directorio de output",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "gemini", "mock"],
        help="Proveedor de LLM a utilizar (sobrescribe .env)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generar historia completa (plan + beats narrados)",
    )
    generate_parser.add_argument(
        "--story-id",
        help="ID de historia existente en DB (formato: nombre_timestamp)",
    )
    generate_parser.add_argument("--title", help="Título de la historia")
    generate_parser.add_argument("--protagonist", help="Protagonista")
    generate_parser.add_argument(
        "--relator",
        default="tercera_persona",
        choices=["primera_persona", "tercera_persona"],
        help="Tipo de relator",
    )
    generate_parser.add_argument("--escenarios", help="Escenario(s)")
    generate_parser.add_argument("--sinopsis", help="Sinopsis de la historia")
    generate_parser.add_argument(
        "--atmosfera",
        help="Atmósfera de la historia",
    )
    generate_parser.add_argument(
        "--input",
        help="Archivo markdown de input (en input_stories/)",
    )
    generate_parser.add_argument("--mock", action="store_true", help="Usar Mock LLM (solo para tests)")
    generate_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Genera debug_prompts_responses_YYYYMMDDHHМM.md con prompts y respuestas completas",
    )
    generate_parser.add_argument(
        "--hasta",
        help="Checkpoint para detener el pipeline (Spec-040). Valores: analyst, mapper:1..5, voz:1..5, journal:1..5",
    )
    generate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output_stories/"),
        help="Directorio de output",
    )

    plan_parser = subparsers.add_parser("plan", help="Generar solo el plan (beats)")
    plan_parser.add_argument("--title", required=True, help="Título")
    plan_parser.add_argument("--mock", action="store_true", help="Usar Mock LLM (solo para tests)")
    plan_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output_stories/"),
        help="Directorio de output",
    )

    narrate_parser = subparsers.add_parser("narrate", help="Narrar beats específicos")
    narrate_parser.add_argument("--story-id", required=True, help="UUID de la historia")
    narrate_parser.add_argument("--beats", required=True, help="Beats a narrar (csv: 1,2,3)")
    narrate_parser.add_argument("--mock", action="store_true", help="Usar Mock LLM (solo para tests)")

    export_parser = subparsers.add_parser("export", help="Exportar historia a archivo")
    export_parser.add_argument("--story-id", required=True, help="UUID de la historia")
    export_parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "json"],
        help="Formato de export",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output_stories/"),
        help="Directorio de output",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "generate":
            if args.story_id:
                commands.generate_from_db(
                    story_id=args.story_id,
                    use_mock=args.mock,
                    output_dir=args.output,
                    provider=args.provider,
                    debug=args.debug,
                )
            elif args.input:
                commands.generate(
                    title="",
                    protagonista="",
                    relator="",
                    escenarios="",
                    sinopsis="",
                    atmosfera="",
                    use_mock=args.mock,
                    output_dir=args.output,
                    provider=args.provider,
                    input_file=args.input,
                    debug=args.debug,
                    hasta=args.hasta,
                )
            else:
                # Validación de campos obligatorios para nueva historia SIN --input
                campos_faltantes = []
                if not args.title:
                    campos_faltantes.append("--title")
                if not args.protagonist:
                    campos_faltantes.append("--protagonist")
                if not args.escenarios:
                    campos_faltantes.append("--escenarios")
                if not args.sinopsis:
                    campos_faltantes.append("--sinopsis")
                if not args.atmosfera:
                    campos_faltantes.append("--atmosfera")

                if campos_faltantes:
                    print(
                        f"Error: Faltan argumentos obligatorios: {', '.join(campos_faltantes)}",
                        file=sys.stderr,
                    )
                    print(
                        "Usa --help para ver todos los parámetros o provee --story-id.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                commands.generate(
                    title=args.title,
                    protagonista=args.protagonist,
                    relator=args.relator or "tercera_persona",
                    escenarios=args.escenarios,
                    sinopsis=args.sinopsis,
                    atmosfera=args.atmosfera,
                    use_mock=args.mock,
                    output_dir=args.output,
                    provider=args.provider,
                    input_file=args.input,
                    debug=args.debug,
                    hasta=args.hasta,
                )
        elif args.command == "plan":
            commands.plan(
                title=args.title,
                use_mock=args.mock,
                output_dir=args.output,
            )
        elif args.command == "narrate":
            commands.narrate(
                story_id=args.story_id,
                beats=args.beats,
                use_mock=args.mock,
            )
        elif args.command == "export":
            commands.export_(
                story_id=args.story_id,
                format=args.format,
                output_dir=args.output,
            )
    except CLIError as e:
        logger.error(f"[CLI] {e.message}", module="runner", line=1)
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(e.exit_code)
    except Exception as e:
        logger.error(f"[ERROR_INESPERADO] {str(e)}", module="runner", line=1)
        print(f"Error inesperado: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
