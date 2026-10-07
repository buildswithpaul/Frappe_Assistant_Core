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

	it("trusts a successful call whose result it cannot read", () => {
		expect(processingSummary([delegate({ result: null })], false)).toBe("Delegated 4 subtasks");
		expect(processingStatus([delegate({ result: null })], false)).toBe("complete");
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
