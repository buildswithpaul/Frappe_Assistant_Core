import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { useBuilderGraph } from "../../composables/useBuilderGraph.js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { graphJsonToVueFlow } from "./graphUtils.js";

const read = (rel) =>
	readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");

const hex = (css, token) =>
	css.match(new RegExp(`${token}:\\s*(#[0-9A-Fa-f]{6})`))?.[1];

/** WCAG relative luminance / contrast ratio. */
function contrast(a, b) {
	const lum = (h) => {
		const c = [1, 3, 5]
			.map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
			.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
		return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
	};
	const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
	return (hi + 0.05) / (lo + 0.05);
}

describe("canvas edge visibility", () => {
	const tokens = read("../../styles/quiet-ledger.css");
	const canvas = read("../../styles/workflow-canvas.css");

	it("draws edges with the edge token, never the hairline border token", () => {
		// --ql-border is 1.16:1 on --ql-bg. Edges drawn with it were invisible:
		// the graph rendered, the connectors did not, and a freshly dragged
		// connection looked like it vanished on release.
		const rule = canvas.match(/\.vue-flow__edge-path\s*\{[^}]*\}/)[0];
		expect(rule).toContain("var(--ql-edge)");
		expect(rule).not.toContain("var(--ql-border)");
	});

	it("keeps the edge colour above the 3:1 WCAG floor in light and dark", () => {
		// Anchor on the selector at line start: the header comment also
		// contains the literal [data-theme="dark"].
		const block = (selector) => {
			const at = tokens.search(new RegExp(`^${selector}\\s*(,|\\{)`, "m"));
			return tokens.slice(at, tokens.indexOf("}", at));
		};
		for (const selector of [":root", '\\[data-theme="dark"\\]']) {
			const css = block(selector);
			const ratio = contrast(hex(css, "--ql-edge"), hex(css, "--ql-bg"));
			expect(ratio, `${selector} edge contrast`).toBeGreaterThanOrEqual(3);
		}
	});

	it("styles the in-progress drag line so a connection is visible while drawn", () => {
		expect(canvas).toMatch(/\.vue-flow__connection-path\s*\{[^}]*stroke:/);
	});

	it("gives every loaded edge an arrowhead, since a DAG needs direction", () => {
		const { edges } = graphJsonToVueFlow(
			JSON.stringify({
				nodes: [
					{ id: "a", type: "agent" },
					{ id: "b", type: "output" },
				],
				edges: [{ id: "e1", source: "a", target: "b" }],
			})
		);
		expect(edges[0].markerEnd).toBe("arrowclosed");
	});

	it("binds a condition edge to the handle its node actually declares", () => {
		// ConditionNode declares source handles id="pass" and id="fail".
		// An edge whose sourceHandle matches nothing is dropped by Vue Flow.
		const node = read("./nodes/ConditionNode.vue");
		const declared = [...node.matchAll(/type="source"[^>]*id="([a-z]+)"/g)].map((m) => m[1]);
		expect(new Set(declared)).toEqual(new Set(["pass", "fail"]));

		const { edges } = graphJsonToVueFlow(
			JSON.stringify({
				nodes: [
					{ id: "c", type: "condition" },
					{ id: "y", type: "output" },
				],
				edges: [{ id: "e1", source: "c", target: "y", condition: "pass" }],
			})
		);
		expect(declared).toContain(edges[0].sourceHandle);
	});
});

describe("isValidConnection under Vue Flow's edge ingestion", () => {
	// createGraphEdges() calls isValidConnection for EVERY edge it ingests and
	// drops the ones it rejects. A duplicate check that does not exclude the
	// edge under test rejects the entire graph on load.
	const build = (edges) => {
		const nodes = ref([
			{ id: "a", type: "agent" },
			{ id: "b", type: "agent" },
			{ id: "out", type: "workflow-output" },
		]);
		const g = useBuilderGraph({
			nodes,
			edges: ref(edges),
			selectedNode: ref(null),
			canEdit: ref(true),
			scheduleAutoSave: () => {},
			project: null,
			canvasAreaRef: ref(null),
		});
		return g;
	};

	it("accepts an edge that is already in the graph (ingestion)", () => {
		const existing = { id: "e1", source: "a", target: "b" };
		const { isValidConnection } = build([existing]);
		expect(isValidConnection(existing)).toBe(true);
	});

	it("still rejects a dragged duplicate of an existing edge", () => {
		const { isValidConnection } = build([{ id: "e1", source: "a", target: "b" }]);
		expect(isValidConnection({ source: "a", target: "b" })).toBe(false);
	});

	it("keeps rejecting the connections the engine cannot execute", () => {
		const { isValidConnection } = build([]);
		expect(isValidConnection({ source: "a", target: "a" })).toBe(false);
		expect(isValidConnection({ source: "out", target: "a" })).toBe(false);
	});
});
