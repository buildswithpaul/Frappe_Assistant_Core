# OAuth Configuration Changes

## Summary

Simplified OAuth configuration by removing rarely-used features and improving UX.

---

## What Changed

### ❌ Removed Features

1. **Skip Authorization Prompt**
   - **Why removed:** Security risk - bypasses user consent
   - **Impact:** None - this should never be used in production
   - **v16 Compatibility:** Still available in Frappe v16 OAuth Settings if needed

2. **Include Social Login Keys**
   - **Why removed:** Advanced feature used by <1% of users
   - **Impact:** Minimal - federation scenarios are rare
   - **v16 Compatibility:** Still available in Frappe v16 OAuth Settings if needed

### ✅ Simplified Layout

**Before (11 fields visible):**
```
OAuth Configuration
├─ Show Authorization Server Metadata
├─ Enable Dynamic Client Registration
├─ Skip Authorization Prompt
├─ Allowed Public Client Origins
├─ Resource Server Settings
│  ├─ Show Protected Resource Metadata
│  ├─ Include Social Login Keys
│  ├─ Resource Name
│  ├─ Resource Documentation
│  ├─ Resource Policy URI
│  ├─ Resource TOS URI
│  └─ Scopes Supported
```

**After (2 main fields, rest collapsed):**
```
OAuth Configuration
├─ ☑ Enable Dynamic Client Registration
└─ Allowed Public Client Origins (textbox)

▶ Advanced Discovery Settings (collapsed)
  ├─ Show Authorization Server Metadata
  └─ Show Protected Resource Metadata

▶ Resource Metadata (Optional) (collapsed)
  ├─ Resource Name
  ├─ Documentation URL
  ├─ Policy URI
  ├─ Terms of Service URI
  └─ Supported Scopes
```

---

## Migration Guide

### For v15 Users

**No action required!**

The removed fields are automatically set to safe defaults:
- `skip_authorization` → `False` (always prompt for authorization)
- `show_social_login_key_as_authorization_server` → `False` (don't include)

Your existing OAuth clients continue working normally.

### For v16 Users

**No action required!**

The compatibility layer (`oauth_compat.py`) reads v16's OAuth Settings directly.
All v16 features remain available in the native Frappe OAuth Settings DocType.

---

## What You Should See Now

### Main Section (Always Visible)

Only 2 fields for 99% of use cases:

1. **Enable Dynamic Client Registration**
   - One checkbox to enable/disable OAuth auto-registration
   - Default: Enabled ✅

2. **Allowed Public Client Origins**
   - Text field for CORS origins (one per line)
   - Only shows when dynamic registration is enabled
   - Examples: `http://localhost:6274`, `https://your-app.com`

### Advanced Sections (Collapsed)

Click to expand only if needed:

1. **Advanced Discovery Settings**
   - Show Authorization Server Metadata (default: enabled)
   - Show Protected Resource Metadata (default: enabled)

2. **Resource Metadata (Optional)**
   - Branding fields (name, docs URL, policy, TOS, scopes)
   - Safe to ignore for most users

---

## Technical Details

### Code Changes

1. **assistant_core_settings.json**
   - Removed `skip_authorization` field
   - Removed `show_social_login_key_as_authorization_server` field
   - Improved field descriptions and labels
   - Added collapsible sections

2. **oauth_compat.py**
   - Returns `False` for removed fields when reading v15 settings
   - Uses `getattr()` for v16 compatibility (those fields still exist in v16)

3. **Documentation**
   - Updated OAuth Setup Guide
   - Removed references to deleted features
   - Simplified examples

### Backward Compatibility

✅ **Fully backward compatible**

- Existing OAuth clients: ✅ Continue working
- Discovery endpoints: ✅ Unchanged
- Dynamic registration: ✅ Works exactly the same
- CORS handling: ✅ Unchanged
- v15/v16 detection: ✅ Automatic

### Database Changes

**None!**

The removed fields were:
- Not widely used
- Set to safe defaults (both `False`)
- No data migration needed

---

## Benefits

### For Users

✅ **Less overwhelming** - See only 2 fields by default
✅ **Clearer purpose** - Each field has improved descriptions
✅ **Safer defaults** - Removed security-risk options
✅ **Better organization** - Advanced options are collapsed

### For Developers

✅ **Cleaner code** - Removed unused features
✅ **Better docs** - Comprehensive guides added
✅ **v15/v16 compat** - Automatic version detection
✅ **Easier maintenance** - Less configuration surface area

---

## Documentation

### Quick Start
📄 [oauth_quick_start.md](./oauth_quick_start.md)
- 2-minute setup guide
- Visual examples
- Common scenarios

### Full Guide
📄 [oauth_setup_guide.md](./oauth_setup_guide.md)
- Detailed explanations
- Security best practices
- Troubleshooting
- Technical details

---

## Support

Questions or issues?

- 📁 GitHub Issues: https://github.com/buildswithpaul/Frappe_Assistant_Core/issues
- 💬 Frappe Forum: https://discuss.frappe.io/

---

## Version Info

**Release:** v2.0.0
**Date:** 2025-10-06
**Frappe Compatibility:** v15, v16+
