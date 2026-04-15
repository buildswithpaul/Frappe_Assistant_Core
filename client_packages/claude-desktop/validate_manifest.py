#!/usr/bin/env python3
"""
Comprehensive manifest validation for Claude Desktop Extension

This script validates manifest.json according to the Claude Desktop Extension specification.
See BUILD.md for detailed documentation and the official Anthropic documentation:
https://www.anthropic.com/engineering/desktop-extensions
"""

import json
import os
import re
import sys
from urllib.parse import urlparse


def validate_manifest():
    """Validate manifest.json comprehensively"""
    print("🔍 Validating manifest.json...")

    # Load and parse JSON
    try:
        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — bundled package manifest next to this script, not user input
        with open("manifest.json") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except FileNotFoundError:
        print("❌ manifest.json not found")
        return False

    errors = []
    warnings = []

    # Check required fields
    required_fields = {
        "dxt_version": str,
        "name": str,
        "display_name": str,
        "version": str,
        "description": str,
        "author": dict,
        "server": dict,
        "tools": list,
    }

    for field, expected_type in required_fields.items():
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(manifest[field], expected_type):
            errors.append(f"Field '{field}' should be {expected_type.__name__}")

    # Validate DXT version
    if "dxt_version" in manifest:
        if manifest["dxt_version"] != "0.1":
            warnings.append(f"DXT version '{manifest['dxt_version']}' may not be supported")

    # Validate version format (semantic versioning)
    if "version" in manifest:
        version_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?(\+[a-zA-Z0-9\-\.]+)?$"
        if not re.match(version_pattern, manifest["version"]):
            errors.append(f"Invalid version format: {manifest['version']} (expected semantic versioning)")

    # Validate name format
    if "name" in manifest:
        name_pattern = r"^[a-z0-9][a-z0-9\-_]*[a-z0-9]$"
        if not re.match(name_pattern, manifest["name"]):
            warnings.append(f"Name '{manifest['name']}' should follow kebab-case convention")

    # Validate author
    if "author" in manifest:
        author = manifest["author"]
        if "name" not in author:
            errors.append("Missing author.name")
        if "email" not in author:
            warnings.append("Missing author.email (recommended)")
        elif author.get("email") and "@" not in author["email"]:
            warnings.append(f"Invalid email format: {author['email']}")

    # Validate server configuration
    if "server" in manifest:
        server = manifest["server"]

        if "type" not in server:
            errors.append("Missing server.type")
        elif server["type"] != "python":
            warnings.append(f"Server type '{server['type']}' - 'python' is recommended")

        if "entry_point" not in server:
            errors.append("Missing server.entry_point")
        else:
            entry_point = server["entry_point"]
            if not os.path.exists(entry_point):
                errors.append(f"Entry point file not found: {entry_point}")
            elif not entry_point.endswith(".py"):
                warnings.append(f"Entry point '{entry_point}' should be a Python file")

        # Validate MCP config if present
        if "mcp_config" in server:
            mcp_config = server["mcp_config"]
            if "command" not in mcp_config:
                warnings.append("Missing mcp_config.command")
            if "args" not in mcp_config:
                warnings.append("Missing mcp_config.args")

    # Validate icon
    if "icon" in manifest:
        icon_path = manifest["icon"]
        if not os.path.exists(icon_path):
            errors.append(f"Icon file not found: {icon_path}")
        elif not icon_path.lower().endswith(".png"):
            warnings.append("Icon should be PNG format")
        else:
            # Check icon size
            size = os.path.getsize(icon_path)
            if size > 1024 * 1024:  # 1MB
                warnings.append(f"Icon file is large ({size:,} bytes) - consider optimizing")
            elif size < 1024:  # 1KB
                warnings.append(f"Icon file is small ({size} bytes) - ensure it's a valid PNG")

    # Validate URLs
    url_fields = []
    if "homepage" in manifest:
        url_fields.append(("homepage", manifest["homepage"]))
    if "support" in manifest:
        url_fields.append(("support", manifest["support"]))
    if "repository" in manifest and isinstance(manifest["repository"], dict):
        if "url" in manifest["repository"]:
            url_fields.append(("repository.url", manifest["repository"]["url"]))

    for field_name, url in url_fields:
        if url:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"Invalid URL in {field_name}: {url}")
            elif parsed.scheme not in ["http", "https"]:
                warnings.append(f"URL in {field_name} should use HTTPS: {url}")

    # Validate license
    if "license" in manifest:
        common_licenses = ["MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause", "ISC"]
        if manifest["license"] not in common_licenses:
            warnings.append(f"License '{manifest['license']}' - consider using a standard SPDX identifier")

    # Validate tools
    if "tools" in manifest:
        tools = manifest["tools"]
        if not tools:
            warnings.append("No tools defined - extension may not be functional")

        tool_names = set()
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                errors.append(f"Tool {i} should be an object")
                continue

            if "name" not in tool:
                errors.append(f"Tool {i} missing name")
            else:
                tool_name = tool["name"]
                if tool_name in tool_names:
                    errors.append(f"Duplicate tool name: {tool_name}")
                tool_names.add(tool_name)

                # Validate tool name format
                if not re.match(r"^[a-z][a-z0-9_]*$", tool_name):
                    warnings.append(f"Tool name '{tool_name}' should use snake_case")

            if "description" not in tool:
                errors.append(f"Tool {i} ({tool.get('name', 'unnamed')}) missing description")
            elif len(tool["description"]) < 10:
                warnings.append(f"Tool '{tool.get('name', i)}' has very short description")

    # Validate user_config if present
    if "user_config" in manifest:
        user_config = manifest["user_config"]
        for config_key, config_value in user_config.items():
            if not isinstance(config_value, dict):
                warnings.append(f"User config '{config_key}' should be an object")
                continue

            if "type" not in config_value:
                warnings.append(f"User config '{config_key}' missing type")

            if config_value.get("sensitive") and "default" in config_value:
                warnings.append(f"Sensitive config '{config_key}' should not have default value")

    # Report results
    print("\n📊 Validation Results:")
    print(f"   🔧 Tools: {len(manifest.get('tools', []))}")
    print(f"   ⚙️ Config options: {len(manifest.get('user_config', {}))}")

    if errors:
        print(f"\n❌ {len(errors)} Error(s):")
        for error in errors:
            print(f"   • {error}")

    if warnings:
        print(f"\n⚠️ {len(warnings)} Warning(s):")
        for warning in warnings:
            print(f"   • {warning}")

    if not errors and not warnings:
        print("\n🎉 Perfect! No issues found.")
    elif not errors:
        print("\n✅ Validation passed with warnings.")
    else:
        print("\n❌ Validation failed!")
        return False

    print(f"\n📦 Extension: {manifest.get('name', 'Unknown')}")
    print(f"🏷️ Version: {manifest.get('version', 'Unknown')}")
    print(f"👤 Author: {manifest.get('author', {}).get('name', 'Unknown')}")

    return True


def main():
    """Main validation process"""
    print("📋 Claude Desktop Extension Manifest Validator")
    print("📚 See BUILD.md for detailed documentation")
    print("🔗 Official docs: https://www.anthropic.com/engineering/desktop-extensions")
    print("-" * 60)

    if not validate_manifest():
        print("\n💡 Fix the errors above and run validation again.")
        sys.exit(1)

    print("\n🚀 Manifest is ready for DXT packaging!")
    print("▶️ Next step: Run 'python build.py' to create the DXT package")


if __name__ == "__main__":
    main()
