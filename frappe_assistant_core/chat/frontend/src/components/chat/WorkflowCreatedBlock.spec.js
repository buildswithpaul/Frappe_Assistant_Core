import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import WorkflowCreatedBlock from "@/components/chat/WorkflowCreatedBlock.vue";

const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

describe("WorkflowCreatedBlock", () => {
	it("renders the workflow name and navigates to the builder on click", async () => {
		push.mockClear();
		const wrapper = mount(WorkflowCreatedBlock, {
			props: { block: { workflow_name: "Invoice Chaser", docname: "WF-00046",
				link: "/copilot/agents/WF-00046", status: "Draft", action: "created" } },
		});
		expect(wrapper.text()).toContain("Invoice Chaser");
		await wrapper.get("button").trigger("click");
		expect(push).toHaveBeenCalledWith({ name: "agent-builder", params: { id: "WF-00046" } });
	});

	it("prints no empty brackets when the block has no status", () => {
		const wrapper = mount(WorkflowCreatedBlock, {
			props: { block: { workflow_name: "Invoice Chaser", docname: "WF-00046", status: null } },
		});
		expect(wrapper.text()).not.toContain("()");
	});

	// production: Frappe's window.__ is present when the SPA is served inside Desk
	it("passes its visible strings through the translator", () => {
		window.__ = (text) => `[${text}]`;
		try {
			const wrapper = mount(WorkflowCreatedBlock, {
				props: { block: { workflow_name: "Invoice Chaser", docname: "WF-00046", action: "updated" } },
			});
			expect(wrapper.text()).toContain("[Updated]");
			expect(wrapper.get("button").text()).toBe("[Open in builder] →");
		} finally {
			delete window.__;
		}
	});
});
