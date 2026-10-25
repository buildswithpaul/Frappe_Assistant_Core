import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

vi.mock("@/api/domains/facPage", () => ({
	facPage: { getPage: vi.fn().mockResolvedValue(null), listMine: vi.fn().mockResolvedValue([]) },
}));
vi.mock("@/api/_core", () => ({ baseCall: vi.fn().mockResolvedValue([]), getCall: vi.fn() }));

import { usePagePanel } from "@/composables/usePagePanel";
import BrowserToolConfirm from "@/widget/panel/BrowserToolConfirm.vue";
import { askConfirm, confirms, resetConfirms } from "@/widget/panel/confirmQueue";
import PageDock from "./PageDock.vue";
import PagePanel from "./PagePanel.vue";

let wrapper;
const mountDock = (props = {}) =>
	(wrapper = mount(PageDock, { props: { messages: [], sessionId: "s1", canShare: true, ...props } }));

function setPhone(phone) {
	window.matchMedia = vi.fn().mockReturnValue({ matches: phone });
}

beforeEach(() => setPhone(false));
afterEach(() => {
	wrapper?.unmount();
	usePagePanel().close();
	resetConfirms();
	delete window.matchMedia;
});

describe("PageDock", () => {
	it("shows the panel only while a page is open, and says when one opens", async () => {
		const w = mountDock();
		expect(w.find(".page-dock").exists()).toBe(false);
		usePagePanel().open("sales-a1b2c3");
		await nextTick();
		expect(w.find(".page-dock").exists()).toBe(true);
		expect(w.emitted("open")).toEqual([["sales-a1b2c3"]]);
	});

	it("closes the page when the conversation changes", async () => {
		const w = mountDock();
		usePagePanel().open("sales-a1b2c3");
		await nextTick();
		await w.setProps({ sessionId: "s2" });
		expect(usePagePanel().openName.value).toBe(null);
	});

	it("passes Share… on, keeping the page open beside the chat", async () => {
		const w = mountDock();
		usePagePanel().open("sales-a1b2c3");
		await flushPromises();
		w.findComponent(PagePanel).vm.$emit("share", "Share this page with my team");
		expect(w.emitted("share")).toEqual([["Share this page with my team"]]);
		expect(usePagePanel().openName.value).toBe("sales-a1b2c3");
	});

	it("closes the full-screen overlay before sharing on a phone, so the composer shows", async () => {
		setPhone(true);
		const w = mountDock();
		usePagePanel().open("sales-a1b2c3");
		await flushPromises();
		w.findComponent(PagePanel).vm.$emit("share", "Share this page with my team");
		expect(usePagePanel().openName.value).toBe(null);
		expect(w.emitted("share")).toHaveLength(1);
	});

	it("registers itself, so chips open the panel rather than Desk", () => {
		expect(usePagePanel().dockMounted.value).toBe(false);
		mountDock();
		expect(usePagePanel().dockMounted.value).toBe(true);
		wrapper.unmount();
		wrapper = null;
		expect(usePagePanel().dockMounted.value).toBe(false);
	});

	it("shows FACO's screenshot request above the open page, and denies it when the page closes", async () => {
		const w = mountDock();
		usePagePanel().open("sales-a1b2c3");
		await flushPromises();
		const decision = askConfirm({ tool_name: "take_screenshot", params: {}, description: "" });
		await nextTick();
		expect(w.findComponent(BrowserToolConfirm).exists()).toBe(true);

		usePagePanel().close();
		await expect(decision).resolves.toBe("deny");
		expect(confirms.value).toEqual([]);
	});
});
