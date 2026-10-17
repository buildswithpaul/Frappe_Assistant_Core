// Page asks arrive as translated templates with literal {doctype}/{name}. The document
// name never leaves the browser, so the fill happens here.

/** Fill a page-ask template; null when it needs a value the page does not have. */
export function fillPageAsk(template, { doctype, name } = {}) {
	if (template.includes("{doctype}") && !doctype) return null;
	if (template.includes("{name}") && !name) return null;
	// Function replacers: a document name may contain "$&" or "$1", which a string replacement would expand.
	return template.replaceAll("{doctype}", () => doctype).replaceAll("{name}", () => name);
}
