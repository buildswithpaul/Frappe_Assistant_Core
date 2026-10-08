import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { useToast } from "@/composables/useToast";

const { getCall, baseCall } = vi.hoisted(() => ({
	getCall: vi.fn(() => Promise.resolve({ triggers: [] })),
	baseCall: vi.fn(() => Promise.resolve({})),
}));

vi.mock("@/api/_core", () => ({
	getCall,
	baseCall,
	friendlyError: vi.fn(),
	networkError: vi.fn(),
	getCsrfToken: () => "",
}));

import { workflows } from "@/api/domains/workflows";
import TriggersModal from "@/components/workflows/triggers/TriggersModal.vue";

const LIST = "frappe_assistant_core.chat.api.workflow_triggers.list_triggers";

describe("triggers.list binding", () => {
	beforeEach(() => {
		getCall.mockClear();
		baseCall.mockClear();
	});

	it("sends the docname alongside the display name", async () => {
		await workflows.triggers.list("Weekly Digest", "WF-00042");

		expect(getCall).toHaveBeenCalledWith(LIST, {
			workflow_name: "Weekly Digest",
			workflow_docname: "WF-00042",
		});
	});

	it("still sends the display name when no docname is known", async () => {
		await workflows.triggers.list("Weekly Digest");

		expect(getCall).toHaveBeenCalledWith(LIST, {
			workflow_name: "Weekly Digest",
			workflow_docname: null,
		});
	});
});

describe("TriggersModal", () => {
	beforeEach(() => {
		getCall.mockClear();
		baseCall.mockClear();
	});

	// Renaming a workflow changes only the display name. If the modal listed
	// by that alone, a renamed agent showed zero triggers while its triggers
	// kept firing.
	it("lists by the workflow docname, not the mutable display name", async () => {
		const wrapper = mount(TriggersModal, {
			props: {
				modelValue: false,
				workflowId: "WF-00042",
				workflowDisplayName: "Weekly Digest (renamed)",
			},
			global: { stubs: { Teleport: true } },
		});
		await wrapper.setProps({ modelValue: true });

		const call = getCall.mock.calls.find(([method]) => method === LIST);
		expect(call).toBeTruthy();
		expect(call[1].workflow_docname).toBe("WF-00042");
	});
});

describe("TriggersModal dialogs", () => {
	beforeEach(() => {
		getCall.mockReset();
		baseCall.mockReset();
		window.confirm = vi.fn(() => true);
		window.alert = vi.fn();
		useToast().toasts.value = [];
	});

	async function openWith(triggers) {
		getCall.mockResolvedValue({ triggers });
		const w = mount(TriggersModal, {
			props: { modelValue: false, workflowId: "WF-1", workflowDisplayName: "Digest" },
			attachTo: document.body,
		});
		await w.setProps({ modelValue: true });
		await flushPromises();
		return w;
	}

	it("asks with an in-app dialog before deleting, never window.confirm", async () => {
		const w = await openWith([{ name: "T1", title: "On submit", enabled: 1 }]);
		await w.findComponent({ name: "TriggerCard" }).vm.$emit("delete", { name: "T1", title: "On submit" });
		await flushPromises();
		expect(window.confirm).not.toHaveBeenCalled();
		expect(document.body.textContent).toContain("Delete trigger");
		expect(baseCall).not.toHaveBeenCalled();
		w.unmount();
	});

	it("reports a failed toggle with a toast, not window.alert", async () => {
		const w = await openWith([{ name: "T1", title: "On submit", enabled: 1 }]);
		baseCall.mockRejectedValue(new Error("nope"));
		await w.findComponent({ name: "TriggerCard" }).vm.$emit("toggle", { name: "T1", enabled: 1 });
		await flushPromises();
		expect(window.alert).not.toHaveBeenCalled();
		const { toasts } = useToast();
		expect(toasts.value.map((t) => t.message)).toEqual([
			expect.stringContaining("Could not switch the trigger: nope"),
		]);
		expect(toasts.value[0].type).toBe("error");
		w.unmount();
	});
});
