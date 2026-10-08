/**
 * What a turn's `delegate` calls achieved, read from the blocks AR persists.
 *
 * - Subtasks come from the call's input `tasks` (an array, or a JSON string
 *   when the model double-encodes it). Unreadable or empty tasks leave the
 *   count unknown; they never count as one.
 * - Done subtasks come from the result text: AR writes one section per task,
 *   "## <id> · <title> — <status>", or "## <id> — not run: …" for a rejected
 *   task (delegation_batch._format_result / _validate); "done" ran.
 *   Readable text without sections ran nothing: AR answers a refused call in
 *   plain text with status success (BATCH_ALREADY_RUNNING, "Nothing to
 *   delegate.", TASKS_NOT_A_LIST).
 * - No result, or one cut short on the socket (truncate_result_for_emit: a
 *   `_truncated` preview, or text ending in the truncation note), leaves the
 *   outcome unknown until the persisted snapshot lands.
 * - A call that errored ran none. A call still running once the turn is no
 *   longer live (not streaming, not waiting on the user) was stopped.
 */

const TRUNCATION_NOTE = "…[truncated — full result available on reload]";
const SECTION = /^## .+ — (.+)$/gm;

function taskCount(input) {
	let tasks = input?.tasks;
	if (typeof tasks === "string") {
		try {
			tasks = JSON.parse(tasks);
		} catch {
			return null;
		}
	}
	return Array.isArray(tasks) && tasks.length ? tasks.length : null;
}

// The result's text, or null when there is none to read yet.
function resultText(result) {
	if (result?._truncated) return null;
	let text = null;
	if (typeof result === "string") {
		text = result;
	} else {
		const items = Array.isArray(result) ? result : result?.content;
		if (Array.isArray(items)) {
			text = items.map((item) => (typeof item?.text === "string" ? item.text : "")).join("\n");
		}
	}
	if (!text?.trim() || text.trimEnd().endsWith(TRUNCATION_NOTE)) return null;
	return text;
}

function doneCount(block, count) {
	if (block.status === "error") return 0;
	const text = resultText(block.result);
	if (text === null) return null;
	const done = [...text.matchAll(SECTION)].filter((m) => m[1].trim() === "done").length;
	return count === null ? done : Math.min(done, count);
}

const add = (a, b) => (a === null || b === null ? null : a + b);

/**
 * { total, done, stopped }: total and done are null when unknown.
 */
export function delegationOutcome(blocks, live) {
	let total = 0;
	let done = 0;
	let stopped = false;
	for (const block of blocks) {
		const count = taskCount(block.input);
		total = add(total, count);
		if (block.status === "running") {
			if (!live) stopped = true;
			done = null;
			continue;
		}
		done = add(done, doneCount(block, count));
	}
	return { total, done, stopped };
}

const subtasks = (n) => `${n} subtask${n === 1 ? "" : "s"}`;

/**
 * The summary line and the header state ("complete", "error", "stopped" or
 * "neutral") for a finished turn's delegation.
 */
export function describeDelegation(blocks, live) {
	const { total, done, stopped } = delegationOutcome(blocks, live);
	if (stopped) return { text: "Delegation stopped", status: "stopped" };
	if (done === null) {
		return { text: total === null ? "Delegated subtasks" : `Delegated ${subtasks(total)}`, status: "neutral" };
	}
	if (total === null) {
		return done === 0
			? { text: "Delegated no subtasks", status: "error" }
			: { text: `Delegated ${subtasks(done)}`, status: "neutral" };
	}
	if (done < total) return { text: `Delegated ${done} of ${total} subtasks`, status: "error" };
	return { text: `Delegated ${subtasks(total)}`, status: "complete" };
}
