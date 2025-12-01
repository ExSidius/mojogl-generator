"""OpenGL registry parsing and code generation."""

import xml.etree.ElementTree as ET
from pathlib import Path

from .types import GLCommand, GLEnum, GLParam, GLType


class GLRegistry:
    """Parser and code generator for OpenGL registry XML."""

    def __init__(self) -> None:
        self.types: dict[str, GLType] = {}
        self.enums: dict[str, GLEnum] = {}
        self.commands: dict[str, GLCommand] = {}
        self.features: dict[str, set[str]] = {}  # version -> command names
        self.extensions: dict[str, set[str]] = {}  # extension -> command names

        # C to Mojo type mapping
        self.c_to_mojo = {
            "void": "NoneType",
            "GLvoid": "NoneType",
            "GLbyte": "Int8",
            "GLshort": "Int16",
            "GLint": "Int32",
            "GLsizei": "Int32",
            "GLubyte": "UInt8",
            "GLushort": "UInt16",
            "GLuint": "UInt32",
            "GLboolean": "UInt8",
            "GLbitfield": "UInt32",
            "GLenum": "UInt32",
            "GLfloat": "Float32",
            "GLclampf": "Float32",
            "GLdouble": "Float64",
            "GLclampd": "Float64",
            "GLchar": "UInt8",
            "GLsync": "Pointer[UInt8]",  # Use UInt8 instead of Void
            "GLintptr": "Int",
            "GLsizeiptr": "Int",
            "GLint64": "Int64",
            "GLuint64": "UInt64",
            # Platform specific
            "GLDEBUGPROC": "Pointer[UInt8]",  # Use UInt8 instead of Void
        }

    def load_gl_registry(self, xml_path: str) -> ET.Element:
        """Load and parse the OpenGL registry XML."""
        tree = ET.parse(xml_path)
        return tree.getroot()

    def parse_types(self, root: ET.Element) -> None:
        """Parse type definitions from the registry."""
        types_group = root.find("types")
        if types_group is None:
            return

        for type_elem in types_group.findall("type"):
            name_elem = type_elem.find("name")
            if name_elem is None:
                continue

            type_name = name_elem.text
            if type_name is None:
                continue

            # Get the full C declaration
            c_decl = "".join(type_elem.itertext()).strip()

            # Map to Mojo type
            mojo_type = self.c_to_mojo.get(type_name, "Pointer[Void]")

            self.types[type_name] = GLType(
                name=type_name, c_decl=c_decl, mojo_type=mojo_type
            )

    def parse_enums(self, root: ET.Element) -> None:
        """Parse enum definitions from the registry."""
        for enums_group in root.findall("enums"):
            group_name = enums_group.get("group")

            for enum_elem in enums_group.findall("enum"):
                name = enum_elem.get("name")
                value_str = enum_elem.get("value")

                if not name or not value_str:
                    continue

                # Parse value (can be hex or decimal)
                try:
                    if value_str.startswith("0x"):
                        value = int(value_str, 16)
                    else:
                        value = int(value_str)
                except ValueError:
                    continue

                self.enums[name] = GLEnum(name=name, value=value, group=group_name)

    def parse_param(self, param_elem: ET.Element) -> GLParam:
        """Parse a function parameter."""
        name_elem = param_elem.find("name")
        ptype_elem = param_elem.find("ptype")

        if name_elem is None:
            raise ValueError("Parameter missing name")

        param_name = name_elem.text or ""

        # Determine type
        if ptype_elem is not None:
            gl_type = ptype_elem.text or "void"
        else:
            # Look for type in text content
            text_content = "".join(param_elem.itertext()).strip()
            gl_type = "void" if "void" in text_content else "GLvoid"

        # Count pointer depth by counting '*' characters
        full_text = "".join(param_elem.itertext())
        pointer_depth = full_text.count("*")

        # Check for const
        is_const = "const" in full_text

        # Check for array notation
        is_array = "[" in full_text and "]" in full_text

        return GLParam(
            name=param_name,
            gl_type=gl_type,
            pointer_depth=pointer_depth,
            is_const=is_const,
            is_array=is_array,
        )

    def parse_commands(self, root: ET.Element) -> None:
        """Parse command definitions from the registry."""
        commands_group = root.find("commands")
        if commands_group is None:
            return

        for command_elem in commands_group.findall("command"):
            proto_elem = command_elem.find("proto")
            if proto_elem is None:
                continue

            # Get command name
            name_elem = proto_elem.find("name")
            if name_elem is None:
                continue
            cmd_name = name_elem.text

            # Get return type
            ptype_elem = proto_elem.find("ptype")
            if ptype_elem is not None:
                return_type = ptype_elem.text or "void"
            else:
                # Look for type in proto text
                proto_text = "".join(proto_elem.itertext()).strip()
                return_type = "void" if proto_text.startswith("void") else "GLvoid"

            # Parse parameters
            params = []
            for param_elem in command_elem.findall("param"):
                try:
                    param = self.parse_param(param_elem)
                    params.append(param)
                except ValueError:
                    continue  # Skip malformed parameters

            self.commands[cmd_name] = GLCommand(
                name=cmd_name, return_type=return_type, params=params
            )

    def parse_features(self, root: ET.Element) -> None:
        """Parse feature definitions (versions) from the registry."""
        for feature_elem in root.findall("feature"):
            api = feature_elem.get("api")
            number = feature_elem.get("number")

            if api != "gl" or not number:
                continue

            command_names = set()

            # Process <require> blocks
            for require_elem in feature_elem.findall("require"):
                for command_elem in require_elem.findall("command"):
                    cmd_name = command_elem.get("name")
                    if cmd_name:
                        command_names.add(cmd_name)

            # Process <remove> blocks (remove from previous versions)
            for remove_elem in feature_elem.findall("remove"):
                for command_elem in remove_elem.findall("command"):
                    cmd_name = command_elem.get("name")
                    if cmd_name and cmd_name in command_names:
                        command_names.remove(cmd_name)

            self.features[number] = command_names

    def get_commands_for_version(self, target_version: str) -> set[str]:
        """Get all commands available in a specific OpenGL version."""
        available_commands = set()

        # Sort versions and include all up to target
        sorted_versions = sorted(
            self.features.keys(), key=lambda v: tuple(map(int, v.split(".")))
        )

        target_tuple = tuple(map(int, target_version.split(".")))

        for version in sorted_versions:
            version_tuple = tuple(map(int, version.split(".")))
            if version_tuple <= target_tuple:
                available_commands.update(self.features[version])

        return available_commands

    def convert_param_to_mojo(self, param: GLParam) -> str:
        """Convert a GL parameter to Mojo syntax."""
        base_type = self.c_to_mojo.get(param.gl_type, "Pointer[UInt8]")

        if param.pointer_depth > 0:
            # For pointers, wrap in Pointer type
            for _ in range(param.pointer_depth):
                if base_type == "NoneType":
                    base_type = "Pointer[UInt8]"  # Use UInt8 instead of Void
                else:
                    base_type = f"Pointer[{base_type}]"

        return base_type

    def generate_types_file(self, output_path: Path) -> None:
        """Generate gl_types.mojo file."""
        content = [
            "# AUTOGENERATED. DO NOT EDIT.",
            "# Generated by mojogl-generator",
            "",
            "# OpenGL type aliases for Mojo",
            "",
        ]

        # Generate type aliases in a reasonable order
        type_order = [
            "GLbyte",
            "GLshort",
            "GLint",
            "GLsizei",
            "GLintptr",
            "GLsizeiptr",
            "GLint64",
            "GLubyte",
            "GLushort",
            "GLuint",
            "GLuint64",
            "GLboolean",
            "GLbitfield",
            "GLenum",
            "GLfloat",
            "GLclampf",
            "GLdouble",
            "GLclampd",
            "GLchar",
            "GLsync",
            "GLDEBUGPROC",
        ]

        for type_name in type_order:
            if type_name in self.types:
                mojo_type = self.types[type_name].mojo_type
                content.append(f"alias {type_name} = {mojo_type}")

        output_path.write_text("\n".join(content) + "\n")

    def generate_enums_file(self, output_path: Path) -> None:
        """Generate gl_enums.mojo file."""
        content = [
            "# AUTOGENERATED. DO NOT EDIT.",
            "# Generated by mojogl-generator",
            "",
            "# OpenGL constants",
            "",
        ]

        # Group enums by their group when available
        groups: dict[str, list[GLEnum]] = {}
        ungrouped = []

        for enum in self.enums.values():
            if enum.group:
                if enum.group not in groups:
                    groups[enum.group] = []
                groups[enum.group].append(enum)
            else:
                ungrouped.append(enum)

        # Output grouped enums
        for group_name, group_enums in sorted(groups.items()):
            content.append(f"# {group_name}")
            for enum in sorted(group_enums, key=lambda e: e.name):
                hex_value = f"0x{enum.value:08X}" if enum.value > 9 else str(enum.value)
                content.append(f"alias {enum.name} = {hex_value}")
            content.append("")

        # Output ungrouped enums
        if ungrouped:
            content.append("# Other constants")
            for enum in sorted(ungrouped, key=lambda e: e.name):
                hex_value = f"0x{enum.value:08X}" if enum.value > 9 else str(enum.value)
                content.append(f"alias {enum.name} = {hex_value}")

        output_path.write_text("\n".join(content) + "\n")

    def generate_core_file(self, output_path: Path, version: str) -> None:
        """Generate gl_core_X_Y.mojo file."""
        command_names = self.get_commands_for_version(version)

        content = [
            "# AUTOGENERATED. DO NOT EDIT.",
            f"# Generated by mojogl-generator for OpenGL {version}",
            "",
            "from .gl_types import *",
            "",
            "# Placeholder function for unloaded GL functions",
            "fn _gl_function_not_loaded() -> NoneType:",
            "    print(\"Error: OpenGL function called before loading library\")",
            "",
        ]

        # Generate function pointer variables with proper initialization
        for cmd_name in sorted(command_names):
            if cmd_name not in self.commands:
                continue

            cmd = self.commands[cmd_name]

            # Build parameter types (without names for function type)
            param_types = []
            for param in cmd.params:
                mojo_type = self.convert_param_to_mojo(param)
                param_types.append(mojo_type)

            # Build return type
            return_mojo_type = self.c_to_mojo.get(cmd.return_type, "NoneType")

            # Generate function type and variable with initialization
            param_type_str = ", ".join(param_types)
            fn_type = f"fn({param_type_str}) -> {return_mojo_type}"
            
            # Initialize with a placeholder function that has the correct signature
            content.append(f"var {cmd_name}: {fn_type} = {fn_type}(_gl_function_not_loaded)")

        output_path.write_text("\n".join(content) + "\n")

    def generate_loader_file(self, output_path: Path, version: str) -> None:
        """Generate gl_loader.mojo file."""
        command_names = self.get_commands_for_version(version)
        version_safe = version.replace(".", "_")

        content = [
            "# AUTOGENERATED. DO NOT EDIT.",
            f"# Generated by mojogl-generator for OpenGL {version}",
            "",
            "from sys import DLHandle",
            "from .gl_types import *",
            f"from .gl_core_{version_safe} import *",
            "",
            f"fn load_gl_core_{version_safe}(lib: DLHandle) raises:",
            '    """Load OpenGL function pointers from the given library handle."""',
        ]

        # Generate loader calls
        for cmd_name in sorted(command_names):
            if cmd_name not in self.commands:
                continue

            cmd = self.commands[cmd_name]

            # Build type signature for get_function
            param_types = []
            for param in cmd.params:
                mojo_type = self.convert_param_to_mojo(param)
                param_types.append(mojo_type)

            return_mojo_type = self.c_to_mojo.get(cmd.return_type, "NoneType")

            param_type_str = ", ".join(param_types)
            fn_type = f"fn({param_type_str}) -> {return_mojo_type}"

            content.append(
                f'    {cmd.name} = lib.get_function[{fn_type}]("{cmd.name}")'
            )

        output_path.write_text("\n".join(content) + "\n")
