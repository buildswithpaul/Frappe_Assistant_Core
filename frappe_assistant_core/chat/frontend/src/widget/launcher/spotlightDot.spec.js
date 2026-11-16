import { describe, it, expect, vi, beforeEach } from "vitest";

const call = vi.fn();
vi.mock("../host/index.js", () => ({ getHost: () => ({ call, user: () => "u@x.test" }) }));

import { refreshSpotlightDot } from "./spotlightDot.js";

const NOTIFICATIONS = "frappe_assistant_core.chat.api.notifications.get_notifications";
const SEATED = { can_use: true, preferences: { privacy_consent_complete: true } };

describe("spotlight dot and the access status", () => {
	beforeEach(() => {
		call.mockReset().mockImplementation(async (method) => {
			if (method.endsWith("get_user_auth_status")) return { message: { success: true, ready: true } };
			return { message: { notifications: [] } };
		});
	});

	it("skips get_notifications unless the access status is ready", async () => {
		const view = { setDot: vi.fn() };
		await refreshSpotlightDot(view, { ...SEATED, status: "no_role" });
		expect(call.mock.calls.map(([m]) => m)).not.toContain(NOTIFICATIONS);
		expect(view.setDot).toHaveBeenLastCalledWith(false);
	});

	it("asks for notifications once the access status is ready", async () => {
		const view = { setDot: vi.fn() };
		await refreshSpotlightDot(view, { ...SEATED, status: "ready" });
		expect(call.mock.calls.map(([m]) => m)).toContain(NOTIFICATIONS);
	});
});
