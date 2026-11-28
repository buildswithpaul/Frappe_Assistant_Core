import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RecordTable from "./RecordTable.vue";

const columns = [{ key: "name", label: "Name" }];
const rows = (n) => Array.from({ length: n }, (_, i) => ({ name: `R-${i + 1}` }));
const note = (view) => mount(RecordTable, { props: { view: { columns, hiddenColumns: 0, ...view } } }).find(".record-note").text();

describe("RecordTable note", () => {
	it("says how much of a list is shown", () => {
		expect(note({ rows: rows(1), total: 1 })).toBe("1 record.");
		expect(note({ rows: rows(3), total: 3 })).toBe("All 3 shown.");
		expect(note({ rows: rows(8), total: 8 })).toContain("First 5 of 8.");
		expect(note({ rows: rows(8), total: 244 })).toContain("8 of 244 returned.");
	});

	it("says a script step's rows are a preview of what the call returned", () => {
		// A step carries the first five rows; the call gave the script eight, of 244 that matched.
		expect(note({ rows: rows(5), returned: 8, total: 244 })).toBe("First 5 of 8. 244 matched.");
		expect(note({ rows: rows(5), returned: 8, total: 8 })).toBe("First 5 of 8.");
	});

	it("says when columns were left out", () => {
		expect(note({ rows: rows(2), total: 2, hiddenColumns: 3 })).toBe("All 2 shown. 3 more columns in Raw.");
	});
});
