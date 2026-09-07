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
});
