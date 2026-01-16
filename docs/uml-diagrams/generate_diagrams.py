#!/usr/bin/env python3
"""Generate PNG images from PlantUML source files."""

import sys
from pathlib import Path

import plantuml  # type: ignore[import-untyped]


def generate_diagram(puml_file: Path, output_file: Path) -> None:
    """Generate PNG from PlantUML source."""
    print(f"Generating {output_file.name}...")
    server = plantuml.PlantUML(url="http://www.plantuml.com/plantuml/img/")
    server.processes_file(filename=str(puml_file), outfile=str(output_file))
    print(f"✓ {output_file.name}")


def main() -> None:
    """Generate all UML diagrams."""
    base_dir = Path(__file__).parent
    puml_dir = base_dir / "diagrams" / "puml"
    png_dir = base_dir / "diagrams" / "png"

    diagrams = ["class-diagram", "sequence-diagram", "activity-diagram"]

    for name in diagrams:
        puml_file = puml_dir / f"{name}.puml"
        png_file = png_dir / f"{name}.png"

        if not puml_file.exists():
            print(f"⚠ {name}.puml not found, skipping")
            continue

        try:
            generate_diagram(puml_file, png_file)
        except Exception as e:
            print(f"✗ {name}: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
