import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { get: vi.fn(), chat: { cancelStream: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

// AR sends a pause deadline as an aware UTC ISO string with microseconds
// (spec §8.4): "2026-09-23T10:30:00.123456+00:00". The local expiry timer
// must arm from the instant that string names, whatever zone this machine is in.
const NOW = Date.UTC(2026, 8, 23, 10, 0, 0);
const THIRTY_MINUTES = 30 * 60 * 1000;

function pendingApproval() {
	return {
		type: "interaction",
		id: "tool-1",
		status: "pending",
		interactionType: "approval",
		interrupts: [{ id: "int-1" }],
	};
}

describe("approval expiry armed from get_pending_interrupt", () => {
	let store;

	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(NOW);
		setActivePinia(createPinia());
		store = useChatStore();
		store.currentSessionId = "s1";
		store.messages = [
			{
				role: "assistant",
				timestamp: new Date(NOW - 60 * 60 * 1000).toISOString(),
				blocks: [pendingApproval()],
			},
		];
		api.get.mockReset();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	async function hydrateWith(expiresAt) {
		api.get.mockResolvedValue({
			pending: true,
			session_id: "s1",
			expires_at: expiresAt,
			event: {
				tool_id: "tool-1",
				tool_name: "create_document",
				input: {},
				interrupts: [{ id: "int-1" }],
			},
		});
		await store.hydratePendingInterrupt("s1");
	}

	const cardStatus = () => store.messages[0].blocks[0].status;

	it("expires the card at the instant AR's UTC string names", async () => {
		await hydrateWith("2026-09-23T10:30:00.123456+00:00");

		vi.advanceTimersByTime(THIRTY_MINUTES);
		expect(cardStatus()).toBe("pending");
		vi.advanceTimersByTime(200);
		expect(cardStatus()).toBe("expired");
	});

	it("reads any offset, not the machine's zone", async () => {
		await hydrateWith("2026-09-23T16:00:00+05:30");

		vi.advanceTimersByTime(THIRTY_MINUTES - 1);
		expect(cardStatus()).toBe("pending");
		vi.advanceTimersByTime(1);
		expect(cardStatus()).toBe("expired");
	});

	it("does not arm a deadline that has already passed", async () => {
		await hydrateWith("2026-09-23T09:59:00+00:00");

		vi.advanceTimersByTime(24 * 60 * 60 * 1000);
		expect(cardStatus()).toBe("pending");
	});
});
