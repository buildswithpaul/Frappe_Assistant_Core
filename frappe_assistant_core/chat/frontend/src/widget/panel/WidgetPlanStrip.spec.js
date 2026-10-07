import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import WidgetPlanStrip from "./WidgetPlanStrip.vue";

const mountStrip = (props) => mount(WidgetPlanStrip, { props });
const labels = (w) => w.findAll(".activity").map((n) => n.text());

describe("WidgetPlanStrip", () => {
	it("heads two running helpers as parallel work and shows both live labels", () => {
		const w = mountStrip({
			plan: {
				tasks: [
					{ id: "a", title: "Customer A", status: "running", helper: true },
					{ id: "b", title: "Customer B", status: "running", helper: true },
				],
			},
			live: true,
			activity: { a: "Reading Sales Invoice list…", b: "Opening Customer B…" },
		});
		expect(w.find(".wps-heading").text()).toBe("Running 2 in parallel…");
		expect(labels(w)).toEqual(["Reading Sales Invoice list…", "Opening Customer B…"]);
	});

	it("heads main-agent work as working through the plan's steps", () => {
		const w = mountStrip({
			plan: {
				tasks: [
					{ id: "1", title: "Inspect fields", status: "running" },
					{ id: "2", title: "Create the invoice", status: "pending" },
				],
			},
			live: true,
		});
		expect(w.find(".wps-heading").text()).toBe("Working through 2 steps…");
		expect(w.findAll(".task-row")).toHaveLength(2);
	});

	it("collapses a finished turn to its tally and expands to rows with helper meta", async () => {
		const w = mountStrip({
			plan: {
				tasks: [
					{ id: "a", title: "Customer A", status: "done", helper: true, duration_ms: 12400, credits: 0.4 },
					{ id: "b", title: "Customer B", status: "done", helper: true, duration_ms: 3000, credits: 1 },
					{ id: "c", title: "Write the summary", status: "running" },
				],
			},
			live: false,
			// A label left over from the turn: the strip must not present it once the turn ended.
			activity: { c: "Writing…" },
		});
		const toggle = w.find(".wps-heading");
		expect(toggle.text()).toBe("✓ Completed 2 of 3 steps");
		expect(toggle.attributes("aria-expanded")).toBe("false");
		expect(w.find(".task-row").exists()).toBe(false);

		await toggle.trigger("click");
		expect(toggle.attributes("aria-expanded")).toBe("true");
		expect(w.findAll(".helper-meta").map((n) => n.text())).toEqual([
			"↳ helper · 12s · 0.4 credits",
			"↳ helper · 3s · 1 credit",
		]);
		expect(w.find(".task-row.is-unfinished").exists()).toBe(true);
		expect(labels(w)).toEqual([]);
	});

	it("renders nothing without a plan", () => {
		expect(mountStrip({ plan: null, live: true }).html()).toBe("<!--v-if-->");
		expect(mountStrip({ plan: { tasks: [] }, live: true }).html()).toBe("<!--v-if-->");
	});
});

describe("WidgetPlanStrip on a stopped turn", () => {
	it("heads the strip as stopped and hands the stopped state to its rows", async () => {
		const w = mountStrip({
			plan: {
				tasks: [
					{ id: "1", title: "Plan the comparison", status: "done" },
					{ id: "a", title: "Customer A", status: "running", helper: true },
					{ id: "4", title: "Compare the totals", status: "pending" },
				],
			},
			live: false,
			stopped: true,
		});
		const toggle = w.find(".wps-heading");
		expect(toggle.text()).toBe("⊘ Stopped after 1 of 3 steps");

		await toggle.trigger("click");
		expect(w.findAll(".task-row.is-stopped")).toHaveLength(2);
		expect(w.find(".task-row.is-unfinished").exists()).toBe(false);
	});
});
