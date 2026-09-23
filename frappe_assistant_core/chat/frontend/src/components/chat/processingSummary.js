/**
 * Pure summary-text logic for ProcessingCard's status line. Kept side-effect
 * free so the live/completed phrasing can be unit tested without mounting the
 * component. Mirrors the live SSE block shape produced by blockHandlers.js.
 */

export function formatToolName(name) {
	if (!name) return "Tool";
	return name
		.replace(/_/g, " ")
		.replace(/([a-z])([A-Z])/g, "$1 $2")
		.split(" ")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

export function processingSummary(blocks, isStreaming) {
	const list = blocks || [];
	const lastBlock = list[list.length - 1];

	// Active streaming states
	if (isStreaming && lastBlock) {
		if (lastBlock.type === "thinking" && lastBlock.isStreaming) {
			return "Thinking...";
		}
		if (lastBlock.type === "tool_call" && lastBlock.status === "running") {
			if (lastBlock.tool_name === "delegate") return "Delegating subtask…";
			if (lastBlock.isInternal) return "Preparing...";
			return `Running ${formatToolName(lastBlock.tool_name)}...`;
		}
	}

	const toolBlocks = list.filter((b) => b.type === "tool_call");
	const ext = toolBlocks.filter((b) => !b.isInternal);
	const internal = toolBlocks.filter((b) => b.isInternal);

	const errorCount = ext.filter((b) => b.status === "error").length;
	const errorSuffix = errorCount > 0 ? ` (${errorCount} failed)` : "";

	if (ext.length === 0) {
		const delegated = internal.filter((b) => b.tool_name === "delegate");
		if (delegated.length > 0) {
			const failed = delegated.filter((b) => b.status === "error").length;
			const suffix = failed > 0 ? ` (${failed} failed)` : "";
			return `Delegated ${delegated.length} subtask${delegated.length === 1 ? "" : "s"}${suffix}`;
		}
		if (internal.length === 0) return "Thought about the request";
		// Thinking outranks the internal-prep labels below it. A gpt-5.x turn
		// with Thinking on typically emits thinking + one internal get_skill,
		// which used to collapse to "Loaded skill documentation" and hid the
		// only visible sign that the toggle did anything. Delegation keeps
		// priority above this — it names real work the user should see.
		if (list.some((b) => b.type === "thinking")) return "Thought about the request";
		if (internal.length === 1 && internal[0].tool_name === "get_skill") {
			return "Loaded skill documentation";
		}
		return "Prepared for the task";
	}

	const uniqueNames = [...new Set(ext.map((b) => b.tool_name))];

	if (uniqueNames.length === 1) {
		return `Used ${formatToolName(uniqueNames[0])}${errorSuffix}`;
	}

	if (uniqueNames.length <= 3) {
		const formatted = uniqueNames.map(formatToolName);
		const last = formatted.pop();
		return `Used ${formatted.join(", ")} and ${last}${errorSuffix}`;
	}

	return `Used ${ext.length} tools${errorSuffix}`;
}
