/**
 * The steps of a ```steps fence, whichever way the model wrote them:
 *
 * - a JSON list of strings, or of objects with a title, a description and a status
 *   (`[{"title": "Purchase Order", "status": "complete"}, …]`), or an object holding that list
 *   under `steps`, the way it writes the callout and metric fences;
 * - the documented form: a `## Step 1: Title` heading per step with its text under it;
 * - one step per line, numbered or bulleted or plain.
 *
 * Each step is `{ title, body, state }`, state "done", "active" or "pending". A step's own status
 * wins; without one, the fence's `current` attribute marks the steps before it done.
 */

const DONE = new Set(["complete", "completed", "done", "finished", "success", "succeeded"]);
const ACTIVE = new Set(["current", "active", "in_progress", "in progress", "running", "doing", "now"]);
const TITLE_KEYS = ["title", "name", "label", "step", "text"];
const BODY_KEYS = ["description", "detail", "details", "body", "note", "summary"];
const HEADING = /^#{1,6}\s+(.*)$/;
const LIST_PREFIX = /^\s*(?:\d+[.)]|[-*•])\s+/;
const STEP_PREFIX = /^step\s*\d+\s*[:.\-–—]\s*/i;

function firstString(item, keys) {
	for (const key of keys) {
		if (typeof item[key] === "string" && item[key].trim()) return item[key].trim();
	}
	return "";
}

function stateOf(status) {
	const value = typeof status === "string" ? status.trim().toLowerCase() : "";
	if (DONE.has(value)) return "done";
	if (ACTIVE.has(value)) return "active";
	return value ? "pending" : null;
}

function fromJson(text) {
	const trimmed = text.trim();
	if (!trimmed.startsWith("[") && !trimmed.startsWith("{")) return null;
	let parsed;
	try {
		parsed = JSON.parse(trimmed);
	} catch {
		return null;
	}
	const title = !Array.isArray(parsed) && typeof parsed?.title === "string" ? parsed.title : "";
	const items = Array.isArray(parsed) ? parsed : parsed?.steps || parsed?.items;
	if (!Array.isArray(items)) return null;
	const steps = items
		.map((item) => {
			if (typeof item === "string") return { title: item.trim(), body: "", state: null };
			if (!item || typeof item !== "object") return null;
			return { title: firstString(item, TITLE_KEYS), body: firstString(item, BODY_KEYS), state: stateOf(item.status) };
		})
		.filter((step) => step && (step.title || step.body));
	return { title, steps };
}

function fromHeadings(lines) {
	const steps = [];
	for (const line of lines) {
		const heading = HEADING.exec(line.trim());
		if (heading) {
			steps.push({ title: heading[1].replace(STEP_PREFIX, "").trim(), lines: [] });
		} else if (steps.length) {
			steps.at(-1).lines.push(line);
		}
	}
	return steps.map(({ title, lines: body }) => ({ title, body: body.join("\n").trim(), state: null }));
}

function fromLines(lines) {
	return lines
		.map((line) => line.replace(LIST_PREFIX, "").replace(STEP_PREFIX, "").trim())
		.filter(Boolean)
		.map((title) => ({ title, body: "", state: null }));
}

/** `{ title, steps }` for a fence body; `title` is set only when a JSON body carries one. */
export function parseSteps(body, current = 0) {
	const text = typeof body === "string" ? body : "";
	const lines = text.split("\n");
	const json = fromJson(text);
	const startsWithHeading = HEADING.test((lines.find((l) => l.trim()) || "").trim());
	const steps = json ? json.steps : startsWithHeading ? fromHeadings(lines) : fromLines(lines);
	const at = Number.isInteger(current) && current > 0 ? current : 0;
	return {
		title: json?.title || "",
		steps: steps.map((step, index) => ({
			...step,
			state: step.state || (at && index + 1 < at ? "done" : at && index + 1 === at ? "active" : "pending"),
		})),
	};
}
