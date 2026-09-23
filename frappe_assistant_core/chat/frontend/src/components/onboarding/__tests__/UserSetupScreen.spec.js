import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import UserSetupScreen from "@/components/onboarding/UserSetupScreen.vue";
import { useUserStore } from "@/stores/userStore";

function mountScreen() {
	return mount(UserSetupScreen, {
		global: {
			stubs: { FacoRobot: true },
		},
	});
}

describe("UserSetupScreen", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("shows the Connect button to an admin", () => {
		const store = useUserStore();
		store.isAdmin = true;
		const wrapper = mountScreen();
		expect(wrapper.find(".connect-btn").exists()).toBe(true);
		expect(wrapper.find(".pending-card").exists()).toBe(false);
	});

	it("shows the Connect button to a pending member (registered but not ready)", () => {
		const store = useUserStore();
		store.isAdmin = false;
		store.userAuthStatus = { user_registered: true, ready: false };
		const wrapper = mountScreen();
		expect(wrapper.find(".connect-btn").exists()).toBe(true);
		expect(wrapper.find(".pending-card").exists()).toBe(false);
	});

	it("shows the passive wait to a genuine non-member (not registered)", () => {
		const store = useUserStore();
		store.isAdmin = false;
		store.userAuthStatus = { user_registered: false, ready: false };
		const wrapper = mountScreen();
		expect(wrapper.find(".connect-btn").exists()).toBe(false);
		expect(wrapper.find(".pending-card").exists()).toBe(true);
	});

	it("shows softened connect copy without FACO Cloud jargon", () => {
		const store = useUserStore();
		store.isAdmin = true;
		const wrapper = mountScreen();
		expect(wrapper.text()).toContain("Connect your account");
		expect(wrapper.text()).toContain("documents and permissions");
		expect(wrapper.text()).not.toMatch(/FACO Cloud/i);
	});
});
