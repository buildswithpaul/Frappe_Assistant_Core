import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({ api: { imports: { importCard: vi.fn() } } }));

import { api } from "@/api/client";
import ImportApprovalSummary from "./ImportApprovalSummary.vue";
import { approvalHeadline } from "./approvalHeadline";

describe("the import approval card (#34415)", () => {
	it("shows the file, new records, rows left out, submitting and the mapping", async () => {
		api.imports.importCard.mockResolvedValue({
			file_name: "invoices.csv",
			doctype: "Sales Invoice",
			update: false,
			rows: 40,
			left_out: 2,
			submit: true,
			mapping: "Customer → Customer, Amount → Outstanding Amount",
		});
		const w = mount(ImportApprovalSummary, { props: { input: { session: "IMP-1", rows: 40 } } });
		await flushPromises();
		const text = w.text();
		expect(text).toContain("invoices.csv");
		expect(text).toContain("New Sales Invoice records");
		expect(text).toContain("40 rows");
		expect(text).toContain("Left out");
		expect(text).toContain("Will be submitted");
		expect(text).toContain("Amount → Outstanding Amount");
	});

	it("shows an update's old and new values on the card itself (PR #392, F6)", async () => {
		api.imports.importCard.mockResolvedValue({
			file_name: "customers.csv",
			doctype: "Customer",
			update: true,
			rows: 7,
			left_out: 0,
			submit: false,
			mapping: "Mobile → Mobile No",
			changes: {
				records: 7,
				fields: 9,
				by_field: { "Mobile No": 7, Territory: 2 },
				samples: [
					{ record: "CUST-0001", changes: [{ label: "Mobile No", old: "98450 11111", new: "98450 22222" }, { label: "Territory", old: "", new: "Karnataka" }] },
				],
			},
		});
		const w = mount(ImportApprovalSummary, { props: { input: { session: "IMP-2", rows: 7 } } });
		await flushPromises();
		const text = w.text();
		expect(text).toContain("9 changes in 7 records");
		expect(text).toContain("CUST-0001");
		expect(text).toContain("98450 11111 → 98450 22222");
		expect(text).toContain("(empty) → Karnataka");
		expect(w.find(".ia-changes p").exists()).toBe(false); // a <p> in a turn is restyled (cf8e5fa8)
	});

	it("shows no changes for new records", async () => {
		api.imports.importCard.mockResolvedValue({ file_name: "c.csv", doctype: "Customer", update: false, rows: 3, changes: null });
		const w = mount(ImportApprovalSummary, { props: { input: { session: "IMP-3" } } });
		await flushPromises();
		expect(w.find(".ia-changes").exists()).toBe(false);
	});

	it("names the import in the card's title", () => {
		const block = { tool_name: "start_import", input: { doctype: "Customer", rows: 250, file_name: "customers.csv", import_type: "Insert New Records" } };
		expect(approvalHeadline(block)).toBe("Import 250 rows of customers.csv as new Customer records");
		const update = { tool_name: "start_import", input: { ...block.input, import_type: "Update Existing Records" } };
		expect(approvalHeadline(update)).toBe("Update 250 Customer records from customers.csv");
	});
});
