/**
 * Pure summary-text logic for ProcessingCard's status line. Kept side-effect
 * free so the live/completed phrasing can be unit tested without mounting the
 * component. Mirrors the live SSE block shape produced by blockHandlers.js.
 */

import { isInternalTool } from "@/utils/internalTools";
import { delegationOutcome } from "./delegationOutcome";

export function formatToolName(name) {
	if (!name) return "Tool";
	return name
		.replace(/_/g, " ")
		.replace(/([a-z])([A-Z])/g, "$1 $2")
		.split(" ")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

function delegateBlocks(list) {
	return list.filter((b) => b.type === "tool_call" && b.tool_name === "delegate");
}

// `live` is false once the turn has ended: not streaming and not paused on a card.
export function processingSummary(blocks, isStreaming, live = isStreaming) {
	const list = blocks || [];
	const lastBlock = list[list.length - 1];

	// Active streaming states
	if (isStreaming && lastBlock) {
		if (lastBlock.type === "thinking" && lastBlock.isStreaming) {
			return "Thinking...";
		}
		if (lastBlock.type === "tool_call" && lastBlock.status === "running") {
			if (lastBlock.tool_name === "delegate") return "Delegating subtask…";
			if (isInternalTool(lastBlock)) return "Preparing...";
			return `Running ${formatToolName(lastBlock.tool_name)}...`;
		}
	}

	const toolBlocks = list.filter((b) => b.type === "tool_call");
	const ext = toolBlocks.filter((b) => !isInternalTool(b));
	const internal = toolBlocks.filter((b) => isInternalTool(b));

	const errorCount = ext.filter((b) => b.status === "error").length;
	const errorSuffix = errorCount > 0 ? ` (${errorCount} failed)` : "";

	if (ext.length === 0) {
		const delegated = delegateBlocks(internal);
		if (delegated.length > 0) {
			const { total, done, stopped } = delegationOutcome(delegated, live);
			if (stopped) return "Delegation stopped";
			if (done < total) return `Delegated ${done} of ${total} subtasks`;
			return `Delegated ${total} subtask${total === 1 ? "" : "s"}`;
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

/**
 * The header icon's state once the card is not active: "error" when a tool
 * failed or delegation ran fewer subtasks than it was given, "stopped" when the
 * turn ended with a tool (delegation included) still running, else "complete".
 */
export function processingStatus(blocks, isStreaming, live = isStreaming) {
	const list = blocks || [];
	const toolBlocks = list.filter((b) => b.type === "tool_call");
	if (toolBlocks.some((b) => b.status === "error")) return "error";
	if (!live && toolBlocks.some((b) => b.status === "running")) return "stopped";
	const delegated = delegateBlocks(toolBlocks);
	if (delegated.length) {
		const { total, done, stopped } = delegationOutcome(delegated, live);
		if (stopped) return "stopped";
		if (done < total) return "error";
	}
	return "complete";
}
