"""MojoGL Generator - OpenGL binding generator for Mojo."""

__version__ = "0.1.0"

from .registry import GLRegistry
from .types import GLType, GLEnum, GLParam, GLCommand

__all__ = ["GLRegistry", "GLType", "GLEnum", "GLParam", "GLCommand"]
