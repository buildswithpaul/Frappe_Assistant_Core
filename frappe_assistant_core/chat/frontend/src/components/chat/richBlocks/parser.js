/**
 * Rich block parser — extracts special code fence blocks from markdown content.
 *
 * Replaces the hardcoded mermaid/chart regex with a dynamic pattern built
 * from the block registry. Supports key="value" attributes on the opening
 * fence line.
 */

import { marked } from "marked";
import DOMPurify from "dompurify";
import { blockRegistry } from "./registry";

/**
 * Parse key="value" pairs from the attribute string on a code fence line.
 * e.g. 'type="info" title="Note"' → { type: 'info', title: 'Note' }
 */
function parseAttributes(attrString) {
	if (!attrString) return {};
	const attrs = {};
	const re = /(\w+)="([^"]*)"/g;
	let m;
	while ((m = re.exec(attrString)) !== null) {
		attrs[m[1]] = m[2];
	}
	return attrs;
}

// Build the regex once from registry keys
const registeredTypes = Object.keys(blockRegistry).join("|");
const blockRegex = new RegExp(
	"```(" + registeredTypes + ")([ \\t]+[^\\n]*)?\\n([\\s\\S]*?)```",
	"g"
);

/**
 * Parse text content for rich blocks (chart, mermaid, callout, metric, etc.)
 *
 * Returns an array of parts:
 *   { type: 'html', html: string }
 *   { type: 'component', component: VueComponent, props: object }
 *
 * @param {string} content — raw markdown string from LLM
 * @param {function} renderMarkdown — function to convert markdown to sanitized HTML
 * @returns {Array}
 */
export function parseRichBlocks(content, renderMarkdown) {
	if (!content) return [];

	const render = renderMarkdown || ((md) => DOMPurify.sanitize(marked.parse(md)));
	const parts = [];
	let lastIndex = 0;

	// Reset regex state (global regexes are stateful)
	blockRegex.lastIndex = 0;
	let match;

	while ((match = blockRegex.exec(content)) !== null) {
		// Add text before this block
		if (match.index > lastIndex) {
			const textBefore = content.slice(lastIndex, match.index);
			if (textBefore.trim()) {
				parts.push({ type: "html", html: render(textBefore) });
			}
		}

		const blockType = match[1];
		const attrString = match[2] ? match[2].trim() : "";
		const blockBody = match[3].trim();
		const entry = blockRegistry[blockType];

		if (entry) {
			const attrs = parseAttributes(attrString);
			const parsed = entry.parseBody(blockBody, attrs);
			// `parseBody` may return several props objects for one fence — a
			// `metric` array is a whole KPI row written as a single block.
			// Each becomes its own component, so the array form renders
			// exactly like the same metrics written as separate fences.
			const propsList = Array.isArray(parsed) ? parsed : parsed ? [parsed] : [];

			if (propsList.length) {
				for (const props of propsList) {
					parts.push({
						type: "component",
						component: entry.component,
						props,
					});
				}
			} else {
				// Nothing usable in the fence — render as a plain code block so
				// the content stays visible instead of vanishing.
				parts.push({ type: "html", html: render("```\n" + blockBody + "\n```") });
			}
		}

		lastIndex = match.index + match[0].length;
	}

	// Add remaining text after last block
	if (lastIndex < content.length) {
		const textAfter = content.slice(lastIndex);
		if (textAfter.trim()) {
			parts.push({ type: "html", html: render(textAfter) });
		}
	}

	// If no special blocks found, just render as HTML
	if (parts.length === 0 && content.trim()) {
		parts.push({ type: "html", html: render(content) });
	}

	return parts;
}
