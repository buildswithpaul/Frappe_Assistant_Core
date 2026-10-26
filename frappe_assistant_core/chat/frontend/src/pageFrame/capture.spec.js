import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("copyWithStyles sizes", () => {
	afterEach(() => {
		vi.restoreAllMocks();
		document.head.querySelectorAll("style[data-test]").forEach((el) => el.remove());
	});

	// Chrome computes a used pixel size for every box; jsdom lays nothing out, so the live sizes a
	// browser would report are added here to the styles jsdom computes.
	function withLiveSizes(sizes) {
		const real = window.getComputedStyle.bind(window);
		vi.spyOn(window, "getComputedStyle").mockImplementation((element) => {
			const style = real(element);
			const live = sizes(element);
			if (!live) return style;
			const names = [...Array.from(style), ...Object.keys(live)];
			return new Proxy(style, {
				get(target, key) {
					if (key === "length") return names.length;
					if (typeof key === "string" && /^\d+$/.test(key)) return names[Number(key)];
					if (key === "getPropertyValue") return (name) => live[name] ?? target.getPropertyValue(name);
					const value = Reflect.get(target, key, target);
					return typeof value === "function" ? value.bind(target) : value;
				},
			});
		});
	}

	it("does not freeze a box at the size it took on the live page", () => {
		const root = document.createElement("div");
		root.innerHTML = '<div class="card"><table><tr><td>Total</td></tr></table></div><img src="/files/x.png">';
		document.body.append(root);
		withLiveSizes((el) =>
			root.contains(el) && ["div", "td", "img"].includes(el.localName)
				? { width: "205px", height: "412px", "min-height": "29px" }
				: null,
		);
		const copy = copyWithStyles(root);
		const card = copy.querySelector(".card").getAttribute("style");
		expect(card).not.toMatch(/(^|;)height:/);
		expect(card).not.toMatch(/(^|;)width:/);
		expect(card).not.toMatch(/min-height:/);
		expect(copy.querySelector("td").getAttribute("style")).not.toMatch(/(^|;)height:/);
		// An image keeps its drawn size, or it would have no box at all.
		expect(copy.querySelector("img").getAttribute("style")).toContain("height:412px");
		root.remove();
	});

	it("keeps a size the page wrote, as it wrote it", () => {
		const sheet = document.createElement("style");
		sheet.dataset.test = "1";
		sheet.textContent = ".chart{height:120px} @media all{.wide{max-width:80%}}";
		document.head.append(sheet);
		const root = document.createElement("div");
		root.innerHTML = '<div class="chart"></div><div class="wide" style="width:50%"></div>';
		document.body.append(root);
		withLiveSizes((el) => (root.contains(el) && el.localName === "div" ? { width: "442px", height: "120px" } : null));
		const copy = copyWithStyles(root);
		expect(copy.querySelector(".chart").getAttribute("style")).toContain("height:120px");
		const wide = copy.querySelector(".wide").getAttribute("style");
		expect(wide).toContain("width:50%");
		expect(wide).toContain("max-width:80%");
		expect(wide).not.toContain("442px");
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
