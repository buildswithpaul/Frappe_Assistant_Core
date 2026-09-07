import { mount } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";

// Replace the rich-block parser with one that emits a single component part,
// so we can inspect the props the renderer binds onto <component :is>.
const Probe = {
	name: "Probe",
	props: ["content", "isStreaming"],
	template: `<div class="probe" :data-streaming="String(isStreaming)">{{ content }}</div>`,
};
vi.mock("@/components/chat/richBlocks/parser", () => ({
	parseRichBlocks: () => [
		{ type: "component", component: Probe, props: { content: "X" } },
	],
}));

import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

function mountRenderer(isStreaming) {
	return mount(MessageBlockRenderer, {
		props: {
			blocks: [{ id: "b1", type: "text", content: "hello" }],
			messageIndex: 0,
			isStreaming,
		},
	});
}

describe("MessageBlockRenderer passes isStreaming to rich blocks", () => {
	it("binds is-streaming=true while streaming", () => {
		const w = mountRenderer(true);
		expect(w.find(".probe").attributes("data-streaming")).toBe("true");
	});

	it("binds is-streaming=false when not streaming", () => {
		const w = mountRenderer(false);
		expect(w.find(".probe").attributes("data-streaming")).toBe("false");
	});
});
