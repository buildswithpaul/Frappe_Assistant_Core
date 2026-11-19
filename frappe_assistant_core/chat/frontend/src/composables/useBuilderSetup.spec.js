import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref, nextTick } from "vue";

const { list, resolveWorkflowTools, setPreference } = vi.hoisted(() => ({
	list: vi.fn().mockResolvedValue({ triggers: [] }),
	resolveWorkflowTools: vi.fn(),
	setPreference: vi.fn().mockResolvedValue({}),
}));
vi.mock("@/api/client", () => ({
	api: { workflows: { triggers: { list }, resolveWorkflowTools }, tools: { setPreference } },
}));

import { useBuilderSetup } from "./useBuilderSetup";

function build({ workflow = {}, schedule = {} } = {}) {
	const panels = { showSetup: ref(false), showTriggersModal: ref(false) };
	const result = useBuilderSetup({
		workflowId: ref("WF-1"),
		workflowDisplayName: ref("Digest"),
		currentWorkflow: ref(workflow),
		scheduleConfig: ref(schedule),
		nodes: ref([]),
		isAdmin: ref(true),
		panels,
	});
	return { ...result, panels };
}

describe("useBuilderSetup", () => {
	beforeEach(() => {
		list.mockClear();
		setPreference.mockClear();
	});

	it("re-reads when the Triggers modal closes, not when it opens", async () => {
		const { panels } = build();
		panels.showTriggersModal.value = true;
		await nextTick();
		expect(list).not.toHaveBeenCalled();
		panels.showTriggersModal.value = false;
		await nextTick();
		expect(list).toHaveBeenCalledTimes(1);
	});

	it("opens setup on arrival for an unfinished draft", () => {
		const { openIfUnfinished, panels } = build({ workflow: { status: "Draft" } });
		openIfUnfinished();
		expect(panels.showSetup.value).toBe(true);
	});

	it("stays out of the way on a live agent or a finished draft", () => {
		const live = build({ workflow: { status: "Active" } });
		live.openIfUnfinished();
		expect(live.panels.showSetup.value).toBe(false);
		const ready = build({ workflow: { status: "Draft", default_user_id: "x" }, schedule: { cron: "0 9 * * 1" } });
		ready.openIfUnfinished();
		expect(ready.panels.showSetup.value).toBe(false);
	});

	it("allows a tool as always_allow and accepts a re-check that clears it", async () => {
		const { allowTool, preflight, stuckTools, writeNote } = build();
		preflight.check = vi.fn().mockResolvedValue([]);
		await allowTool({ tool: "send_email", user: "me" });
		expect(setPreference).toHaveBeenCalledWith("send_email", "always_allow");
		expect(stuckTools.value).toEqual([]);
		expect(writeNote.value).toBe("");
	});

	it("falls back to the Connections instruction when the re-check still flags the tool", async () => {
		// A prefixed MCP server stores the preference under a name the SPA can't see.
		const { allowTool, preflight, stuckTools, writeNote } = build();
		preflight.check = vi.fn().mockResolvedValue([{ tool: "send_email" }]);
		await allowTool({ tool: "send_email", user: "me" });
		expect(stuckTools.value).toEqual(["send_email"]);
		expect(writeNote.value).toContain("Settings → Connections");
	});
});
