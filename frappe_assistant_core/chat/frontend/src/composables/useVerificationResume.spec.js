import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent, h } from "vue";
import { mount, flushPromises } from "@vue/test-utils";

const registration = vi.hoisted(() => ({
	resendVerification: vi.fn(),
	changePendingEmail: vi.fn(),
	getLocalStatus: vi.fn(),
	getState: vi.fn(),
	getTerms: vi.fn(),
	register: vi.fn(),
}));
vi.mock("@/api/client", () => ({ api: { registration } }));

import { useVerificationResume } from "@/composables/useVerificationResume";

function mountHost() {
	const onVerified = vi.fn();
	let flow;
	const Host = defineComponent({
		setup() {
			flow = useVerificationResume({ onVerified });
			return () => h("div");
		},
	});
	const wrapper = mount(Host);
	return { wrapper, flow, onVerified };
}

beforeEach(() => {
	Object.values(registration).forEach((fn) => fn.mockReset());
	registration.getTerms.mockResolvedValue({ version: "v1" });
});

describe("resume", () => {
	it("puts a pending signup back on the pending screen with the masked address", () => {
		const { flow } = mountHost();

		expect(flow.resume({ status: "Pending Email Verification", owner_email_masked: "p***@x.com" })).toBe(true);
		expect(flow.verificationPending.value).toBe(true);
		expect(flow.reconnectMode.value).toBe(false);
		expect(flow.pendingEmail.value).toBe("p***@x.com");
	});

	it("resumes a reconnect this site started but never finished", () => {
		const { flow } = mountHost();

		const resumed = flow.resume({
			exists: true,
			status: "Active",
			reregistration: true,
			local_status: "Pending Email Verification",
		});

		expect(resumed).toBe(true);
		expect(flow.reconnectMode.value).toBe(true);
	});

	it("leaves an ordinary returning tenant to the reconnect card", () => {
		const { flow } = mountHost();

		expect(flow.resume({ exists: true, status: "Active", reregistration: true, local_status: "Registered" })).toBe(false);
		expect(flow.verificationPending.value).toBe(false);
	});
});

describe("resend", () => {
	it("waits for the result before releasing the button", async () => {
		const { flow } = mountHost();
		let resolve;
		registration.resendVerification.mockReturnValue(new Promise((r) => (resolve = r)));
		const done = vi.fn();

		const pending = flow.resend(done);
		await flushPromises();
		expect(done).not.toHaveBeenCalled();

		resolve({ success: true });
		await pending;
		expect(done).toHaveBeenCalledOnce();
		expect(flow.pendingNotice.value).toBe("Email resent. Check your inbox.");
	});

	it("shows the cooldown", async () => {
		const { flow } = mountHost();
		registration.resendVerification.mockResolvedValue({ success: false, retry_after: 42 });

		await flow.resend();

		expect(flow.pendingNotice.value).toBe("Wait 42s before sending again.");
	});

	it("shows the server's error", async () => {
		const { flow } = mountHost();
		registration.resendVerification.mockResolvedValue({ success: false, error: "Too many verification emails." });

		await flow.resend();

		expect(flow.pendingNotice.value).toBe("Too many verification emails.");
	});

	it("sends a reconnect link, and says why, when the site is already verified", async () => {
		const { flow } = mountHost();
		flow.enterPending();
		registration.resendVerification.mockResolvedValue({
			success: false,
			already_verified: true,
			reconnect_required: true,
			owner_email_masked: "o***@x.com",
		});
		registration.register.mockResolvedValue({ success: true, verification_pending: true });

		await flow.resend();

		expect(registration.register).toHaveBeenCalledWith(null, "v1");
		expect(flow.pendingNotice.value).toContain("already verified");
		expect(flow.pendingNotice.value).toContain("o***@x.com");
		expect(flow.reconnectMode.value).toBe(true);
	});

	it("re-registers instead of resending while reconnecting", async () => {
		const { flow } = mountHost();
		flow.enterPending({ email: "o***@x.com", reconnect: true });
		registration.register.mockResolvedValue({ success: true, verification_pending: true });

		await flow.resend();

		expect(registration.resendVerification).not.toHaveBeenCalled();
		expect(registration.register).toHaveBeenCalled();
		expect(flow.pendingNotice.value).toBe("We sent a new link to o***@x.com.");
	});
});

describe("changeEmail", () => {
	it("reports success so the form can close", async () => {
		const { flow } = mountHost();
		registration.changePendingEmail.mockResolvedValue({ success: true, owner_email_masked: "n***@x.com" });
		const done = vi.fn();

		await flow.changeEmail("new@x.com", done);

		expect(done).toHaveBeenCalledWith(true);
		expect(flow.pendingEmail.value).toBe("n***@x.com");
	});

	it("reports failure so the form stays open", async () => {
		const { flow } = mountHost();
		registration.changePendingEmail.mockResolvedValue({ success: false, error: "Nope." });
		const done = vi.fn();

		await flow.changeEmail("new@x.com", done);

		expect(done).toHaveBeenCalledWith(false);
		expect(flow.pendingNotice.value).toBe("Nope.");
	});
});

describe("waiting for another tab", () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it("polls this site's own status, never FAC Cloud's lookup", async () => {
		const { flow, onVerified } = mountHost();
		registration.getLocalStatus.mockResolvedValue({ registration_status: "Registered" });
		flow.enterPending();
		await flushPromises();

		await vi.advanceTimersByTimeAsync(5000);

		expect(registration.getLocalStatus).toHaveBeenCalled();
		expect(registration.getState).not.toHaveBeenCalled();
		expect(onVerified).toHaveBeenCalledOnce();
	});

	it("checks when the window regains focus", async () => {
		const { flow, onVerified } = mountHost();
		registration.getLocalStatus.mockResolvedValue({ registration_status: "Registered" });
		flow.enterPending();
		await flushPromises();

		window.dispatchEvent(new Event("focus"));
		await flushPromises();

		expect(onVerified).toHaveBeenCalledOnce();
	});

	it("stops polling once unmounted", async () => {
		const { flow, wrapper } = mountHost();
		registration.getLocalStatus.mockResolvedValue({ registration_status: "Pending Email Verification" });
		flow.enterPending();
		await flushPromises();

		wrapper.unmount();
		await vi.advanceTimersByTimeAsync(20000);
		window.dispatchEvent(new Event("focus"));
		await flushPromises();

		expect(registration.getLocalStatus).not.toHaveBeenCalled();
	});
});
