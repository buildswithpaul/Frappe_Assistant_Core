import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describeDraftBuilder } from "@/utils/facPageDraftCases";

// The Desk page inlines this plain script with Frappe's render_include, so the test loads it the same way:
// as source text, evaluated for the functions it declares.
const SOURCE = readFileSync(
	resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages/fac_page_draft.js"),
	"utf-8",
);
const { fac_page_draft_srcdoc, fac_page_draft_frame } = new Function(
	`${SOURCE}\nreturn { fac_page_draft_srcdoc, fac_page_draft_frame };`,
)();

describeDraftBuilder("Desk copy", { srcdoc: fac_page_draft_srcdoc, frame: fac_page_draft_frame });
