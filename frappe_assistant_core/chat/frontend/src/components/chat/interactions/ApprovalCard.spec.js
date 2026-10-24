import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";

const messagePreview = vi.fn();
const currentCode = vi.fn();
const fieldPlacement = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		tools: {
			messagePreview: (...a) => messagePreview(...a),
			currentCode: (...a) => currentCode(...a),
			fieldPlacement: (...a) => fieldPlacement(...a),
		},
	},
}));

import ApprovalCard from "@/components/chat/interactions/ApprovalCard.vue";
import CodePreview from "@/components/chat/interactions/CodePreview.vue";

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
	currentCode.mockReset();
	currentCode.mockRejectedValue(new Error("not fetched"));
	fieldPlacement.mockReset();
	fieldPlacement.mockRejectedValue(new Error("not fetched"));
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

describe("ApprovalCard for customisations", () => {
	const lines = (n) => Array.from({ length: n }, (_, i) => `line_${i} = ${i}`).join("\n");
	const scriptBlock = (data, tool = "create_document") => ({
		id: "t6",
		tool_name: tool,
		input: { doctype: "Server Script", ...(tool === "update_document" ? { name: "SS-1" } : {}), data },
		interrupts,
	});

	it("renders a 400-line script in full inside a scrolling block", () => {
		const wrapper = mount(ApprovalCard, { props: { block: scriptBlock({ script: lines(400) }) } });
		const text = wrapper.find(".code-preview pre").text();
		expect(text).toContain("line_0 = 0");
		expect(text).toContain("line_399 = 399");
		expect(wrapper.find(".code-scroll").exists()).toBe(true);
	});

	it("never hides code rows behind show all", () => {
		const data = { a: "1", b: "2", c: "3", d: "4", e: "5", f: "6", script: "print(1)" };
		const wrapper = mount(ApprovalCard, { props: { block: scriptBlock(data) } });
		expect(wrapper.find(".code-preview").exists()).toBe(true);
		expect(wrapper.find(".field-toggle").exists()).toBe(true);
		expect(wrapper.find(".field-toggle").text()).toContain("Show all fields");
	});

	it("renders child table rows as a table", () => {
		const transitions = [
			{ name: "x1", idx: 1, state: "Draft", action: "Submit", next_state: "Pending" },
			{ name: "x2", idx: 2, state: "Pending", action: "Approve", next_state: "Approved" },
		];
		const block = { id: "t7", tool_name: "create_document", input: { doctype: "Workflow", data: { transitions } }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		const table = wrapper.find("table.child-table");
		expect(table.exists()).toBe(true);
		const text = table.text();
		for (const v of ["Draft", "Submit", "Pending", "Approve", "Approved"]) expect(text).toContain(v);
		expect(table.findAll("tbody tr")).toHaveLength(2);
		expect(text).not.toContain("x1");
	});

	it("shows only ten child rows and counts the rest", () => {
		const rows = Array.from({ length: 13 }, (_, i) => ({ state: `S${i}` }));
		const block = { id: "t8", tool_name: "create_document", input: { doctype: "Workflow", data: { states: rows } }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		expect(wrapper.findAll("table.child-table tbody tr")).toHaveLength(10);
		expect(wrapper.text()).toContain("+ 3 more");
	});

	it("still truncates long non-code text at 120", () => {
		const block = { id: "t9", tool_name: "create_document", input: { doctype: "ToDo", description: "x".repeat(300) }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		expect(wrapper.find(".code-preview").exists()).toBe(false);
		const value = wrapper.findAll(".field-value").find((v) => v.text().startsWith("xxx"));
		expect(value.text()).toBe("x".repeat(120) + "…");
	});

	it("update card shows a line diff of old vs new code", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "a\nold\nc" });
		const wrapper = mount(ApprovalCard, {
			props: { block: scriptBlock({ script: "a\nnew\nc" }, "update_document") },
		});
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Server Script", "SS-1", ["script"]);
		expect(wrapper.find(".diff-del").text()).toContain("old");
		expect(wrapper.find(".diff-add").text()).toContain("new");
	});

	it("diff falls back to new code when the current value cannot be fetched", async () => {
		currentCode.mockReset();
		currentCode.mockRejectedValue(new Error("denied"));
		const wrapper = mount(ApprovalCard, {
			props: { block: scriptBlock({ script: "a\nnew\nc" }, "update_document") },
		});
		await flushPromises();
		expect(wrapper.find(".diff-add").exists()).toBe(false);
		expect(wrapper.find(".code-preview pre").text()).toContain("new");
	});

	it("does not fetch current code for a create", async () => {
		mount(ApprovalCard, { props: { block: scriptBlock({ script: "x" }) } });
		await flushPromises();
		expect(currentCode).not.toHaveBeenCalled();
	});
});

describe("ApprovalCard switching code on", () => {
	const switchBlock = (doctype, data, name = "REC-1") => ({
		id: "t10",
		tool_name: "update_document",
		input: { doctype, name, data },
		interrupts,
	});
	const goesLive = (wrapper) => wrapper.find('[data-test="goes-live"]');

	it("Client Script switched on: fetches the stored script and shows it as going live", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "frappe.ui.form.on('Lead', {})" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Client Script", { enabled: 1 }) } });
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Client Script", "REC-1", ["script"]);
		expect(goesLive(wrapper).text()).toBe("This goes live");
		expect(wrapper.find(".code-preview pre").text()).toContain("frappe.ui.form.on('Lead', {})");
		expect(wrapper.find(".diff-add").exists()).toBe(false);
	});

	it("Server Script switched on with disabled 0: shows the stored script as going live", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "frappe.db.delete('ToDo')" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Server Script", { disabled: "0" }) } });
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Server Script", "REC-1", ["script"]);
		expect(goesLive(wrapper).text()).toBe("This goes live");
		expect(wrapper.find(".code-preview pre").text()).toContain("frappe.db.delete('ToDo')");
	});

	it("Notification switched on: shows its stored condition and message", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ condition: "doc.grand_total > 0", message: "<p>Hi {{ doc.name }}</p>" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Notification", { enabled: true }) } });
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Notification", "REC-1", ["subject", "condition", "message"]);
		const text = wrapper.findAll(".code-preview pre").map((p) => p.text()).join("\n");
		expect(text).toContain("doc.grand_total > 0");
		expect(text).toContain("Hi {{ doc.name }}");
	});

	it("FAC Page published: shows its stored html, script and style as going live", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ html: "<div id='planner'></div>", script: "renderPlanner()", style: ".planner { gap: 8px; }" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("FAC Page", { published: 1 }, "team-planner") } });
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("FAC Page", "team-planner", ["html", "script", "style", "roles"]);
		expect(goesLive(wrapper).text()).toBe("This goes live");
		const text = wrapper.findAll(".code-preview pre").map((p) => p.text()).join("\n");
		expect(text).toContain("<div id='planner'></div>");
		expect(text).toContain("renderPlanner()");
		expect(text).toContain(".planner { gap: 8px; }");
	});

	const preview = (wrapper, label) => wrapper.findAllComponents(CodePreview).find((c) => c.props("label") === label);

	const publish = async (roles) => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ html: "<p>x</p>", script: "", style: "", roles });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("FAC Page", { published: 1 }, "team-planner") } });
		await flushPromises();
		return wrapper;
	};
	const audience = (wrapper) => wrapper.find('[data-test="goes-live-audience"]');
	const everyone = (wrapper) => wrapper.find('[data-test="goes-live-everyone"]');

	it("FAC Page published: says which roles it goes live to", async () => {
		const wrapper = await publish(["Sales User", "Report Manager"]);
		expect(audience(wrapper).text()).toBe("Goes live to: Sales User, Report Manager");
		expect(everyone(wrapper).exists()).toBe(false);
	});

	it("FAC Page published with no code and no roles: says (empty) and raises no load error", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ html: "", script: "", style: "", roles: [] });
		const empty = mount(ApprovalCard, { props: { block: switchBlock("FAC Page", { published: 1 }, "team-planner") } });
		await flushPromises();
		expect(empty.find('[data-test="goes-live-empty"]').text()).toBe("(empty)");
		expect(empty.find('[data-test="goes-live-missing"]').exists()).toBe(false);
		expect(audience(empty).text()).toBe("Goes live to: System Managers only");
	});

	it("FAC Page published with no roles: says System Managers only", async () => {
		const wrapper = await publish([]);
		expect(audience(wrapper).text()).toBe("Goes live to: System Managers only");
	});

	it.each([["All"], ["Guest"]])("FAC Page published to %s: names it and warns it reaches every user", async (role) => {
		const wrapper = await publish(["Sales User", role]);
		expect(audience(wrapper).text()).toBe(`Goes live to: Sales User, ${role}`);
		expect(everyone(wrapper).text()).toBe("All and Guest include every user who can log in.");
	});

	it("an update that also sets the roles shows them as the change, not the stored ones", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ html: "", script: "", style: "", roles: [] });
		const wrapper = mount(ApprovalCard, {
			props: { block: switchBlock("FAC Page", { published: 1, roles: [{ role: "Sales User" }] }, "team-planner") },
		});
		await flushPromises();
		expect(audience(wrapper).exists()).toBe(false);
		expect(wrapper.text()).toContain("Sales User");
	});

	it("FAC Page style change: shows style as a diffed CSS code block, not a plain field", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ style: ".a {}\n.old {}" });
		const wrapper = mount(ApprovalCard, {
			props: { block: switchBlock("FAC Page", { style: ".a {}\n.new {}" }, "team-planner") },
		});
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("FAC Page", "team-planner", ["style"]);
		expect(preview(wrapper, "Style").props("language")).toBe("css");
		expect(wrapper.find(".diff-del").text()).toContain(".old {}");
		expect(wrapper.find(".diff-add").text()).toContain(".new {}");
		expect(wrapper.findAll(".field-key").map((k) => k.text())).not.toContain("Style");
	});

	it("FAC Page published with a style change: diffs the style and shows the stored html and script", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ style: ".old {}", html: "<div id='planner'></div>", script: "renderPlanner()" });
		const wrapper = mount(ApprovalCard, {
			props: { block: switchBlock("FAC Page", { published: 1, style: ".new {}" }, "team-planner") },
		});
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("FAC Page", "team-planner", ["style", "html", "script", "roles"]);
		expect(goesLive(wrapper).text()).toBe("This goes live");
		expect(wrapper.find(".diff-del").text()).toContain(".old {}");
		expect(wrapper.find(".diff-add").text()).toContain(".new {}");
		const text = wrapper.findAll(".code-preview pre").map((p) => p.text()).join("\n");
		expect(text).toContain("<div id='planner'></div>");
		expect(text).toContain("renderPlanner()");
	});

	it("style on any other doctype stays a plain field", async () => {
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Web Page", { style: ".x {}" }) } });
		await flushPromises();
		expect(preview(wrapper, "Style")).toBeUndefined();
		expect(currentCode).not.toHaveBeenCalled();
	});

	it("switch on that also changes the code keeps the diff and still says it goes live", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "a\nold\nc" });
		const wrapper = mount(ApprovalCard, {
			props: { block: switchBlock("Server Script", { disabled: 0, script: "a\nnew\nc" }) },
		});
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Server Script", "REC-1", ["script"]);
		expect(goesLive(wrapper).text()).toBe("This goes live");
		expect(wrapper.findAll(".code-preview")).toHaveLength(1);
		expect(wrapper.find(".diff-del").text()).toContain("old");
		expect(wrapper.find(".diff-add").text()).toContain("new");
	});

	it("says the code could not be loaded when the stored code cannot be fetched", async () => {
		currentCode.mockReset();
		currentCode.mockRejectedValue(new Error("denied"));
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Client Script", { enabled: "1" }) } });
		await flushPromises();
		expect(goesLive(wrapper).text()).toBe("This goes live");
		expect(wrapper.find('[data-test="goes-live-missing"]').text()).toBe(
			"Couldn't load the code that goes live. Check it in Desk before approving.",
		);
	});

	it("keeps Approve disabled while the code that goes live loads", async () => {
		let resolve;
		currentCode.mockReset();
		currentCode.mockReturnValue(new Promise((r) => (resolve = r)));
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Client Script", { enabled: 1 }) } });
		await flushPromises();
		expect(wrapper.find('[data-test="goes-live-loading"]').text()).toBe("Loading the code that goes live…");
		expect(wrapper.find(".ql-btn-approve").attributes("disabled")).toBeDefined();
		resolve({ script: "console.log(1)" });
		await flushPromises();
		expect(wrapper.find('[data-test="goes-live-loading"]').exists()).toBe(false);
		expect(wrapper.find(".ql-btn-approve").attributes("disabled")).toBeUndefined();
	});

	it("leaves Approve enabled beside the notice when the stored code cannot be fetched", async () => {
		currentCode.mockReset();
		currentCode.mockRejectedValue(new Error("denied"));
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Server Script", { disabled: 0 }) } });
		await flushPromises();
		expect(wrapper.find('[data-test="goes-live-missing"]').exists()).toBe(true);
		expect(wrapper.find(".ql-btn-approve").attributes("disabled")).toBeUndefined();
	});

	it("Notification switched on: shows its stored subject", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ subject: "Order {{ doc.name }} approved", condition: "", message: "" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Notification", { enabled: 1 }) } });
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Notification", "REC-1", ["subject", "condition", "message"]);
		expect(wrapper.find(".code-preview pre").text()).toContain("Order {{ doc.name }} approved");
	});

	it.each([[""], [null], [" 0 "], [0.4], ["1abc"], ["Infinity"]])("Server Script disabled %j is not canonical, so the card shows the code", async (value) => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "x = 1" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Server Script", { disabled: value }) } });
		await flushPromises();
		expect(currentCode).toHaveBeenCalledWith("Server Script", "REC-1", ["script"]);
		expect(goesLive(wrapper).exists()).toBe(true);
	});

	it.each([["2"], [" 1 "], ["1.5"], [" 0 "], ["abc"]])("Client Script enabled %j is not canonical, so the card shows the code", async (value) => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "x" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Client Script", { enabled: value }) } });
		await flushPromises();
		expect(goesLive(wrapper).exists()).toBe(true);
	});

	it("says (empty) when every stored field that goes live is empty", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({ script: "" });
		const wrapper = mount(ApprovalCard, { props: { block: switchBlock("Client Script", { enabled: 1 }) } });
		await flushPromises();
		expect(wrapper.find('[data-test="goes-live-empty"]').text()).toBe("(empty)");
		expect(wrapper.find(".code-preview").exists()).toBe(false);
	});

	it("an update that does not switch on makes no extra fetch and shows no go-live label", async () => {
		currentCode.mockReset();
		currentCode.mockResolvedValue({});
		for (const block of [
			switchBlock("Client Script", { enabled: 0 }),
			switchBlock("Server Script", { disabled: 1 }),
			switchBlock("Notification", { enabled: "0" }),
			switchBlock("Server Script", { disabled: "1" }),
			switchBlock("Server Script", { disabled: true }),
			switchBlock("Client Script", { enabled: false }),
			switchBlock("FAC Page", { published: 0 }),
			switchBlock("FAC Page", { title: "Planner" }),
			switchBlock("Server Script", { script_type: "API" }),
			switchBlock("Client Script", { dt: "Lead" }),
			switchBlock("ToDo", { enabled: 1 }),
		]) {
			const wrapper = mount(ApprovalCard, { props: { block } });
			await flushPromises();
			expect(goesLive(wrapper).exists()).toBe(false);
		}
		expect(currentCode).not.toHaveBeenCalled();
	});
});

describe("ApprovalCard plain-language copy and trust", () => {
	const customisationInterrupts = [{ id: "i1", reason: { risk: "customisation" } }];

	it("server script card says when the code runs", () => {
		const data = { script_type: "DocType Event", reference_doctype: "Sales Invoice", doctype_event: "Before Submit", script: "x" };
		const block = { id: "c1", tool_name: "create_document", input: { doctype: "Server Script", data }, interrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		expect(wrapper.find(".approval-subtitle").text()).toBe("This code will run every time someone submits a Sales Invoice");
	});

	it("update card for a Server Script with no event says what it changes, not the generic ERP line", () => {
		const input = { doctype: "Server Script", name: "SS-1", data: { disabled: 1 } };
		const wrapper = mount(ApprovalCard, { props: { block: { id: "c4", tool_name: "update_document", input, interrupts } } });
		expect(wrapper.find(".approval-subtitle").text()).toBe("Changes server code that runs on this site");
	});

	it("Workflow State create says it changes how records are approved", () => {
		const input = { doctype: "Workflow State", data: { workflow_state_name: "Pending" } };
		const wrapper = mount(ApprovalCard, { props: { block: { id: "c5", tool_name: "create_document", input, interrupts } } });
		expect(wrapper.find(".approval-subtitle").text()).toBe("Changes how records are approved for everyone");
	});

	it("rename update card flags the rename and does not list it as a change", () => {
		const input = { doctype: "Server Script", name: "Old Script", data: { name: "New Script", script: "pass" } };
		const wrapper = mount(ApprovalCard, { props: { block: { id: "c6", tool_name: "update_document", input, interrupts } } });
		const rows = wrapper.findAll(".field-key").map((k) => k.text());
		expect(rows).toEqual(["Doctype", "Name"]);
		expect(wrapper.text()).not.toContain("New Script");
		expect(wrapper.find("[data-test='rename-notice']").text()).toBe(
			"Renaming isn't possible here. Only the other changes will be saved.",
		);
	});

	it.each([
		["new_name inside data", { doctype: "Role", name: "A", data: { new_name: "B", desk_access: 1 } }],
		["rename inside data", { doctype: "Role", name: "A", data: { rename: "B", desk_access: 1 } }],
		["top-level new_name", { doctype: "Role", name: "A", new_name: "B", data: { desk_access: 1 } }],
	])("flags a rename sent as %s on a prefixed update tool", (_label, input) => {
		const wrapper = mount(ApprovalCard, { props: { block: { id: "c7", tool_name: "erp_update_document", input, interrupts } } });
		expect(wrapper.find("[data-test='rename-notice']").exists()).toBe(true);
		expect(wrapper.findAll(".field-key").map((k) => k.text())).toEqual(["Doctype", "Name", "Desk Access"]);
	});

	it("shows no rename notice when the update restates the same name or does not rename", () => {
		const input = { doctype: "Role", name: "A", data: { name: "A", desk_access: 1 } };
		const wrapper = mount(ApprovalCard, { props: { block: { id: "c8", tool_name: "update_document", input, interrupts } } });
		expect(wrapper.find("[data-test='rename-notice']").exists()).toBe(false);
	});

	it("trust checkbox hidden for customisation risk", () => {
		const block = { id: "c2", tool_name: "create_document", input: { doctype: "Server Script", data: { script: "x" } }, interrupts: customisationInterrupts };
		const wrapper = mount(ApprovalCard, { props: { block } });
		expect(wrapper.find(".trust-choice").exists()).toBe(false);
		expect(wrapper.text()).not.toContain("Don't ask again");
		expect(wrapper.find(".ql-btn-approve").text()).toBe("Approve");
	});

	it("trust checkbox shown otherwise", () => {
		const block = { id: "c3", tool_name: "create_document", input: { doctype: "ToDo", data: {} }, interrupts: [{ id: "i1", reason: { risk: "other" } }] };
		const wrapper = mount(ApprovalCard, { props: { block } });
		expect(wrapper.find(".trust-choice").text()).toBe("Don't ask again for this tool");
	});
});


describe("ApprovalCard Custom Field placement", () => {
	const customField = (data, tool = "create_document", extra = {}) => ({
		id: "p1",
		tool_name: tool,
		input: { doctype: "Custom Field", data, ...extra },
		interrupts,
	});
	const field = { dt: "Customer", insert_after: "email_id", fieldtype: "Data", label: "PO" };

	it("shows where the field will appear, taken from the server's sentence", async () => {
		fieldPlacement.mockResolvedValue({
			sentence: "Will appear on the Details tab, in the Customer section",
			warning: false,
		});
		const wrapper = mount(ApprovalCard, { props: { block: customField(field) } });
		await flushPromises();
		expect(fieldPlacement).toHaveBeenCalledWith("Customer", "email_id", "Data");
		const line = wrapper.find('[data-test="placement"]');
		expect(line.text()).toBe("Will appear on the Details tab, in the Customer section");
		expect(line.classes()).not.toContain("note-warning");
	});

	it("flags a hidden spot with the warning style", async () => {
		fieldPlacement.mockResolvedValue({
			sentence: "Will appear on the More Info tab (collapsed — hidden until someone opens it)",
			warning: true,
		});
		const wrapper = mount(ApprovalCard, { props: { block: customField(field) } });
		await flushPromises();
		expect(wrapper.find('[data-test="placement"]').classes()).toContain("note-warning");
	});

	it("shows nothing and still lets the user approve when the lookup fails", async () => {
		const wrapper = mount(ApprovalCard, { props: { block: customField(field) } });
		await flushPromises();
		expect(wrapper.find('[data-test="placement"]').exists()).toBe(false);
		await wrapper.find(".ql-btn-approve").trigger("click");
		expect(wrapper.emitted("approve")).toHaveLength(1);
	});

	it("skips the lookup for an update that does not name the form, and for other records", async () => {
		mount(ApprovalCard, { props: { block: customField({ label: "PO" }, "update_document", { name: "Customer-po" }) } });
		mount(ApprovalCard, {
			props: { block: { id: "p2", tool_name: "create_document", input: { doctype: "ToDo", data: { dt: "Customer" } }, interrupts } },
		});
		await flushPromises();
		expect(fieldPlacement).not.toHaveBeenCalled();
	});

	it("makes no lookup for an update that names dt but not insert_after", async () => {
		mount(ApprovalCard, { props: { block: customField({ dt: "Customer", depends_on: "eval:doc.qty" }, "update_document", { name: "Customer-po" }) } });
		await flushPromises();
		expect(fieldPlacement).not.toHaveBeenCalled();
	});
});

describe("ApprovalCard field conditions", () => {
	const NOTICE = "Checked in the Desk form only — imports, the API and FACO's own writes are not checked.";
	const card = (input, tool = "create_document") =>
		mount(ApprovalCard, { props: { block: { id: "d1", tool_name: tool, input, interrupts } } });
	const conditionInput = { doctype: "Custom Field", data: { dt: "Sales Order", depends_on: "eval:doc.base_grand_total > 100000" } };

	it("Custom Field create: sentence in the row, raw expression only under the toggle, and the notice", async () => {
		const wrapper = card(conditionInput);
		await flushPromises();
		expect(wrapper.text()).toContain("when Base Grand Total is over 100000");
		expect(wrapper.text()).toContain(NOTICE);
		expect(wrapper.text()).not.toContain("eval:doc");
		await wrapper.find(".condition-toggle").trigger("click");
		expect(wrapper.find(".condition-code").text()).toBe("eval:doc.base_grand_total > 100000");
	});

	it("shows a condition sentence in the normal font", async () => {
		const wrapper = card(conditionInput);
		await flushPromises();
		const value = wrapper.findAll(".field-value").find((v) => v.find(".condition-value").exists());
		expect(value.classes()).not.toContain("value-mono");
		expect(value.classes()).not.toContain("value-money");
	});

	it("falls back to 'Has a condition' for an expression it cannot read", async () => {
		const wrapper = card({ doctype: "Custom Field", data: { dt: "Sales Order", depends_on: "eval:doc.a > 1 && doc.b" } });
		await flushPromises();
		expect(wrapper.find(".condition-value").text()).toContain("Has a condition");
		expect(wrapper.text()).not.toContain("doc.a > 1");
	});

	it("Custom Field update carries the notice", async () => {
		const wrapper = card({ doctype: "Custom Field", name: "Sales Order-po", data: { mandatory_depends_on: "eval:doc.qty" } }, "update_document");
		await flushPromises();
		expect(wrapper.find('[data-test="condition-notice"]').text()).toBe(NOTICE);
		expect(wrapper.text()).toContain("when Qty is set");
	});

	it("Property Setter carries the notice and reads its value as a sentence", async () => {
		const wrapper = card({ doctype: "Property Setter", data: { doc_type: "Sales Order", property: "read_only_depends_on", value: "eval:doc.status == 'Closed'" } });
		await flushPromises();
		expect(wrapper.find('[data-test="condition-notice"]').text()).toBe(NOTICE);
		expect(wrapper.text()).toContain("when Status is Closed");
		expect(wrapper.text()).not.toContain("eval:doc");
	});

	it("a write that sets no condition has no notice", async () => {
		const wrapper = card({ doctype: "Property Setter", data: { property: "hidden", value: "1" } });
		await flushPromises();
		expect(wrapper.find('[data-test="condition-notice"]').exists()).toBe(false);
		expect(wrapper.find(".condition-toggle").exists()).toBe(false);
	});
});
