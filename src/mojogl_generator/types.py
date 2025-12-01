"""Data types for OpenGL registry parsing."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GLType:
    """Represents an OpenGL type definition."""

    name: str  # "GLint"
    c_decl: str  # "typedef int GLint;"
    mojo_type: str  # "Int32"


@dataclass
class GLEnum:
    """Represents an OpenGL enum constant."""

    name: str  # "GL_COLOR_BUFFER_BIT"
    value: int  # 0x00004000
    group: Optional[str] = None  # logical grouping, e.g. "ClearBufferMask"


@dataclass
class GLParam:
    """Represents a function parameter."""

    name: str  # "target"
    gl_type: str  # "GLenum"
    pointer_depth: int  # 0, 1, 2, etc.
    is_const: bool = False
    is_array: bool = False


@dataclass
class GLCommand:
    """Represents an OpenGL function/command."""

    name: str  # "glClear"
    return_type: str  # "void" or "GLenum"
    params: list[GLParam] = field(default_factory=list)
    version: Optional[str] = None  # "4.6"
    profiles: set[str] = field(default_factory=set)  # {"core"} or {"compatibility"}
    extensions: set[str] = field(default_factory=set)
