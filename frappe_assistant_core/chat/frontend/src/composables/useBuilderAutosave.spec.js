import { describe, it, expect, vi } from "vitest";
import { ref, h } from "vue";
import { mount } from "@vue/test-utils";
import { useBuilderAutosave } from "./useBuilderAutosave";

function withAutosave(storeOverrides = {}) {
	let api;
	const workflowStore = {
		isDirty: true,
		saveWorkflow: vi.fn().mockResolvedValue({}),
		markDirty: vi.fn(),
		...storeOverrides,
	};
	mount({
		setup() {
			api = useBuilderAutosave({
				workflowStore,
				workflowId: ref("WF-1"),
				canEdit: ref(true),
				nodes: ref([]),
				edges: ref([]),
				globalSettings: ref({}),
				selectedNode: ref(null),
				toGraphJson: () => "{}",
				checkLocally: () => true,
				checkOnServer: vi.fn().mockResolvedValue(true),
			});
			return () => h("div");
		},
	});
	return { api, workflowStore };
}

describe("useBuilderAutosave", () => {
	it("reports a failed save to its caller", async () => {
		const { api } = withAutosave({
			saveWorkflow: vi.fn().mockRejectedValue(new Error("403")),
		});
		expect(await api.save()).toBe(false);
		expect(api.saveError.value).toBe("403");
	});

	it("reports a successful save", async () => {
		const { api } = withAutosave();
		expect(await api.save()).toBe(true);
	});

	it("lets the author leave only when the edits are saved", async () => {
		const failing = withAutosave({
			saveWorkflow: vi.fn().mockRejectedValue(new Error("down")),
		});
		expect(await failing.api.saveBeforeLeave()).toBe(false);
		const clean = withAutosave({ isDirty: false });
		expect(await clean.api.saveBeforeLeave()).toBe(true);
		expect(clean.workflowStore.saveWorkflow).not.toHaveBeenCalled();
	});
});
