import { describe, it, expect } from "vitest";
import { applyVisualViewportFrame } from "./useVisualViewportFrame.js";

describe("applyVisualViewportFrame", () => {
	it("pins the shell to the visual viewport box", () => {
		const el = { style: {} };
		applyVisualViewportFrame(el, {
			offsetTop: 40,
			offsetLeft: 0,
			width: 1024,
			height: 688,
		});
		expect(el.style.top).toBe("40px");
		expect(el.style.left).toBe("0px");
		expect(el.style.width).toBe("1024px");
		expect(el.style.height).toBe("688px");
		expect(el.style.right).toBe("auto");
		expect(el.style.bottom).toBe("auto");
	});

	it("never grows past window.innerHeight so the composer toolbar stays on-screen", () => {
		const el = { style: {} };
		applyVisualViewportFrame(
			el,
			{ offsetTop: 0, offsetLeft: 0, width: 390, height: 844 },
			720,
		);
		expect(el.style.height).toBe("720px");
	});

	it("clears inline offsets when visualViewport is missing", () => {
		const el = {
			style: {
				top: "40px",
				height: "688px",
				right: "auto",
				bottom: "auto",
			},
		};
		applyVisualViewportFrame(el, null);
		expect(el.style.top).toBe("");
		expect(el.style.height).toBe("");
		expect(el.style.right).toBe("");
		expect(el.style.bottom).toBe("");
	});
});
