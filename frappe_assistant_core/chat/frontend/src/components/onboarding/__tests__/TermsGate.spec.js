import { mount, flushPromises } from "@vue/test-utils";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import TermsGate from "@/components/onboarding/TermsGate.vue";
import { useUserStore } from "@/stores/userStore";

const getTerms = vi.fn(() => Promise.resolve({ version: "1.0" }));
const acceptUpdatedTerms = vi.fn(() => Promise.resolve({ success: true }));

vi.mock("@/api/client", () => ({
	api: {
		registration: {
			getTerms: (...a) => getTerms(...a),
			acceptUpdatedTerms: (...a) => acceptUpdatedTerms(...a),
		},
	},
}));

function mountGate(termsState) {
	const store = useUserStore();
	store.termsState = termsState;
	const wrapper = mount(TermsGate, {
		global: { stubs: { FacoRobot: true, TermsModal: true } },
	});
	return { wrapper, store };
}

describe("TermsGate", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		getTerms.mockClear();
		acceptUpdatedTerms.mockClear();
	});

	it("offers the accept action to an admin", () => {
		const { wrapper } = mountGate({
			acceptance_required: true,
			can_accept: true,
			required_version: "1.0",
		});

		expect(wrapper.find('[data-test="terms-gate-review"]').exists()).toBe(true);
		expect(wrapper.find('[data-test="terms-gate-notice"]').exists()).toBe(false);
		expect(wrapper.text()).toContain("1.0");
	});

	it("tells a non-admin to ask their administrator, with no accept action", () => {
		// Acceptance binds the whole tenant, so it must not be offered to a
		// user who has no authority to give it.
		const { wrapper } = mountGate({ acceptance_required: true, can_accept: false });

		expect(wrapper.find('[data-test="terms-gate-notice"]').exists()).toBe(true);
		expect(wrapper.find('[data-test="terms-gate-review"]').exists()).toBe(false);
	});

	it("clears the gate after a successful acceptance", async () => {
		const { wrapper, store } = mountGate({
			acceptance_required: true,
			can_accept: true,
			required_version: "1.0",
		});

		await wrapper.find('[data-test="terms-gate-review"]').trigger("click");
		await flushPromises();

		// Accepts the version actually displayed, not the gate's required_version.
		wrapper.findComponent({ name: "TermsModal" }).vm.$emit("accept", "1.0");
		await flushPromises();

		expect(acceptUpdatedTerms).toHaveBeenCalledWith("1.0");
		expect(store.termsState.acceptance_required).toBe(false);
	});

	it("keeps the gate up and surfaces the reason when acceptance fails", async () => {
		acceptUpdatedTerms.mockResolvedValueOnce({ success: false, error: "Terms version mismatch." });
		const { wrapper, store } = mountGate({
			acceptance_required: true,
			can_accept: true,
			required_version: "1.0",
		});

		await wrapper.find('[data-test="terms-gate-review"]').trigger("click");
		await flushPromises();
		wrapper.findComponent({ name: "TermsModal" }).vm.$emit("accept", "0.9");
		await flushPromises();

		expect(store.termsState.acceptance_required).toBe(true);
		expect(wrapper.text()).toContain("Terms version mismatch.");
	});
});
