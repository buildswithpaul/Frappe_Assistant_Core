import { describe, it, expect } from "vitest";

import { planBlock } from "./buildPlan.testdata";
import { answerText, findQuestionGroups } from "./questionGroup";

function question(id, status = "pending", extra = {}) {
	return { id, type: "interaction", interactionType: "single_select", status, ...extra };
}

function approval(id, status = "pending") {
	return { id, type: "interaction", interactionType: "approval", status };
}

function tool(id) {
	return { id, type: "tool_call", tool_name: "ask_user" };
}

function text(id) {
	return { id, type: "text", content: "Some prose." };
}

const idsOf = (groups) => [...groups.values()].map((g) => g.map((b) => b.id));

describe("findQuestionGroups", () => {
	it("groups two waiting questions under the first one's id", () => {
		const groups = findQuestionGroups([tool("t1"), tool("t2"), question("q1"), question("q2")]);
		expect([...groups.keys()]).toEqual(["q1"]);
		expect(idsOf(groups)).toEqual([["q1", "q2"]]);
	});

	it("leaves a single question on its own", () => {
		expect(findQuestionGroups([tool("t1"), question("q1")]).size).toBe(0);
	});

	it("keeps questions together across the tool calls that asked them", () => {
		const groups = findQuestionGroups([tool("t1"), question("q1"), tool("t2"), question("q2")]);
		expect(idsOf(groups)).toEqual([["q1", "q2"]]);
	});

	it("never pulls an approval into a group", () => {
		const groups = findQuestionGroups([question("q1"), approval("a1"), question("q2"), question("q3")]);
		expect(idsOf(groups)).toEqual([["q2", "q3"]]);
	});

	it("never folds a build plan into a group", () => {
		const plan = { ...planBlock(), id: "p1" };
		expect(findQuestionGroups([question("q1"), plan]).size).toBe(0);
		expect(idsOf(findQuestionGroups([plan, question("q2"), question("q3")]))).toEqual([["q2", "q3"]]);
	});

	it("splits groups at prose", () => {
		const groups = findQuestionGroups([question("q1"), text("x"), question("q2")]);
		expect(groups.size).toBe(0);
	});

	it("groups answered questions from one pause as a record", () => {
		const groups = findQuestionGroups([question("q1", "answered"), question("q2", "answered")]);
		expect(idsOf(groups)).toEqual([["q1", "q2"]]);
	});

	it("does not mix waiting and answered questions", () => {
		const groups = findQuestionGroups([question("q1", "answered"), question("q2"), question("q3")]);
		expect(idsOf(groups)).toEqual([["q2", "q3"]]);
	});
});

describe("answerText", () => {
	it("joins a multi-choice answer", () => {
		expect(answerText(["Email", "Phone"])).toBe("Email, Phone");
	});

	it("words yes and no as the confirm buttons do", () => {
		expect(answerText("yes")).toBe("Yes");
		expect(answerText("no")).toBe("No");
	});

	it("returns a typed answer as it was typed", () => {
		expect(answerText("Last quarter")).toBe("Last quarter");
	});
});
