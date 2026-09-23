import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";

// Stub vue-echarts so we don't render a real canvas; expose a fake instance.
const fakeInline = {
	getDataURL: vi.fn(() => "data:image/png;base64,INLINE"),
};
vi.mock("vue-echarts", () => ({
	default: {
		name: "VChart",
		props: ["option", "autoresize"],
		template: "<div class='v-chart-stub' />",
		setup(_p, { expose }) {
			expose({ chart: fakeInline });
			return () => {};
		},
	},
}));

// Stub echarts/core init used by capture() for the modal instance.
const disposeSpy = vi.fn();
const setOptionSpy = vi.fn();
vi.mock("echarts/core", async (importOriginal) => {
	const actual = await importOriginal();
	return {
		...actual,
		init: vi.fn(() => ({ setOption: setOptionSpy, dispose: disposeSpy })),
	};
});

import ChartRenderer from "@/components/chat/ChartRenderer.vue";

const ExpandableStub = {
	name: "ExpandableArtifact",
	props: ["capture", "canCapture", "toPng", "title", "disabled"],
	template: `<div class="exp-stub"><slot /></div>`,
};

const CONFIG = {
	type: "bar",
	title: "Sales",
	data: { categories: ["A", "B"], series: [{ name: "S", values: [1, 2] }] },
};

function mountChart(props = {}) {
	return mount(ChartRenderer, {
		props: { config: CONFIG, ...props },
		global: { stubs: { ExpandableArtifact: ExpandableStub } },
	});
}

describe("ChartRenderer expand integration", () => {
	it("wraps the chart in ExpandableArtifact with capture/canCapture/toPng", async () => {
		const w = mountChart();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		expect(exp.exists()).toBe(true);
		expect(typeof exp.props("capture")).toBe("function");
		expect(typeof exp.props("canCapture")).toBe("function");
		expect(typeof exp.props("toPng")).toBe("function");
	});

	it("canCapture is true for a valid chart", async () => {
		const w = mountChart();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		expect(exp.props("canCapture")()).toBe(true);
	});

	it("toPng uses the inline chart's getDataURL at pixelRatio 2", async () => {
		const w = mountChart();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		const url = await exp.props("toPng")();
		expect(url).toBe("data:image/png;base64,INLINE");
		expect(fakeInline.getDataURL).toHaveBeenCalledWith(
			expect.objectContaining({ type: "png", pixelRatio: 2, backgroundColor: "#fff" })
		);
	});

	it("capture builds a fresh instance and its cleanup disposes it", async () => {
		const w = mountChart();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		const result = exp.props("capture")();
		expect(result).not.toBeNull();
		expect(result.node.tagName.toLowerCase()).toBe("div");
		expect(setOptionSpy).toHaveBeenCalled();
		result.cleanup();
		expect(disposeSpy).toHaveBeenCalledTimes(1);
	});

	it("canCapture is false when the chart is in an error state", async () => {
		const w = mountChart({ config: { type: "nope", data: {} } });
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		expect(exp.props("canCapture")()).toBe(false);
	});

	it("forwards isStreaming to disabled", async () => {
		const w = mountChart({ isStreaming: true });
		await flushPromises();
		expect(w.findComponent(ExpandableStub).props("disabled")).toBe(true);
	});
});
