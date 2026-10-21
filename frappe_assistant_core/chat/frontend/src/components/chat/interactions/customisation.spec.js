import { describe, it, expect } from "vitest";
import { writeConsequence } from "./customisation";

describe("writeConsequence", () => {
	it("states the write effect for record tools", () => {
		expect(writeConsequence("create_document", {})).toBe("This will write a new record to your ERP");
		expect(writeConsequence("update_document", {})).toBe("This will modify an existing record in your ERP");
		expect(writeConsequence("delete_document", {})).toBe("This will permanently delete a record from your ERP");
	});

	it("follows the requested document action", () => {
		expect(writeConsequence("document_action", { action: "cancel" })).toContain("cancel a submitted record");
		expect(writeConsequence("document_action", {})).toContain("submit a record");
		expect(writeConsequence("document_action", { action: "weird" })).toContain("submit, cancel or amend");
	});

	it("says nothing for tools that may not write", () => {
		expect(writeConsequence("ask_user", {})).toBe("");
	});
});
