// Relevance stack for the landing suggestion grid (spec §7).
// Personalized (≤3) → pinned → contextual → defaults; dedup by description;
// drop anything the Resume cards already own; always fill to 4.

const TILE_COUNT = 4;
const PERSONALIZED_CAP = 3;

const FALLBACK_TILES = [
	{
		name: "What can you help me with?",
		description: "What can you help me with?",
		subtext: "A quick tour of what I can do",
		source: "default",
	},
	{
		name: "Summarize my recent activity",
		description: "Summarize my recent activity",
		subtext: "What changed lately",
		source: "default",
	},
	{
		name: "How do I create a new document?",
		description: "How do I create a new document?",
		subtext: "Guided, step by step",
		source: "default",
	},
	{
		name: "Show me my pending tasks",
		description: "Show me my pending tasks",
		subtext: "What needs attention",
		source: "default",
	},
];

function norm(text) {
	return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function duplicatesResume(description, resumePreview) {
	const d = norm(description);
	const r = norm(resumePreview);
	if (!d || !r) return false;
	return r.includes(d) || d.includes(r);
}

export function selectWelcomeTiles({ suggestions = [], resumePreviews = [], resumePreview = "" }) {
	const previews = [...(resumePreviews || []), resumePreview].filter(Boolean);
	const dupResume = (description) => previews.some((p) => duplicatesResume(description, p));

	const seen = new Set();
	const pool = suggestions.filter((sg) => {
		const key = norm(sg.description);
		if (!key || seen.has(key) || dupResume(sg.description)) return false;
		seen.add(key);
		return true;
	});

	const bySource = (src) => pool.filter((sg) => sg.source === src);
	const ordered = [
		...bySource("personalized").slice(0, PERSONALIZED_CAP),
		...bySource("pinned"),
		...bySource("contextual"),
		...bySource("default"),
	];

	for (const fallback of FALLBACK_TILES) {
		if (ordered.length >= TILE_COUNT) break;
		const key = norm(fallback.description);
		if (!key || seen.has(key) || dupResume(fallback.description)) continue;
		seen.add(key);
		ordered.push(fallback);
	}

	return ordered.slice(0, TILE_COUNT).map((sg) => ({
		...sg,
		personalized: sg.source === "personalized",
	}));
}
