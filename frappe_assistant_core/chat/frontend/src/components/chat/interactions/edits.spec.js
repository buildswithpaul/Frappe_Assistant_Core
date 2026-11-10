import { describe, expect, it } from "vitest";

import { applyEdits, editedFields } from "./edits";

const edit = (field, find, replace) => ({ field, find, replace });

describe("applyEdits", () => {
	it("replaces a single match", () => {
		expect(applyEdits({ html: "a<b>c" }, [edit("html", "<b>", "<i>")]).values).toEqual({ html: "a<i>c" });
	});

	it("fails on zero or two matches and names the field", () => {
		for (const stored of ["x x", "z"]) {
			const result = applyEdits({ html: stored }, [edit("html", "x", "y")]);
			expect(result.error).toBeTruthy();
			expect(result.failedFields).toEqual(["html"]);
			expect(result.values).toEqual({});
		}
	});

	it("counts matches without overlap, as the server does", () => {
		expect(applyEdits({ script: "aaa" }, [edit("script", "aa", "b")]).values).toEqual({ script: "ba" });
	});

	it("applies edits in order, each seeing the one before", () => {
		const result = applyEdits({ script: "one" }, [edit("script", "one", "two"), edit("script", "two", "three")]);
		expect(result.values).toEqual({ script: "three" });
		expect(applyEdits({ script: "one" }, [edit("script", "two", "x"), edit("script", "one", "two")]).error).toBeTruthy();
	});

	it("treats $& and regex characters literally", () => {
		const result = applyEdits({ script: "f('.*(')" }, [edit("script", ".*(", "$&\\1")]);
		expect(result.values.script).toBe("f('$&\\1')");
	});

	it("matches LF find against CRLF code and keeps the CRLF endings", () => {
		const result = applyEdits({ script: "a\r\nb\r\nc" }, [edit("script", "b\nc", "B\nC")]);
		expect(result.values.script).toBe("a\r\nB\r\nC");
	});

	it("leaves LF code alone", () => {
		expect(applyEdits({ script: "a\nb" }, [edit("script", "a\nb", "c\nd")]).values.script).toBe("c\nd");
	});

	it("reads a missing stored value as empty, so a find on it fails", () => {
		expect(applyEdits({}, [edit("style", "x", "y")]).failedFields).toEqual(["style"]);
	});

	it("rejects an empty find", () => {
		expect(applyEdits({ html: "a" }, [edit("html", "", "y")]).failedFields).toEqual(["html"]);
	});

	it("keeps the fields that applied when another fails", () => {
		const result = applyEdits({ html: "a", script: "b" }, [edit("html", "a", "A"), edit("script", "zz", "y")]);
		expect(result.values).toEqual({ html: "A" });
		expect(result.failedFields).toEqual(["script"]);
	});

	it("never throws on malformed edits", () => {
		const result = applyEdits({ html: "a" }, [null, { field: "html" }]);
		expect(result.error).toBeTruthy();
	});
});

describe("editedFields", () => {
	it("lists each edited field once", () => {
		expect(editedFields({ edits: [edit("html", "a", "b"), edit("script", "a", "b"), edit("html", "c", "d")] })).toEqual([
			"html",
			"script",
		]);
	});

	it("is empty without edits or for malformed ones", () => {
		expect(editedFields({ data: {} })).toEqual([]);
		expect(editedFields({ edits: "x" })).toEqual([]);
		expect(editedFields({ edits: [null, { field: 3 }] })).toEqual([]);
	});
});
