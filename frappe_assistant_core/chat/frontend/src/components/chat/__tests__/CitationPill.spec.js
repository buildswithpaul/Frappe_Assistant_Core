import { describe, it, expect, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import CitationPill from "@/components/chat/CitationPill.vue";

const source = { n: 1, document_name: "Team Notes.md", passage_preview: "Cut-off is 3:30 PM." };

// jsdom has no layout, so each test states where the popover would land and how wide the
// scrolling messages column is; the component only reads those two rectangles.
function mountInColumn({ column, popover }) {
	const host = document.createElement("div");
	host.style.overflowY = "auto";
	document.body.appendChild(host);
	vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function () {
		if (this === host) return { left: column[0], right: column[1] };
		if (this.classList.contains("citation-popover")) return { left: popover[0], right: popover[1] };
		return { left: 0, right: 0 };
	});
	return mount(CitationPill, { props: { source }, attachTo: host });
}

async function hover(wrapper) {
	await wrapper.get(".citation-pill-wrap").trigger("mouseenter");
	await flushPromises();
	return wrapper.get(".citation-popover").attributes("style");
}

afterEach(() => {
	vi.restoreAllMocks();
	document.body.innerHTML = "";
});

describe("CitationPill popover", () => {
	it("shifts right when it would start left of the messages column (under the sidebar)", async () => {
		const w = mountInColumn({ column: [300, 1100], popover: [204, 556] });
		expect(await hover(w)).toContain("--pop-shift: 104px");
		w.unmount();
	});

	it("shifts left when it would run past the right edge of the column", async () => {
		const w = mountInColumn({ column: [300, 1100], popover: [900, 1252] });
		expect(await hover(w)).toContain("--pop-shift: -160px");
		w.unmount();
	});

	it("stays centred on the pill when it already fits", async () => {
		const w = mountInColumn({ column: [300, 1100], popover: [500, 852] });
		expect(await hover(w)).toContain("--pop-shift: 0px");
		w.unmount();
	});

	it("still opens the document from the shifted popover", async () => {
		const w = mountInColumn({ column: [300, 1100], popover: [204, 556] });
		await hover(w);
		await w.get(".pop-open").trigger("click");
		expect(w.emitted("preview-document")[0]).toEqual([source]);
		w.unmount();
	});
});
