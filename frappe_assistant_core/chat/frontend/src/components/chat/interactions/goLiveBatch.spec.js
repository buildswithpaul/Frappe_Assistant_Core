import { describe, it, expect } from "vitest";
import { findGoLiveBatch, isGoLiveApproval } from "./goLiveBatch";

const approval = (id, reason = {}, extra = {}) => ({
	type: "interaction",
	id,
	interactionType: "approval",
	status: "pending",
	interrupts: [{ id: `i-${id}`, reason: { type: "approval", ...reason } }],
	...extra,
});
const goLive = (id) => approval(id, { risk: "customisation" });

describe("findGoLiveBatch", () => {
	it("batches two customisation approvals", () => {
		const blocks = [goLive("a"), { type: "text", id: "t" }, goLive("b")];
		expect(findGoLiveBatch(blocks).map((b) => b.id)).toEqual(["a", "b"]);
	});

	it("one alone is not a batch", () => {
		expect(findGoLiveBatch([goLive("a")])).toEqual([]);
	});

	it("keeps R2 and R3 out", () => {
		const blocks = [goLive("a"), goLive("b"), approval("r2", { level: "R2" }), approval("r3", { level: "R3" })];
		expect(findGoLiveBatch(blocks).map((b) => b.id)).toEqual(["a", "b"]);
		expect(isGoLiveApproval(blocks[2])).toBe(false);
		expect(isGoLiveApproval(blocks[3])).toBe(false);
	});

	it("keeps questions and decided cards out", () => {
		const question = { ...goLive("q"), interactionType: "question" };
		const done = { ...goLive("d"), status: "approved" };
		expect(findGoLiveBatch([goLive("a"), question, done])).toEqual([]);
		expect(findGoLiveBatch([goLive("a"), goLive("b"), question, done]).map((b) => b.id)).toEqual(["a", "b"]);
	});
});
