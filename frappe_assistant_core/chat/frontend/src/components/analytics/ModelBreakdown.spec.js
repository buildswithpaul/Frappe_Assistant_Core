import { mount } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";
import ModelBreakdown from "./ModelBreakdown.vue";

vi.mock("vue-echarts", () => ({
	default: { name: "VChart", props: ["option"], template: "<div/>" },
}));

const MODELS = [
	{ model_id: "claude-sonnet-4-6", credits_consumed: 40 },
	{ model_id: "global.anthropic.claude-haiku-4-5-20251001-v1:0", credits_consumed: 10 },
];

function chartOption(models = MODELS) {
	const wrapper = mount(ModelBreakdown, {
		props: { models, totalCredits: 100 },
	});
	return wrapper.findComponent({ name: "VChart" }).props("option");
}

describe("ModelBreakdown", () => {
	it("labels the axis with readable model names", () => {
		expect(chartOption().yAxis.data).toEqual(["Claude Sonnet 4.6", "Claude Haiku 4.5"]);
	});

	it("keeps the raw model id in the tooltip", () => {
		const html = chartOption().tooltip.formatter([{ dataIndex: 0, value: 40 }]);
		expect(html).toContain("claude-sonnet-4-6");
		expect(html).toContain("Claude Sonnet 4.6");
	});

	it("fits the axis to the data instead of fixing it at 100", () => {
		expect(chartOption().xAxis.max).not.toBe(100);
	});

	it("escapes hostile model ids in the tooltip", () => {
		const option = chartOption([{ model_id: '<img src=x onerror=alert(1)>"', credits_consumed: 5 }]);
		const html = option.tooltip.formatter([{ dataIndex: 0, value: 5 }]);
		expect(html).not.toContain("<img");
		expect(html).not.toContain('"<');
		expect(html.replace(/<(strong|\/strong|br\/|span style="[^"]*"|\/span)>/g, "")).not.toMatch(/[<>"]/);
	});
});
