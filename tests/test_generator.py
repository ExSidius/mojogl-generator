#!/usr/bin/env python3
"""Tests for the OpenGL binding generator."""

import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
import tempfile

from mojogl_generator import GLRegistry, GLType, GLEnum, GLParam, GLCommand


class TestGLTypeMapping:
    """Test GL type to Mojo type mapping."""

    def test_basic_types(self):
        registry = GLRegistry()

        assert registry.c_to_mojo["GLint"] == "Int32"
        assert registry.c_to_mojo["GLfloat"] == "Float32"
        assert registry.c_to_mojo["GLdouble"] == "Float64"
        assert registry.c_to_mojo["GLuint"] == "UInt32"
        assert registry.c_to_mojo["void"] == "NoneType"

    def test_pointer_conversion(self):
        registry = GLRegistry()

        # Test single pointer
        param = GLParam(name="data", gl_type="GLfloat", pointer_depth=1)
        result = registry.convert_param_to_mojo(param)
        assert result == "Pointer[Float32]"

        # Test double pointer
        param = GLParam(name="data", gl_type="GLint", pointer_depth=2)
        result = registry.convert_param_to_mojo(param)
        assert result == "Pointer[Pointer[Int32]]"

        # Test void pointer
        param = GLParam(name="data", gl_type="void", pointer_depth=1)
        result = registry.convert_param_to_mojo(param)
        assert result == "Pointer[Void]"


class TestXMLParsing:
    """Test XML parsing functionality."""

    def test_parse_types(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <registry>
            <types>
                <type>typedef float <name>GLfloat</name>;</type>
                <type>typedef int <name>GLint</name>;</type>
            </types>
        </registry>"""

        root = ET.fromstring(xml_content)
        registry = GLRegistry()
        registry.parse_types(root)

        assert "GLfloat" in registry.types
        assert registry.types["GLfloat"].mojo_type == "Float32"
        assert "GLint" in registry.types
        assert registry.types["GLint"].mojo_type == "Int32"

    def test_parse_enums(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <registry>
            <enums group="ClearBufferMask">
                <enum value="0x00004000" name="GL_COLOR_BUFFER_BIT"/>
                <enum value="0x00000100" name="GL_DEPTH_BUFFER_BIT"/>
            </enums>
        </registry>"""

        root = ET.fromstring(xml_content)
        registry = GLRegistry()
        registry.parse_enums(root)

        assert "GL_COLOR_BUFFER_BIT" in registry.enums
        assert registry.enums["GL_COLOR_BUFFER_BIT"].value == 0x00004000
        assert registry.enums["GL_COLOR_BUFFER_BIT"].group == "ClearBufferMask"

    def test_parse_simple_command(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <registry>
            <commands>
                <command>
                    <proto>void <name>glClear</name></proto>
                    <param><ptype>GLbitfield</ptype> <name>mask</name></param>
                </command>
            </commands>
        </registry>"""

        root = ET.fromstring(xml_content)
        registry = GLRegistry()
        registry.parse_commands(root)

        assert "glClear" in registry.commands
        cmd = registry.commands["glClear"]
        assert cmd.name == "glClear"
        assert cmd.return_type == "void"
        assert len(cmd.params) == 1
        assert cmd.params[0].name == "mask"
        assert cmd.params[0].gl_type == "GLbitfield"
        assert cmd.params[0].pointer_depth == 0

    def test_parse_command_with_pointer(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <registry>
            <commands>
                <command>
                    <proto>void <name>glBufferData</name></proto>
                    <param><ptype>GLenum</ptype> <name>target</name></param>
                    <param><ptype>GLsizeiptr</ptype> <name>size</name></param>
                    <param>const void *<name>data</name></param>
                    <param><ptype>GLenum</ptype> <name>usage</name></param>
                </command>
            </commands>
        </registry>"""

        root = ET.fromstring(xml_content)
        registry = GLRegistry()
        registry.parse_commands(root)

        assert "glBufferData" in registry.commands
        cmd = registry.commands["glBufferData"]
        assert cmd.name == "glBufferData"
        assert len(cmd.params) == 4

        # Check the void* parameter
        data_param = cmd.params[2]
        assert data_param.name == "data"
        assert data_param.pointer_depth == 1
        assert data_param.is_const


class TestVersionFiltering:
    """Test OpenGL version filtering."""

    def test_feature_parsing(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <registry>
            <feature api="gl" number="3.0">
                <require>
                    <command name="glClear"/>
                    <command name="glDrawArrays"/>
                </require>
            </feature>
            <feature api="gl" number="4.0">
                <require>
                    <command name="glBlendFuncSeparate"/>
                </require>
            </feature>
        </registry>"""

        root = ET.fromstring(xml_content)
        registry = GLRegistry()
        registry.parse_features(root)

        assert "3.0" in registry.features
        assert "glClear" in registry.features["3.0"]
        assert "glDrawArrays" in registry.features["3.0"]

        assert "4.0" in registry.features
        assert "glBlendFuncSeparate" in registry.features["4.0"]

    def test_get_commands_for_version(self):
        registry = GLRegistry()
        registry.features = {
            "3.0": {"glClear", "glDrawArrays"},
            "3.3": {"glBindVertexArray"},
            "4.0": {"glBlendFuncSeparate"},
            "4.6": {"glSpecializeShader"},
        }

        # Test 3.3 includes 3.0 commands
        commands_3_3 = registry.get_commands_for_version("3.3")
        assert "glClear" in commands_3_3
        assert "glDrawArrays" in commands_3_3
        assert "glBindVertexArray" in commands_3_3
        assert "glBlendFuncSeparate" not in commands_3_3

        # Test 4.6 includes all previous commands
        commands_4_6 = registry.get_commands_for_version("4.6")
        assert "glClear" in commands_4_6
        assert "glDrawArrays" in commands_4_6
        assert "glBindVertexArray" in commands_4_6
        assert "glBlendFuncSeparate" in commands_4_6
        assert "glSpecializeShader" in commands_4_6


class TestCodeGeneration:
    """Test Mojo code generation."""

    def test_generate_types_file(self):
        registry = GLRegistry()
        registry.types = {
            "GLint": GLType("GLint", "typedef int GLint;", "Int32"),
            "GLfloat": GLType("GLfloat", "typedef float GLfloat;", "Float32"),
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mojo", delete=False) as f:
            output_path = Path(f.name)

        try:
            registry.generate_types_file(output_path)
            content = output_path.read_text()

            assert "# AUTOGENERATED. DO NOT EDIT." in content
            assert "alias GLint = Int32" in content
            assert "alias GLfloat = Float32" in content

        finally:
            output_path.unlink()

    def test_generate_enums_file(self):
        registry = GLRegistry()
        registry.enums = {
            "GL_COLOR_BUFFER_BIT": GLEnum(
                "GL_COLOR_BUFFER_BIT", 0x00004000, "ClearBufferMask"
            ),
            "GL_DEPTH_BUFFER_BIT": GLEnum(
                "GL_DEPTH_BUFFER_BIT", 0x00000100, "ClearBufferMask"
            ),
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mojo", delete=False) as f:
            output_path = Path(f.name)

        try:
            registry.generate_enums_file(output_path)
            content = output_path.read_text()

            assert "# AUTOGENERATED. DO NOT EDIT." in content
            assert "alias GL_COLOR_BUFFER_BIT = 0x00004000" in content
            assert "alias GL_DEPTH_BUFFER_BIT = 0x00000100" in content
            assert "# ClearBufferMask" in content

        finally:
            output_path.unlink()

    def test_generate_core_file(self):
        registry = GLRegistry()
        registry.commands = {
            "glClear": GLCommand(
                name="glClear",
                return_type="void",
                params=[GLParam("mask", "GLbitfield", 0)],
            )
        }
        registry.features = {"4.6": {"glClear"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mojo", delete=False) as f:
            output_path = Path(f.name)

        try:
            registry.generate_core_file(output_path, "4.6")
            content = output_path.read_text()

            assert "# AUTOGENERATED. DO NOT EDIT." in content
            assert "from .gl_types import *" in content
            assert "var glClear: fn(mask: UInt32) -> NoneType" in content

        finally:
            output_path.unlink()


class TestIntegration:
    """Integration tests using real XML snippets."""

    def test_minimal_gl_xml(self):
        """Test with a minimal but realistic gl.xml structure."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <registry>
            <types>
                <type>typedef unsigned int <name>GLbitfield</name>;</type>
                <type>typedef float <name>GLfloat</name>;</type>
            </types>
            <enums group="ClearBufferMask">
                <enum value="0x00004000" name="GL_COLOR_BUFFER_BIT"/>
            </enums>
            <commands>
                <command>
                    <proto>void <name>glClear</name></proto>
                    <param><ptype>GLbitfield</ptype> <name>mask</name></param>
                </command>
                <command>
                    <proto>void <name>glClearColor</name></proto>
                    <param><ptype>GLfloat</ptype> <name>red</name></param>
                    <param><ptype>GLfloat</ptype> <name>green</name></param>
                    <param><ptype>GLfloat</ptype> <name>blue</name></param>
                    <param><ptype>GLfloat</ptype> <name>alpha</name></param>
                </command>
            </commands>
            <feature api="gl" number="1.0">
                <require>
                    <command name="glClear"/>
                    <command name="glClearColor"/>
                </require>
            </feature>
        </registry>"""

        root = ET.fromstring(xml_content)
        registry = GLRegistry()

        # Parse all sections
        registry.parse_types(root)
        registry.parse_enums(root)
        registry.parse_commands(root)
        registry.parse_features(root)

        # Verify parsing worked correctly
        assert len(registry.types) >= 2
        assert len(registry.enums) >= 1
        assert len(registry.commands) >= 2
        assert len(registry.features) >= 1

        # Test command filtering
        commands_1_0 = registry.get_commands_for_version("1.0")
        assert "glClear" in commands_1_0
        assert "glClearColor" in commands_1_0

        # Test type conversion
        clear_cmd = registry.commands["glClear"]
        mask_param = clear_cmd.params[0]
        mojo_type = registry.convert_param_to_mojo(mask_param)
        assert mojo_type == "UInt32"  # GLbitfield -> UInt32


if __name__ == "__main__":
    pytest.main([__file__])
