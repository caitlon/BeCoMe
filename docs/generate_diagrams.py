#!/usr/bin/env python3
"""
Generate PNG images from PlantUML diagram files.

This script reads .puml files and generates PNG images using
the PlantUML online service.
"""

import sys
from pathlib import Path

import plantuml  # type: ignore[import-untyped]


def generate_diagram(puml_file: Path, output_file: Path) -> None:
    """
    Generate PNG diagram from PlantUML file.

    Args:
        puml_file: Path to .puml source file
        output_file: Path to output PNG file
    """
    print(f"Generating {output_file.name} from {puml_file.name}...")

    # Create PlantUML server connection
    server = plantuml.PlantUML(url="http://www.plantuml.com/plantuml/img/")

    # Generate PNG
    server.processes_file(filename=str(puml_file), outfile=str(output_file))

    print(f"✓ Generated {output_file}")


def main() -> None:
    """Generate all UML diagrams."""
    # Define paths
    docs_dir: Path = Path(__file__).parent
    uml_dir: Path = docs_dir / "uml-diagrams"

    # List of diagrams to generate
    diagrams: list[tuple[str, str]] = [
        ("class-diagram.puml", "class-diagram.png"),
        ("sequence-diagram.puml", "sequence-diagram.png"),
        ("activity-diagram.puml", "activity-diagram.png"),
    ]

    # Generate each diagram
    for puml_name, png_name in diagrams:
        puml_file: Path = uml_dir / puml_name
        output_file: Path = uml_dir / png_name

        if not puml_file.exists():
            print(f"⚠ Skipping {puml_name} (file not found)")
            continue

        try:
            generate_diagram(puml_file, output_file)
        except Exception as e:
            print(f"✗ Error generating {png_name}: {e}", file=sys.stderr)
            continue

    print("\n✓ All diagrams generated successfully!")


if __name__ == "__main__":
    main()
