import { describe, it, expect } from "vitest";

import { titleWord } from "./toolLabel";
import { formatToolName } from "@/components/chat/processingSummary";

describe("titleWord", () => {
	it("capitalises words and keeps acronyms upper case", () => {
		expect(["crm", "pdf", "sql", "mcp", "api", "url", "lead"].map(titleWord)).toEqual([
			"CRM", "PDF", "SQL", "MCP", "API", "URL", "Lead",
		]);
	});

	it("is what the processing summary uses", () => {
		expect(formatToolName("get_crm_activity")).toBe("Get CRM Activity");
	});
});
