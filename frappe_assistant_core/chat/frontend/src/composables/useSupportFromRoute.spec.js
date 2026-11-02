import { describe, it, expect, vi } from "vitest";
import { reactive, nextTick } from "vue";
import { useSupportFromRoute } from "./useSupportFromRoute";

function make(query) {
	const route = reactive({ path: "/chat", query });
	const router = { replace: vi.fn() };
	const supportStore = { open: vi.fn() };
	useSupportFromRoute({ route, router, supportStore });
	return { route, router, supportStore };
}

describe("useSupportFromRoute", () => {
	it("opens Give feedback for ?feedback=1 and strips the query", () => {
		const { router, supportStore } = make({ feedback: "1" });
		expect(supportStore.open).toHaveBeenCalledWith({ mode: "feedback" });
		expect(router.replace).toHaveBeenCalledWith(
			expect.objectContaining({ path: "/chat", query: { feedback: undefined }, hash: undefined })
		);
	});
	it("opens Report an issue for ?feedback=issue", () => {
		expect(make({ feedback: "issue" }).supportStore.open).toHaveBeenCalledWith({ mode: "issue" });
	});
	it("ignores any other value but still strips it", () => {
		for (const feedback of ["", "yes", ["1", "1"]]) {
			const { router, supportStore } = make({ feedback });
			expect(supportStore.open).not.toHaveBeenCalled();
			expect(router.replace).toHaveBeenCalledWith(expect.objectContaining({ query: { feedback: undefined } }));
		}
	});
	it("keeps the other query params", () => {
		const { router } = make({ feedback: "1", prompt: "hi" });
		expect(router.replace).toHaveBeenCalledWith(expect.objectContaining({ query: { prompt: "hi", feedback: undefined } }));
	});
	it("does nothing without the param", () => {
		const { router, supportStore } = make({});
		expect(supportStore.open).not.toHaveBeenCalled();
		expect(router.replace).not.toHaveBeenCalled();
	});
	it("reacts to a later navigation, as a Spotlight button makes from an open chat", async () => {
		const { route, supportStore } = make({});
		route.query = { feedback: "1" };
		await nextTick();
		expect(supportStore.open).toHaveBeenCalledWith({ mode: "feedback" });
	});
});
