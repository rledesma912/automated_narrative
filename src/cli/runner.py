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

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generar historia completa (plan + beats narrados)",
    )
    generate_parser.add_argument("--title", required=True, help="Título de la historia")
    generate_parser.add_argument("--protagonist", required=True, help="Protagonista")
    generate_parser.add_argument(
        "--relator",
        default="tercera_persona",
        choices=["primera_persona", "tercera_persona"],
        help="Tipo de relator",
    )
    generate_parser.add_argument("--escenarios", required=True, help="Escenario(s)")
    generate_parser.add_argument("--sinopsis", required=True, help="Sinopsis de la historia")
    generate_parser.add_argument(
        "--atmosfera",
        required=True,
        help="Atmósfera de la historia",
    )
    generate_parser.add_argument("--beats", type=int, default=10, help="Cantidad de beats")
    generate_parser.add_argument("--real", action="store_true", help="Usar Ollama real (no Mock)")
    generate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output_stories/"),
        help="Directorio de output",
    )

    plan_parser = subparsers.add_parser("plan", help="Generar solo el plan (beats)")
    plan_parser.add_argument("--title", required=True, help="Título")
    plan_parser.add_argument("--beats", type=int, default=10, help="Cantidad de beats")
    plan_parser.add_argument(
        "--mock", action="store_true", default=True, help="Usar Mock (default)"
    )
    plan_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output_stories/"),
        help="Directorio de output",
    )

    narrate_parser = subparsers.add_parser("narrate", help="Narrar beats específicos")
    narrate_parser.add_argument("--story-id", required=True, help="UUID de la historia")
    narrate_parser.add_argument("--beats", required=True, help="Beats a narrar (csv: 1,2,3)")
    narrate_parser.add_argument("--real", action="store_true", help="Usar Ollama real")

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
            commands.generate(
                title=args.title,
                protagonista=args.protagonist,
                relator=args.relator,
                escenarios=args.escenarios,
                sinopsis=args.sinopsis,
                atmosfera=args.atmosfera,
                num_beats=args.beats,
                use_mock=not args.real,
                output_dir=args.output,
            )
        elif args.command == "plan":
            commands.plan(
                title=args.title,
                num_beats=args.beats,
                use_mock=args.mock,
                output_dir=args.output,
            )
        elif args.command == "narrate":
            commands.narrate(
                story_id=args.story_id,
                beats=args.beats,
                use_mock=not args.real,
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
        logger.error(f"[UNEXPECTED] {str(e)}", module="runner", line=1)
        print(f"Error inesperado: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
