import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { defineComponent, nextTick, ref } from "vue";

import { usePagePanel } from "./usePagePanel";

const pageWrite = (name, id) => ({
	type: "tool_call",
	id,
	tool_name: "update_document",
	status: "success",
	input: { doctype: "FAC Page", name, data: { html: "<p>x</p>" } },
	result: { success: true, name, doctype: "FAC Page" },
});

// A create as it streams in: running with no record name, which arrives with its result.
const runningCreate = (id) => ({
	type: "tool_call",
	id,
	tool_name: "create_document",
	status: "running",
	input: { doctype: "FAC Page", data: { title: "Sales", visibility: "Only me" } },
	result: null,
});

function land(block, name) {
	block.status = "success";
	block.result = { success: true, name, doctype: "FAC Page" };
}

// The dock calls usePagePanel with the conversation; a component gives the watcher a scope.
function track(messages) {
	let panel;
	mount(defineComponent({ setup: () => ((panel = usePagePanel(messages)), () => null) }));
	return panel;
}

afterEach(() => usePagePanel().close());

describe("usePagePanel", () => {
	it("opens and closes one page by name, shared across callers", () => {
		usePagePanel().open("sales-a1b2c3");
		expect(usePagePanel().openName.value).toBe("sales-a1b2c3");
		usePagePanel().close();
		expect(usePagePanel().openName.value).toBe(null);
	});

	it("bumps refreshKey when a write to the open page lands", async () => {
		const messages = ref([{ role: "assistant", blocks: [pageWrite("sales-a1b2c3", "t1")] }]);
		const panel = track(messages);
		panel.open("sales-a1b2c3");
		// Opening fetches the page itself; the write lands afterwards, as it does in use.
		await nextTick();
		const before = panel.refreshKey.value;

		messages.value[0].blocks.push(pageWrite("sales-a1b2c3", "t2"));
		await nextTick();

		expect(panel.refreshKey.value).toBe(before + 1);
	});

	it("leaves refreshKey alone when another page is written", async () => {
		const messages = ref([{ role: "assistant", blocks: [pageWrite("sales-a1b2c3", "t1")] }]);
		const panel = track(messages);
		panel.open("sales-a1b2c3");
		// Opening fetches the page itself; the write lands afterwards, as it does in use.
		await nextTick();
		const before = panel.refreshKey.value;

		messages.value[0].blocks.push(pageWrite("costs-a1b2c3", "t2"));
		await nextTick();

		expect(panel.refreshKey.value).toBe(before);
	});

	it("exposes the conversation's chips, so the panel knows the version and pending state", async () => {
		const messages = ref([
			{ role: "user", content: "make a page" },
			{ role: "assistant", blocks: [pageWrite("sales-a1b2c3", "t1"), pageWrite("sales-a1b2c3", "t2")] },
		]);
		const panel = track(messages);
		await nextTick();
		expect(panel.chips.value).toEqual([{ name: "sales-a1b2c3", title: "sales-a1b2c3", version: 2, pending: false }]);
	});

	it("opens a page FACO creates during the turn, once its save lands", async () => {
		const messages = ref([{ role: "assistant", blocks: [runningCreate("t1")] }]);
		const panel = track(messages);
		await nextTick();
		expect(panel.openName.value).toBe(null);

		land(messages.value[0].blocks[0], "sales-59f062");
		await nextTick();

		expect(panel.openName.value).toBe("sales-59f062");
	});

	it("does not open a page from the conversation's history", async () => {
		const panel = track(ref([{ role: "assistant", blocks: [pageWrite("sales-a1b2c3", "t1")] }]));
		await nextTick();
		expect(panel.openName.value).toBe(null);
	});

	it("keeps the page the user has open when FACO saves another", async () => {
		const messages = ref([{ role: "assistant", blocks: [runningCreate("t1")] }]);
		const panel = track(messages);
		panel.open("costs-a1b2c3");
		await nextTick();

		land(messages.value[0].blocks[0], "sales-59f062");
		await nextTick();

		expect(panel.openName.value).toBe("costs-a1b2c3");
	});

	it("leaves a saved page behind its chip on a phone, where the panel would cover the reply", async () => {
		const matchMedia = window.matchMedia;
		window.matchMedia = (query) => ({ matches: query === "(max-width: 767px)" });
		try {
			const messages = ref([{ role: "assistant", blocks: [runningCreate("t1")] }]);
			const panel = track(messages);
			await nextTick();

			land(messages.value[0].blocks[0], "sales-59f062");
			await nextTick();

			expect(panel.openName.value).toBe(null);
			expect(panel.chips.value.map((chip) => chip.name)).toEqual(["sales-59f062"]);
		} finally {
			window.matchMedia = matchMedia;
		}
	});

	it("does not open a page whose write failed", async () => {
		const messages = ref([{ role: "assistant", blocks: [runningCreate("t1")] }]);
		const panel = track(messages);
		await nextTick();

		const block = messages.value[0].blocks[0];
		block.status = "error";
		block.result = { success: false, error: "x" };
		await nextTick();

		expect(panel.openName.value).toBe(null);
	});
});
