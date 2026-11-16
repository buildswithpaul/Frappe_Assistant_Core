import { describe, expect, it } from "vitest";
import { conversationImportSessions, startedImports } from "./importSessions";

const call = (tool_name, extra = {}) => ({ id: tool_name, type: "tool_call", status: "success", tool_name, ...extra });

describe("the import sessions a conversation worked on (#34416)", () => {
	it("finds the session a start_import started, once", () => {
		const blocks = [
			call("start_import", { input: { session: "IMP-1" }, result: [{ text: '{"success": true, "session": "IMP-1"}' }] }),
			call("start_import", { input: { session: "IMP-1" }, result: { success: true, session: "IMP-1" } }),
		];
		expect(startedImports(blocks)).toEqual(["IMP-1"]);
	});

	it("leaves out a start_import that failed, is waiting or ran another tool", () => {
		const blocks = [
			call("start_import", { input: { session: "IMP-2" }, result: { success: false, error: "no" } }),
			call("start_import", { status: "pending", input: { session: "IMP-3" } }),
			call("dry_run_import", { input: { session: "IMP-4" }, result: { success: true } }),
		];
		expect(startedImports(blocks)).toEqual([]);
	});

	it("lists every session the conversation's tools named, in order", () => {
		const messages = [
			{ blocks: [call("start_import_session", { result: { success: true, session_id: "IMP-5" } })] },
			{ blocks: [call("dry_run_import", { input: { session: "IMP-5" } }), call("set_column_mapping", { input: { session: "IMP-6" } })] },
			{ blocks: [{ type: "text", content: "done" }, call("list_documents", { input: { doctype: "Customer" } })] },
		];
		expect(conversationImportSessions(messages)).toEqual(["IMP-5", "IMP-6"]);
	});
});
