// The processing indicator covers every moment the backend is working and no
// other element conveys progress. Gate on what the LAST block is doing, not
// on a whitelist of block types — new block types default to "show".
export function shouldShowProcessingIndicator(isStreaming, blocks) {
	if (!isStreaming) return false;
	if (!blocks || blocks.length === 0) return true;
	const last = blocks[blocks.length - 1];
	if (last.type === "text") return false;
	if (last.type === "interaction" && last.status === "pending") return false;
	if (last.type === "tool_call" && last.status === "running") return false;
	if (last.type === "thinking" && last.isStreaming) return false;
	return true;
}
