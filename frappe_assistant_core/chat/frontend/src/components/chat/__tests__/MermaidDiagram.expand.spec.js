import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";

// Mermaid pulls in a huge ESM bundle; stub it so the component mounts fast and
// deterministically. render() returns a trivial <svg> string.
vi.mock("mermaid", () => ({
	default: {
		initialize: vi.fn(),
		render: vi.fn(async (id, _content) => ({
			svg: `<svg id="${id}" width="100%" viewBox="0 0 300 150" style="max-width: 300px;"><rect/></svg>`,
		})),
	},
}));

import MermaidDiagram from "@/components/chat/MermaidDiagram.vue";

const ExpandableStub = {
	name: "ExpandableArtifact",
	props: ["capture", "canCapture", "toPng", "title", "disabled"],
	template: `<div class="exp-stub"><slot /></div>`,
};

function mountDiagram(props = {}) {
	return mount(MermaidDiagram, {
		props: { content: "graph TD; A-->B", ...props },
		global: { stubs: { ExpandableArtifact: ExpandableStub } },
	});
}

describe("MermaidDiagram expand integration", () => {
	it("wraps content in ExpandableArtifact and passes capture/canCapture/toPng", async () => {
		const w = mountDiagram();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		expect(exp.exists()).toBe(true);
		expect(typeof exp.props("capture")).toBe("function");
		expect(typeof exp.props("canCapture")).toBe("function");
		expect(typeof exp.props("toPng")).toBe("function");
	});

	it("canCapture is true after render and capture() returns a cloned svg node", async () => {
		const w = mountDiagram();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		expect(exp.props("canCapture")()).toBe(true);
		const result = exp.props("capture")();
		expect(result).not.toBeNull();
		expect(result.node.tagName.toLowerCase()).toBe("svg");
		// it is a CLONE, not the live node
		const liveSvg = w.find("svg").element;
		expect(result.node).not.toBe(liveSvg);
	});

	it("capture() normalizes the clone to intrinsic viewBox size (sharp zoom)", async () => {
		const w = mountDiagram();
		await flushPromises();
		const exp = w.findComponent(ExpandableStub);
		const { node } = exp.props("capture")();
		// width/height pinned to viewBox dimensions, not "100%"
		expect(node.getAttribute("width")).toBe("300");
		expect(node.getAttribute("height")).toBe("150");
		// the max-width inline constraint is stripped
		expect(node.style.maxWidth).toBe("");
	});

	it("canCapture is false before any svg has rendered (error/fallback)", () => {
		const w = mountDiagram();
		// Before flushPromises the async render hasn't populated the container.
		const exp = w.findComponent(ExpandableStub);
		expect(exp.props("canCapture")()).toBe(false);
	});

	it("forwards isStreaming to ExpandableArtifact.disabled", async () => {
		const w = mountDiagram({ isStreaming: true });
		await flushPromises();
		expect(w.findComponent(ExpandableStub).props("disabled")).toBe(true);
	});
});
