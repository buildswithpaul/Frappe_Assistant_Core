import { describe, it, expect, vi, beforeEach, afterEach, onTestFinished } from "vitest";
import { mount, flushPromises, enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { nextTick } from "vue";

const getQuotaStatus = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		chat: { getMessages: vi.fn().mockResolvedValue({ messages: [] }), send: vi.fn().mockResolvedValue({}) },
		init: { initialize: vi.fn().mockResolvedValue(null) },
		models: { getAvailable: vi.fn().mockResolvedValue({ models: [] }) },
		billing: { getQuotaStatus: (...a) => getQuotaStatus(...a) },
		users: { getMyCreditStatus: vi.fn().mockResolvedValue(null) },
		get: vi.fn(),
	},
}));

import { api } from "@/api/client";
import WidgetPanel from "./WidgetPanel.vue";
import PanelApp from "./PanelApp.vue";
import WidgetWelcome from "./WidgetWelcome.vue";
import BrowserToolConfirm from "./BrowserToolConfirm.vue";
import { createRouterShim } from "./routerShim.js";
import { computePlacement, placePanel } from "./placement.js";
import { resetConfirms, listenForConfirms } from "./confirmQueue.js";
import { bridge } from "../bridge.js";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useModelStore } from "@/stores/modelStore";
import { useSpotlightStore } from "@/stores/spotlightStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { configureSurface, resetSurface } from "@/stores/chat/surface";
import { DAILY_KEY, localDate } from "@/components/spotlight/spotlightRules";

// A panel left mounted keeps its document-level listeners alive into the next test.
enableAutoUnmount(afterEach);

const stubs = { ChatInterface: true, InputArea: true, CreditMeter: true };
const SendStub = { template: "<i />" };

describe("router shim", () => {
	it("opens FAC Chat for any route a shared component pushes", async () => {
		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		const router = createRouterShim();
		await router.push("/settings/billing?tab=plans");
		expect(open).toHaveBeenCalledWith("/copilot/settings/billing?tab=plans", "_blank", "noopener");
		// The shim has no pages of its own: the navigation itself must be cancelled.
		expect(router.currentRoute.value.fullPath).toBe("/");
	});
});

describe("widget panel", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		resetConfirms();
		localStorage.clear();
		getQuotaStatus.mockReset().mockResolvedValue(null);
		window.frappe = { set_route: vi.fn(), get_route: () => ["List", "ToDo"], session: { user: "u@x.test" } };
		bridge.state.sessionId = "faco_1";
	});

	it("routes /app links through frappe.set_route instead of reloading", async () => {
		const w = mount(WidgetPanel, {
			global: {
				stubs: {
					// Message renderers stop propagation on their own clicks; the interceptor must still see them.
					ChatInterface: { template: '<div><a href="/app/sales-invoice/INV-1" @click.stop>x</a></div>' },
					InputArea: true,
					CreditMeter: true,
				},
			},
		});
		useChatStore().messages = [{ role: "user", content: "hi", blocks: [] }];
		await flushPromises();
		await w.find('a[href="/app/sales-invoice/INV-1"]').trigger("click");
		expect(window.frappe.set_route).toHaveBeenCalledWith("sales-invoice", "INV-1");
	});

	it("asks the launcher to close, and hands the session to FAC Chat on expand", async () => {
		const emit = vi.spyOn(bridge, "emit");
		const assign = vi.fn();
		const original = Object.getOwnPropertyDescriptor(window, "location");
		Object.defineProperty(window, "location", { value: { assign }, configurable: true });
		onTestFinished(() => Object.defineProperty(window, "location", original));
		const w = mount(WidgetPanel, { global: { stubs } });
		await w.find('[data-test="close"]').trigger("click");
		expect(emit).toHaveBeenCalledWith("close");
		await w.find('[data-test="expand"]').trigger("click");
		expect(JSON.parse(sessionStorage.getItem("faco_active_session")).id).toBe("faco_1");
		expect(assign).toHaveBeenCalledWith("/copilot");
	});

	it("tells the launcher to hide for good once the preference is saved", async () => {
		window.frappe.call = vi.fn().mockResolvedValue({ message: { success: true } });
		const emit = vi.spyOn(bridge, "emit");
		const w = mount(WidgetPanel, { global: { stubs } });
		await w.find('[data-test="hide"]').trigger("click");
		await flushPromises();
		expect(window.frappe.call).toHaveBeenCalledWith({
			method: "frappe_assistant_core.chat.api.settings.widget.update_user_preference",
			args: { field: "hide_widget", value: "1" },
		});
		expect(emit).toHaveBeenCalledWith("close");
		expect(emit).toHaveBeenCalledWith("hide");
	});

	it("keeps the widget when saving the preference fails", async () => {
		// update_user_preference answers 200 {success:false} on a validation error.
		window.frappe.call = vi.fn().mockResolvedValue({ message: { success: false, message: "nope" } });
		const emit = vi.spyOn(bridge, "emit");
		const w = mount(WidgetPanel, { global: { stubs } });
		await w.find('[data-test="hide"]').trigger("click");
		await flushPromises();
		expect(emit).not.toHaveBeenCalledWith("hide");
		expect(emit).not.toHaveBeenCalledWith("close");
	});

	it("shows the welcome until there is a conversation", async () => {
		const w = mount(WidgetPanel, { global: { stubs } });
		expect(w.text()).toContain("Hi! I'm FACO");
		useChatStore().messages = [{ role: "user", content: "hi", blocks: [] }];
		await nextTick();
		expect(w.text()).not.toContain("Hi! I'm FACO");
	});

	it("puts a browser-tool confirmation in the message list and resolves the launcher's promise", async () => {
		// PanelApp starts this listener for the whole life of the panel.
		onTestFinished(listenForConfirms());
		const w = mount(WidgetPanel, { global: { stubs } });
		const resolve = vi.fn();
		bridge.emit("confirm", {
			request: { tool_name: "take_screenshot", params: {}, description: "x" },
			resolve,
		});
		await nextTick();
		expect(w.text()).toContain("Capture screenshot");
		await w.find('[data-test="confirm-trust"]').trigger("click");
		expect(resolve).toHaveBeenCalledWith("trust");
		expect(w.text()).not.toContain("Capture screenshot");
	});

	it("keeps a confirmation that arrives before the panel is ready", async () => {
		// The launcher asks right after open(), while PanelApp is still initialising and the chat
		// is not mounted yet.
		const app = mount(PanelApp, { global: { stubs: { WidgetPanel: true, WidgetSetupGate: true, SpotlightHost: true, ToastContainer: true } } });
		onTestFinished(() => app.unmount());
		const resolve = vi.fn();
		bridge.emit("confirm", { request: { tool_name: "get_form_data", params: {}, description: "" }, resolve });
		const w = mount(WidgetPanel, { global: { stubs } });
		await nextTick();
		expect(w.text()).toContain("Read form data");
	});

	it("refuses an admin's send when credits are exhausted and raises the quota Spotlight", async () => {
		const chat = useChatStore();
		const send = vi.spyOn(chat, "sendMessage").mockResolvedValue();
		const spot = vi.spyOn(useSpotlightStore(), "onQuotaExhausted").mockResolvedValue();
		useUserStore().quotaInfo = { credits_exhausted: true, is_admin: true };
		const w = mount(WidgetPanel, { global: { stubs: { ...stubs, InputArea: SendStub } } });
		await w.findComponent(SendStub).vm.$emit("send", { message: "hello" });
		expect(spot).toHaveBeenCalled();
		expect(send).not.toHaveBeenCalled();
	});

	it("still sends a member's message when credits are exhausted, so they see the server's error", async () => {
		// The Spotlight is admin-only; refusing here would swallow the text with nothing shown.
		const chat = useChatStore();
		const send = vi.spyOn(chat, "sendMessage").mockResolvedValue();
		const spot = vi.spyOn(useSpotlightStore(), "onQuotaExhausted").mockResolvedValue();
		useUserStore().quotaInfo = { credits_exhausted: true, is_admin: false };
		const w = mount(WidgetPanel, { global: { stubs: { ...stubs, InputArea: SendStub } } });
		await w.findComponent(SendStub).vm.$emit("send", { message: "hello" });
		await flushPromises();
		expect(send).toHaveBeenCalled();
		expect(spot).not.toHaveBeenCalled();
	});

	it("sends through the store when credits remain", async () => {
		const chat = useChatStore();
		const send = vi.spyOn(chat, "sendMessage").mockResolvedValue();
		useUserStore().quotaInfo = { credits_exhausted: false, is_admin: true };
		const w = mount(WidgetPanel, { global: { stubs: { ...stubs, InputArea: SendStub } } });
		await w.findComponent(SendStub).vm.$emit("send", { message: "hello" });
		await flushPromises();
		expect(send).toHaveBeenCalledWith("hello", [], null, null, null, { skipQueue: false });
	});

	it("fetches the full quota once on mount, because the boot payload lacks the admission flags", async () => {
		getQuotaStatus.mockResolvedValue({ credits_exhausted: true, is_admin: true });
		const pinia = createPinia();
		mount(WidgetPanel, { global: { plugins: [pinia], stubs } });
		await flushPromises();
		expect(getQuotaStatus).toHaveBeenCalledTimes(1);
		expect(useUserStore(pinia).quotaInfo.credits_exhausted).toBe(true);
	});

	describe("overage notice", () => {
		const overage = { is_admin: true, in_overage: true, credits_exhausted: false, credit_balance: 1500, billing_cycle_start: "2026-10-01" };

		it("shows once per cycle to an admin on prepaid credits, and stays dismissed", async () => {
			getQuotaStatus.mockResolvedValue(overage);
			const w = mount(WidgetPanel, { global: { stubs } });
			await flushPromises();
			expect(w.text()).toContain("Your monthly credits are used up — FAC Chat is now drawing on your prepaid credits (1.5K left).");
			await w.find('[data-test="overage-dismiss"]').trigger("click");
			expect(w.find('[data-test="overage"]').exists()).toBe(false);

			const again = mount(WidgetPanel, { global: { stubs } });
			await flushPromises();
			expect(again.find('[data-test="overage"]').exists()).toBe(false);
		});

		it("is not shown to a member", async () => {
			getQuotaStatus.mockResolvedValue({ ...overage, is_admin: false });
			const w = mount(WidgetPanel, { global: { stubs } });
			await flushPromises();
			expect(w.find('[data-test="overage"]').exists()).toBe(false);
		});
	});

	describe("mic requested by the launcher's Ctrl+Shift+Space", () => {
		const Input = { template: '<div><button class="mic-btn" /></div>' };
		const mountWith = () => mount(WidgetPanel, { attachTo: document.body, global: { stubs: { ...stubs, InputArea: Input } } });
		afterEach(() => (bridge.state.micRequested = false));

		// Production: the launcher sets the flag on a fresh Desk page, opens the panel, and the chat
		// mounts only after bootstrap, so the flag is already there when WidgetPanel mounts.
		it("clicks the mic once on mount and clears the request", () => {
			bridge.state.micRequested = true;
			const click = vi.spyOn(HTMLElement.prototype, "click");
			mountWith();
			expect(click).toHaveBeenCalledTimes(1);
			expect(click.mock.instances[0].className).toBe("mic-btn");
			expect(bridge.state.micRequested).toBe(false);
		});

		it("does nothing on mount when no mic was requested", () => {
			const click = vi.spyOn(HTMLElement.prototype, "click");
			mountWith();
			expect(click).not.toHaveBeenCalled();
		});

		it("clicks the mic for a later request while mounted, once the open has landed", () => {
			vi.useFakeTimers();
			const click = vi.spyOn(HTMLElement.prototype, "click");
			mountWith();
			bridge.state.micRequested = true;
			bridge.emit("mic");
			expect(click).not.toHaveBeenCalled();
			vi.runAllTimers();
			expect(click).toHaveBeenCalledTimes(1);
			expect(click.mock.instances[0].className).toBe("mic-btn");
			expect(bridge.state.micRequested).toBe(false);
			vi.useRealTimers();
		});

		it("stops listening once the panel is gone", () => {
			vi.useFakeTimers();
			const click = vi.spyOn(HTMLElement.prototype, "click");
			mountWith().unmount();
			bridge.emit("mic");
			vi.runAllTimers();
			expect(click).not.toHaveBeenCalled();
			vi.useRealTimers();
		});
	});
});

describe("welcome", () => {
	afterEach(() => delete window.frappe);

	it("names the page the user is on", async () => {
		window.frappe = { get_route: () => ["List", "Sales Invoice"], router: { on: vi.fn(), off: vi.fn() } };
		const w = mount(WidgetWelcome);
		await nextTick();
		expect(w.find(".ww-context").exists()).toBe(true);
		expect(w.find(".ww-context").text()).toContain("Sales Invoice");
	});
});

describe("browser tool confirmation card", () => {
	it("uses the shipped copy and emits exactly approve, trust or deny", async () => {
		const w = mount(BrowserToolConfirm, { props: { request: { tool_name: "capture_diagnostics", params: {}, description: "" } } });
		expect(w.text()).toContain("Collect page diagnostics");
		await w.find('[data-test="confirm-deny"]').trigger("click");
		await w.find('[data-test="confirm-approve"]').trigger("click");
		await w.find('[data-test="confirm-trust"]').trigger("click");
		expect(w.emitted("decide").map((e) => e[0])).toEqual(["deny", "approve", "trust"]);
	});

	it("falls back to a generic line for an unknown tool, escaping nothing by hand", () => {
		const w = mount(BrowserToolConfirm, { props: { request: { tool_name: "<b>x</b>", params: {}, description: "" } } });
		expect(w.find("b").exists()).toBe(false);
		expect(w.text()).toContain("Run browser tool");
	});
});

describe("panel bootstrap", () => {
	const ready = {
		access: { user: "u@x.test", is_admin: false, status: "ready", preferences: { privacy_consent_complete: true } },
		user_auth: { ready: true },
		sessions: [],
	};
	const gateless = { SpotlightHost: true, ToastContainer: true, WidgetPanel: true };

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		window.frappe = { session: { user: "u@x.test" }, get_route: () => [] };
		bridge.state.sessionId = "faco_1";
		bridge.state.restored = false;
		api.init.initialize.mockResolvedValue(ready);
	});
	afterEach(() => resetSurface());

	it("routes automatically in memory and leaves FAC Chat's saved model choice alone", async () => {
		// A FAC Chat user who picked a model, then opens the widget on Desk (same localStorage).
		// A real catalogue answers: restoreAllMocks would otherwise reset getAvailable to undefined
		// and send loadModels down its error branch, which never touches the saved choice.
		api.models.getAvailable.mockResolvedValue({
			models: [{ model_id: "gpt-saved", tier: "Standard", tier_rank: 1, display_name: "GPT" }],
			default_model: "gpt-saved",
			max_tier_rank: 3,
			auto_mode: { enabled: true },
		});
		localStorage.setItem("faco_selected_model", "gpt-saved");
		mount(PanelApp, { global: { stubs: gateless } });
		await flushPromises();
		expect(useModelStore().models).toHaveLength(1);
		expect(useModelStore().currentModelId).toBe("auto");
		expect(localStorage.getItem("faco_selected_model")).toBe("gpt-saved");
	});

	it("does not clear FAC Chat's saved model when it has been retired", async () => {
		api.models.getAvailable.mockResolvedValue({
			models: [{ model_id: "other", tier: "Standard", tier_rank: 1 }],
			max_tier_rank: 3,
			auto_mode: { enabled: true },
		});
		localStorage.setItem("faco_selected_model", "retired-model");
		mount(PanelApp, { global: { stubs: gateless } });
		await flushPromises();
		expect(useModelStore().currentModelId).toBe("auto");
		expect(localStorage.getItem("faco_selected_model")).toBe("retired-model");
	});

	it("adopts the launcher's session and publishes it back", async () => {
		const emit = vi.spyOn(bridge, "emit");
		mount(PanelApp, { global: { stubs: gateless } });
		await flushPromises();
		expect(useChatStore().currentSessionId).toBe("faco_1");
		expect(emit).toHaveBeenCalledWith("session", "faco_1");
	});

	it("restores the saved conversation when the launcher resumed one", async () => {
		bridge.state.restored = true;
		const load = vi.spyOn(useChatStore(), "loadMessages").mockResolvedValue();
		mount(PanelApp, { global: { stubs: gateless } });
		await flushPromises();
		expect(load).toHaveBeenCalledWith("faco_1");
	});

	it("shows the setup gate, not the chat, until setup and consent are complete", async () => {
		api.init.initialize.mockResolvedValue({ ...ready, user_auth: { ready: false } });
		const w = mount(PanelApp, { global: { stubs: { ...gateless, WidgetSetupGate: { template: '<i class="gate" />' } } } });
		await flushPromises();
		expect(w.find(".gate").exists()).toBe(true);
		expect(w.findComponent(WidgetPanel).exists()).toBe(false);
	});

	it("keeps the widget's Spotlight daily cap under its own surface", async () => {
		configureSurface({ name: "widget", clientType: "widget", spotlightSurface: "widget" });
		const user = useUserStore();
		user.user = "u@x.test";
		user.registrationStatus = "ready";
		useNotificationStore().notifications = [
			{ id: "n1", display_style: "modal", title: "Agents", action_label: "Try", action_route: "/agents", dismissible: true },
		];
		await useSpotlightStore().evaluate();
		expect(localStorage.getItem(DAILY_KEY("u@x.test", "widget"))).toBe(localDate());
		expect(localStorage.getItem(DAILY_KEY("u@x.test", "spa"))).toBeNull();
	});
});

describe("placement", () => {
	const btn = (o) => ({ left: 0, right: 0, top: 0, bottom: 0, width: 56, height: 56, ...o });

	it("sits above the launcher and aligns to it on a desktop", () => {
		const css = computePlacement({ btnRect: btn({ left: 1500, right: 1556, top: 900, bottom: 956 }), width: 1600, height: 1000 });
		expect(css.bottom).toBe("110px");
		expect(css.top).toBe("auto");
		expect(css.right).toBe("44px");
		expect(css.left).toBe("auto");
	});

	it("goes below a launcher dragged to the top", () => {
		const css = computePlacement({ btnRect: btn({ left: 20, right: 76, top: 10, bottom: 66 }), width: 1600, height: 1000 });
		expect(css.top).toBe("82px");
		expect(css.bottom).toBe("auto");
		expect(css.left).toBe("20px");
	});

	it("anchors to the rect it is handed when the launcher button is hidden (0x0)", () => {
		document.body.innerHTML = "";
		const launcher = document.createElement("div");
		launcher.id = "fac-widget-launcher";
		launcher.attachShadow({ mode: "open" }).innerHTML = '<button class="faco-toggle-btn"></button>';
		document.body.appendChild(launcher);
		window.innerWidth = 1600;
		window.innerHeight = 1000;
		const host = document.createElement("div");
		const used = placePanel(host, btn({ left: 1500, right: 1556, top: 900, bottom: 956 }));
		expect(used.width).toBe(56);
		expect(host.style.bottom).toBe("110px");
		expect(host.style.right).toBe("44px");
		launcher.remove();
	});

	it("leaves a phone-width screen to the full-screen stylesheet rule", () => {
		expect(computePlacement({ btnRect: btn({ left: 300, right: 356, top: 700, bottom: 756 }), width: 400, height: 800 })).toEqual({});
	});

	it("becomes a bottom sheet under 1024px, whatever the saved launcher position", () => {
		const css = computePlacement({ btnRect: btn({ left: 20, right: 76, top: 10, bottom: 66 }), width: 800, height: 900 });
		expect(css).toMatchObject({ left: "8px", right: "8px", top: "auto", bottom: "76px", width: "auto" });
		expect(css.height).toBe("min(72dvh, calc(100svh - 92px))");
	});
});

afterEach(() => vi.restoreAllMocks());
