/**
 * Internal tools — housekeeping the agent does behind the scenes, rendered as
 * slim inline indicators rather than tool rows. `delegate` is here because the
 * plan rail already shows the delegated work. Must match INTERNAL_TOOLS in
 * chat/api/block_builder.py (test_block_builder_internal_tools pins it).
 */
export const INTERNAL_TOOLS = new Set([
	"get_skill",
	"workspace_read_file",
	"workspace_write_file",
	"workspace_list_files",
	"workspace_delete_file",
	"ask_user",
	"delegate",
]);

// The name decides as well as the flag: rows persisted before a tool joined the
// server's list keep `isInternal: false`.
export function isInternalTool(block) {
	return Boolean(block?.isInternal) || INTERNAL_TOOLS.has(block?.tool_name);
}
