import { describe, expect, it } from "vitest";

import { copyWithStyles, pageText } from "./capture";

// jsdom loads no images, so the drawing itself is checked in Chrome (task-8-report.md); this checks
// what goes into the picture and the text that always comes with it.
describe("copyWithStyles", () => {
	it("copies the page with its styles inline, leaving out anything that loads or runs", () => {
		const root = document.createElement("div");
		root.innerHTML =
			'<p class="big">₹70,29,354</p><script>x()</script><style>.big{color:red}</style>' +
			'<svg width="20" height="10"><rect width="5" height="5" fill="#123456"></rect></svg><input value="typed">';
		root.querySelector("p").style.color = "rgb(255, 0, 0)";
		root.querySelector("input").value = "edited";
		document.body.append(root);
		const copy = copyWithStyles(root);
		expect(copy.querySelector("script")).toBeNull();
		expect(copy.querySelector("style")).toBeNull();
		expect(copy.querySelector("p").getAttribute("style")).toContain("color:rgb(255, 0, 0)");
		expect(copy.querySelector("rect").getAttribute("fill")).toBe("#123456");
		expect(copy.querySelector("rect").hasAttribute("style")).toBe(false);
		expect(copy.querySelector("input").getAttribute("value")).toBe("edited");
		// The picture has no document to inherit from, so its root carries the page's text styles.
		expect(copy.getAttribute("style")).toMatch(/^font-family:/);
		root.remove();
	});
});

describe("pageText", () => {
	it("gives the page's visible text, trimmed to a size FACO can read", () => {
		const root = document.createElement("div");
		root.textContent = "Sales 70,29,354\n\n\n\nIndia 74%";
		expect(pageText(root)).toBe("Sales 70,29,354\n\nIndia 74%");
		root.textContent = "x".repeat(7000);
		expect(pageText(root)).toHaveLength(6001);
	});
});
