import { describe, it, expect } from "vitest";
import { deriveHeading, deriveIndexEntries, completedExchangeCount } from "./indexEntries.js";

const T = "2026-07-20T09:14:00";
const user = (content, extra = {}) => ({ role: "user", content, timestamp: T, ...extra });
const assistant = (blocks = [], extra = {}) => ({
	role: "assistant",
	content: "",
	blocks,
	message_id: extra.message_id ?? "m-1",
	isStreaming: false,
	...extra,
});
const tool = (status = "success", isInternal = false) => ({
	type: "tool_call", id: "t1", tool_name: "get_document", isInternal, status,
});

describe("deriveHeading", () => {
	it("strips greeting filler and takes the first clause", () => {
		expect(deriveHeading("Hey, can you show overdue audits? And also RAMS.", 1)).toBe(
			"show overdue audits"
		);
	});
	it("truncates on a word boundary at ~48 chars", () => {
		const h = deriveHeading(
			"List every single health and safety audit record for all of our construction sites",
			1
		);
		expect(h.length).toBeLessThanOrEqual(49);
		expect(h.endsWith("…")).toBe(true);
		expect(h).not.toMatch(/\s…$/);
	});
	it("falls back to Exchange N for empty prompts", () => {
		expect(deriveHeading("   ", 4)).toBe("Exchange 4");
	});
});

describe("deriveIndexEntries", () => {
	it("builds one exchange per user turn with markers from the assistant blocks", () => {
		const msgs = [
			user("Show overdue audits"),
			assistant([tool(), tool("error"), tool("success", true),
				{ type: "text", id: "x", content: "a\n```chart\n{}\n```" },
				{ type: "generated_documents", id: "g", items: [{}] },
			]),
		];
		const [e] = deriveIndexEntries(msgs);
		expect(e).toMatchObject({
			kind: "exchange", index: 0, messageId: "m-1",
			toolCount: 2, hasChart: true, hasFiles: true,
			approval: null, streaming: false, completed: true,
		});
		expect(e.time).toMatch(/\d{1,2}:\d{2}/);
	});
	it("flags pending and resolved approvals", () => {
		const pending = deriveIndexEntries([
			user("Create tickets"),
			assistant([{ type: "interaction", id: "i", status: "pending" }]),
		]);
		expect(pending[0].approval).toBe("pending");
		const resolved = deriveIndexEntries([
			user("Create tickets"),
			assistant([{ type: "interaction", id: "i", status: "answered" }]),
		]);
		expect(resolved[0].approval).toBe("resolved");
	});
	it("mirrors divider rows and marks streaming exchanges incomplete", () => {
		const msgs = [
			user("One"), assistant(),
			{ role: "divider", content: "Context summarized" },
			user("Two"), assistant([], { isStreaming: true, message_id: null }),
		];
		const entries = deriveIndexEntries(msgs);
		expect(entries.map((e) => e.kind)).toEqual(["exchange", "divider", "exchange"]);
		expect(entries[2]).toMatchObject({ streaming: true, completed: false, index: 3 });
		expect(completedExchangeCount(entries)).toBe(1);
	});
	it("merges a second assistant message into the same exchange", () => {
		const msgs = [user("One"), assistant([tool()]), assistant([tool()], { message_id: "m-2" })];
		const entries = deriveIndexEntries(msgs);
		expect(entries).toHaveLength(1);
		expect(entries[0].toolCount).toBe(2);
	});
	it("tolerates junk", () => {
		expect(deriveIndexEntries(null)).toEqual([]);
		expect(deriveIndexEntries([assistant()])).toHaveLength(1); // orphan assistant → synthetic exchange
	});
});
