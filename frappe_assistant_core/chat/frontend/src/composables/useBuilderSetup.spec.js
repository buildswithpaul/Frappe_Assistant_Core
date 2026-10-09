import { describe, it, expect, vi } from "vitest";
import { ref, nextTick } from "vue";

const list = vi.fn().mockResolvedValue({ triggers: [] });
vi.mock("@/api/client", () => ({
	api: { workflows: { triggers: { list: (...a) => list(...a) }, resolveWorkflowTools: vi.fn() } },
}));

import { useBuilderSetup } from "./useBuilderSetup";

function build() {
	const flags = {
		showSetup: ref(false),
		showTriggersModal: ref(false),
		showScheduleModal: ref(false),
	};
	useBuilderSetup({
		workflowId: ref("WF-1"),
		workflowDisplayName: ref("Digest"),
		currentWorkflow: ref({}),
		scheduleConfig: ref({}),
		nodes: ref([]),
		isAdmin: ref(true),
		panels: flags,
	});
	return flags;
}

describe("useBuilderSetup refresh", () => {
	it("re-reads when the Triggers or Schedule modal closes, not when it opens", async () => {
		list.mockClear();
		const f = build();
		f.showTriggersModal.value = true;
		await nextTick();
		expect(list).not.toHaveBeenCalled();
		f.showTriggersModal.value = false;
		await nextTick();
		expect(list).toHaveBeenCalledTimes(1);
		f.showScheduleModal.value = true;
		await nextTick();
		f.showScheduleModal.value = false;
		await nextTick();
		expect(list).toHaveBeenCalledTimes(2);
	});
});
