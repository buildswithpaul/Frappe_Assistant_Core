import { describe, it, expect } from "vitest";
import { deriveArtifacts } from "@/utils/contextArtifacts.js";

describe("deriveArtifacts", () => {
	it("returns hasArtifacts=false and empty model for no blocks", () => {
		const r = deriveArtifacts([]);
		expect(r.hasArtifacts).toBe(false);
		expect(r.approval).toBe(null);
		expect(r.records).toEqual([]);
		expect(r.charts).toEqual([]);
		expect(r.documents).toEqual([]);
	});

	it("tolerates non-array input", () => {
		expect(deriveArtifacts(null).hasArtifacts).toBe(false);
		expect(deriveArtifacts(undefined).hasArtifacts).toBe(false);
	});

	it("derives a pending approval from an interaction block", () => {
		const r = deriveArtifacts([
			{
				type: "interaction",
				id: "i1",
				status: "pending",
				tool_name: "create_document",
				input: { doctype: "Sales Order", name: "Promantia", grand_total: "₹47,000.00" },
			},
		]);
		expect(r.approval).not.toBe(null);
		expect(r.approval.id).toBe("i1");
		expect(r.approval.title).toBe("Create Document");
		expect(r.approval.subtitle).toContain("Promantia");
		expect(r.approval.subtitle).toContain("₹47,000.00");
		expect(r.hasArtifacts).toBe(true);
	});

	it("ignores resolved interactions for the approval slot", () => {
		const r = deriveArtifacts([
			{ type: "interaction", id: "i1", status: "approved", tool_name: "create_document", input: {} },
		]);
		expect(r.approval).toBe(null);
	});

	it("labels read tools as sources and write tools as records", () => {
		const r = deriveArtifacts([
			{ type: "tool_call", id: "t1", status: "success", tool_name: "search_documents", input: { doctype: "Customer", name: "Promantia" } },
			{ type: "tool_call", id: "t2", status: "success", tool_name: "create_document", input: { doctype: "Sales Order", name: "SO-001" } },
		]);
		expect(r.records).toHaveLength(2);
		expect(r.records[0]).toMatchObject({ label: "Customer: Promantia", kind: "source" });
		expect(r.records[1]).toMatchObject({ label: "Sales Order: SO-001", kind: "record" });
	});

	it("drops compute-only tool_calls that reference no record", () => {
		// run_python_code / generate_report carry no doctype/name — they must not
		// appear as record chips (the rail is records & sources, not tools used).
		// They do still show up in the activity timeline, so hasArtifacts is true.
		const r = deriveArtifacts([
			{ type: "tool_call", id: "t1", status: "success", tool_name: "run_python_code", input: { code: "print(1)" } },
			{ type: "tool_call", id: "t2", status: "success", tool_name: "generate_report", input: { report_type: "cashflow" } },
		]);
		expect(r.records).toEqual([]);
		expect(r.activity).toHaveLength(2);
		expect(r.hasArtifacts).toBe(true);
	});

	it("keeps a record tool alongside compute-only tools, dropping only the latter", () => {
		const r = deriveArtifacts([
			{ type: "tool_call", id: "t1", status: "success", tool_name: "run_python_code", input: { code: "x=1" } },
			{ type: "tool_call", id: "t2", status: "success", tool_name: "create_document", input: { doctype: "Sales Order", name: "SO-9" } },
			{ type: "tool_call", id: "t3", status: "success", tool_name: "generate_report", input: {} },
		]);
		expect(r.records).toHaveLength(1);
		expect(r.records[0]).toMatchObject({ label: "Sales Order: SO-9", kind: "record" });
	});

	it("skips non-success tool_calls", () => {
		const r = deriveArtifacts([
			{ type: "tool_call", id: "t1", status: "running", tool_name: "create_document", input: { doctype: "Sales Order" } },
			{ type: "tool_call", id: "t2", status: "error", tool_name: "create_document", input: { doctype: "Sales Order" } },
		]);
		expect(r.records).toEqual([]);
	});

	it("merges RAG sources from a sources block", () => {
		const r = deriveArtifacts([
			{
				type: "sources",
				id: "s1",
				items: [
					{ n: 1, document_id: "d1", document_name: "Q3 Report", document_type: "File" },
					{ n: 2, document_id: "d2", document_name: "Pricing Policy" },
				],
			},
		]);
		expect(r.records).toHaveLength(2);
		expect(r.records[0].label).toBe("File: Q3 Report");
		expect(r.records[1].label).toBe("Pricing Policy");
		expect(r.records.every((rec) => rec.kind === "source")).toBe(true);
	});

	it("dedupes records by key", () => {
		const r = deriveArtifacts([
			{ type: "sources", id: "s1", items: [{ n: 1, document_id: "d1", document_name: "Doc" }] },
			{ type: "sources", id: "s2", items: [{ n: 1, document_id: "d1", document_name: "Doc" }] },
		]);
		expect(r.records).toHaveLength(1);
	});

	it("counts ```chart fences as generated charts", () => {
		const r = deriveArtifacts([
			{ type: "text", id: "x1", content: "Here it is:\n```chart\n{...}\n```\nand another\n```chart\n{...}\n```" },
		]);
		expect(r.charts).toHaveLength(2);
		expect(r.charts[0].label).toBe("Generated chart");
	});

	it("collects generated documents", () => {
		const r = deriveArtifacts([
			{
				type: "generated_documents",
				id: "g1",
				items: [{ file_url: "/files/a.pdf", file_name: "Invoice.pdf", file_size_display: "12 KB" }],
			},
		]);
		expect(r.documents).toHaveLength(1);
		expect(r.documents[0]).toMatchObject({ url: "/files/a.pdf", label: "Invoice.pdf", size: "12 KB" });
		expect(r.hasArtifacts).toBe(true);
	});

	it("plain Q&A (only text + thinking) has no artifacts", () => {
		const r = deriveArtifacts([
			{ type: "thinking", id: "th1", content: "..." },
			{ type: "text", id: "x1", content: "The answer is 42." },
		]);
		expect(r.hasArtifacts).toBe(false);
	});
});

describe("deriveArtifacts activity", () => {
	it("exposes timeline rows and counts them for hasArtifacts", () => {
		const out = deriveArtifacts([
			{ type: "tool_call", id: "t1", tool_name: "get_document", status: "running", input: { doctype: "HD Ticket" } },
		]);
		expect(out.activity).toHaveLength(1);
		expect(out.activity[0].status).toBe("running");
		expect(out.hasArtifacts).toBe(true); // rail appears during streaming
	});
	it("skips internal tools", () => {
		const out = deriveArtifacts([
			{ type: "tool_call", id: "t1", tool_name: "remember", isInternal: true, status: "success" },
		]);
		expect(out.activity).toHaveLength(0);
	});
});
