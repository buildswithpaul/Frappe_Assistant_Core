import { describe, it, expect, vi, beforeEach } from "vitest";

const { getCall, baseCall } = vi.hoisted(() => ({
	getCall: vi.fn(() => Promise.resolve({})),
	baseCall: vi.fn(() => Promise.resolve({})),
}));
vi.mock("@/api/_core", () => ({
	getCall,
	baseCall,
	friendlyError: vi.fn(),
	networkError: vi.fn(),
	getCsrfToken: () => "",
}));

import { user } from "@/api/domains/user";
import { workflows } from "@/api/domains/workflows";

describe("workflows.runNode", () => {
	beforeEach(() => baseCall.mockClear());

	it("sends no user_id; the workflow's runtime user decides", async () => {
		await workflows.runNode("WF-1", "n1", "hi");
		const [, payload] = baseCall.mock.calls[0];
		expect(payload).toEqual({ name: "WF-1", node_id: "n1", input_text: "hi" });
		expect(payload).not.toHaveProperty("user_id");
	});
});

describe("runtime-user tool calls", () => {
	beforeEach(() => {
		getCall.mockClear();
		baseCall.mockClear();
	});

	it("lists tools for the named runtime user", async () => {
		await user.listTools("ops@example.com");
		expect(getCall).toHaveBeenCalledWith("frappe_assistant_core.chat.api.list_user_tools", {
			runtime_user: "ops@example.com",
		});
	});

	it("resolves directives for the named runtime user", async () => {
		const directives = [{ tool_name: "list_documents" }];
		await workflows.resolveWorkflowTools(directives, "ops@example.com");
		expect(baseCall).toHaveBeenCalledWith("frappe_assistant_core.chat.api.resolve_workflow_tools", {
			tool_directives: directives,
			runtime_user: "ops@example.com",
		});
	});
});

describe("workflows.searchLink", () => {
	beforeEach(() => getCall.mockClear());

	it("searches the doctype on this site through Frappe's permission-aware link search", async () => {
		await workflows.searchLink("Company", "North");
		expect(getCall).toHaveBeenCalledWith("frappe.desk.search.search_link", {
			doctype: "Company",
			txt: "North",
			page_length: 10,
		});
	});

	it("sends an empty search text rather than undefined", async () => {
		await workflows.searchLink("Company");
		expect(getCall.mock.calls[0][1].txt).toBe("");
	});
});
