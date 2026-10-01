import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

import ApprovalCard from "@/components/chat/interactions/ApprovalCard.vue";

// document_action only uses "reason" for cancel. The LLM often still sends it (empty)
// on submit and amend, which showed up as a "Reason —" row on the approval card.
function rows(tool_name, input) {
	const wrapper = mount(ApprovalCard, { props: { block: { id: "b1", tool_name, input } } });
	const keys = wrapper.findAll(".field-key").map((n) => n.text());
	const values = wrapper.findAll(".field-value").map((n) => n.text());
	return Object.fromEntries(keys.map((k, i) => [k, values[i]]));
}

const DOC = { doctype: "Sales Invoice", name: "ACC-SINV-2026-00007" };

describe("ApprovalCard — document_action Reason row", () => {
	it("hides Reason on submit", () => {
		const shown = rows("document_action", { ...DOC, action: "submit", reason: "" });
		expect(shown).not.toHaveProperty("Reason");
		expect(shown).toHaveProperty("Action", "submit");
	});

	it("hides Reason when submit is the default (no action given)", () => {
		expect(rows("document_action", { ...DOC, reason: null })).not.toHaveProperty("Reason");
	});

	it("hides Reason on amend, even when one is sent", () => {
		expect(rows("document_action", { ...DOC, action: "amend", reason: "leftover" })).not.toHaveProperty(
			"Reason"
		);
	});

	it("shows Reason on cancel", () => {
		const shown = rows("document_action", { ...DOC, action: "cancel", reason: "Billed twice" });
		expect(shown).toHaveProperty("Reason", "Billed twice");
	});

	it("hides an empty or blank Reason on cancel", () => {
		for (const reason of ["", "   ", null]) {
			expect(rows("document_action", { ...DOC, action: "cancel", reason })).not.toHaveProperty("Reason");
		}
	});

	it("leaves other tools' rows alone", () => {
		const shown = rows("update_document", { ...DOC, reason: "" });
		expect(shown).toHaveProperty("Reason", "—");
	});
});
