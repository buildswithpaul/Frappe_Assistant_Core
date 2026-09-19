# MCP tool profiles

Tool profiles reduce `tools/list` context and registry work by selecting a
declared subset before FAC runs its normal enablement, role and DocType
permission checks. A profile is a context filter, never an authorization
mechanism.

External apps register profiles in `hooks.py`:

```python
assistant_tool_profiles = [
    {
        "name": "operations-compact",
        "description": "Normal operations tools",
        "source_app": "my_app",
        "default": False,
        "tools": ["list_documents", "get_document", "my_domain_tool"],
    }
]
```

Selection order:

1. `X-Assistant-Tool-Profile` request header.
2. Site config key `fac_mcp_tool_profile`.
3. One hook profile marked `default=True`.
4. No profile: expose the historical permission-filtered tool set.

An unknown selected profile fails closed and exposes no tools for that request.
The same profile must be used for `tools/list` and `tools/call`. Profiles may
reference tools from another installed app; missing tools are simply absent.

Release procedure:

1. Deploy FAC profile support and the app declarations.
2. Migrate and clear caches.
3. Verify the unprofiled registry and each profile with an authorized test user.
4. Set `fac_mcp_tool_profile` only after the selected profile passes its golden
   tasks.
5. Remove that site-config value to restore the historical full surface.
