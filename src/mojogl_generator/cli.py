"""Command line interface for the MojoGL generator."""

import argparse
import sys
import urllib.request
from pathlib import Path

from .registry import GLRegistry


def download_gl_xml(output_path: Path, force: bool = False) -> None:
    """Download the latest gl.xml from Khronos registry."""
    if output_path.exists() and not force:
        print(f"gl.xml already exists at {output_path}. Use --force to re-download.")
        return

    url = (
        "https://raw.githubusercontent.com/KhronosGroup/OpenGL-Registry/main/xml/gl.xml"
    )
    print(f"Downloading gl.xml from {url}...")

    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"Downloaded gl.xml to {output_path}")
    except Exception as e:
        print(f"Failed to download gl.xml: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate Mojo OpenGL bindings")
    parser.add_argument(
        "--version", default="4.6", help="Target OpenGL version (default: 4.6)"
    )
    parser.add_argument(
        "--profile", default="core", help="Target profile (default: core)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("mojo/mojogl"),
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--gl-xml", type=Path, default=Path("gl.xml"), help="Path to gl.xml file"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download latest gl.xml from Khronos registry",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-download of gl.xml"
    )

    args = parser.parse_args()

    # Download gl.xml if requested
    if args.download or not args.gl_xml.exists():
        download_gl_xml(args.gl_xml, args.force)

    if not args.gl_xml.exists():
        print(f"gl.xml not found at {args.gl_xml}. Use --download to fetch it.")
        sys.exit(1)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating OpenGL {args.version} {args.profile} bindings...")

    # Parse registry
    registry = GLRegistry()
    root = registry.load_gl_registry(str(args.gl_xml))

    registry.parse_types(root)
    registry.parse_enums(root)
    registry.parse_commands(root)
    registry.parse_features(root)

    # Generate files
    version_safe = args.version.replace(".", "_")

    print("Generating gl_types.mojo...")
    registry.generate_types_file(args.output_dir / "gl_types.mojo")

    print("Generating gl_enums.mojo...")
    registry.generate_enums_file(args.output_dir / "gl_enums.mojo")

    print(f"Generating gl_core_{version_safe}.mojo...")
    registry.generate_core_file(
        args.output_dir / f"gl_core_{version_safe}.mojo", args.version
    )

    print("Generating gl_loader.mojo...")
    registry.generate_loader_file(args.output_dir / "gl_loader.mojo", args.version)

    # Generate package init file
    init_content = f"""# MojoGL - OpenGL bindings for Mojo
# Auto-generated bindings for OpenGL {args.version}

from .gl_types import *
from .gl_enums import *
from .gl_core_{version_safe} import *
from .gl_loader import *
"""
    (args.output_dir / "__init__.mojo").write_text(init_content)

    command_count = len(registry.get_commands_for_version(args.version))
    print(f"Generated bindings for {command_count} OpenGL {args.version} functions")
    print(f"Output written to: {args.output_dir}")


if __name__ == "__main__":
    main()
