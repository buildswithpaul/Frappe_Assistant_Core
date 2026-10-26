/**
 * The FAC Pages a conversation wrote, read from its persisted tool_call blocks, so a reload
 * shows the same chips without a block type of its own.
 */
import { isDryRun, toolFailed, toolResult } from "@/utils/toolResult";
import { baseToolName } from "@/utils/toolNames";

const PAGE_DOCTYPE = "FAC Page";
const PAGE_WRITES = new Set(["create_document", "update_document"]);
const IN_FLIGHT = new Set(["running", "pending"]);

function pageWrite(block) {
	if (block?.type !== "tool_call" || !PAGE_WRITES.has(baseToolName(block.tool_name))) return null;
	const result = toolResult(block);
	if ((block.input?.doctype || result.doctype) !== PAGE_DOCTYPE) return null;
	// A create's record name exists only once it has run: a personal page's name is not its slug.
	const name = result.name || block.input?.name;
	if (typeof name !== "string" || !name) return null;
	const title = block.input?.data?.title;
	return { name, title: typeof title === "string" && title ? title : null };
}

/**
 * One chip per page, in the order the pages first appear: `{name, title, version, pending}`.
 * `version` counts the successful writes; `pending` is true while a write to the page runs.
 * A dry run, a failed write or a cancelled one adds nothing.
 */
export function derivePageChips(blocks) {
	const chips = new Map();
	for (const block of blocks || []) {
		const write = pageWrite(block);
		if (!write) continue;
		const inFlight = IN_FLIGHT.has(block.status);
		// Only a write that ran and saved counts: not a dry run, a failure, or a cancelled call.
		if (!inFlight && (block.status !== "success" || toolFailed(block) || isDryRun(block))) continue;

		let chip = chips.get(write.name);
		if (!chip) {
			chip = { name: write.name, title: write.name, version: 0, pending: false };
			chips.set(write.name, chip);
		}
		if (write.title) chip.title = write.title;
		if (inFlight) chip.pending = true;
		else chip.version += 1;
	}
	return [...chips.values()];
}

/**
 * Every FAC Page write call, in order: `{id, inFlight, name}`. `name` is set only once the write
 * ran and saved, which for a create is when its result arrives.
 */
export function pageWriteCalls(blocks) {
	const calls = [];
	for (const block of blocks || []) {
		if (block?.type !== "tool_call" || !PAGE_WRITES.has(baseToolName(block.tool_name))) continue;
		if ((block.input?.doctype || toolResult(block).doctype) !== PAGE_DOCTYPE) continue;
		const inFlight = IN_FLIGHT.has(block.status);
		const saved = block.status === "success" && !toolFailed(block) && !isDryRun(block);
		calls.push({ id: block.id, inFlight, name: saved ? pageWrite(block)?.name || null : null });
	}
	return calls;
}

/** The pages one message wrote, carrying the conversation's version, title and pending state. */
export function chipsForMessage(blocks, conversationChips = []) {
	return derivePageChips(blocks).map(
		(chip) => conversationChips.find((known) => known.name === chip.name) || chip,
	);
}
