import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import TaskList from "../TaskList.vue";

function mountList(tasks) {
	return mount(TaskList, { props: { tasks } });
}

describe("TaskList", () => {
	it("renders nothing when there are no tasks", () => {
		expect(mountList([]).find(".task-section").exists()).toBe(false);
	});

	it("renders the title and note in separate elements (no overlap)", () => {
		const wrapper = mountList([
			{ id: "1", title: "Inspect required fields", status: "done", note: "found company 'FAC' (INR)" },
		]);
		const row = wrapper.find(".task-row");
		const title = row.find(".title");
		const note = row.find(".note");
		expect(title.exists()).toBe(true);
		expect(note.exists()).toBe(true);
		// title and note are distinct nodes; note is NOT inside the title line
		expect(row.find(".task-line").element.contains(note.element)).toBe(false);
		expect(title.text()).toBe("Inspect required fields");
		expect(note.text()).toContain("found company");
	});

	it("styles a failed task's note as a reason card", () => {
		const wrapper = mountList([
			{ id: "1", title: "Submit the demo invoices", status: "failed", note: "Posting date is in a closed period" },
		]);
		const note = wrapper.find(".task-row.is-failed .note");
		expect(note.exists()).toBe(true);
		expect(note.classes()).toContain("is-reason");
		expect(note.text()).toBe("Posting date is in a closed period");
	});

	it("does not render a note element when the task has none", () => {
		const wrapper = mountList([{ id: "1", title: "Create demo territories", status: "running" }]);
		expect(wrapper.find(".note").exists()).toBe(false);
	});

	it("applies status and child classes", () => {
		const wrapper = mountList([
			{ id: "1", title: "Parent", status: "running" },
			{ id: "2", title: "Child", status: "pending", parentId: "1" },
		]);
		const rows = wrapper.findAll(".task-row");
		expect(rows[0].classes()).toContain("is-running");
		expect(rows[1].classes()).toContain("is-child");
	});

	it("exposes note in the aria-label for screen readers", () => {
		const wrapper = mountList([
			{ id: "1", title: "Inspect", status: "failed", note: "closed period" },
		]);
		expect(wrapper.find(".task-row").attributes("aria-label")).toBe(
			"Inspect — failed: closed period"
		);
	});
});

// Live-bug repro: the model closes each task as it goes, but the FINAL task is
// the "answer the user" step — it flips to `running`, the answer streams, and
// nothing ever closes it. AR deliberately never fakes it to `done`
// (streaming.py:783-797 "running stays running"), so the rail kept rendering a
// spinning glyph forever, including after a reload. The widget never had this
// bug because it collapses the plan on plan_complete.
describe("TaskList after the turn ends", () => {
	const PARTIAL = [
		{ id: "1", title: "Create a Sales Return", status: "done" },
		{ id: "2", title: "Create a Credit Note", status: "done" },
		{ id: "3", title: "Create a refund Payment Entry", status: "done" },
		{ id: "4", title: "Explain how the return reverses stock", status: "running" },
	];

	it("stops presenting a left-open task as in-flight", () => {
		const wrapper = mount(TaskList, { props: { tasks: PARTIAL, live: false } });
		const last = wrapper.findAll(".task-row")[3];

		expect(last.classes()).not.toContain("is-running");
		expect(last.classes()).toContain("is-unfinished");
	});

	it("says how much of the plan actually completed", () => {
		const wrapper = mount(TaskList, { props: { tasks: PARTIAL, live: false } });

		expect(wrapper.find(".task-summary").text()).toBe("Completed 3 of 4 steps");
	});

	it("keeps a running task in-flight while the turn is still live", () => {
		const wrapper = mount(TaskList, { props: { tasks: PARTIAL, live: true } });
		const last = wrapper.findAll(".task-row")[3];

		expect(last.classes()).toContain("is-running");
		expect(wrapper.find(".task-summary").exists()).toBe(false);
	});

	it("does not nag when every task closed cleanly", () => {
		const done = PARTIAL.map((t) => ({ ...t, status: "done" }));
		const wrapper = mount(TaskList, { props: { tasks: done, live: false } });

		expect(wrapper.find(".task-summary").exists()).toBe(false);
	});
});

describe("TaskList parallel helpers", () => {
	it("shows a live label under each running helper row while live", () => {
		const wrapper = mount(TaskList, {
			props: {
				tasks: [
					{ id: "a", title: "Customer A", status: "running", helper: true },
					{ id: "b", title: "Customer B", status: "running", helper: true },
				],
				activity: { a: "Reading Sales Invoice list…", b: "Opening Customer B…" },
				live: true,
			},
		});
		const labels = wrapper.findAll(".activity").map((n) => n.text());
		expect(labels).toEqual(["Reading Sales Invoice list…", "Opening Customer B…"]);
	});

	it("shows helper meta on a finished helper row and no label after the turn", () => {
		const wrapper = mount(TaskList, {
			props: {
				tasks: [
					{
						id: "a",
						title: "Customer A",
						status: "done",
						helper: true,
						duration_ms: 12400,
						credits: 0.4,
					},
				],
				activity: { a: "stale label" },
				live: false,
			},
		});
		expect(wrapper.find(".helper-meta").text()).toBe("↳ helper · 12s · 0.4 credits");
		expect(wrapper.find(".activity").exists()).toBe(false);
	});

	it("rounds helper credits like the widget, singular for exactly one", () => {
		const meta = (credits) =>
			mount(TaskList, {
				props: { tasks: [{ id: "a", title: "A", status: "done", helper: true, credits }] },
			})
				.find(".helper-meta")
				.text();
		expect(meta(0.123456)).toBe("↳ helper · 0.12 credits");
		expect(meta(1)).toBe("↳ helper · 1 credit");
		expect(meta(0.999)).toBe("↳ helper · 1 credit");
		expect(meta(NaN)).toBe("↳ helper");
		expect(meta(Infinity)).toBe("↳ helper");
	});

	it("drops the live label from a helper the turn left running", () => {
		const wrapper = mount(TaskList, {
			props: {
				tasks: [{ id: "a", title: "Customer A", status: "running", helper: true }],
				activity: { a: "Reading Sales Invoice list…" },
				live: false,
			},
		});
		expect(wrapper.find(".activity").exists()).toBe(false);
	});

	it("keeps the old specialist tag for legacy delegated rows without helper fields", () => {
		const wrapper = mount(TaskList, {
			props: { tasks: [{ id: "a", title: "A", status: "done", delegated: true }] },
		});
		expect(wrapper.find(".delegated").exists()).toBe(true);
	});
});

describe("TaskList bare", () => {
	it("leaves the heading and the tally to its host", () => {
		const tasks = [{ id: "a", title: "A", status: "running" }];
		const framed = mount(TaskList, { props: { tasks, live: false } });
		expect(framed.find(".task-head").exists()).toBe(true);
		expect(framed.find(".task-summary").exists()).toBe(true);
		const bare = mount(TaskList, { props: { tasks, live: false, bare: true } });
		expect(bare.find(".task-head").exists()).toBe(false);
		expect(bare.find(".task-summary").exists()).toBe(false);
		expect(bare.find(".task-row").exists()).toBe(true);
	});
});
