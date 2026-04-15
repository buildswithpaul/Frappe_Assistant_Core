#!/usr/bin/env python3
"""
Build script for Claude Desktop Extension

This script validates the manifest and creates a DXT package.
See BUILD.md for detailed documentation.
"""

import json
import os
import py_compile
import sys
import zipfile
from pathlib import Path


def validate_manifest():
    """Validate manifest.json structure"""
    print("🔍 Validating manifest.json...")

    try:
        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — bundled package manifest next to build.py, not user input
        with open("manifest.json") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in manifest.json: {e}")
        return None
    except FileNotFoundError:
        print("❌ manifest.json not found")
        return None

    # Check required fields
    required_fields = ["name", "version", "description", "server"]
    for field in required_fields:
        if field not in manifest:
            print(f"❌ Missing required field: {field}")
            return None

    # Validate server configuration
    server = manifest.get("server", {})
    if "entry_point" not in server:
        print("❌ Missing server.entry_point")
        return None

    entry_point = server["entry_point"]
    if not os.path.exists(entry_point):
        print(f"❌ Entry point file not found: {entry_point}")
        return None

    print(f"✅ Manifest valid - {manifest['name']} v{manifest['version']}")
    return manifest


def test_bridge_script(entry_point):
    """Test the bridge script syntax"""
    print("🧪 Testing bridge script syntax...")

    try:
        py_compile.compile(entry_point, doraise=True)
        print("✅ Bridge script syntax is valid")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Bridge script has syntax errors: {e}")
        return False


def create_dxt(manifest):
    """Create DXT package"""
    version = manifest["version"]
    name = manifest["name"]
    filename = f"{name}-v{version}.dxt"

    # Files to include in package
    files_to_include = ["manifest.json", "requirements.txt", "icon.png", "README.md", "LICENSE"]

    # Add server directory
    server_entry = manifest.get("server", {}).get("entry_point", "")
    if server_entry and os.path.exists(server_entry):
        server_dir = os.path.dirname(server_entry)
        if server_dir:
            files_to_include.append(server_dir + "/")

    # Optional files/directories
    optional_items = ["assets/", "CHANGELOG.md", "CONTRIBUTING.md", "BUILD.md"]

    print(f"📦 Creating {filename}...")

    with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as dxt:
        # Add required files
        for file_path in files_to_include:
            if file_path.endswith("/"):
                # Directory
                dir_path = file_path.rstrip("/")
                if os.path.exists(dir_path):
                    for root, _dirs, files in os.walk(dir_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arc_path = os.path.relpath(full_path)
                            dxt.write(full_path, arc_path)
                    print(f"  ✅ Added {dir_path}/")
            else:
                # Single file
                if os.path.exists(file_path):
                    dxt.write(file_path)
                    print(f"  ✅ Added {file_path}")
                else:
                    print(f"  ❌ Missing required file: {file_path}")
                    return None

        # Add optional items
        for item in optional_items:
            if os.path.exists(item):
                if os.path.isdir(item):
                    for root, _dirs, files in os.walk(item):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arc_path = os.path.relpath(full_path)
                            dxt.write(full_path, arc_path)
                else:
                    dxt.write(item)
                print(f"  ✅ Added {item}")

    if os.path.exists(filename):
        size = os.path.getsize(filename)
        print(f"🎉 Successfully created {filename}")
        print(f"📊 Package size: {size:,} bytes")
        return filename
    else:
        print("❌ Failed to create DXT package")
        return None


def main():
    """Main build process"""
    print("🏗️ Building Claude Desktop Extension...")

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Step 1: Validate manifest
    manifest = validate_manifest()
    if not manifest:
        print("❌ Build failed: Manifest validation error")
        sys.exit(1)

    # Step 2: Test bridge script
    entry_point = manifest.get("server", {}).get("entry_point")
    if not test_bridge_script(entry_point):
        print("❌ Build failed: Bridge script error")
        sys.exit(1)

    # Step 3: Create DXT package
    dxt_file = create_dxt(manifest)
    if not dxt_file:
        print("❌ Build failed: Package creation error")
        sys.exit(1)

    # Success!
    print("\n🚀 Build complete!")
    print(f"📦 Extension package: {dxt_file}")
    print(f"🔧 Installation: Double-click {dxt_file} or drag to Claude Desktop")
    print("📚 Documentation: See BUILD.md for testing and validation")


if __name__ == "__main__":
    main()
