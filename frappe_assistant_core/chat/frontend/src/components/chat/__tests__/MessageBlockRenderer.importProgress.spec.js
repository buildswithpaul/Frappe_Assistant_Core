import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({ api: { imports: { progress: vi.fn() } } }));

import { api } from "@/api/client";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";
import { _reset } from "@/composables/useImportProgress";

const started = {
	id: "t1",
	type: "tool_call",
	tool_name: "start_import",
	status: "success",
	input: { session: "IMP-1" },
	result: { success: true, session: "IMP-1", state: "started", data_import: "DI-1" },
};

function mountRenderer(blocks) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0 },
		global: { stubs: { ProcessingCard: true, ProcessingIndicator: true } },
	});
}

beforeEach(() => {
	_reset();
	api.imports.progress.mockResolvedValue({
		sessions: [
			{
				session: "IMP-1",
				status: "Importing",
				importing: true,
				ended: false,
				data_import: "DI-1",
				total: 250,
				created: 120,
				failed: 0,
				file_name: "customers.csv",
				url: "/app/fac-import-session/IMP-1",
			},
		],
		steps: [],
	});
});

describe("an import's progress under the message that started it (#34416)", () => {
	it("shows the file, the rows done of the total and a Desk link, with no model call", async () => {
		const w = mountRenderer([started, { id: "x1", type: "text", content: "Importing." }]);
		await flushPromises();
		const block = w.find(".import-progress");
		expect(block.exists()).toBe(true);
		expect(block.text()).toContain("Importing customers.csv");
		expect(block.text()).toContain("120 of 250 rows");
		expect(block.find("a.ip-link").attributes("href")).toContain("/app/fac-import-session/IMP-1");
	});

	it("shows nothing for a message that started no import", async () => {
		const w = mountRenderer([{ id: "x1", type: "text", content: "Hello" }]);
		await flushPromises();
		expect(w.find(".import-progress").exists()).toBe(false);
		expect(api.imports.progress).not.toHaveBeenCalled();
	});
});
