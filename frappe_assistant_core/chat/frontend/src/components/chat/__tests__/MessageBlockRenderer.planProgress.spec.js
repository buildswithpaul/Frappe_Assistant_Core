import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({ api: { imports: { progress: vi.fn(), planProgress: vi.fn() } } }));

import { api } from "@/api/client";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

// #34351: a migration plan ran with text only; nothing showed where each file stood.

const ran = {
	id: "r1",
	type: "tool_call",
	tool_name: "run_migration_plan",
	status: "success",
	input: { plan: "IMP-7" },
	result: { success: true, plan: "IMP-7", status: "Running" },
};

const plan = (status, ended) => ({
	plan: "IMP-7",
	status,
	ended,
	files: [
		{ session: "IMP-7", file_name: "groups.csv", status: "Completed", created: 4, failed: 0 },
		{ session: "IMP-8", file_name: "items.csv", status: "Importing", created: 120, failed: 2 },
	],
	url: "/app/fac-import-session/IMP-7",
});

function mountRenderer(blocks) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0 },
		global: { stubs: { ProcessingCard: true, ProcessingIndicator: true } },
	});
}

describe("a migration plan's progress under the message that ran it", () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it("shows each file's status and counts, and reads again while the plan runs", async () => {
		api.imports.planProgress.mockResolvedValueOnce(plan("Running", false)).mockResolvedValue(plan("Completed", true));
		const w = mountRenderer([ran, { id: "x1", type: "text", content: "The plan is running." }]);
		await flushPromises();

		const block = w.find(".plan-progress");
		expect(block.text()).toContain("groups.csv");
		expect(block.text()).toContain("items.csv");
		expect(block.text()).toContain("120 created");
		expect(block.text()).toContain("2 failed");
		expect(api.imports.planProgress).toHaveBeenCalledWith("IMP-7");

		await vi.advanceTimersByTimeAsync(15000);
		expect(w.find(".plan-progress").text()).toContain("Completed");
		await vi.advanceTimersByTimeAsync(30000);
		expect(api.imports.planProgress).toHaveBeenCalledTimes(2); // ended: not read again
	});

	it("shows nothing for a message that ran no plan", async () => {
		mountRenderer([{ id: "x1", type: "text", content: "Hello" }]);
		await flushPromises();
		expect(api.imports.planProgress).not.toHaveBeenCalled();
	});
});
