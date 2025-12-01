# MojoGL

OpenGL bindings for Mojo, automatically generated from the Khronos OpenGL registry.

## Features

- Auto-generated bindings from official OpenGL XML registry
- Support for multiple OpenGL versions (3.0 to 4.6)
- Type-safe Mojo function signatures
- Comprehensive test suite
- Cross-platform support

## Quick Start

### Generate Bindings

```bash
# Install generator
uv add mojogl-generator

# Generate OpenGL 4.6 core bindings
uv run mojogl-generate --download --version 4.6 --output-dir mojo/mojogl

# Generate for specific version  
uv run mojogl-generate --version 3.3 --output-dir mojo/mojogl
```

### Use in Mojo Code

```mojo
from sys.ffi import OwnedDLHandle
from mojogl.gl_loader import load_gl_core_4_6
from mojogl.gl_enums import GL_COLOR_BUFFER_BIT
from mojogl.gl_types import GLbitfield

fn main() raises:
    # Load OpenGL library (platform-specific)
    var lib = OwnedDLHandle("libGL.so.1")  # Linux
    # var lib = OwnedDLHandle("opengl32.dll")  # Windows
    # var lib = OwnedDLHandle("/System/Library/Frameworks/OpenGL.framework/OpenGL")  # macOS
    
    # Load function pointers
    load_gl_core_4_6(lib)
    
    # Use OpenGL functions
    glClear(GL_COLOR_BUFFER_BIT)
    glClearColor(0.2, 0.3, 0.3, 1.0)
```

## Project Structure

```
mojogl/
├── mojo/mojogl/                # Generated Mojo package
│   ├── __init__.mojo           # Package init
│   ├── gl_types.mojo           # Type aliases (GLint, GLfloat, etc.)
│   ├── gl_enums.mojo           # OpenGL constants
│   ├── gl_core_4_6.mojo        # Function declarations
│   ├── gl_loader.mojo          # Dynamic loading functions
│   └── examples/               # Example programs
├── src/mojogl_generator/       # Python generator package
├── tests/                      # Python tests for generator
└── pyproject.toml              # Python package configuration
```

## Development

### Running Tests

```bash
# Install with dev dependencies
uv sync --extra dev

# Run generator tests
uv run pytest

# Generate bindings for testing
uv run mojogl-generate --download --output-dir mojo/mojogl
```

### Supported OpenGL Versions

- OpenGL 3.0+
- Core and compatibility profiles
- Extension support (future)

### Contributing

1. Ensure all tests pass
2. Follow existing code style
3. Add tests for new functionality
4. Update documentation as needed

## License

This project follows the same licensing as the Khronos OpenGL registry.