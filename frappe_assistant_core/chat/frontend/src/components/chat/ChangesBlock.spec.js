import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, it, expect, vi, beforeEach } from "vitest";

const undoChange = vi.fn();
vi.mock("@/api/client", () => ({
	api: { chat: { undoChange: (...a) => undoChange(...a) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn() }));

import ChangesBlock from "@/components/chat/ChangesBlock.vue";
import { useChatStore } from "@/stores/chatStore";

// The block as the relay persists it and a reload returns it.
const changesBlock = () => ({
	type: "changes_made",
	id: "changes_made_1",
	changes: [
		{ doctype: "Note", name: "NOTE-0003", action: "create", undo: "delete", undone: false },
		{ doctype: "ToDo", name: "TD-0001", action: "create", undo: "delete", undone: true },
	],
});

let store;

beforeEach(() => {
	setActivePinia(createPinia());
	store = useChatStore();
	store.currentSessionId = "s1";
	undoChange.mockReset();
});

// The component receives the very block the store holds, as MessageBlockRenderer passes it.
function mountBlock({ isStreaming = false } = {}) {
	store.messages = [{ role: "assistant", message_id: "m1", blocks: [changesBlock()] }];
	const block = store.messages[0].blocks[0];
	return mount(ChangesBlock, { props: { block, messageId: "m1", isStreaming } });
}

const row = (wrapper, name) => wrapper.find(`[data-change="${name}"]`);

describe("ChangesBlock", () => {
	it("ChangesBlock renders rows and undone state", () => {
		const wrapper = mountBlock();
		expect(wrapper.text()).toContain("Changes made");
		expect(row(wrapper, "NOTE-0003").text()).toContain("Created Note · NOTE-0003");
		expect(row(wrapper, "NOTE-0003").find("button").text()).toBe("Undo");
		expect(row(wrapper, "TD-0001").text()).toContain("Undone");
		expect(row(wrapper, "TD-0001").find("button").exists()).toBe(false);
	});

	it("undo calls the store and shows a refusal reason", async () => {
		undoChange.mockResolvedValue({ success: false, reason: "Something now links to it" });
		const wrapper = mountBlock();
		await row(wrapper, "NOTE-0003").find("button").trigger("click");
		await flushPromises();
		expect(undoChange).toHaveBeenCalledWith("s1", "m1", "Note", "NOTE-0003");
		expect(row(wrapper, "NOTE-0003").text()).toContain("Something now links to it");
		expect(row(wrapper, "NOTE-0003").find("button").text()).toBe("Undo");
		expect(store.messages[0].blocks[0].changes[0].undone).toBe(false);
	});

	it("marks the row undone when the undo succeeds", async () => {
		undoChange.mockResolvedValue({ success: true });
		const wrapper = mountBlock();
		await row(wrapper, "NOTE-0003").find("button").trigger("click");
		await flushPromises();
		expect(store.messages[0].blocks[0].changes[0].undone).toBe(true);
		expect(row(wrapper, "NOTE-0003").text()).toContain("Undone");
		expect(row(wrapper, "NOTE-0003").find("button").exists()).toBe(false);
	});

	it("shows a thrown refusal inline", async () => {
		undoChange.mockRejectedValue(new Error("You do not have permission to delete Note NOTE-0003"));
		const wrapper = mountBlock();
		await row(wrapper, "NOTE-0003").find("button").trigger("click");
		await flushPromises();
		expect(row(wrapper, "NOTE-0003").text()).toContain("You do not have permission to delete Note NOTE-0003");
	});

	// A live-stream undo could be reset by the stream's final snapshot of the blocks.
	it("keeps Undo disabled and sends nothing while the message streams", async () => {
		const wrapper = mountBlock({ isStreaming: true });
		const button = row(wrapper, "NOTE-0003").find("button");
		expect(button.attributes("disabled")).toBeDefined();
		await button.trigger("click");
		await flushPromises();
		expect(undoChange).not.toHaveBeenCalled();
	});

	// production: Frappe's window.__ is present when the SPA is served inside Desk
	it("passes its visible strings through the translator", () => {
		window.__ = (text, args) => `[${text}]${args ? args.join("|") : ""}`;
		try {
			const wrapper = mountBlock();
			expect(wrapper.text()).toContain("[Changes made]");
			expect(row(wrapper, "NOTE-0003").find("button").text()).toBe("[Undo]");
			expect(row(wrapper, "TD-0001").text()).toContain("[Undone]");
		} finally {
			delete window.__;
		}
	});
});
