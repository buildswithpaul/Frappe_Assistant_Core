import { describe, it, expect } from "vitest";
import { useArtifactZoom } from "./useArtifactZoom";

describe("useArtifactZoom", () => {
	it("starts at identity transform", () => {
		const z = useArtifactZoom();
		expect(z.scale.value).toBe(1);
		expect(z.transformStyle.value).toBe("translate(0px, 0px) scale(1)");
	});

	it("zoomIn / zoomOut step the scale and clamp to [0.1, 10]", () => {
		const z = useArtifactZoom();
		z.zoomIn();
		expect(z.scale.value).toBeCloseTo(1.2, 5);
		z.reset();
		// clamp upper bound
		for (let i = 0; i < 50; i++) z.zoomIn();
		expect(z.scale.value).toBe(10);
		// clamp lower bound
		for (let i = 0; i < 100; i++) z.zoomOut();
		expect(z.scale.value).toBe(0.1);
	});

	it("wheel zoom keeps the point under the cursor fixed", () => {
		const z = useArtifactZoom();
		// Cursor at content-space point (100, 50). Zoom in by one notch.
		// Invariant: screenPoint = translate + scale * contentPoint stays equal
		// before and after the wheel event.
		const cursor = { x: 100, y: 50 };
		const before = {
			x: z.tx.value + z.scale.value * cursor.x,
			y: z.ty.value + z.scale.value * cursor.y,
		};
		z.onWheel({
			deltaY: -100,
			clientX: before.x,
			clientY: before.y,
			currentTarget: { getBoundingClientRect: () => ({ left: 0, top: 0 }) },
			preventDefault() {},
		});
		const after = {
			x: z.tx.value + z.scale.value * cursor.x,
			y: z.ty.value + z.scale.value * cursor.y,
		};
		expect(after.x).toBeCloseTo(before.x, 3);
		expect(after.y).toBeCloseTo(before.y, 3);
		expect(z.scale.value).toBeGreaterThan(1);
	});

	it("reset returns to identity", () => {
		const z = useArtifactZoom();
		z.zoomIn();
		z.pan(40, -20);
		z.reset();
		expect(z.scale.value).toBe(1);
		expect(z.tx.value).toBe(0);
		expect(z.ty.value).toBe(0);
	});

	it("pan accumulates deltas", () => {
		const z = useArtifactZoom();
		z.pan(10, 5);
		z.pan(-3, 2);
		expect(z.tx.value).toBe(7);
		expect(z.ty.value).toBe(7);
	});

	it("fit scales a large bbox to fit the viewport with padding and centers it", () => {
		const z = useArtifactZoom();
		// content 1000x500, viewport 400x400, padding 0.9 → scale = 0.9*min(0.4,0.8)=0.36
		z.fit({ width: 1000, height: 500 }, { width: 400, height: 400 });
		expect(z.scale.value).toBeCloseTo(0.36, 5);
		// centered: tx = (400 - 1000*0.36)/2 = 20 ; ty = (400 - 500*0.36)/2 = 110
		expect(z.tx.value).toBeCloseTo(20, 3);
		expect(z.ty.value).toBeCloseTo(110, 3);
	});

	it("fit never scales above 1 (small artifact stays its natural size)", () => {
		const z = useArtifactZoom();
		z.fit({ width: 100, height: 80 }, { width: 800, height: 600 });
		expect(z.scale.value).toBe(1);
	});
});
