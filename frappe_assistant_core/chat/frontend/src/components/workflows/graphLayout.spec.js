import { describe, it, expect } from "vitest";
import { autoLayout, hasOverlaps } from "./graphLayout";

const at = (id, x, y) => ({ id, type: "agent", position: { x, y }, data: {} });

describe("hasOverlaps", () => {
	it("flags two nodes on the same spot", () => {
		expect(hasOverlaps([at("a", 0, 0), at("b", 0, 0)])).toBe(true);
	});

	it("flags two nodes almost on top of each other", () => {
		expect(hasOverlaps([at("a", 0, 0), at("b", 30, 30)])).toBe(true);
	});

	it("flags a node that has no position", () => {
		expect(hasOverlaps([at("a", 0, 0), { id: "b", type: "agent", data: {} }])).toBe(true);
	});

	it("passes a spaced graph", () => {
		expect(hasOverlaps([at("a", 0, 0), at("b", 300, 0)])).toBe(false);
	});

	it("keeps a tightly authored 200px-spaced graph", () => {
		expect(hasOverlaps([at("a", 0, 0), at("b", 200, 0), at("c", 400, 0)])).toBe(false);
	});

	it("passes a single node", () => {
		expect(hasOverlaps([at("a", 0, 0)])).toBe(false);
	});
});

describe("autoLayout", () => {
	it("lays a chain out left to right with no overlaps", () => {
		const nodes = [at("a", 0, 0), at("b", 0, 0), at("c", 0, 0)];
		const edges = [
			{ source: "a", target: "b" },
			{ source: "b", target: "c" },
		];
		const out = autoLayout(nodes, edges);
		expect(out.map((n) => n.position.x)).toEqual([80, 380, 680]);
		expect(hasOverlaps(out)).toBe(false);
		expect(nodes[0].position).toEqual({ x: 0, y: 0 });
	});

	it("stacks siblings and parks unreachable nodes in their own column", () => {
		const nodes = [at("in", 0, 0), at("x", 0, 0), at("y", 0, 0), at("lost", 0, 0)];
		const edges = [
			{ source: "in", target: "x" },
			{ source: "in", target: "y" },
			{ source: "lost", target: "lost" },
		];
		const out = autoLayout(nodes, edges);
		const pos = Object.fromEntries(out.map((n) => [n.id, n.position]));
		expect(pos.x.x).toBe(pos.y.x);
		expect(pos.x.y).not.toBe(pos.y.y);
		expect(pos.lost.x).toBeGreaterThan(pos.x.x);
		expect(hasOverlaps(out)).toBe(false);
	});

	it("survives a cycle", () => {
		const nodes = [at("a", 0, 0), at("b", 0, 0)];
		const out = autoLayout(nodes, [
			{ source: "a", target: "b" },
			{ source: "b", target: "a" },
		]);
		expect(hasOverlaps(out)).toBe(false);
	});
});
