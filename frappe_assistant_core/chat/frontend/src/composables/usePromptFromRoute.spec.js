import { describe, it, expect, vi } from "vitest";
import { ref, reactive, nextTick } from "vue";
import { usePromptFromRoute, MAX_PROMPT_CHARS } from "./usePromptFromRoute";

function make(query, isNew = true) {
	const route = reactive({ path: "/chat", query });
	const router = { replace: vi.fn() };
	const pendingPrompt = ref("");
	usePromptFromRoute({ route, router, pendingPrompt, isNewChat: () => isNew });
	return { route, router, pendingPrompt };
}

describe("usePromptFromRoute", () => {
	it("prefills a new chat and strips the query", () => {
		const { router, pendingPrompt } = make({ prompt: "Show overdue invoices" });
		expect(pendingPrompt.value).toBe("Show overdue invoices");
		expect(router.replace).toHaveBeenCalledWith(
			expect.objectContaining({
				path: "/chat",
				query: { prompt: undefined },
				hash: undefined,
			})
		);
	});
	it("truncates long prompts and keeps markup as plain text", () => {
		const { pendingPrompt } = make({ prompt: "<b>x</b>" + "a".repeat(3000) });
		expect(pendingPrompt.value.length).toBe(MAX_PROMPT_CHARS);
		expect(pendingPrompt.value.startsWith("<b>x</b>")).toBe(true);
	});
	it("ignores existing conversations and empty or array values", () => {
		expect(make({ prompt: "hi" }, false).pendingPrompt.value).toBe("");
		expect(make({ prompt: "" }).pendingPrompt.value).toBe("");
		expect(make({ prompt: ["a", "b"] }).pendingPrompt.value).toBe("");
	});
	it("strips query param even when rejecting the prompt (existing chat)", () => {
		const { router } = make({ prompt: "hi" }, false);
		expect(router.replace).toHaveBeenCalledWith(
			expect.objectContaining({ query: { prompt: undefined } })
		);
	});
	it("strips query param even when rejecting empty prompt", () => {
		const { router } = make({ prompt: "" });
		expect(router.replace).toHaveBeenCalledWith(
			expect.objectContaining({ query: { prompt: undefined } })
		);
	});
	it("does not strip when there is no prompt param", () => {
		const { router } = make({});
		expect(router.replace).not.toHaveBeenCalled();
	});
	it("reacts to a later navigation", async () => {
		const { route, pendingPrompt } = make({});
		route.query = { prompt: "later" };
		await nextTick();
		expect(pendingPrompt.value).toBe("later");
	});
});
