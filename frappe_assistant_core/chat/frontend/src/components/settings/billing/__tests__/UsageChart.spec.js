import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";

/**
 * The chart lives under the Prepaid Credits card, so it answers "what did my
 * purchased credits pay for". Its feed now returns prepaid draw only.
 *
 * Two things used to go wrong here. The series list was hardcoded to five
 * sources and everything else — Suggestions, Web Search, Voice Transcription —
 * was silently filtered out of the bars, so the chart quietly under-reported.
 * And the empty state read "No consumption yet", which is false and alarming
 * for the common case: a tenant comfortably inside its monthly quota has spent
 * no prepaid credits at all.
 */

const getConsumptionBreakdown = vi.fn();

vi.mock("@/api/client", () => ({
	api: { billing: { getConsumptionBreakdown: (...a) => getConsumptionBreakdown(...a) } },
}));
vi.mock("vue-echarts", () => ({ default: { name: "VChart", props: ["option"], template: "<div />" } }));

import UsageChart from "../UsageChart.vue";

async function render(series) {
	getConsumptionBreakdown.mockResolvedValue({ series });
	const wrapper = mount(UsageChart);
	await flushPromises();
	return wrapper;
}

function seriesNames(wrapper) {
	const chart = wrapper.findComponent({ name: "VChart" });
	return (chart.props("option").series || []).map((s) => s.name);
}

beforeEach(() => getConsumptionBreakdown.mockReset());

describe("UsageChart", () => {
	it("names itself after what it actually measures", async () => {
		const wrapper = await render([{ date: "2026-09-08", source: "Chat", credits: 3110 }]);
		expect(wrapper.text()).toContain("Prepaid Credit Consumption");
	});

	it("plots sources beyond the historical hardcoded five", async () => {
		const wrapper = await render([
			{ date: "2026-09-08", source: "Chat", credits: 100 },
			{ date: "2026-09-08", source: "Suggestions", credits: 14 },
			{ date: "2026-09-08", source: "Web Search", credits: 6 },
			{ date: "2026-09-08", source: "Voice Transcription", credits: 2 },
		]);
		expect(seriesNames(wrapper).sort()).toEqual(
			["Chat", "Suggestions", "Voice Transcription", "Web Search"].sort(),
		);
	});

	it("keeps a stable order for the known sources", async () => {
		const wrapper = await render([
			{ date: "2026-09-08", source: "Workflow", credits: 5 },
			{ date: "2026-09-08", source: "Chat", credits: 5 },
			{ date: "2026-09-08", source: "Memory Extraction", credits: 5 },
		]);
		expect(seriesNames(wrapper)).toEqual(["Chat", "Memory Extraction", "Workflow"]);
	});

	it("gives every source its own colour, unknown ones included", async () => {
		const wrapper = await render([
			{ date: "2026-09-08", source: "Chat", credits: 5 },
			{ date: "2026-09-08", source: "Suggestions", credits: 5 },
			{ date: "2026-09-08", source: "Something New", credits: 5 },
		]);
		const colors = wrapper
			.findComponent({ name: "VChart" })
			.props("option")
			.series.map((s) => s.itemStyle.color);
		expect(new Set(colors).size).toBe(3);
	});

	it("explains an empty chart as quota coverage, not as no usage", async () => {
		const wrapper = await render([]);
		expect(wrapper.text()).toContain("monthly quota");
		expect(wrapper.text()).not.toContain("No consumption yet");
	});

	it("survives a failed load without rendering a chart", async () => {
		getConsumptionBreakdown.mockResolvedValue({ error: "boom" });
		const wrapper = mount(UsageChart);
		await flushPromises();
		expect(wrapper.findComponent({ name: "VChart" }).exists()).toBe(false);
	});
});
