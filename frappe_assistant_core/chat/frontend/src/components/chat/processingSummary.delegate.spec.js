import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { processingSummary, processingStatus } from "./processingSummary";
import ProcessingCard from "./ProcessingCard.vue";

// The shapes AR's delegate tool really produces: `tasks` in the input (a JSON
// string when the model double-encodes it), and a result with one
// "## <id> · <title> — <status>" section per task, or "## <id> — not run: …"
// for a task it rejected (delegation_batch._format_result / _validate).
const TASKS = [
	{ task_id: "t-1", instructions: "A" },
	{ task_id: "t-2", instructions: "B" },
	{ task_id: "t-3", instructions: "C" },
	{ task_id: "t-4", instructions: "D" },
];
const delegate = (extra) => ({
	type: "tool_call",
	id: "d1",
	tool_name: "delegate",
	isInternal: true,
	status: "success",
	input: { tasks: TASKS },
	...extra,
});
const section = (id, status) => `## ${id} · Task ${id} — ${status}\nfindings`;
const allDone = TASKS.map((t) => section(t.task_id, "done")).join("\n\n");
const noneRan = TASKS.map((t) => `## ${t.task_id} — not run: no open plan task with this id.`).join("\n\n");

describe("processingSummary for delegation", () => {
	it("counts the subtasks of a call, not the calls", () => {
		expect(processingSummary([delegate({ result: allDone })], false)).toBe("Delegated 4 subtasks");
	});

	it("reads tasks sent as a JSON string", () => {
		const block = delegate({ input: { tasks: JSON.stringify(TASKS) }, result: allDone });
		expect(processingSummary([block], false)).toBe("Delegated 4 subtasks");
	});

	it("says how many ran when some did not", () => {
		const result = [
			section("t-1", "done"),
			section("t-2", "done"),
			"## t-3 · Task t-3 — failed: Timed out. Handle it yourself.",
			"## t-4 · Task t-4 — skipped: Stopped. Handle it yourself.",
		].join("\n\n");
		expect(processingSummary([delegate({ result })], false)).toBe("Delegated 2 of 4 subtasks");
	});

	it("does not claim delegation when the call ran no subtask", () => {
		expect(processingSummary([delegate({ result: noneRan })], false)).toBe("Delegated 0 of 4 subtasks");
		expect(processingStatus([delegate({ result: noneRan })], false)).toBe("error");
	});

	it("reads the Strands list form of a result", () => {
		const block = delegate({ result: [{ text: noneRan }] });
		expect(processingSummary([block], false)).toBe("Delegated 0 of 4 subtasks");
	});

	it("says delegation stopped when the turn ended with it still running", () => {
		const block = delegate({ status: "running", result: null });
		expect(processingSummary([block], false)).toBe("Delegation stopped");
		expect(processingStatus([block], false)).toBe("stopped");
	});

	it("keeps a delegate on a paused turn in flight, not stopped", () => {
		const block = delegate({ status: "running", result: null });
		expect(processingStatus([block], false, true)).not.toBe("stopped");
	});

	// No result text yet (a hydrated block whose result was not kept): the
	// count is known, the outcome is not, so no checkmark.
	it("stays neutral about a call whose result it has not got", () => {
		expect(processingSummary([delegate({ result: null })], false)).toBe("Delegated 4 subtasks");
		expect(processingStatus([delegate({ result: null })], false)).toBe("neutral");
	});
});

// AR answers some delegate calls with plain text and status success
// (delegation_batch.BATCH_ALREADY_RUNNING, run_batch's "Nothing to delegate.",
// delegation.TASKS_NOT_A_LIST). Readable text without task sections ran nothing.
const BATCH_ALREADY_RUNNING =
	"A delegate batch is already running for this turn; put all independent tasks in ONE " +
	"delegate call and wait for its result.";
const TASKS_NOT_A_LIST =
	'Nothing delegated: tasks must be a list of {"task_id": "<plan task id>", ' +
	'"instructions": "<full description>"} objects.';

describe("processingSummary for delegate calls AR turned away", () => {
	it("counts a concurrent call AR refused as none run", () => {
		const blocks = [
			delegate({ result: allDone }),
			delegate({ id: "d2", result: BATCH_ALREADY_RUNNING }),
		];
		expect(processingSummary(blocks, false)).toBe("Delegated 4 of 8 subtasks");
		expect(processingStatus(blocks, false)).toBe("error");
	});

	it("counts a call with nothing to delegate as none run", () => {
		const block = delegate({ result: "Nothing to delegate." });
		expect(processingSummary([block], false)).toBe("Delegated 0 of 4 subtasks");
		expect(processingStatus([block], false)).toBe("error");
	});

	it("does not invent a subtask for tasks it cannot read", () => {
		const block = delegate({ input: { tasks: "not json" }, result: TASKS_NOT_A_LIST });
		expect(processingSummary([block], false)).toBe("Delegated no subtasks");
		expect(processingStatus([block], false)).toBe("error");
	});

	// truncate_result_for_emit caps the live socket copy; the persisted block
	// keeps the full result, which the stream_complete snapshot brings.
	it("stays neutral about a result cut short on the socket", () => {
		const listCut = delegate({ result: { _truncated: true, preview: "[{\"text\": \"## t-1", _note: "full result available on reload" } });
		const textCut = delegate({ result: `${section("t-1", "done")}\n\n…[truncated — full result available on reload]` });
		for (const block of [listCut, textCut]) {
			expect(processingSummary([block], false)).toBe("Delegated 4 subtasks");
			expect(processingStatus([block], false)).toBe("neutral");
		}
	});
});

describe("ProcessingCard header for delegation", () => {
	const header = (blocks) =>
		mount(ProcessingCard, { props: { blocks, isStreaming: false, messageIndex: 0 } }).find(
			".processing-status-icon"
		);

	it("shows no checkmark for a call that ran no subtask", () => {
		expect(header([delegate({ result: noneRan })]).classes()).toContain("status-error");
	});

	it("shows a stopped icon for a delegate the turn left running", () => {
		expect(header([delegate({ status: "running", result: null })]).classes()).toContain("status-stopped");
	});

	it("shows a stopped icon for any tool the ended turn left running", () => {
		const tool = { type: "tool_call", id: "t1", tool_name: "list_documents", status: "running" };
		expect(header([tool]).classes()).toContain("status-stopped");
	});

	it("keeps the checkmark when every subtask ran", () => {
		expect(header([delegate({ result: allDone })]).classes()).toContain("status-complete");
	});
});
