import { mount } from "@vue/test-utils";
import { describe, it, expect, vi, afterEach } from "vitest";
import ActivityTimeline from "../ActivityTimeline.vue";

const doneRow = {
	id: "t1", status: "success", label: "Read record → HSA-2026-0041",
	target: "HSA-2026-0041", toolName: "get_document", hasTarget: true,
	block: { startTime: "2026-07-20T09:00:00.000Z", endTime: "2026-07-20T09:00:01.200Z" },
};
const runningRow = {
	id: "t2", status: "running", label: "Searched documents",
	target: null, toolName: "search_documents", hasTarget: false,
	block: { startTime: "2026-07-20T09:00:01.000Z", endTime: null },
};

afterEach(() => vi.useRealTimers());

describe("ActivityTimeline", () => {
	it("renders one node per row with status classes and durations", () => {
		const wrapper = mount(ActivityTimeline, { props: { rows: [doneRow, runningRow] } });
		expect(wrapper.findAll(".tl-row")).toHaveLength(2);
		expect(wrapper.find(".tl-row.is-success .tl-duration").text()).toBe("1.2s");
		expect(wrapper.find(".tl-row.is-running").exists()).toBe(true);
	});
	it("compresses to a summary 2.5s after the last tool finishes", async () => {
		vi.useFakeTimers();
		const wrapper = mount(ActivityTimeline, { props: { rows: [runningRow] } });
		await wrapper.setProps({ rows: [doneRow, { ...runningRow, status: "success", block: { ...runningRow.block, endTime: "2026-07-20T09:00:03.000Z" } }] });
		await vi.advanceTimersByTimeAsync(2600);
		expect(wrapper.find(".tl-summary").text()).toContain("2 actions");
		await wrapper.find(".tl-summary").trigger("click");
		expect(wrapper.findAll(".tl-row")).toHaveLength(2);
	});
	it("starts expanded for a fresh non-streaming turn without collapsing", () => {
		const wrapper = mount(ActivityTimeline, { props: { rows: [doneRow] } });
		expect(wrapper.find(".tl-summary").exists()).toBe(false);
	});
});

// Live-bug repro: a stopped turn persisted its `delegate` tool block with
// status `running` and no end time. After a reload the rail showed
// "Delegate 1m 5s…" behind a pulsing live dot, and the timer kept ticking on
// a turn that had long ended.
describe("ActivityTimeline after the turn ends", () => {
	const leftRunning = {
		id: "d1", status: "running", label: "Delegate",
		target: null, toolName: "delegate", hasTarget: false,
		block: { startTime: "2026-07-20T09:00:00.000Z", endTime: null },
	};

	it("shows a tool left running as stopped, with no live dot and no timer", async () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-07-20T09:01:05.000Z"));
		const wrapper = mount(ActivityTimeline, { props: { rows: [leftRunning], live: false } });
		const row = wrapper.find(".tl-row");

		expect(row.classes()).not.toContain("is-running");
		expect(row.classes()).toContain("is-stopped");
		expect(row.find(".tl-node").text()).toBe("⊘");
		expect(row.find(".tl-duration").text()).toBe("stopped");

		await vi.advanceTimersByTimeAsync(3000);
		expect(wrapper.find(".tl-row .tl-duration").text()).toBe("stopped");
	});

	it("keeps the elapsed time when the left-running tool has an end time", () => {
		const ended = { ...leftRunning, block: { ...leftRunning.block, endTime: "2026-07-20T09:00:04.000Z" } };
		const wrapper = mount(ActivityTimeline, { props: { rows: [ended], live: false } });

		expect(wrapper.find(".tl-row .tl-duration").text()).toBe("4.0s");
	});

	it("still ticks a running tool while the turn is live", async () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-07-20T09:00:05.000Z"));
		const wrapper = mount(ActivityTimeline, { props: { rows: [leftRunning], live: true } });

		expect(wrapper.find(".tl-row").classes()).toContain("is-running");
		expect(wrapper.find(".tl-row .tl-duration").text()).toBe("5.0s…");
	});
});
