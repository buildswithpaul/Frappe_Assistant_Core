import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import FeatureTour from "@/components/onboarding/FeatureTour.vue";

// GDPR (spec §8.1, F4): memory consent starts OFF and turns ON only for an
// explicit "Opt-Out" workspace policy. Opt-In, no policy, a failed request and
// the loading state all leave it off, and Get Started waits for the request.

const { getConfig, saveInitialConsent, updateProfile, warn, error, push } = vi.hoisted(() => ({
	getConfig: vi.fn(),
	saveInitialConsent: vi.fn(),
	updateProfile: vi.fn(),
	warn: vi.fn(),
	error: vi.fn(),
	push: vi.fn(),
}));

vi.mock("@/api/client", () => ({
	api: {
		privacy: { getConfig, saveInitialConsent },
		profile: { update: updateProfile },
	},
}));
vi.mock("@/utils/logger", () => ({ logger: { warn, error } }));
vi.mock("@/stores/userStore", () => ({ useUserStore: () => ({}) }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

const STUBS = {
	WelcomeStage: true,
	OnboardingProgress: true,
	FeatureReel: true,
	PlanCard: true,
	ProfileCard: true,
	PrivacyCard: true,
};

function deferred() {
	let resolve;
	const promise = new Promise((res) => {
		resolve = res;
	});
	return { promise, resolve };
}

async function mountAtSetup() {
	const wrapper = mount(FeatureTour, { global: { stubs: STUBS } });
	wrapper.findComponent({ name: "FeatureReel" }).vm.$emit("complete");
	await flushPromises();
	wrapper.findComponent({ name: "PlanCard" }).vm.$emit("continue");
	await flushPromises();
	await wrapper.find(".skip-link").trigger("click");
	return wrapper;
}

const consentShown = (wrapper) =>
	wrapper.findComponent({ name: "PrivacyCard" }).props("memoryConsent");
const finishButton = (wrapper) => wrapper.find('[data-test="tour-finish"]');

describe("FeatureTour memory consent default", () => {
	let wrapper;

	beforeEach(() => {
		getConfig.mockReset();
		saveInitialConsent.mockReset().mockResolvedValue({ success: true, memory_consent: true });
		updateProfile.mockReset();
		warn.mockReset();
		error.mockReset();
	});

	afterEach(() => {
		wrapper?.unmount();
		wrapper = undefined;
	});

	it("stays off for a member on an Opt-In workspace", async () => {
		getConfig.mockResolvedValue({
			is_admin: false,
			default_memory_consent: "Opt-In",
			user_privacy: { memory_consent: false, processing_restricted: false },
		});
		wrapper = await mountAtSetup();

		expect(consentShown(wrapper)).toBe(false);
	});

	it("starts on only for an Opt-Out workspace", async () => {
		getConfig.mockResolvedValue({ is_admin: false, default_memory_consent: "Opt-Out" });
		wrapper = await mountAtSetup();

		expect(consentShown(wrapper)).toBe(true);
	});

	it("reads an admin's tenant block from a server that predates the top-level policy", async () => {
		getConfig.mockResolvedValue({
			is_admin: true,
			tenant: { default_memory_consent: "Opt-Out" },
		});
		wrapper = await mountAtSetup();

		expect(consentShown(wrapper)).toBe(true);
	});

	it("stays off when the workspace states no policy", async () => {
		getConfig.mockResolvedValue({ is_admin: false, default_memory_consent: null });
		wrapper = await mountAtSetup();

		expect(consentShown(wrapper)).toBe(false);
	});

	it("stays off when the policy request fails, and still lets the user finish", async () => {
		getConfig.mockRejectedValue(new Error("network"));
		wrapper = await mountAtSetup();

		expect(consentShown(wrapper)).toBe(false);
		expect(finishButton(wrapper).attributes("disabled")).toBeUndefined();
		expect(warn).toHaveBeenCalled();
	});

	it("keeps consent off and Get Started disabled while the policy loads", async () => {
		const policy = deferred();
		getConfig.mockReturnValue(policy.promise);
		wrapper = await mountAtSetup();

		expect(consentShown(wrapper)).toBe(false);
		expect(finishButton(wrapper).attributes("disabled")).toBeDefined();

		policy.resolve({ is_admin: false, default_memory_consent: "Opt-In" });
		await flushPromises();

		expect(finishButton(wrapper).attributes("disabled")).toBeUndefined();
	});

	it("never overwrites a choice the user made while the policy loaded", async () => {
		const policy = deferred();
		getConfig.mockReturnValue(policy.promise);
		wrapper = await mountAtSetup();
		const card = wrapper.findComponent({ name: "PrivacyCard" });

		card.vm.$emit("update:memoryConsent", true);
		card.vm.$emit("update:memoryConsent", false);
		policy.resolve({ is_admin: false, default_memory_consent: "Opt-Out" });
		await flushPromises();

		expect(consentShown(wrapper)).toBe(false);
	});

	it("saves the consent it showed when the user finishes", async () => {
		getConfig.mockResolvedValue({ is_admin: false, default_memory_consent: "Opt-Out" });
		wrapper = await mountAtSetup();

		await finishButton(wrapper).trigger("click");
		await flushPromises();

		expect(saveInitialConsent).toHaveBeenCalledWith(true);
	});
});
