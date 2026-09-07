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
