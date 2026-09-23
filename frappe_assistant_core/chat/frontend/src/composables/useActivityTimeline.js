/**
 * Builds plain-language activity-timeline rows from a turn's tool_call blocks.
 * Each row = one external tool call, phrased as *what the AI did* rather than
 * "Used <Tool> ›" (spec §3.2). Pure + side-effect free so it can be unit
 * tested and reused. Internal tools (block.isInternal) are skipped — they're
 * plumbing, not user-facing actions.
 */

// Friendly verb + object phrasing per known MCP tool. Falls back to a
// humanized tool name. `target` is pulled from the tool input when present
// and rendered emphasized in the row.
const TOOL_PHRASING = {
	search_link: { verb: "Searched", noun: "records" },
	search_documents: { verb: "Searched", noun: "documents" },
	list_documents: { verb: "Listed", noun: "records" },
	get_document: { verb: "Read", noun: "record" },
	get_doctype_info: { verb: "Read", noun: "doctype" },
	run_database_query: { verb: "Queried", noun: "the database" },
	create_document: { verb: "Prepared", noun: "new record" },
	update_document: { verb: "Prepared", noun: "update" },
	submit_document: { verb: "Prepared", noun: "submission" },
	generate_report: { verb: "Generated", noun: "report" },
};

function humanizeToolName(name) {
	if (!name) return "Tool";
	return name
		.replace(/_/g, " ")
		.replace(/([a-z])([A-Z])/g, "$1 $2")
		.split(" ")
		.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
		.join(" ");
}

// Best-effort "what was touched" extracted from the tool input.
function extractTarget(block) {
	const input = block.input || {};
	return (
		input.doctype ||
		input.document_type ||
		input.txt ||
		input.search_term ||
		input.name ||
		input.docname ||
		null
	);
}

/**
 * One row for one tool_call block, or null when the block isn't a user-facing
 * tool call. Exposed per-block so a renderer can build rows in place and keep
 * the turn's chronology, instead of hoisting every row into a second list.
 *
 * `labelPrefix` is `label` minus the target, so a renderer can emphasize the
 * touched record (spec §3.2) without parsing the flat string back apart.
 */
export function toolRowFrom(block) {
	if (!block || block.type !== "tool_call") return null;
	if (block.isInternal) return null;

	const phrasing = TOOL_PHRASING[block.tool_name];
	const target = extractTarget(block);
	const base = phrasing
		? `${phrasing.verb} ${phrasing.noun}`
		: humanizeToolName(block.tool_name);

	return {
		id: block.id,
		status: block.status, // "running" | "success" | "error" | "cancelled"
		label: target ? `${base} → ${target}` : base,
		labelPrefix: target ? `${base} → ` : base,
		target,
		toolName: block.tool_name,
		hasTarget: Boolean(target),
		block, // raw block for the expandable I/O drawer
	};
}

export function buildTimelineRows(blocks) {
	const rows = [];
	for (const block of blocks || []) {
		const row = toolRowFrom(block);
		if (row) rows.push(row);
	}
	return rows;
}

export function useActivityTimeline(blocks) {
	return { rows: buildTimelineRows(blocks) };
}

export function toolDurationMs(block) {
	if (typeof block?.duration_ms === "number") return block.duration_ms;
	if (!block?.startTime || !block?.endTime) return null;
	const ms = new Date(block.endTime).getTime() - new Date(block.startTime).getTime();
	return Number.isFinite(ms) && ms >= 0 ? ms : null;
}
