import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";
import { usePagePanel } from "@/composables/usePagePanel";

const pageCreate = {
	id: "t1",
	type: "tool_call",
	tool_name: "create_document",
	status: "success",
	input: { doctype: "FAC Page", data: { title: "Sales this month" } },
	result: { success: true, name: "sales-a1b2c3", doctype: "FAC Page" },
};

function mountRenderer(blocks) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0 },
		global: { stubs: { ProcessingCard: true, ProcessingIndicator: true } },
	});
}

// The SPA mounts a PageDock beside the conversation; the widget does not (FacPageChip.spec covers it).
let unregister;
beforeEach(() => (unregister = usePagePanel().registerDock()));
afterEach(() => {
	unregister();
	usePagePanel().close();
});

describe("page chips in the message footer", () => {
	it("shows a chip for a page this message wrote, and opens it on click", async () => {
		const w = mountRenderer([pageCreate, { id: "x1", type: "text", content: "Here it is." }]);
		const chip = w.find(".fac-page-chip");
		expect(chip.text()).toContain("Sales this month");
		expect(chip.text()).toContain("v1");
		await chip.trigger("click");
		expect(usePagePanel().openName.value).toBe("sales-a1b2c3");
	});

	it("shows no chip for a message that wrote no page", () => {
		const w = mountRenderer([{ id: "x1", type: "text", content: "Hello" }]);
		expect(w.find(".fac-page-chip").exists()).toBe(false);
	});
});
