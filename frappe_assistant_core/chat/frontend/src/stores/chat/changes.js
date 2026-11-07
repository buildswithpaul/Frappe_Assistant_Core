/**
 * The records a turn created without asking, listed in one `changes_made` block per message
 * so the user can undo them. The relay persists the same block, so a reload brings it back.
 */

import { api } from "@/api/client";
import { generateBlockId } from "./utils";

export const CHANGES_BLOCK = "changes_made";

const isName = (value) => typeof value === "string" && value.trim() !== "";

/** The changes from an event that name a record; anything else cannot be undone. */
export function usableChanges(changes) {
	if (!Array.isArray(changes)) return [];
	return changes.filter((c) => c && typeof c === "object" && isName(c.doctype) && isName(c.name));
}

/** Join changes to the message's block (made if absent); a listed change keeps its undone flag. */
export function mergeChanges(blocks, changes) {
	let block = blocks.find((b) => b.type === CHANGES_BLOCK);
	if (!block) {
		block = { type: CHANGES_BLOCK, id: generateBlockId(CHANGES_BLOCK), changes: [] };
		blocks.push(block);
	}
	for (const change of changes) {
		const listed = block.changes.some((c) => c.doctype === change.doctype && c.name === change.name);
		if (listed) continue;
		block.changes.push({
			doctype: change.doctype,
			name: change.name,
			action: change.action,
			undo: change.undo,
			undone: false,
		});
	}
	return block;
}

function findChange(messages, messageId, doctype, name) {
	const message = messages.find((m) => m.role === "assistant" && m.message_id === messageId);
	const block = message?.blocks?.find((b) => b.type === CHANGES_BLOCK);
	return block?.changes?.find((c) => c.doctype === doctype && c.name === name) || null;
}

/**
 * Undo one listed change. Resolves to `{ success: true }`, or `{ success: false, reason }` with
 * a reason fit to show the user (the server's refusal, or a thrown error's safe message).
 */
export function createChangeActions({ messages, currentSessionId }) {
	async function undoChange({ messageId, doctype, name }) {
		let result;
		try {
			result = await api.chat.undoChange(currentSessionId.value, messageId, doctype, name);
		} catch (error) {
			return { success: false, reason: error?.message || "" };
		}
		if (!result?.success) return { success: false, reason: result?.reason || "" };
		const change = findChange(messages.value, messageId, doctype, name);
		if (change) change.undone = true;
		return { success: true };
	}

	return { undoChange };
}
