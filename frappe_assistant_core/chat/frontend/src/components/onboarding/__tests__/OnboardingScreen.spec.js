import { mount, flushPromises } from "@vue/test-utils";
import { vi, describe, it, expect, beforeEach } from "vitest";
import OnboardingScreen from "@/components/onboarding/OnboardingScreen.vue";

const getState = vi.fn();
const register = vi.fn();
const getTerms = vi.fn(() => Promise.resolve({ version: "v1" }));

vi.mock("@/api/client", () => ({
	api: { registration: { getState: (...a) => getState(...a), register: (...a) => register(...a), getTerms: (...a) => getTerms(...a) } },
}));

function mountScreen() {
	return mount(OnboardingScreen, {
		props: { isAdmin: true },
		global: { stubs: { FacoRobot: true, PartnerCodeStep: true, TermsModal: true, EmailVerificationPending: true } },
	});
}

describe("OnboardingScreen reconnect", () => {
	beforeEach(() => { getState.mockReset(); register.mockReset(); });

	it("shows reconnect card for a returning tenant", async () => {
		getState.mockResolvedValue({ exists: true, reregistration: true, owner_email_masked: "p***@x.com" });
		const w = mountScreen();
		await flushPromises();
		expect(w.find('[data-test="reconnect-card"]').exists()).toBe(true);
		expect(w.text()).toContain("p***@x.com");
		expect(w.findComponent({ name: "PartnerCodeStep" }).exists()).toBe(false);
	});

	it("runs the full funnel for a brand-new site", async () => {
		getState.mockResolvedValue({ exists: false });
		const w = mountScreen();
		await flushPromises();
		expect(w.find('[data-test="reconnect-card"]').exists()).toBe(false);
		expect(w.findComponent({ name: "PartnerCodeStep" }).exists()).toBe(true);
	});

	it("degrades to full funnel when lookup fails", async () => {
		getState.mockRejectedValue(new Error("network"));
		const w = mountScreen();
		await flushPromises();
		expect(w.find('[data-test="reconnect-card"]').exists()).toBe(false);
		expect(w.findComponent({ name: "PartnerCodeStep" }).exists()).toBe(true);
	});

	it("reconnect button fires register and shows pending", async () => {
		getState.mockResolvedValue({ exists: true, reregistration: true, owner_email_masked: "p***@x.com" });
		register.mockResolvedValue({ success: true, verification_pending: true });
		const w = mountScreen();
		await flushPromises();
		await w.find('[data-test="reconnect-send"]').trigger("click");
		await flushPromises();
		expect(register).toHaveBeenCalled();
		expect(w.findComponent({ name: "EmailVerificationPending" }).exists()).toBe(true);
	});
});

// A local or firewalled site can never work in cloud mode, so the generic
// "Try Again" card is a dead end there. AR marks that case with a structured
// error_code and the screen must route it to the two-door panel instead.
describe("OnboardingScreen unreachable-site routing", () => {
	beforeEach(() => {
		getState.mockReset();
		register.mockReset();
		getState.mockResolvedValue({ exists: true, reregistration: true, owner_email_masked: "p***@x.com" });
	});

	async function failRegistrationWith(result) {
		register.mockResolvedValue(result);
		const w = mountScreen();
		await flushPromises();
		await w.find('[data-test="reconnect-send"]').trigger("click");
		await flushPromises();
		return w;
	}

	it("shows the two-door panel for SITE_UNREACHABLE", async () => {
		const w = await failRegistrationWith({
			success: false,
			error: "FAC Cloud could not reach http://mysite.localhost:8000.",
			error_code: "SITE_UNREACHABLE",
		});

		expect(w.findComponent({ name: "SiteUnreachablePanel" }).exists()).toBe(true);
		expect(w.find(".error-card").exists()).toBe(false);
	});

	it("passes AR's message through to the panel unaltered", async () => {
		const message = "FAC Cloud could not reach http://mysite.localhost:8000.";
		const w = await failRegistrationWith({ success: false, error: message, error_code: "SITE_UNREACHABLE" });

		expect(w.findComponent({ name: "SiteUnreachablePanel" }).props("message")).toBe(message);
	});

	it("keeps the generic retry card for every other failure", async () => {
		const w = await failRegistrationWith({ success: false, error: "Registration failed. Please try again." });

		expect(w.find(".error-card").exists()).toBe(true);
		expect(w.findComponent({ name: "SiteUnreachablePanel" }).exists()).toBe(false);
	});

	it("returns to the funnel when the panel asks to retry", async () => {
		const w = await failRegistrationWith({
			success: false,
			error: "FAC Cloud could not reach http://mysite.localhost:8000.",
			error_code: "SITE_UNREACHABLE",
		});

		w.findComponent({ name: "SiteUnreachablePanel" }).vm.$emit("retry");
		await flushPromises();

		expect(w.findComponent({ name: "SiteUnreachablePanel" }).exists()).toBe(false);
		expect(w.findComponent({ name: "PartnerCodeStep" }).exists()).toBe(true);
	});
});
