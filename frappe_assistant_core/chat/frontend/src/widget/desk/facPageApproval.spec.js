import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describePageApproval } from "@/utils/__tests__/facPageApprovalCases";

// The Desk page inlines this plain script with Frappe's render_include, so the test loads it the same way:
// as source text, evaluated for the functions it declares.
const SOURCE = readFileSync(
	resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages/fac_page_approval.js"),
	"utf-8",
);
const NAMES = [
	"fac_page_approval_key",
	"fac_page_script_hash",
	"fac_page_approved_script",
	"fac_page_approve_script",
	"fac_page_needs_review",
	"fac_page_script_review",
	"fac_page_line_diff",
];
const api = new Function(`${SOURCE}\nreturn { ${NAMES.join(", ")} };`)();

describePageApproval("Desk copy", api);
