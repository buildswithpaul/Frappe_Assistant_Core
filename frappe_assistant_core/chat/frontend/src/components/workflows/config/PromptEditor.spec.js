import { describe, it, expect, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import PromptEditor from "./PromptEditor.vue";

const wrappers = [];

function mountEditor(props) {
	const w = mount(PromptEditor, { props, attachTo: document.body });
	wrappers.push(w);
	return w;
}

function dialog() {
	return document.body.querySelector('[role="dialog"]');
}

afterEach(() => {
	while (wrappers.length) wrappers.pop().unmount();
	delete window.__;
});

describe("PromptEditor expand", () => {
	it("opens a large editor that edits the same prompt", async () => {
		const w = mountEditor({ modelValue: "Summarise the report" });
		await w.get('[data-test="expand-prompt"]').trigger("click");
		const big = document.body.querySelector('[data-test="expanded-prompt"]');
		expect(big.value).toBe("Summarise the report");
		big.value = "Summarise and rank";
		big.dispatchEvent(new Event("input"));
		expect(w.emitted("update:modelValue").at(-1)).toEqual(["Summarise and rank"]);
	});

	it("labels the large editor's textarea", async () => {
		const w = mountEditor({ modelValue: "" });
		await w.get('[data-test="expand-prompt"]').trigger("click");
		const big = document.body.querySelector('[data-test="expanded-prompt"]');
		expect(big.getAttribute("aria-label")).toBe("System prompt");
	});

	it("closes on Escape even when focus is on the body", async () => {
		const w = mountEditor({ modelValue: "" });
		await w.get('[data-test="expand-prompt"]').trigger("click");
		document.activeElement.blur();
		document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();
		expect(dialog()).toBeNull();
	});

	it("closes on Done", async () => {
		const w = mountEditor({ modelValue: "" });
		await w.get('[data-test="expand-prompt"]').trigger("click");
		dialog().querySelector(".prompt-modal-close").click();
		await nextTick();
		expect(dialog()).toBeNull();
	});

	it("hides the variable inserter and makes the prompt read-only when readonly", async () => {
		const w = mountEditor({ modelValue: "Fixed", readonly: true, variables: { region: "EU" } });
		await w.get('[data-test="expand-prompt"]').trigger("click");
		expect(dialog().querySelector(".insert-btn")).toBeNull();
		const big = dialog().querySelector('[data-test="expanded-prompt"]');
		expect(big.readOnly).toBe(true);
	});

	it("inserts a variable at the caret in the large editor", async () => {
		const w = mountEditor({ modelValue: "Hello world", variables: { region: "EU" } });
		await w.get('[data-test="expand-prompt"]').trigger("click");
		const big = dialog().querySelector('[data-test="expanded-prompt"]');
		big.setSelectionRange(5, 5);
		dialog().querySelector(".insert-btn").click();
		await nextTick();
		dialog().querySelector(".inserter-item").click();
		expect(w.emitted("update:modelValue").at(-1)).toEqual(["Hello{{region}} world"]);
	});

	it("returns focus to the Expand button on close", async () => {
		const w = mountEditor({ modelValue: "" });
		const expand = w.get('[data-test="expand-prompt"]').element;
		expand.focus();
		await w.get('[data-test="expand-prompt"]').trigger("click");
		await nextTick();
		expect(document.activeElement).toBe(dialog().querySelector('[data-test="expanded-prompt"]'));
		dialog().querySelector(".prompt-modal-close").click();
		await nextTick();
		expect(document.activeElement).toBe(expand);
	});

	it("routes its visible strings through __()", () => {
		window.__ = (text) => `T:${text}`;
		const w = mountEditor({ modelValue: "" });
		expect(w.get("label").text()).toBe("T:System prompt");
	});
});
