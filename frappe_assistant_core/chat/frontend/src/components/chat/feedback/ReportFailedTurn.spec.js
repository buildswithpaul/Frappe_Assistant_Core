import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { useSupportStore } from "@/stores/supportStore";
import MessageBubble from "../MessageBubble.vue";

const failed = (lastError) => ({
	role: "assistant",
	content: "partial",
	isStreaming: false,
	errored: true,
	lastError,
});

describe("Report this on the retry line", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		// production: ChatView mounts SupportModal, which registers itself as a host.
		useSupportStore().registerHost();
	});

	const mountBubble = (message) => mount(MessageBubble, { props: { message, canRetry: true } });

	it("report from the retry line works after the banner has gone", async () => {
		// production: handleStreamError stores lastError on the bubble, then the banner auto-dismisses after 8 s.
		const w = mountBubble(failed({ code: "MODEL_FAILED", message: "Model failed", at: "2026-11-17T10:00:00.000Z" }));
		await w.find("[data-test=report-failed-turn]").trigger("click");

		const support = useSupportStore();
		expect(support.isOpen).toBe(true);
		expect(support.mode).toBe("issue");
		expect(support.prefill).toBe("Error: Model failed\nCode: MODEL_FAILED\nTime: 2026-11-17T10:00:00.000Z\n\n");
	});

	it("is absent where no support modal is mounted", () => {
		// production: the Desk widget renders the bubble without a SupportModal.
		useSupportStore().unregisterHost();
		const w = mountBubble(failed({ code: "MODEL_FAILED", message: "x", at: "t" }));
		expect(w.find("[data-test=report-failed-turn]").exists()).toBe(false);
	});

	it("is absent for a non-reportable code", () => {
		const w = mountBubble(failed({ code: "quota_exhausted", message: "x", at: "t" }));
		expect(w.find("[data-test=report-failed-turn]").exists()).toBe(false);
	});

	it("is absent when no failure was recorded (a reloaded interrupted turn)", () => {
		expect(mountBubble(failed(undefined)).find("[data-test=report-failed-turn]").exists()).toBe(false);
	});

	it("still offers Retry", async () => {
		const w = mountBubble(failed(null));
		await w.find(".retry-btn").trigger("click");
		expect(w.emitted("retry")).toBeTruthy();
	});
});
