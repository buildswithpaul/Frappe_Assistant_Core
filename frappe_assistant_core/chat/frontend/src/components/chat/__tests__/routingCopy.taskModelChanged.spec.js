import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { taskModelChangedText } from "../routingCopy.js";

vi.mock("@/api/client", () => ({ api: { chat: {} } }));
vi.mock("frappe-ui", () => ({ call: vi.fn() }));
import { useChatStore } from "@/stores/chatStore";

const REASONS = ["unavailable", "rate_limited", "plan", "health", "tier"];

describe("task_model_changed copy", () => {
	it("has its own plain sentence for every reason", () => {
		const lines = REASONS.map(taskModelChangedText);
		expect(new Set(lines).size).toBe(REASONS.length);
		for (const line of lines) expect(line).toMatch(/^Switched to a /);
	});

	it("says a stronger model for a tier change and a different one otherwise", () => {
		expect(taskModelChangedText("tier")).toBe("Switched to a stronger model for this step");
		expect(taskModelChangedText("unavailable")).toBe(
			"Switched to a different model for this task because the previous one isn't available right now"
		);
	});

	it("falls back to a generic sentence for an unknown or missing reason", () => {
		for (const reason of ["brand_new", "", null, undefined, 42]) {
			expect(taskModelChangedText(reason)).toBe("Switched to a different model for this task");
		}
	});

	it("never shows model ids or field names", () => {
		for (const reason of [...REASONS, "x"]) {
			expect(taskModelChangedText(reason)).not.toMatch(/_|gpt|claude/i);
		}
	});
});

describe("routing_notice handling", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		store.messages.push({ id: "a1", role: "assistant", content: "", isStreaming: true, blocks: [] });
	});

	it("records a task_model_changed notice on the answering message", () => {
		store.handleRoutingNotice({ code: "task_model_changed", from: "a", to: "b", reason: "tier" });
		expect(store.messages.at(-1).taskModelChange).toEqual({ reason: "tier", from: "a", to: "b" });
	});

	it("ignores other codes and malformed payloads", () => {
		store.handleRoutingNotice({ code: "downgraded_for_credits" });
		store.handleRoutingNotice(null);
		store.handleRoutingNotice({});
		expect(store.messages.at(-1).taskModelChange).toBeUndefined();
	});

	it("keeps a notice with an unknown reason renderable", () => {
		store.handleRoutingNotice({ code: "task_model_changed", reason: "brand_new" });
		expect(taskModelChangedText(store.messages.at(-1).taskModelChange.reason)).toMatch(/^Switched/);
	});
});
