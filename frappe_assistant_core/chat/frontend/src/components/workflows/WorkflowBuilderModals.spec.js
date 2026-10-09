import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import WorkflowBuilderModals from "./WorkflowBuilderModals.vue";

function mountModals() {
	setActivePinia(createPinia());
	return mount(WorkflowBuilderModals, {
		props: {
			scheduleConfig: {},
			pendingActivation: true,
			activationWarnings: [
				{ tool: "create_document", server: "", user: "ops@example.com", nodes: ["Draft reply"] },
				{ tool: "send_email", server: "", user: "ar@example.com", nodes: ["Per customer"] },
			],
		},
		global: {
			stubs: {
				RunInputModal: true,
				ScheduleModal: true,
				VariablesModal: true,
				ShareTemplateModal: true,
				TriggersModal: true,
				Teleport: true,
			},
		},
	});
}

describe("activation confirmation", () => {
	it("names every tool, node and runtime user", () => {
		const text = mountModals().text();
		expect(text).toContain("create_document (Draft reply)");
		expect(text).toContain("send_email (Per customer)");
		expect(text).toContain("ops@example.com, ar@example.com");
	});

	it("confirm and cancel emit their events", async () => {
		const wrapper = mountModals();
		const buttons = wrapper.findAll("button");
		await buttons.find((b) => b.text() === "Activate anyway").trigger("click");
		await buttons.find((b) => b.text() === "Cancel").trigger("click");
		expect(wrapper.emitted("activation-confirm")).toHaveLength(1);
		expect(wrapper.emitted("activation-cancel")).toHaveLength(1);
	});
});
