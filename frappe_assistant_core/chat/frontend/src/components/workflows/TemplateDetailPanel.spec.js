import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

const toast = vi.hoisted(() => ({ showError: vi.fn(), showSuccess: vi.fn(), showToast: vi.fn() }));
vi.mock("@/composables/useToast", () => ({ useToast: () => toast }));

import { useWorkflowStore } from "@/stores/workflowStore";
import TemplateDetailPanel from "./TemplateDetailPanel.vue";

async function importWith(result) {
	const store = useWorkflowStore();
	store.importTemplate = vi.fn().mockResolvedValue(result);
	const wrapper = mount(TemplateDetailPanel, {
		props: { template: null, startInImportMode: true },
		global: {
			stubs: {
				TemplateImportStep: {
					template: '<button class="go" @click="$emit(\'import\', { name: \'My agent\', variables: null })" />',
				},
				TemplateDetailBody: true,
				TemplateDetailFooter: true,
				TemplateReportModal: true,
			},
		},
	});
	await wrapper.setProps({ template: { name: "LST-1", template_name: "Ticket First Reply" } });
	await wrapper.find(".go").trigger("click");
	await flushPromises();
	return wrapper;
}

describe("TemplateDetailPanel import", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		toast.showSuccess.mockReset();
		toast.showError.mockReset();
		toast.showToast.mockReset();
	});

	it("says a trigger was added switched off when the import created one", async () => {
		const wrapper = await importWith({ target_name: "WF-1", trigger_created: "abc123" });
		expect(toast.showSuccess).toHaveBeenCalledWith(
			"Agent imported. A trigger was added, switched off — turn it on in Setup."
		);
		expect(wrapper.emitted("created")[0]).toEqual(["WF-1"]);
	});

	it("says why the trigger could not be added", async () => {
		// production: import_listing returns trigger_note when create_trigger refused the
		// template's trigger (e.g. HD Ticket on a site without Helpdesk)
		await importWith({ target_name: "WF-1", trigger_note: "DocType HD Ticket not found" });
		expect(toast.showToast).toHaveBeenCalledWith(
			"Its trigger could not be added (DocType HD Ticket not found). Add one in Setup → Triggers.",
			"info",
			8000
		);
	});

	it("keeps the plain message when no trigger was created", async () => {
		await importWith({ target_name: "WF-1" });
		expect(toast.showSuccess).toHaveBeenCalledWith("Agent imported. Opening builder…");
	});
});
