import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";

const initializeSpy = vi.fn();
vi.mock("mermaid", () => ({
	default: {
		initialize: (...args) => initializeSpy(...args),
		render: vi.fn(async (id) => ({ svg: `<svg id="${id}" viewBox="0 0 100 50"><text>x</text></svg>` })),
	},
}));

import MermaidDiagram from "@/components/chat/MermaidDiagram.vue";

// Stub the wrapper so we don't pull the modal in.
const ExpandableStub = {
	name: "ExpandableArtifact",
	props: ["capture", "canCapture", "toPng", "title", "disabled"],
	template: `<div><slot /></div>`,
};

describe("MermaidDiagram uses native SVG text labels (no foreignObject)", () => {
	it("initializes mermaid with htmlLabels:false at root and flowchart", async () => {
		mount(MermaidDiagram, {
			props: { content: "graph TD; A-->B" },
			global: { stubs: { ExpandableArtifact: ExpandableStub } },
		});
		await flushPromises();
		expect(initializeSpy).toHaveBeenCalled();
		const cfg = initializeSpy.mock.calls[0][0];
		expect(cfg.htmlLabels).toBe(false);
		expect(cfg.flowchart.htmlLabels).toBe(false);
	});
});
