import { describe, it, expect, vi } from "vitest";

const { getCall } = vi.hoisted(() => ({ getCall: vi.fn() }));
vi.mock("@/api/_core", () => ({
	getCall,
	baseCall: vi.fn(),
	friendlyError: vi.fn(),
	networkError: vi.fn(),
	getCsrfToken: () => "",
}));

import { workflows } from "@/api/domains/workflows";

describe("getTemplate", () => {
	it("carries the template's requires block", async () => {
		getCall.mockResolvedValue({
			name: "L-1",
			title: "Weekly Collections Brief",
			source: { graph_json: "{}", requires: '{"reports":["Accounts Receivable Summary"]}' },
		});
		const tpl = await workflows.getTemplate(null, "L-1");
		expect(tpl.requires).toBe('{"reports":["Accounts Receivable Summary"]}');
	});
});
