import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createErrorState, ERROR_AUTO_DISMISS_MS } from "./errorState";

describe("createErrorState", () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it("auto-dismisses the error after the timeout", () => {
		const s = createErrorState();
		s.setError("The AI is temporarily unavailable.", "LLM_UNAVAILABLE");
		expect(s.error.value).toBe("The AI is temporarily unavailable.");
		expect(s.errorCode.value).toBe("LLM_UNAVAILABLE");

		vi.advanceTimersByTime(ERROR_AUTO_DISMISS_MS - 1);
		expect(s.error.value).not.toBeNull();

		vi.advanceTimersByTime(1);
		expect(s.error.value).toBeNull();
		expect(s.errorCode.value).toBeNull();
	});

	it("a newer error resets the timer instead of inheriting the old one", () => {
		const s = createErrorState();
		s.setError("first");
		vi.advanceTimersByTime(ERROR_AUTO_DISMISS_MS - 1000);
		s.setError("second");

		vi.advanceTimersByTime(1000);
		expect(s.error.value).toBe("second"); // old timer must not fire

		vi.advanceTimersByTime(ERROR_AUTO_DISMISS_MS - 1000);
		expect(s.error.value).toBeNull();
	});

	it("manual clearError cancels the pending timer", () => {
		const s = createErrorState();
		s.setError("oops");
		s.clearError();
		expect(s.error.value).toBeNull();

		s.setError("again");
		vi.advanceTimersByTime(1);
		expect(s.error.value).toBe("again"); // cancelled timer must not clear the new error
	});

	it("respects a custom autoDismissMs", () => {
		const s = createErrorState({ autoDismissMs: 100 });
		s.setError("quick");
		vi.advanceTimersByTime(100);
		expect(s.error.value).toBeNull();
	});
});
