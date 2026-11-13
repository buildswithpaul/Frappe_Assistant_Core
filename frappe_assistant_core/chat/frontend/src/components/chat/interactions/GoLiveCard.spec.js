import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, it, expect, vi } from "vitest";

vi.mock("@/api/client", () => ({
	api: {
		tools: {
			currentCode: vi.fn().mockRejectedValue(new Error("not fetched")),
			fieldPlacement: vi.fn().mockRejectedValue(new Error("not fetched")),
			codeGoingLive: vi.fn().mockResolvedValue([]),
		},
	},
}));

import GoLiveCard from "./GoLiveCard.vue";
import ApprovalDetails from "./ApprovalDetails.vue";

const serverScript = (id, name) => ({
	type: "interaction",
	id,
	interactionType: "approval",
	tool_name: "update_document",
	input: { doctype: "Server Script", name, data: { disabled: 0, script: "frappe.msgprint(1)" } },
	status: "pending",
	interrupts: [
		{
			id: `i-${id}`,
			name: "faco-update_document-approval",
			reason: {
				type: "approval",
				tool: "update_document",
				risk: "customisation",
				details: { doctype: "Server Script", name, data: { disabled: 0, script: "frappe.msgprint(1)" } },
			},
		},
	],
});

function mountCard(blocks = [serverScript("a", "Alpha"), serverScript("b", "Beta")]) {
	return mount(GoLiveCard, {
		props: { blocks, submitting: false },
		global: { stubs: { InteractionCard: { props: ["block"], template: `<div class="single-card">{{ block.id }}</div>` } } },
	});
}

const button = (wrapper, label) => wrapper.findAll("button").find((b) => b.text() === label);

describe("GoLiveCard", () => {
	it("titles the card with the count", () => {
		expect(mountCard().find(".approval-title").text()).toBe("2 changes go live");
	});

	it("shows each headline with its code hidden", () => {
		const wrapper = mountCard();
		const rows = wrapper.findAll(".glc-item");
		expect(rows).toHaveLength(2);
		expect(rows[0].text()).toContain("Alpha");
		expect(rows[1].text()).toContain("Beta");
		expect(wrapper.find(".single-card").exists()).toBe(false);
	});

	it("show code reveals only that row's details", async () => {
		const wrapper = mountCard();
		await wrapper.findAll(".glc-toggle")[1].trigger("click");
		const details = wrapper.findAllComponents(ApprovalDetails);
		expect(details).toHaveLength(1);
		expect(details[0].props("block").id).toBe("b");
		expect(wrapper.findAll(".glc-toggle")[1].text()).toBe("Hide code");

		await wrapper.findAll(".glc-toggle")[1].trigger("click");
		expect(wrapper.findComponent(ApprovalDetails).exists()).toBe(false);
	});

	it("approve all emits once per undecided block", async () => {
		const blocks = [serverScript("a", "Alpha"), serverScript("b", "Beta"), serverScript("c", "Gamma")];
		blocks[0].decision = { resolution: "approved", responses: [] };
		const wrapper = mountCard(blocks);
		await button(wrapper, "Approve all").trigger("click");
		expect(wrapper.emitted("approve")).toEqual([
			["b", [{ interruptId: "i-b", response: "approve" }]],
			["c", [{ interruptId: "i-c", response: "approve" }]],
		]);
	});

	it("reject all emits reject with rejected", async () => {
		const wrapper = mountCard();
		await button(wrapper, "Reject all").trigger("click");
		expect(wrapper.emitted("reject")).toEqual([
			["a", [{ interruptId: "i-a", response: "rejected" }]],
			["b", [{ interruptId: "i-b", response: "rejected" }]],
		]);
		expect(wrapper.emitted("approve")).toBeUndefined();
	});

	it("review each shows every block's own card", async () => {
		const wrapper = mountCard();
		await button(wrapper, "Review each").trigger("click");
		expect(wrapper.findAll(".single-card").map((c) => c.text())).toEqual(["a", "b"]);
		expect(button(wrapper, "Approve all")).toBeUndefined();
	});

	it("shows read-only details with no decision controls inside an item", async () => {
		const wrapper = mount(GoLiveCard, {
			props: { blocks: [serverScript("a", "Alpha"), serverScript("b", "Beta")], submitting: false },
			global: { plugins: [createPinia()] },
		});
		await wrapper.findAll(".glc-toggle")[0].trigger("click");
		const item = wrapper.findAll(".glc-item")[0];
		expect(item.findComponent(ApprovalDetails).exists()).toBe(true);
		expect(item.find(".glc-code").text()).toContain("frappe.msgprint(1)");
		expect(item.find(".ql-btn-approve").exists()).toBe(false);
		expect(item.find(".ql-btn-reject").exists()).toBe(false);
		expect(item.find(".trust-choice").exists()).toBe(false);
		expect(item.find("input[type=checkbox]").exists()).toBe(false);
	});

	it("disables Approve all while a revealed item is still loading its code", async () => {
		const wrapper = mountCard();
		await wrapper.findAll(".glc-toggle")[0].trigger("click");
		const details = wrapper.findComponent(ApprovalDetails);
		details.vm.$emit("blocking", true);
		await wrapper.vm.$nextTick();
		expect(button(wrapper, "Approve all").attributes("disabled")).toBeDefined();
		expect(button(wrapper, "Reject all").attributes("disabled")).toBeUndefined();

		details.vm.$emit("blocking", false);
		await wrapper.vm.$nextTick();
		expect(button(wrapper, "Approve all").attributes("disabled")).toBeUndefined();
	});

	it("labels decided items and reads Decided once all are decided", async () => {
		const blocks = [serverScript("a", "Alpha"), serverScript("b", "Beta")];
		blocks[0].decision = { resolution: "approved", responses: [] };
		const wrapper = mountCard(blocks);
		expect(wrapper.findAll(".glc-decision").map((d) => d.text())).toEqual(["Approved"]);
		expect(wrapper.find(".glc-status").exists()).toBe(false);

		blocks[1].decision = { resolution: "rejected", responses: [] };
		await wrapper.setProps({ blocks: [...blocks] });
		expect(wrapper.findAll(".glc-decision").map((d) => d.text())).toEqual(["Approved", "Rejected"]);
		expect(wrapper.find(".glc-status").text()).toBe("Decided");
	});
});
