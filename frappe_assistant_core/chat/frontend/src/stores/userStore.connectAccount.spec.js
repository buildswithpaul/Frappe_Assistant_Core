import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		user: {
			connectFACServer: vi.fn(),
			verifySiteConnection: vi.fn(),
			getAuthStatus: vi.fn(),
			getCurrent: vi.fn(),
		},
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";

// What AR's test_mcp_server answered on prod for a site whose firewall blocks
// FAC Cloud: frappe.ping passes, the authenticated MCP call does not.
const FIREWALL_REFUSAL = {
	success: false,
	tool_count: 0,
	error: "MCP server Main Frappe Site answered HTTP 403: You got banned permanently from this server.",
};

describe("connectAccount", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		for (const fn of Object.values(api.user)) fn.mockReset();
		api.user.connectFACServer.mockResolvedValue({ success: true, message: "Connected" });
		api.user.getAuthStatus.mockResolvedValue({ success: true, ready_for_streaming: true });
	});

	it("holds the user at setup with the site's own reason when FAC Cloud is refused", async () => {
		api.user.verifySiteConnection.mockResolvedValue(FIREWALL_REFUSAL);

		const result = await useUserStore().connectAccount();

		expect(result.success).toBe(false);
		expect(result.error).toContain("banned permanently");
		expect(api.user.getAuthStatus).not.toHaveBeenCalled();
	});

	it("lets the user in when the site answers", async () => {
		api.user.verifySiteConnection.mockResolvedValue({ success: true, error: null });

		const result = await useUserStore().connectAccount();

		expect(result.success).toBe(true);
	});

	it("does not strand the user when the check itself cannot run", async () => {
		api.user.verifySiteConnection.mockRejectedValue(new Error("network down"));

		const result = await useUserStore().connectAccount();

		expect(result.success).toBe(true);
	});
});
