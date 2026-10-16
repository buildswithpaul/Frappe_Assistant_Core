import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";

const messagePreview = vi.fn();
vi.mock("@/api/client", () => ({ api: { tools: { messagePreview: (...a) => messagePreview(...a) } } }));

import ApprovalCard from "@/components/chat/interactions/ApprovalCard.vue";

const interrupts = [{ id: "i1", reason: { type: "approval" } }];

function emailBlock(input = {}) {
	return {
		id: "t1",
		tool_name: "send_email",
		input: { recipients: ["a@x.com"], subject: "Hello", message: "Hi there", ...input },
		interrupts,
	};
}

function buttons(wrapper) {
	return wrapper.findAll("button").map((b) => b.text());
}

beforeEach(() => {
	messagePreview.mockReset();
});

describe("ApprovalCard for a message tool", () => {
	it("shows the email preview with Send email, Reject and the don't-ask-again choice", async () => {
		messagePreview.mockResolvedValue({ can_send: true, title: "Send email", sender: "s@x.com", will_email: true });
		const wrapper = mount(ApprovalCard, { props: { block: emailBlock() } });
		await flushPromises();
		expect(messagePreview).toHaveBeenCalledWith("send_email", {});
		expect(wrapper.findComponent({ name: "EmailPreview" }).exists()).toBe(true);
		expect(wrapper.find(".approval-table").exists()).toBe(false);
		expect(buttons(wrapper)).toEqual(["Send email", "Reject"]);
		expect(wrapper.find(".trust-choice").text()).toBe("Don't ask again for this tool");
		await wrapper.find(".ql-btn-approve").trigger("click");
		expect(wrapper.emitted("approve")[0]).toEqual(["t1", [{ interruptId: "i1", response: "approve" }]]);
	});

	it("sends trust when don't-ask-again is ticked", async () => {
		messagePreview.mockResolvedValue({ can_send: true, title: "Send email", sender: "s@x.com", will_email: true });
		const wrapper = mount(ApprovalCard, { props: { block: emailBlock() } });
		await flushPromises();
		await wrapper.find(".trust-choice input").setValue(true);
		await wrapper.find(".ql-btn-approve").trigger("click");
		expect(wrapper.emitted("approve")[0]).toEqual(["t1", [{ interruptId: "i1", response: "trust" }]]);
	});

	it("passes the ticket to the reply preview and labels the button Send reply", async () => {
		messagePreview.mockResolvedValue({
			can_send: true,
			title: "Send reply on 12",
			context: "Wrong tax",
			to: ["c@x.com"],
			subject: "Re: Wrong tax",
			sender: "s@x.com",
			will_email: true,
		});
		const block = { id: "t2", tool_name: "reply_to_helpdesk_ticket", input: { ticket: "12", message: "<p>Hi</p>" }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		await flushPromises();
		expect(messagePreview).toHaveBeenCalledWith("reply_to_helpdesk_ticket", { ticket: "12" });
		expect(wrapper.text()).toContain("Send reply on 12");
		expect(wrapper.text()).toContain("c@x.com");
		expect(buttons(wrapper)[0]).toBe("Send reply");
	});

	it("keeps Send disabled while the preview loads", () => {
		messagePreview.mockReturnValue(new Promise(() => {}));
		const wrapper = mount(ApprovalCard, { props: { block: emailBlock() } });
		expect(wrapper.find(".ql-btn-approve").attributes("disabled")).toBeDefined();
		expect(wrapper.find(".trust-choice input").attributes("disabled")).toBeDefined();
	});

	it("offers only Reject when the preview cannot load", async () => {
		messagePreview.mockRejectedValue(new Error("boom"));
		const wrapper = mount(ApprovalCard, { props: { block: emailBlock() } });
		await flushPromises();
		expect(wrapper.text()).toContain("Couldn't load the preview");
		expect(buttons(wrapper)).toEqual(["Reject"]);
		expect(wrapper.find(".trust-choice").exists()).toBe(false);
	});

	it("shows the reason and only Dismiss when the user cannot send", async () => {
		messagePreview.mockResolvedValue({
			can_send: false,
			reason: "Only Helpdesk agents can send replies.",
			title: "Send reply on 12",
			will_email: true,
		});
		const block = { id: "t3", tool_name: "reply_to_helpdesk_ticket", input: { ticket: "12", message: "x" }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		await flushPromises();
		expect(wrapper.text()).toContain("Only Helpdesk agents can send replies.");
		expect(buttons(wrapper)).toEqual(["Dismiss"]);
		expect(wrapper.find(".trust-choice").exists()).toBe(false);
		await wrapper.find("button").trigger("click");
		expect(wrapper.emitted("reject")[0]).toEqual(["t3", [{ interruptId: "i1", response: "rejected" }]]);
	});
});

describe("ApprovalCard for a CRM email", () => {
	const crmBlock = (input) => ({
		id: "t5",
		tool_name: "send_crm_email",
		input: { doctype: "CRM Lead", name: "CRM-LEAD-1", subject: "Hi", message: "Body", ...input },
		interrupts,
	});

	it("uses the recipients the tool call names over the record's email", async () => {
		messagePreview.mockResolvedValue({ can_send: true, title: "Send email on Priya", to: ["lead@x.com"], sender: "s@x.com", will_email: true });
		const wrapper = mount(ApprovalCard, { props: { block: crmBlock({ recipients: ["boss@x.com"] }) } });
		await flushPromises();
		expect(messagePreview).toHaveBeenCalledWith("send_crm_email", { doctype: "CRM Lead", name: "CRM-LEAD-1" });
		expect(wrapper.text()).toContain("boss@x.com");
		expect(wrapper.text()).not.toContain("lead@x.com");
	});

	it("falls back to the record's email when the call names none", async () => {
		messagePreview.mockResolvedValue({ can_send: true, title: "Send email on Priya", to: ["lead@x.com"], sender: "s@x.com", will_email: true });
		const wrapper = mount(ApprovalCard, { props: { block: crmBlock({ recipients: [] }) } });
		await flushPromises();
		expect(wrapper.text()).toContain("lead@x.com");
	});

	it("offers only Dismiss when the email has nobody to go to", async () => {
		messagePreview.mockResolvedValue({ can_send: true, title: "Send email on Priya", to: null, sender: "s@x.com", will_email: true });
		const wrapper = mount(ApprovalCard, { props: { block: crmBlock({ recipients: [] }) } });
		await flushPromises();
		expect(wrapper.text()).toContain("This email has no recipient.");
		expect(buttons(wrapper)).toEqual(["Dismiss"]);
	});
});

describe("ApprovalCard for other tools", () => {
	it("keeps the field table and never fetches a preview", () => {
		const block = { id: "t4", tool_name: "create_document", input: { doctype: "ToDo", description: "x" }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		expect(messagePreview).not.toHaveBeenCalled();
		expect(wrapper.find(".approval-table").exists()).toBe(true);
		expect(buttons(wrapper)).toEqual(["Approve", "Reject"]);
		expect(wrapper.find(".trust-choice").exists()).toBe(true);
	});
});
