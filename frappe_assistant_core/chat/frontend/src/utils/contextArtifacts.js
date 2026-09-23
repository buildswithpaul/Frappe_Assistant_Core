/**
 * contextArtifacts — derive the Context Rail model from an assistant turn's
 * `blocks` array. Pure, synchronous, no I/O. Block shapes match
 * MessageBlockRenderer.vue: tool_call, sources, generated_documents,
 * interaction, text.
 */

import { formatToolName, flattenInput } from "@/components/chat/interactions/helpers.js";
import { buildTimelineRows } from "@/composables/useActivityTimeline.js";
// formatToolName is still used for the approval card title (an interaction, not
// a record); record chips deliberately do NOT fall back to a tool name.

// Tool names that read/touch ERP records but do not write. Used to label a
// touched record as a "source" rather than a mutation in the Records list.
const READ_TOOLS = new Set([
	"search_documents",
	"get_document",
	"list_documents",
	"run_report",
	"get_doctype_info",
	"search_link",
]);

/**
 * Resolve a human label for the *record* a tool touched, or null when the tool
 * didn't reference one.
 *
 * The rail lists records & sources — not tools. Compute-only tools like
 * run_python_code, generate_report, or analyze_business_data carry no
 * doctype/name in their input, so they resolve to null and are dropped: the
 * rail must never degrade into a list of raw tool names (which is exactly what
 * the old tool-name fallback produced). Only tool calls that name an actual
 * ERP document earn a chip.
 */
function recordLabel(block) {
	const flat = block.input ? flattenInput(block.input) : {};
	const doctype = flat.doctype || "";
	const name = flat.name || flat.docname || flat.title || "";
	if (doctype && name) return `${doctype}: ${name}`;
	if (doctype) return doctype;
	if (name) return String(name);
	return null;
}

/**
 * Derive the rail content for a single assistant turn.
 * @param {Array} blocks
 * @returns {{approval: object|null, plan: object|null, records: Array, charts: Array, documents: Array, activity: Array, hasArtifacts: boolean}}
 */
export function deriveArtifacts(blocks) {
	const safe = Array.isArray(blocks) ? blocks : [];

	// 1) Pending approval (mirrors the in-thread interaction card).
	let approval = null;
	let plan = null;
	for (const b of safe) {
		if (b.type === "interaction" && b.status === "pending") {
			const flat = b.input ? flattenInput(b.input) : {};
			approval = {
				id: b.id,
				title: formatToolName(b.tool_name),
				subtitle: [flat.name || flat.docname || flat.title, flat.grand_total || flat.amount || flat.total]
					.filter(Boolean)
					.join(" · "),
			};
			break; // one approval shown at a time
		}
	}

	// 1b) Plan (live or hydrated) — single plan block per turn.
	for (const b of safe) {
		if (b.type === "plan") {
			plan = { status: b.status || "running", tasks: b.tasks || [] };
			break;
		}
	}

	// 2) Records & sources the AI touched (tool_call blocks + RAG sources).
	const records = [];
	const seen = new Set();
	const pushRecord = (key, label, kind) => {
		if (!label || seen.has(key)) return;
		seen.add(key);
		records.push({ key, label, kind });
	};

	for (const b of safe) {
		if (b.type === "tool_call" && b.status === "success") {
			const isRead = READ_TOOLS.has(b.tool_name);
			pushRecord(`tool-${b.id}`, recordLabel(b), isRead ? "source" : "record");
		}
		if (b.type === "sources" && Array.isArray(b.items)) {
			for (const item of b.items) {
				const label = item.document_type
					? `${item.document_type}: ${item.document_name || "Unknown"}`
					: item.document_name || "Unknown document";
				pushRecord(`src-${item.document_id ?? item.n}`, label, "source");
			}
		}
	}

	// 3) Generated charts (```chart fenced blocks in text).
	const charts = [];
	for (const b of safe) {
		if (b.type === "text" && typeof b.content === "string") {
			const matches = b.content.match(/```chart/g);
			if (matches) {
				for (let i = 0; i < matches.length; i++) {
					charts.push({ key: `chart-${b.id}-${i}`, label: "Generated chart" });
				}
			}
		}
	}

	// 4) Generated documents (PDFs etc.).
	const documents = [];
	for (const b of safe) {
		if (b.type === "generated_documents" && Array.isArray(b.items)) {
			for (const item of b.items) {
				documents.push({
					key: item.file_url,
					label: item.file_name || "Untitled document",
					url: item.file_url,
					size: item.file_size_display || "",
				});
			}
		}
	}

	const activity = buildTimelineRows(safe);

	const hasArtifacts =
		Boolean(approval) ||
		Boolean(plan && plan.tasks.length) ||
		records.length > 0 ||
		charts.length > 0 ||
		documents.length > 0 ||
		activity.length > 0;

	return { approval, plan, records, charts, documents, activity, hasArtifacts };
}
