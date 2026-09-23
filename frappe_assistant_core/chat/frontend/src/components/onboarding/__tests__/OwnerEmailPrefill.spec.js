import { mount, flushPromises } from "@vue/test-utils";
import { vi, describe, it, expect, beforeEach } from "vitest";
import OnboardingScreen from "@/components/onboarding/OnboardingScreen.vue";
import PartnerCodeStep from "@/components/onboarding/PartnerCodeStep.vue";

const getState = vi.fn();
const register = vi.fn();
const getTerms = vi.fn(() => Promise.resolve({ version: "v1" }));

vi.mock("@/api/client", () => ({
	api: {
		registration: {
			getState: (...a) => getState(...a),
			register: (...a) => register(...a),
			getTerms: (...a) => getTerms(...a),
		},
	},
}));

describe("owner email prefill", () => {
	beforeEach(() => {
		getState.mockReset();
		register.mockReset();
	});

	it("offers the registering admin's own address", async () => {
		getState.mockResolvedValue({ exists: false, suggested_owner_email: "clinton@acme.com" });
		const w = mount(OnboardingScreen, {
			props: { isAdmin: true },
			global: { stubs: { FacoRobot: true, TermsModal: true, EmailVerificationPending: true } },
		});
		await flushPromises();

		expect(w.find("#owner-email").element.value).toBe("clinton@acme.com");
	});

	it("leaves the field empty when the server suggests nothing", async () => {
		// A session account with no real address of its own. Offering the
		// placeholder would invite the admin to accept an address registration
		// refuses anyway.
		getState.mockResolvedValue({ exists: false, suggested_owner_email: null });
		const w = mount(OnboardingScreen, {
			props: { isAdmin: true },
			global: { stubs: { FacoRobot: true, TermsModal: true, EmailVerificationPending: true } },
		});
		await flushPromises();

		expect(w.find("#owner-email").element.value).toBe("");
	});

	it("does not overwrite an address the admin has started typing", async () => {
		// The suggestion resolves after mount, so it races the keyboard.
		const w = mount(PartnerCodeStep, { props: { initialEmail: "" } });
		await w.find("#owner-email").setValue("accounts@acme.com");

		await w.setProps({ initialEmail: "clinton@acme.com" });

		expect(w.find("#owner-email").element.value).toBe("accounts@acme.com");
	});

	it("still fills a field the admin has not touched", async () => {
		const w = mount(PartnerCodeStep, { props: { initialEmail: "" } });

		await w.setProps({ initialEmail: "clinton@acme.com" });

		expect(w.find("#owner-email").element.value).toBe("clinton@acme.com");
	});
});
