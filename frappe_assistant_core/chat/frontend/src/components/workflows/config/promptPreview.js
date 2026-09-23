/**
 * What the model actually receives.
 *
 * The author writes half a system prompt: the engine substitutes the workflow's
 * global variables and appends a tool block built from the node's directives.
 * These helpers mirror both so the preview shows the whole thing — including
 * the "these tools are not available" line that otherwise goes unread.
 *
 * Mirrors assistant_runtime_workflows/engine/tool_resolver.py
 * :build_tool_directive_prompt.
 */

const PLACEHOLDER = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

/**
 * Substitute {{ name }} placeholders. Unknown names are left in place and
 * reported — the engine renders them empty, which is worth seeing beforehand.
 */
export function substituteVariables(text, variables = {}) {
	const unresolved = new Set();
	const resolved = String(text || "").replace(PLACEHOLDER, (match, name) => {
		if (Object.prototype.hasOwnProperty.call(variables, name)) {
			return String(variables[name] ?? "");
		}
		unresolved.add(name);
		return match;
	});
	return { text: resolved, unresolved: [...unresolved] };
}

/**
 * The block the engine appends to the node's system prompt.
 *
 * @param {Array} directives - the node's tool_directives
 * @param {Map}   resolution - directive name -> resolve_workflow_tools entry
 */
export function buildToolDirectiveBlock(directives = [], resolution = new Map()) {
	if (!directives.length) return "";

	const nameFor = (d) => resolution.get(d.tool_name)?.prefixed_name || d.tool_name;
	const isResolved = (d) => {
		const entry = resolution.get(d.tool_name);
		// No resolution data yet — assume the tool exists rather than
		// previewing a failure the author has no evidence for.
		return !entry || entry.status === "resolved";
	};

	const primary = directives.filter((d) => (d.priority || "primary") === "primary" && isResolved(d));
	const secondary = directives.filter((d) => d.priority === "secondary" && isResolved(d));
	const missing = directives.filter((d) => !isResolved(d));

	const sections = [];

	if (primary.length) {
		sections.push("## Required Tools", "", "You MUST use these tools to complete this task:", "");
		for (const d of primary) sections.push(`- \`${nameFor(d)}\``);
		sections.push("");
	}

	if (secondary.length) {
		sections.push("## Additional Tools", "", "You may also use:", "");
		for (const d of secondary) sections.push(`- \`${nameFor(d)}\``);
		sections.push("");
	}

	if (missing.length) {
		sections.push(`Note: These tools are not available: ${missing.map((d) => d.tool_name).join(", ")}`);
		sections.push("");
	}

	return sections.join("\n").replace(/\s+$/, "");
}

/** Rough token estimate — ~4 characters per token, good enough to size a prompt. */
export function estimateTokens(text) {
	const chars = String(text || "").trim().length;
	return chars ? Math.ceil(chars / 4) : 0;
}

/**
 * The full prompt the node will send, plus what the author should know about it.
 *
 * @returns {{text: string, unresolvedVariables: string[], missingTools: string[], tokens: number}}
 */
export function buildResolvedPrompt({
	systemPrompt = "",
	variables = {},
	directives = [],
	resolution = new Map(),
} = {}) {
	const { text: substituted, unresolved } = substituteVariables(systemPrompt, variables);
	const block = buildToolDirectiveBlock(directives, resolution);
	const text = block ? `${substituted}\n\n${block}` : substituted;

	const missingTools = directives
		.filter((d) => resolution.get(d.tool_name)?.status === "missing")
		.map((d) => d.tool_name);

	return {
		text,
		unresolvedVariables: unresolved,
		missingTools,
		tokens: estimateTokens(text),
	};
}
