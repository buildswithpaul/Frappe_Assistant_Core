import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

const wf = vi.hoisted(() => ({
	create: vi.fn(),
	get: vi.fn(),
	delete: vi.fn(),
	list: vi.fn(),
	cancelRun: vi.fn(),
	listRuns: vi.fn(),
	getRun: vi.fn(),
}));
vi.mock("@/api/client", () => ({
	api: { workflows: wf },
	default: { workflows: wf },
}));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { useToast } from "@/composables/useToast";
import { useUserStore } from "@/stores/userStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import BlankWorkflowModal from "@/components/workflows/BlankWorkflowModal.vue";
import RunHistoryPanel from "@/components/workflows/RunHistoryPanel.vue";
import WorkflowList from "@/views/WorkflowList.vue";

function failure(message) {
	const err = new Error("raw");
	Object.defineProperty(err, "userMessage", { value: message });
	return err;
}

function toastMessages() {
	return useToast().toasts.value.map((t) => `${t.type}:${t.message}`);
}

describe("failed workflow actions toast", () => {
	beforeEach(() => {
		Object.values(wf).forEach((f) => f.mockReset());
		wf.list.mockResolvedValue({ workflows: [], total: 0 });
		wf.listRuns.mockResolvedValue({ runs: [], total: 0 });
		setActivePinia(createPinia());
		useToast().toasts.value = [];
	});

	it("create", async () => {
		wf.create.mockRejectedValue(failure("quota reached"));
		const w = mount(BlankWorkflowModal, {
			props: { modelValue: true },
			attachTo: document.body,
		});
		await w.findComponent({ name: "BlankWorkflowForm" }).vm.$emit("create", {
			name: "A",
			description: "",
		});
		await flushPromises();
		expect(toastMessages()).toEqual(["error:Could not create the agent: quota reached"]);
		w.unmount();
	});

	function mountList() {
		useUserStore().workflowsEnabled = true;
		return mount(WorkflowList, {
			global: {
				stubs: {
					NavigationSidebar: true,
					WorkflowListTopBar: true,
					MarketplaceView: true,
					UploadTemplateModal: true,
					BlankWorkflowModal: true,
					WorkflowDeleteModal: true,
					MyAgentsSection: true,
				},
			},
		});
	}

	it("duplicate", async () => {
		wf.get.mockRejectedValue(failure("source gone"));
		const w = mountList();
		await w.findComponent({ name: "MyAgentsSection" }).vm.$emit("duplicate", { name: "WF-1" });
		await flushPromises();
		expect(toastMessages()).toEqual(["error:Could not duplicate the agent: source gone"]);
	});

	it("delete", async () => {
		wf.delete.mockRejectedValue(failure("in use"));
		const w = mountList();
		await w.findComponent({ name: "MyAgentsSection" }).vm.$emit("delete", { name: "WF-1" });
		await w.findComponent({ name: "WorkflowDeleteModal" }).vm.$emit("confirm");
		await flushPromises();
		expect(toastMessages()).toEqual(["error:Could not delete the agent: in use"]);
	});

	it("cancel run", async () => {
		wf.cancelRun.mockRejectedValue(failure("engine busy"));
		wf.listRuns.mockResolvedValue({ runs: [{ name: "R1", status: "Running" }], total: 1 });
		const store = useWorkflowStore();
		store.activeRunName = "R1";
		store.isRunning = true;
		const w = mount(RunHistoryPanel, { props: { workflowId: "WF-1" } });
		await flushPromises();
		await w.get(".cancel-btn").trigger("click");
		await flushPromises();
		expect(toastMessages()).toEqual(["error:Could not cancel the run: engine busy"]);
	});
});
