import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		feedback: {
			pulseState: vi.fn().mockResolvedValue({ due: true }),
			markPulseShown: vi.fn().mockResolvedValue({ ok: true }),
			dismissPulse: vi.fn().mockResolvedValue({ ok: true }),
			submitPulse: vi.fn().mockResolvedValue({ feedback_id: "f" }),
		},
	},
}));

import { api } from "@/api/client";
import { usePulseStore } from "@/stores/pulseStore";
import PulseCard from "./PulseCard.vue";

describe("PulseCard", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		// production: maybeShow() flips visible once pulse_state says due.
		usePulseStore().visible = true;
	});

	it("shows the copy and five rating buttons", () => {
		const w = mount(PulseCard);
		expect(w.text()).toContain("How is FACO doing for you?");
		expect(w.findAll("[data-rating]")).toHaveLength(5);
	});

	it("marks shown only once the card is mounted", () => {
		expect(api.feedback.markPulseShown).not.toHaveBeenCalled();
		const w = mount(PulseCard);
		expect(api.feedback.markPulseShown).toHaveBeenCalledTimes(1);
		w.unmount();
	});

	it("remounting while visible marks shown only once", () => {
		mount(PulseCard).unmount();
		mount(PulseCard).unmount();
		expect(api.feedback.markPulseShown).toHaveBeenCalledTimes(1);
	});

	it("dismiss calls dismiss_pulse", async () => {
		const w = mount(PulseCard);
		await w.find("[data-test=pulse-dismiss]").trigger("click");
		expect(api.feedback.dismissPulse).toHaveBeenCalledTimes(1);
	});

	it("Send posts rating, comment and contact_ok, then thanks", async () => {
		const w = mount(PulseCard);
		await w.find("[data-rating='4']").trigger("click");
		await w.find("[data-test=pulse-comment]").setValue("  more charts ");
		await w.find("[data-test=pulse-contact]").setValue(true);
		await w.find("[data-test=pulse-send]").trigger("click");
		await flushPromises();
		expect(api.feedback.submitPulse).toHaveBeenCalledWith({ rating: 4, comment: "more charts", contactOk: true });
		expect(w.text()).toContain("Thank you, that helps.");
	});

	it("a failed Send shows an inline error and keeps the card", async () => {
		api.feedback.submitPulse.mockRejectedValueOnce(new Error("boom"));
		const w = mount(PulseCard);
		await w.find("[data-rating='2']").trigger("click");
		await w.find("[data-test=pulse-send]").trigger("click");
		await flushPromises();
		expect(w.find("[data-test=pulse-error]").text()).toBe("Couldn't send. Please try again.");
		expect(w.find("[data-test=pulse-send]").exists()).toBe(true);
	});
});
