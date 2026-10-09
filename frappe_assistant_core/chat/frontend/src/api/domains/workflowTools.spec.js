import { describe, it, expect, vi, beforeEach } from "vitest";

const { baseCall } = vi.hoisted(() => ({ baseCall: vi.fn(() => Promise.resolve({})) }));
vi.mock("@/api/_core", () => ({
	getCall: vi.fn(),
	baseCall,
	friendlyError: vi.fn(),
	networkError: vi.fn(),
	getCsrfToken: () => "",
}));

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
