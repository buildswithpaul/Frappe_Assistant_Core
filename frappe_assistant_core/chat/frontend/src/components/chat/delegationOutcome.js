/**
 * What a turn's `delegate` calls achieved, read from the blocks AR persists.
 *
 * - Subtasks come from the call's input `tasks` (an array, or a JSON string
 *   when the model double-encodes it); a call without readable tasks counts as one.
 * - Done subtasks come from the result text: AR writes one section per task,
 *   "## <id> · <title> — <status>", or "## <id> — not run: …" for a rejected
 *   task (delegation_batch._format_result / _validate). A section whose status
 *   is "done" ran. A result without such sections is unknown, and a successful
 *   call with an unknown result counts every subtask as done.
 * - A call that errored ran none. A call still running once the turn is no
 *   longer live (not streaming, not paused) was stopped.
 */

function parseTasks(input) {
	let tasks = input?.tasks;
	if (typeof tasks === "string") {
		try {
			tasks = JSON.parse(tasks);
		} catch {
			return null;
		}
	}
	return Array.isArray(tasks) ? tasks : null;
}

function resultText(result) {
	if (typeof result === "string") return result;
	const items = Array.isArray(result) ? result : result?.content;
	if (!Array.isArray(items)) return "";
	return items.map((item) => (typeof item?.text === "string" ? item.text : "")).join("\n");
}

const SECTION = /^## .+ — (.+)$/gm;

function doneCount(block) {
	const statuses = [...resultText(block.result).matchAll(SECTION)].map((m) => m[1]);
	if (!statuses.length) return null;
	return statuses.filter((status) => status.trim() === "done").length;
}

export function delegationOutcome(blocks, live) {
	let total = 0;
	let done = 0;
	let stopped = false;
	for (const block of blocks) {
		const count = parseTasks(block.input)?.length || 1;
		total += count;
		if (block.status === "running") {
			if (!live) stopped = true;
			continue;
		}
		if (block.status === "error") continue;
		const ran = doneCount(block);
		done += ran === null ? count : Math.min(ran, count);
	}
	return { total, done, stopped };
}
