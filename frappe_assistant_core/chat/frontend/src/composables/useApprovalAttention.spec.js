import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent, reactive } from "vue";
import { mount } from "@vue/test-utils";
import { useApprovalAttention, FLASH_INTERVAL_MS } from "./useApprovalAttention";

function setHidden(hidden) {
	Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
}

function mountWith(chatStore) {
	const Dummy = defineComponent({
		setup() {
			useApprovalAttention(chatStore);
			return () => null;
		},
	});
	return mount(Dummy);
}

describe("useApprovalAttention", () => {
	let chatStore;

	beforeEach(() => {
		vi.useFakeTimers();
		document.title = "FAC Chat";
		setHidden(true);
		chatStore = reactive({ hasPendingInteraction: false });
	});

	afterEach(() => {
		vi.useRealTimers();
		delete document.hidden;
		document.title = "FAC Chat";
	});

	it("flashes the title while an approval waits in a hidden tab", async () => {
		const wrapper = mountWith(chatStore);
		chatStore.hasPendingInteraction = true;
		await wrapper.vm.$nextTick();

		vi.advanceTimersByTime(FLASH_INTERVAL_MS);
		expect(document.title).toBe("● Approval needed");

		vi.advanceTimersByTime(FLASH_INTERVAL_MS);
		expect(document.title).toBe("FAC Chat");
	});

	it("restores the title once the approval is resolved", async () => {
		const wrapper = mountWith(chatStore);
		chatStore.hasPendingInteraction = true;
		await wrapper.vm.$nextTick();
		vi.advanceTimersByTime(FLASH_INTERVAL_MS);

		chatStore.hasPendingInteraction = false;
		await wrapper.vm.$nextTick();

		expect(document.title).toBe("FAC Chat");
		vi.advanceTimersByTime(FLASH_INTERVAL_MS * 3);
		expect(document.title).toBe("FAC Chat");
	});

	it("stops flashing when the user comes back to the tab", async () => {
		const wrapper = mountWith(chatStore);
		chatStore.hasPendingInteraction = true;
		await wrapper.vm.$nextTick();
		vi.advanceTimersByTime(FLASH_INTERVAL_MS);

		setHidden(false);
		document.dispatchEvent(new Event("visibilitychange"));

		expect(document.title).toBe("FAC Chat");
		vi.advanceTimersByTime(FLASH_INTERVAL_MS * 3);
		expect(document.title).toBe("FAC Chat");
	});

	it("does not touch the title when nothing is pending", async () => {
		mountWith(chatStore);
		vi.advanceTimersByTime(FLASH_INTERVAL_MS * 3);
		expect(document.title).toBe("FAC Chat");
	});

	it("stops flashing when the view unmounts", async () => {
		const wrapper = mountWith(chatStore);
		chatStore.hasPendingInteraction = true;
		await wrapper.vm.$nextTick();
		vi.advanceTimersByTime(FLASH_INTERVAL_MS);

		wrapper.unmount();

		expect(document.title).toBe("FAC Chat");
		vi.advanceTimersByTime(FLASH_INTERVAL_MS * 3);
		expect(document.title).toBe("FAC Chat");
	});
});
