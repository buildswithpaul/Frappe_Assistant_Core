# Building Claude Desktop Extension

This guide explains how to build, validate, and package the Claude Desktop Extension for Frappe ERP.

## 📚 **Official Documentation**

- **[Claude Desktop Extensions](https://www.anthropic.com/engineering/desktop-extensions)** - Official Anthropic documentation
- **[MCP Protocol](https://modelcontextprotocol.io)** - Model Context Protocol specification
- **[Extension Development Guide](https://docs.anthropic.com/claude/desktop/extensions)** - Detailed development docs

## 🏗️ **DXT File Creation**

A DXT (Desktop Extension) file is essentially a ZIP archive with a `.dxt` extension containing your extension files.

### Prerequisites

- **Python 3.8+** installed and available in PATH
- **ZIP utility** (built into most operating systems)
- **Claude Desktop** for testing

### Manual Build Process

#### 1. **Prepare Build Environment**

```bash
# Navigate to the extension directory
cd client_packages/claude-desktop

# Ensure all dependencies are available
pip install -r requirements.txt

# Test the bridge script syntax
python -m py_compile server/frappe_assistant_stdio_bridge.py
```

#### 2. **Validate Manifest** (See [Manifest Validation](#manifest-validation))

```bash
# Validate manifest.json structure
python -c "
import json
import sys

try:
    with open('manifest.json', 'r') as f:
        manifest = json.load(f)
    print('✅ Manifest JSON is valid')
    print(f'📦 Extension: {manifest[\"name\"]}')
    print(f'🏷️ Version: {manifest[\"version\"]}')
except Exception as e:
    print(f'❌ Manifest validation failed: {e}')
    sys.exit(1)
"
```

#### 3. **Create DXT Package**

**On macOS/Linux:**
```bash
# Create DXT file
zip -r "claude-for-frappe-v$(grep -o '\"version\": \"[^\"]*\"' manifest.json | cut -d'"' -f4).dxt" \
  manifest.json \
  server/ \
  requirements.txt \
  icon.png \
  assets/ \
  README.md \
  LICENSE

# Verify package contents
unzip -l *.dxt
```

**On Windows:**
```powershell
# Get version from manifest
$version = (Get-Content manifest.json | ConvertFrom-Json).version

# Create DXT file
Compress-Archive -Path manifest.json, server, requirements.txt, icon.png, assets, README.md, LICENSE -DestinationPath "claude-for-frappe-v$version.dxt"

# Verify package contents
Expand-Archive -Path "*.dxt" -DestinationPath temp -Force
Get-ChildItem temp -Recurse
Remove-Item temp -Recurse
```

### Automated Build Script

Create a `build.py` script for consistent builds:

```python
#!/usr/bin/env python3
"""
Build script for Claude Desktop Extension
"""
import json
import zipfile
import os
import sys
from pathlib import Path

def validate_manifest():
    """Validate manifest.json structure"""
    try:
        with open('manifest.json', 'r') as f:
            manifest = json.load(f)
        
        required_fields = ['name', 'version', 'description', 'server']
        for field in required_fields:
            if field not in manifest:
                raise ValueError(f"Missing required field: {field}")
        
        print(f"✅ Manifest valid - {manifest['name']} v{manifest['version']}")
        return manifest
    except Exception as e:
        print(f"❌ Manifest validation failed: {e}")
        sys.exit(1)

def create_dxt(manifest):
    """Create DXT package"""
    version = manifest['version']
    filename = f"claude-for-frappe-v{version}.dxt"
    
    # Files to include in package
    files_to_include = [
        'manifest.json',
        'server/frappe_assistant_stdio_bridge.py',
        'requirements.txt',
        'icon.png',
        'README.md',
        'LICENSE'
    ]
    
    # Optional files/directories
    optional_items = [
        'assets/',
        'CHANGELOG.md',
        'CONTRIBUTING.md'
    ]
    
    print(f"📦 Creating {filename}...")
    
    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as dxt:
        # Add required files
        for file_path in files_to_include:
            if os.path.exists(file_path):
                dxt.write(file_path)
                print(f"  ✅ Added {file_path}")
            else:
                print(f"  ❌ Missing required file: {file_path}")
                sys.exit(1)
        
        # Add optional items
        for item in optional_items:
            if os.path.exists(item):
                if os.path.isdir(item):
                    for root, dirs, files in os.walk(item):
                        for file in files:
                            file_path = os.path.join(root, file)
                            dxt.write(file_path)
                else:
                    dxt.write(item)
                print(f"  ✅ Added {item}")
    
    print(f"🎉 Successfully created {filename}")
    print(f"📊 Package size: {os.path.getsize(filename)} bytes")
    return filename

def main():
    """Main build process"""
    print("🏗️ Building Claude Desktop Extension...")
    
    # Validate manifest
    manifest = validate_manifest()
    
    # Test Python syntax
    print("🧪 Testing bridge script...")
    import py_compile
    try:
        py_compile.compile('server/frappe_assistant_stdio_bridge.py', doraise=True)
        print("✅ Bridge script syntax is valid")
    except py_compile.PyCompileError as e:
        print(f"❌ Bridge script has syntax errors: {e}")
        sys.exit(1)
    
    # Create DXT package
    dxt_file = create_dxt(manifest)
    
    print(f"\n🚀 Build complete! Install with:")
    print(f"   Double-click {dxt_file} or drag to Claude Desktop")

if __name__ == "__main__":
    main()
```

## ✅ **Manifest Validation**

### Required Manifest Structure

```json
{
  "dxt_version": "0.1",
  "name": "claude-for-frappe",
  "display_name": "Claude for Frappe ERP",
  "version": "1.0.1",
  "description": "Brief description",
  "long_description": "Detailed description",
  "author": {
    "name": "Author Name",
    "email": "author@email.com"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/user/repo"
  },
  "homepage": "https://github.com/user/repo",
  "support": "https://github.com/user/repo/issues",
  "icon": "icon.png",
  "license": "MIT",
  "server": {
    "type": "python",
    "entry_point": "server/frappe_assistant_stdio_bridge.py",
    "mcp_config": { /* MCP configuration */ }
  },
  "user_config": { /* User configuration schema */ },
  "tools": [ /* Tool definitions */ ]
}
```

### Validation Checklist

- [ ] **JSON Syntax**: Valid JSON format
- [ ] **Required Fields**: All required fields present
- [ ] **Version Format**: Semantic versioning (e.g., "1.0.1")
- [ ] **Entry Point**: Python script exists and is valid
- [ ] **Icon File**: PNG icon exists and is reasonable size
- [ ] **URLs**: All URLs are valid and accessible
- [ ] **Tools Array**: All tools have name and description

### Validation Script

```python
#!/usr/bin/env python3
"""
Comprehensive manifest validation
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
        with open('manifest.json', 'r') as f:
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
        'dxt_version': str,
        'name': str,
        'display_name': str,
        'version': str,
        'description': str,
        'author': dict,
        'server': dict,
        'tools': list
    }
    
    for field, expected_type in required_fields.items():
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(manifest[field], expected_type):
            errors.append(f"Field '{field}' should be {expected_type.__name__}")
    
    # Validate version format
    if 'version' in manifest:
        version_pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?(\+[a-zA-Z0-9\-\.]+)?$'
        if not re.match(version_pattern, manifest['version']):
            errors.append(f"Invalid version format: {manifest['version']}")
    
    # Validate author
    if 'author' in manifest:
        if 'name' not in manifest['author']:
            errors.append("Missing author.name")
        if 'email' not in manifest['author']:
            warnings.append("Missing author.email (recommended)")
    
    # Validate server configuration
    if 'server' in manifest:
        server = manifest['server']
        if 'type' not in server:
            errors.append("Missing server.type")
        elif server['type'] != 'python':
            warnings.append("Server type is not 'python'")
        
        if 'entry_point' not in server:
            errors.append("Missing server.entry_point")
        elif not os.path.exists(server['entry_point']):
            errors.append(f"Entry point file not found: {server['entry_point']}")
    
    # Validate icon
    if 'icon' in manifest:
        icon_path = manifest['icon']
        if not os.path.exists(icon_path):
            errors.append(f"Icon file not found: {icon_path}")
        elif not icon_path.lower().endswith('.png'):
            warnings.append("Icon should be PNG format")
        else:
            # Check icon size
            size = os.path.getsize(icon_path)
            if size > 1024 * 1024:  # 1MB
                warnings.append(f"Icon file is large ({size} bytes)")
            elif size < 1024:  # 1KB
                warnings.append(f"Icon file is small ({size} bytes)")
    
    # Validate URLs
    url_fields = ['homepage', 'support']
    if 'repository' in manifest and 'url' in manifest['repository']:
        url_fields.append('repository.url')
    
    for field in url_fields:
        if '.' in field:
            # Nested field
            obj, key = field.split('.')
            url = manifest.get(obj, {}).get(key)
        else:
            url = manifest.get(field)
        
        if url:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"Invalid URL in {field}: {url}")
    
    # Validate tools
    if 'tools' in manifest:
        for i, tool in enumerate(manifest['tools']):
            if not isinstance(tool, dict):
                errors.append(f"Tool {i} should be an object")
                continue
            
            if 'name' not in tool:
                errors.append(f"Tool {i} missing name")
            if 'description' not in tool:
                errors.append(f"Tool {i} missing description")
    
    # Report results
    if errors:
        print("❌ Validation failed:")
        for error in errors:
            print(f"   • {error}")
        return False
    
    if warnings:
        print("⚠️ Warnings:")
        for warning in warnings:
            print(f"   • {warning}")
    
    print("✅ Manifest validation passed!")
    print(f"📦 Extension: {manifest.get('name', 'Unknown')}")
    print(f"🏷️ Version: {manifest.get('version', 'Unknown')}")
    print(f"🔧 Tools: {len(manifest.get('tools', []))}")
    
    return True

if __name__ == "__main__":
    if not validate_manifest():
        sys.exit(1)
```

## 🧪 **Testing the Extension**

### Local Testing

1. **Test Bridge Script**:
   ```bash
   python server/frappe_assistant_stdio_bridge.py --help
   ```

2. **Install Development Version**:
   ```bash
   # Build DXT
   python build.py
   
   # Install in Claude Desktop
   # Double-click the .dxt file or drag to Claude Desktop
   ```

3. **Test Basic Connectivity**:
   - Configure Frappe server details in Claude Desktop
   - Try basic commands like "List all customers"

### Integration Testing

```python
#!/usr/bin/env python3
"""
Integration test for the extension
"""
import subprocess
import json
import sys

def test_bridge_script():
    """Test the bridge script can start"""
    try:
        result = subprocess.run([
            'python', 'server/frappe_assistant_stdio_bridge.py', '--version'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Bridge script runs successfully")
            return True
        else:
            print(f"❌ Bridge script failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("⏰ Bridge script timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing bridge script: {e}")
        return False

def test_manifest_tools():
    """Test that all manifest tools are documented"""
    with open('manifest.json', 'r') as f:
        manifest = json.load(f)
    
    tools = manifest.get('tools', [])
    documented_tools = set()
    
    # Check if tools are documented in README
    try:
        with open('README.md', 'r') as f:
            readme_content = f.read()
        
        for tool in tools:
            tool_name = tool.get('name', '')
            if f"`{tool_name}`" in readme_content:
                documented_tools.add(tool_name)
        
        undocumented = len(tools) - len(documented_tools)
        if undocumented > 0:
            print(f"⚠️ {undocumented} tools not documented in README")
        else:
            print("✅ All tools documented in README")
        
        return undocumented == 0
        
    except FileNotFoundError:
        print("❌ README.md not found")
        return False

def main():
    """Run all tests"""
    print("🧪 Running extension tests...")
    
    tests = [
        ("Manifest validation", lambda: validate_manifest()),
        ("Bridge script", test_bridge_script),
        ("Tool documentation", test_manifest_tools),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        if test_func():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Extension is ready.")
        return True
    else:
        print("❌ Some tests failed. Please fix issues before release.")
        return False

if __name__ == "__main__":
    from manifest_validator import validate_manifest  # Import our validator
    if not main():
        sys.exit(1)
```

## 📦 **Release Process**

### 1. Version Bump
```bash
# Update version in manifest.json
# Update CHANGELOG.md
# Update README.md version badges
```

### 2. Build and Test
```bash
python validate_manifest.py
python build.py
python test_extension.py
```

### 3. Create Release
```bash
# Tag the release
git tag v1.0.1
git push origin v1.0.1

# Upload DXT to GitHub releases
# Update documentation
```

## 🔧 **Troubleshooting**

### Common Issues

**"Extension won't install"**
- Check manifest.json syntax
- Verify all required files are included
- Ensure DXT file isn't corrupted

**"Bridge script fails to start"**
- Check Python syntax with `python -m py_compile`
- Verify all imports are available
- Check Python version compatibility

**"Tools not working"**
- Verify Frappe server connection
- Check API credentials
- Ensure Frappe Assistant Core app is installed

### Debug Mode

Enable debug logging in Claude Desktop:
```json
{
  "debug_mode": "1"
}
```

## 📚 **Additional Resources**

- **[Claude Desktop Extensions](https://www.anthropic.com/engineering/desktop-extensions)** - Official documentation
- **[MCP Specification](https://modelcontextprotocol.io)** - Protocol details
- **[Frappe Assistant Core](https://github.com/buildswithpaul/Frappe_Assistant_Core)** - Server-side documentation
- **[Extension Examples](https://github.com/anthropics/claude-desktop-examples)** - Community examples

---

**Building the future of AI-powered ERP interactions** 🚀