/**
 * The import sessions a conversation worked on (#34416), read from its persisted tool_call blocks,
 * so a reloaded conversation shows the same progress block and Import card.
 */
import { toolFailed, toolResult } from "@/utils/toolResult";
import { baseToolName } from "@/utils/toolNames";

// The tools that name a session: start_import_session opens one, the others take one
const TAKES_SESSION = new Set(["dry_run_import", "set_column_mapping", "start_import", "start_import_session"]);

function sessionOf(block) {
	const result = toolResult(block);
	const name = block.input?.session || result.session || result.session_id;
	return typeof name === "string" && name ? name : null;
}

/** The sessions whose import this message started (a start_import that ran), in order, once each. */
export function startedImports(blocks) {
	const names = [];
	for (const block of blocks || []) {
		if (block?.type !== "tool_call" || baseToolName(block.tool_name) !== "start_import") continue;
		if (block.status !== "success" || toolFailed(block)) continue;
		const name = sessionOf(block);
		if (name && !names.includes(name)) names.push(name);
	}
	return names;
}

/** The migration plans this message ran (a run_migration_plan that started or reported), once each. */
export function startedPlans(blocks) {
	const names = [];
	for (const block of blocks || []) {
		if (block?.type !== "tool_call" || baseToolName(block.tool_name) !== "run_migration_plan") continue;
		if (block.status !== "success" || toolFailed(block)) continue;
		const name = block.input?.plan || toolResult(block).plan;
		if (typeof name === "string" && name && !names.includes(name)) names.push(name);
	}
	return names;
}

/** Every session the conversation's messages worked on, in the order they first appear. */
export function conversationImportSessions(messages) {
	const names = [];
	for (const message of messages || []) {
		for (const block of message?.blocks || []) {
			if (block?.type !== "tool_call" || !TAKES_SESSION.has(baseToolName(block.tool_name))) continue;
			if (toolFailed(block)) continue;
			const name = sessionOf(block);
			if (name && !names.includes(name)) names.push(name);
		}
	}
	return names;
}

/** The sessions this message mapped (a set_column_mapping that saved), the latest call per session. */
export function mappedSessions(blocks) {
	return mappingSteps(blocks).map((step) => step.session);
}

/** The same, each with the id of the block that saved its mapping last: where its review card goes. */
export function mappingSteps(blocks) {
	const steps = [];
	for (const block of blocks || []) {
		if (block?.type !== "tool_call" || baseToolName(block.tool_name) !== "set_column_mapping") continue;
		if (block.status !== "success" || toolFailed(block)) continue;
		const name = sessionOf(block);
		if (!name) continue;
		const at = steps.findIndex((step) => step.session === name);
		if (at !== -1) steps.splice(at, 1);
		steps.push({ session: name, blockId: block.id });
	}
	return steps;
}
