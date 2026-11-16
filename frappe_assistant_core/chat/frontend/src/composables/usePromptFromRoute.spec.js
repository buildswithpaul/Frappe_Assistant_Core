import { describe, it, expect, vi } from "vitest";
import { ref, reactive, nextTick } from "vue";
import { usePromptFromRoute, MAX_PROMPT_CHARS } from "./usePromptFromRoute";

function make(query, isNew = true) {
	const route = reactive({ path: "/chat", query });
	const router = { replace: vi.fn() };
	const pendingPrompt = ref("");
	const openPage = vi.fn();
	usePromptFromRoute({ route, router, pendingPrompt, isNewChat: () => isNew, openPage });
	return { route, router, pendingPrompt, openPage };
}

describe("usePromptFromRoute", () => {
	it("opens the named page beside a new chat whose prompt it fills, and strips both params", () => {
		// The Desk Pages gallery links Edit with FACO and Share as /copilot/chat?prompt=…&page=<name>.
		const { router, openPage, pendingPrompt } = make({ prompt: "Change my page", page: "payment-tracker-3fa9c1" });
		expect(pendingPrompt.value).toBe("Change my page");
		expect(openPage).toHaveBeenCalledWith("payment-tracker-3fa9c1");
		const query = router.replace.mock.calls[0][0].query;
		expect(query.prompt).toBeUndefined();
		expect(query.page).toBeUndefined();
		expect("page" in query).toBe(true);
	});
	it("opens no page for an existing chat, and still strips both params", () => {
		const { router, openPage } = make({ prompt: "hi", page: "p" }, false);
		expect(openPage).not.toHaveBeenCalled();
		const query = router.replace.mock.calls[0][0].query;
		expect([query.prompt, query.page]).toEqual([undefined, undefined]);
	});

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
