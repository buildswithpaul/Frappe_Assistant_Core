import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { useUserStore } from "@/stores/userStore";
import CreditPurchaseModal from "../CreditPurchaseModal.vue";

const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

function mountModal(status) {
	const store = useUserStore();
	// The billing page opens the modal for an admin; myCreditStatus comes from get_my_credit_status.
	store.myCreditStatus = status;
	vi.spyOn(store, "loadMyCreditStatus").mockResolvedValue();
	return mount(CreditPurchaseModal, {
		props: { isOpen: true, gateways: [] },
		global: { stubs: { Teleport: true } },
	});
}

describe("CreditPurchaseModal personal limit notice", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		push.mockReset();
	});

	it("tells a buyer at their personal limit that credits won't lift it, and links to Users", async () => {
		const wrapper = mountModal({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 11234 });
		await flushPromises();
		const notice = wrapper.find("[data-test='personal-limit-notice']");
		expect(notice.exists()).toBe(true);
		expect(notice.text()).toContain("won't raise your personal limit");
		await notice.find("[data-test='open-users']").trigger("click");
		expect(push).toHaveBeenCalledWith({ name: "settings-users" });
		expect(wrapper.emitted("close")).toBeTruthy();
	});

	it("shows nothing extra for a buyer under their limit", async () => {
		const wrapper = mountModal({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 200 });
		await flushPromises();
		expect(wrapper.find("[data-test='personal-limit-notice']").exists()).toBe(false);
	});

	it("refreshes the buyer's own status when it opens", async () => {
		setActivePinia(createPinia());
		const store = useUserStore();
		const load = vi.spyOn(store, "loadMyCreditStatus").mockResolvedValue();
		mount(CreditPurchaseModal, { props: { isOpen: true, gateways: [] }, global: { stubs: { Teleport: true } } });
		expect(load).toHaveBeenCalled();
	});
});
