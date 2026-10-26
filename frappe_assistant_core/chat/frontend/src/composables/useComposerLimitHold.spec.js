import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises, enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h } from "vue";

const getMyCreditStatus = vi.fn();
vi.mock("@/api/client", () => ({ api: { users: { getMyCreditStatus: (...a) => getMyCreditStatus(...a) } } }));

import { useComposerLimitHold } from "./useComposerLimitHold";

enableAutoUnmount(afterEach);

const AT_LIMIT = { has_individual_limit: true, monthly_credit_limit: 100, credits_used_this_month: 120 };
const NO_LIMIT = { has_individual_limit: false, monthly_credit_limit: 0, credits_used_this_month: 120 };

function mountHold(handlers) {
	let hold;
	const Probe = defineComponent({
		setup() {
			hold = useComposerLimitHold(handlers);
			return () => h("i");
		},
	});
	mount(Probe);
	return () => hold;
}

describe("useComposerLimitHold", () => {
	let send;
	let continueTurn;

	beforeEach(() => {
		setActivePinia(createPinia());
		getMyCreditStatus.mockReset();
		send = vi.fn();
		continueTurn = vi.fn();
	});

	it("holds a send and a continue at the personal limit, since AR would refuse both", async () => {
		getMyCreditStatus.mockResolvedValue(AT_LIMIT);
		const hold = mountHold({ send, continueTurn });
		await flushPromises();

		expect(hold().held.value).toBe(true);
		expect(hold().send({ message: "Show my tasks", files: [] })).toBe(false);
		expect(hold().continueTurn("msg-1")).toBe(false);
		expect(send).not.toHaveBeenCalled();
		expect(continueTurn).not.toHaveBeenCalled();
	});

	it("passes a send and a continue through when no limit stops them", async () => {
		getMyCreditStatus.mockResolvedValue(NO_LIMIT);
		const hold = mountHold({ send, continueTurn });
		await flushPromises();

		hold().send({ message: "Show my tasks", files: [] });
		hold().continueTurn("msg-1");
		expect(send).toHaveBeenCalledWith({ message: "Show my tasks", files: [] });
		expect(continueTurn).toHaveBeenCalledWith("msg-1");
	});

	it("lifts the hold once the limit changes, read again when the window regains focus", async () => {
		getMyCreditStatus.mockResolvedValue(AT_LIMIT);
		const hold = mountHold({ send, continueTurn });
		await flushPromises();
		expect(hold().held.value).toBe(true);

		getMyCreditStatus.mockResolvedValue(NO_LIMIT);
		window.dispatchEvent(new Event("focus"));
		await flushPromises();

		expect(hold().held.value).toBe(false);
		hold().send({ message: "Now it goes", files: [] });
		expect(send).toHaveBeenCalledTimes(1);
	});

	it("holds only what it is given: an approval card's decision is never wrapped", async () => {
		// A decision resumes a paused turn; if AR refuses it, the user_limit_reached notice explains why.
		getMyCreditStatus.mockResolvedValue(AT_LIMIT);
		const hold = mountHold({ send, continueTurn });
		await flushPromises();
		expect(Object.keys(hold()).sort()).toEqual(["block", "continueTurn", "held", "recheck", "send"]);
	});
});
