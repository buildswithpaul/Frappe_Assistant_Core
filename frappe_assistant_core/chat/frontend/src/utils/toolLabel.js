// A tool name's words as a person reads them: "add_crm_activity" → "Add CRM Activity".
const ACRONYMS = new Set(["crm", "pdf", "sql", "mcp", "api", "url", "hd", "id"]);

export function titleWord(word) {
	if (ACRONYMS.has(word.toLowerCase())) return word.toUpperCase();
	return word.charAt(0).toUpperCase() + word.slice(1);
}
