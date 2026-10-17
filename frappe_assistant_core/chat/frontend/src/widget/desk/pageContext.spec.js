import { describe, it, expect, afterEach } from "vitest";
import { detectContext } from "./pageContext.js";

const formPage = (doctype, name) => ({ frm: { doctype, docname: name, doc: { name }, is_new: () => false } });
const deskOn = (route, formview) => (window.frappe = { get_route: () => route, views: { formview } });

describe("detectContext on a form", () => {
	afterEach(() => delete window.frappe);

	it("names the record the form shows", () => {
		deskOn(["Form", "Sales Invoice", "SINV-0002"], { "Sales Invoice": formPage("Sales Invoice", "SINV-0002") });
		expect(detectContext()).toMatchObject({ type: "Form", doctype: "Sales Invoice", name: "SINV-0002" });
	});

	it("does not report the previous record while Desk is still loading the one being opened", () => {
		// The form page is reused per doctype and keeps the last record's doc until form-refresh.
		deskOn(["Form", "Sales Invoice", "SINV-0002"], { "Sales Invoice": formPage("Sales Invoice", "SINV-0001") });
		const context = detectContext();
		expect(context).toMatchObject({ type: "Form", doctype: "Sales Invoice" });
		expect(context).not.toHaveProperty("name");
	});
});
