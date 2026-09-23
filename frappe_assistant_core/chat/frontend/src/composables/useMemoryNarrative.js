/**
 * Composable for transforming flat memory arrays into readable narrative sections.
 *
 * Takes individual memory items ("Prefers concise responses", "Works in finance")
 * and groups them into flowing prose paragraphs with warm section headings.
 * Each sentence retains its memoryId for inline delete/share actions.
 */

import { computed } from "vue";

const TYPE_CONFIG = {
	preference: { title: "What I know about how you work" },
	fact: { title: "Things you've shared with me" },
	summary: { title: "From our conversations" },
};

const TYPE_ORDER = ["preference", "fact", "summary"];

/**
 * Normalize a memory content string into a proper sentence.
 * - Capitalize first letter
 * - Ensure trailing period
 * - Trim whitespace
 */
function normalizeSentence(content) {
	let text = (content || "").trim();
	if (!text) return "";

	// Capitalize first letter
	text = text.charAt(0).toUpperCase() + text.slice(1);

	// Ensure trailing period (but not double punctuation)
	if (!/[.!?]$/.test(text)) {
		text += ".";
	}

	return text;
}

/**
 * Build narrative sections from a flat array of memory objects.
 *
 * @param {Array} memories - Array of { memory_id, content, memory_type, ... }
 * @param {string|null} activeFilter - Filter to a single type, or null for all
 * @returns {Array} sections - [{ key, title, sentences: [{ text, memoryId }] }]
 */
export function buildNarrative(memories, activeFilter = null) {
	const source = activeFilter
		? memories.filter((m) => m.memory_type === activeFilter)
		: memories;

	// Group by type
	const groups = {};
	for (const m of source) {
		const type = m.memory_type || "fact";
		if (!groups[type]) groups[type] = [];
		groups[type].push({
			text: normalizeSentence(m.content),
			memoryId: m.memory_id,
		});
	}

	// Build ordered sections (only for types that have memories)
	const sections = [];
	for (const key of TYPE_ORDER) {
		if (groups[key]?.length) {
			sections.push({
				key,
				title: TYPE_CONFIG[key]?.title || key,
				sentences: groups[key],
			});
		}
	}

	return sections;
}

/**
 * Reactive composable wrapper around buildNarrative.
 *
 * @param {import('vue').Ref<Array>} memories - Reactive memories array
 * @param {import('vue').Ref<string|null>} activeFilter - Reactive filter ref
 * @returns {{ sections: import('vue').ComputedRef<Array> }}
 */
export function useMemoryNarrative(memories, activeFilter) {
	const sections = computed(() => buildNarrative(memories.value, activeFilter.value));

	return { sections };
}
