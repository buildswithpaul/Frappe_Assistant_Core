import { describe, expect, it, vi } from "vitest";

import { restartFailure, sendWithRestartRetry } from "./restartRetry";

// A worker that is restarting answers the send with {status: "retry"} and saves nothing (#34895).
const RETRY = { status: "retry", retry_after: 2, message: "Server restarting, retrying…" };
const PROCESSING = { status: "processing", session_id: "s1" };

describe("sendWithRestartRetry", () => {
	it("re-sends once after retry_after and shows the restarting status", async () => {
		const send = vi.fn().mockResolvedValueOnce(RETRY).mockResolvedValueOnce(PROCESSING);
		const order = [];
		const onRetrying = vi.fn(() => order.push("retrying"));
		const wait = vi.fn(async (ms) => order.push(`wait ${ms}`));

		const ack = await sendWithRestartRetry(send, { wait, onRetrying });

		expect(ack).toEqual(PROCESSING);
		expect(send).toHaveBeenCalledTimes(2);
		expect(order).toEqual(["retrying", "wait 2000"]);
	});

	it("a second retry surfaces SERVER_RESTARTING", async () => {
		const send = vi.fn().mockResolvedValue(RETRY);
		const wait = vi.fn(async () => {});

		const ack = await sendWithRestartRetry(send, { wait, onRetrying: () => {} });

		expect(send).toHaveBeenCalledTimes(2);
		expect(restartFailure(ack)).toEqual({
			message: "The server is restarting. Try again in a moment.",
			code: "SERVER_RESTARTING",
		});
	});

	it("passes a processing ack straight through", async () => {
		const send = vi.fn().mockResolvedValue(PROCESSING);
		const wait = vi.fn();
		const onRetrying = vi.fn();

		expect(await sendWithRestartRetry(send, { wait, onRetrying })).toEqual(PROCESSING);
		expect(send).toHaveBeenCalledTimes(1);
		expect(wait).not.toHaveBeenCalled();
		expect(onRetrying).not.toHaveBeenCalled();
		expect(restartFailure(PROCESSING)).toBeNull();
	});
});
