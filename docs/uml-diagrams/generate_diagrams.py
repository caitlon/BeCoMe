#!/usr/bin/env python3
"""Generate PNG images from PlantUML source files for all language versions."""

import shutil
import subprocess
import sys
from pathlib import Path


def _check_plantuml() -> str:
    """Return path to plantuml executable or exit with an error."""
    path = shutil.which("plantuml")
    if path is None:
        print(
            "Error: plantuml CLI not found in PATH.\nInstall via Homebrew: brew install plantuml",
            file=sys.stderr,
        )
        sys.exit(1)
    return path


def generate_diagram(plantuml_bin: str, puml_file: Path, output_file: Path) -> None:
    """Generate PNG from PlantUML source using local CLI with pipe mode."""
    print(f"  Generating {output_file.name}...")
    with open(puml_file, "rb") as src, open(output_file, "wb") as dst:
        result = subprocess.run(  # noqa: S603 -- fixed plantuml argv, no shell, no user input
            [plantuml_bin, "-tpng", "-pipe"],
            stdin=src,
            stdout=dst,
            stderr=subprocess.PIPE,
            text=False,
        )
    if result.returncode != 0:
        output_file.unlink(missing_ok=True)
        stderr = result.stderr.decode().strip() if result.stderr else ""
        raise RuntimeError(stderr or f"plantuml exited with code {result.returncode}")
    print(f"  ✓ {output_file.name}")


def main() -> None:
    """Generate all UML diagrams.

    English diagrams live at the top level; the Czech localization (kept local
    only) is regenerated into ``cs/`` when that directory is present.
    """
    plantuml_bin = _check_plantuml()
    base_dir = Path(__file__).parent
    lang_roots = {"en": base_dir, "cs": base_dir / "cs"}
    diagrams = [
        "class-diagram",
        "class-diagram-patterns",
        "sequence-diagram",
        "activity-diagram",
        "activity-diagram-simplified",
    ]
    failed = False

    for lang, root in lang_roots.items():
        print(f"\n[{lang.upper()}] Generating diagrams...")
        puml_dir = root / "diagrams" / "puml"
        png_dir = root / "diagrams" / "png"

        if not puml_dir.exists():
            print(f"  ⚠ Directory {puml_dir} not found, skipping")
            continue

        png_dir.mkdir(parents=True, exist_ok=True)

        for name in diagrams:
            puml_file = puml_dir / f"{name}.puml"
            png_file = png_dir / f"{name}.png"

            if not puml_file.exists():
                print(f"  ⚠ {name}.puml not found, skipping")
                continue

            try:
                generate_diagram(plantuml_bin, puml_file, png_file)
            except Exception as e:
                print(f"  ✗ {name}: {e}", file=sys.stderr)
                failed = True

    print("\nDone.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
