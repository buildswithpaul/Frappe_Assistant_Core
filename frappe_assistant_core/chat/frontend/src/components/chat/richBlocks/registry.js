/**
 * Rich block component registry.
 *
 * Maps code fence type names to Vue components and their parsers.
 * To add a new rich block: add an entry here and create the Vue component.
 *
 * Chart and Mermaid renderers are lazy — they each pull in ~hundreds of kB
 * (echarts, mermaid + katex). Async-loading keeps the main chat bundle lean
 * for conversations that never render diagrams.
 */

import { defineAsyncComponent } from "vue";
import CalloutBlock from "./CalloutBlock.vue";
import MetricBlock from "./MetricBlock.vue";
import StepsBlock from "./StepsBlock.vue";
import AccordionBlock from "./AccordionBlock.vue";
import TabsBlock from "./TabsBlock.vue";

const ChartRenderer = defineAsyncComponent(() => import("../ChartRenderer.vue"));
const MermaidDiagram = defineAsyncComponent(() => import("../MermaidDiagram.vue"));

// The model reaches for a JSON body on any fence, having generalised from
// `chart`/`mermaid` sitting beside them in the same skill doc. Every block
// that documents fence-line attributes therefore has to read a JSON body
// too, or the payload lands on the user's screen as visible JSON.
function parseJsonBody(body) {
	const trimmed = (body || "").trim();
	if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
	try {
		const parsed = JSON.parse(trimmed);
		return parsed && typeof parsed === "object" ? parsed : null;
	} catch {
		return null;
	}
}

/** JSON body as a plain object, or `{}` for an array / non-JSON body. */
function jsonObjectBody(body) {
	const parsed = parseJsonBody(body);
	return parsed && !Array.isArray(parsed) ? parsed : {};
}

/**
 * First non-empty value for `keys`, attributes first then the JSON body.
 * Attributes win because they are the documented dialect — a fence carrying
 * both is a model hedging its bets, and the explicit form is the intent.
 */
function picker(attrs, json) {
	return (...keys) => {
		for (const key of keys) {
			if (attrs[key]) return String(attrs[key]);
		}
		for (const key of keys) {
			const value = json[key];
			if (value !== undefined && value !== null && value !== "") {
				return String(value);
			}
		}
		return "";
	};
}

const CALLOUT_TYPES = ["info", "warning", "tip", "success", "error"];

function metricProps(attrs, json) {
	const pick = picker(attrs, json);
	const props = {
		title: pick("title", "label"),
		value: pick("value"),
		change: pick("change", "delta"),
		trend: pick("trend"),
		description: pick("description", "suffix"),
	};
	return props.title || props.value ? props : null;
}

export const blockRegistry = {
	chart: {
		component: ChartRenderer,
		parseBody: (body) => {
			try {
				return { config: JSON.parse(body) };
			} catch {
				return null;
			}
		},
	},

	mermaid: {
		component: MermaidDiagram,
		parseBody: (body) => ({ content: body }),
	},

	// A JSON body is read the same way `metric` reads one. Without it a
	// `{"type":"warning","title":…,"content":…}` fence rendered an *info*
	// box with no title and the raw JSON as its text — the payload the
	// model meant as structure, shown to the user as punctuation.
	// An unrecognised JSON shape keeps its body visible: better a reader
	// sees the raw object than an empty box that looks like a UI fault.
	callout: {
		component: CalloutBlock,
		parseBody: (body, attrs) => {
			const json = jsonObjectBody(body);
			const pick = picker(attrs, json);
			const type = pick("type");
			const text = pick("content", "body", "text", "message");
			return {
				type: CALLOUT_TYPES.includes(type) ? type : "info",
				title: pick("title", "heading"),
				body: text || body,
			};
		},
	},

	// `metric` data can arrive three ways. Fence-line attributes are the
	// documented dialect; a JSON object keyed on label/value is what the
	// model actually writes most of the time, having generalised from the
	// `chart` fence documented right beside it; and a JSON *array* is how it
	// writes a whole KPI row in one fence. The array yields one props object
	// per entry, so it renders identically to the same metrics written as
	// separate fences — `.metric-block` is inline-flex, so they flow into a
	// row on their own.
	//
	// Returning null (or an empty array) makes the parser fall back to a
	// visible code block. Rendering a card with nothing in it is the one
	// outcome that has to stay impossible: it looks like a UI glitch and
	// gives no clue that the fence was malformed.
	metric: {
		component: MetricBlock,
		parseBody: (body, attrs) => {
			const parsed = parseJsonBody(body);
			if (Array.isArray(parsed)) {
				return parsed
					.map((entry) =>
						metricProps(attrs, entry && typeof entry === "object" ? entry : {})
					)
					.filter(Boolean);
			}
			return metricProps(attrs, parsed || {});
		},
	},

	steps: {
		component: StepsBlock,
		parseBody: (body, attrs) => ({
			title: attrs.title || "",
			current: attrs.current ? parseInt(attrs.current, 10) : 0,
			body: body,
		}),
	},

	accordion: {
		component: AccordionBlock,
		parseBody: (body) => ({ body }),
	},

	tabs: {
		component: TabsBlock,
		parseBody: (body, attrs) => ({
			defaultTab: attrs.default || "",
			body: body,
		}),
	},
};
