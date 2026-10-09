import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import RunOutputActions from "./RunOutputActions.vue";
import RunCardDetails from "./RunCardDetails.vue";
import { useToast } from "@/composables/useToast";

const button = (w, label) => w.findAll("button").find((b) => b.text() === label);

describe("RunOutputActions", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		document.body.innerHTML = "";
	});

	it("copies the text", async () => {
		const writeText = vi.fn().mockResolvedValue();
		vi.stubGlobal("navigator", { clipboard: { writeText } });
		const w = mount(RunOutputActions, { props: { text: "hello" } });
		await button(w, "Copy").trigger("click");
		expect(writeText).toHaveBeenCalledWith("hello");
	});

	it("shows an error toast when the clipboard is unavailable", async () => {
		vi.stubGlobal("navigator", {});
		const { toasts } = useToast();
		toasts.value = [];
		const w = mount(RunOutputActions, { props: { text: "hello" } });
		await button(w, "Copy").trigger("click");
		await Promise.resolve();
		expect(toasts.value.some((t) => t.type === "error")).toBe(true);
	});

	it("downloads through a blob URL that is revoked afterwards", async () => {
		const create = vi.fn(() => "blob:x");
		const revoke = vi.fn();
		vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
		const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
		const w = mount(RunOutputActions, { props: { text: "hello", filename: "r.md" } });
		await button(w, "Download").trigger("click");
		expect(create).toHaveBeenCalled();
		expect(click).toHaveBeenCalled();
		expect(revoke).toHaveBeenCalledWith("blob:x");
		click.mockRestore();
	});

	it("omits Download when asked", () => {
		const w = mount(RunOutputActions, { props: { text: "hello", downloadable: false } });
		expect(button(w, "Download")).toBeUndefined();
		expect(button(w, "Copy")).toBeDefined();
	});

	it("opens full screen, closes on Escape and returns focus to the opener", async () => {
		const w = mount(RunOutputActions, { props: { text: "# Title" }, attachTo: document.body });
		const opener = button(w, "Full screen");
		opener.element.focus();
		await opener.trigger("click");
		await new Promise((r) => setTimeout(r, 0));
		const dialog = document.body.querySelector('[role="dialog"]');
		expect(dialog.querySelector("h1").textContent).toBe("Title");
		expect(dialog.contains(document.activeElement)).toBe(true);
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await new Promise((r) => setTimeout(r, 0));
		expect(document.body.querySelector('[role="dialog"]')).toBeNull();
		expect(document.activeElement).toBe(opener.element);
		w.unmount();
	});

	it("keeps Tab inside the full screen dialog", async () => {
		const w = mount(RunOutputActions, { props: { text: "x" }, attachTo: document.body });
		await button(w, "Full screen").trigger("click");
		await new Promise((r) => setTimeout(r, 0));
		const close = document.body.querySelector(".fs-close");
		close.focus();
		const ev = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
		document.dispatchEvent(ev);
		expect(ev.defaultPrevented).toBe(true);
		w.unmount();
	});
});

describe("RunCardDetails partial output", () => {
	const failed = {
		name: "R1",
		status: "Failed",
		node_runs: [{ node_id: "b", node_label: "Rank", status: "Completed", output_text: "ranked list" }],
	};

	it("shows the last finished step on a failed run, without Download", () => {
		const w = mount(RunCardDetails, { props: { run: failed } });
		expect(w.text()).toContain("Partial output");
		expect(w.find(".run-result.partial").text()).toContain("ranked list");
		expect(button(w, "Copy")).toBeDefined();
		expect(button(w, "Download")).toBeUndefined();
	});

	it("says when the partial text is cut at 10,000 characters", () => {
		const run = { ...failed, node_runs: [{ ...failed.node_runs[0], output_text_truncated: 1 }] };
		const w = mount(RunCardDetails, { props: { run } });
		expect(w.text()).toContain("first 10,000 characters");
	});

	it("offers Download on a completed run's result", () => {
		const run = { name: "R2", status: "Completed", output_data: "done", node_runs: [] };
		const w = mount(RunCardDetails, { props: { run } });
		expect(button(w, "Download")).toBeDefined();
	});
});
