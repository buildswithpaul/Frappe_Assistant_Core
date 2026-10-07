import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import WidgetPlanStrip from "./WidgetPlanStrip.vue";

const mountStrip = (props) => mount(WidgetPlanStrip, { props });
const labels = (w) => w.findAll(".activity").map((n) => n.text());

describe("WidgetPlanStrip", () => {
	it("heads two running helpers as parallel work and shows both live labels when opened", async () => {
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
		expect(w.find(".wps-status").text()).toBe("⠿ Running 2 in parallel · 0 of 2 done");
		await w.find(".wps-heading").trigger("click");
		expect(labels(w)).toEqual(["Reading Sales Invoice list…", "Opening Customer B…"]);
	});

	it("heads main-agent work as working through the plan's steps", async () => {
		const w = mountStrip({
			plan: {
				tasks: [
					{ id: "1", title: "Inspect fields", status: "running" },
					{ id: "2", title: "Create the invoice", status: "pending" },
				],
			},
			live: true,
		});
		expect(w.find(".wps-status").text()).toBe("⠿ Working through 2 steps · 0 of 2 done");
		await w.find(".wps-heading").trigger("click");
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

// The strip used to list every row while the turn ran, so four helpers and the
// label took half the panel. It is now one status line, expandable on demand.
describe("WidgetPlanStrip one-line status", () => {
	const parallelPlan = {
		tasks: [
			{ id: "1", title: "Plan the comparison", status: "done" },
			{ id: "a", title: "Customer A", status: "running", helper: true },
			{ id: "b", title: "Customer B", status: "running", helper: true },
			{ id: "c", title: "Customer C", status: "pending", helper: true },
		],
	};

	it("collapses a running parallel turn to counts and the latest helper label", async () => {
		const w = mountStrip({ plan: parallelPlan, live: true, activity: {} });
		// Two task_activity events in one tick: B, then A. Vue delivers one change, and the key
		// order (A first reported) cannot tell which came last; chatStore.lastActivityTaskId can.
		await w.setProps({
			activity: { a: "Reading Sales Invoice list…", b: "Opening Customer B…" },
			latestActivityId: "a",
		});

		const line = w.find(".wps-heading");
		expect(line.find(".wps-status").text()).toBe("⠿ Running 2 in parallel · 1 of 4 done");
		expect(line.find(".wps-activity").text()).toBe("— Reading Sales Invoice list…");
		expect(line.classes()).toContain("wps-oneline");
		expect(line.attributes("aria-expanded")).toBe("false");
		expect(w.find(".task-row").exists()).toBe(false);
	});

	it("shows the latest reporter even when it is not the first running helper", () => {
		const w = mountStrip({
			plan: parallelPlan,
			live: true,
			activity: { a: "Reading Sales Invoice list…", b: "Opening Customer B…" },
			latestActivityId: "b",
		});
		expect(w.find(".wps-activity").text()).toBe("— Opening Customer B…");
	});

	it("falls back to another running helper once the latest one has finished", () => {
		const plan = {
			tasks: parallelPlan.tasks.map((task) => (task.id === "a" ? { ...task, status: "done" } : task)),
		};
		const w = mountStrip({
			plan,
			live: true,
			activity: { b: "Opening Customer B…", a: "Reading Sales Invoice list…" },
			latestActivityId: "a",
		});
		expect(w.find(".wps-activity").text()).toBe("— Opening Customer B…");
	});

	it("announces the status from a live region outside the button, only while running", async () => {
		const w = mountStrip({ plan: parallelPlan, live: true });
		expect(w.find(".wps-heading [aria-live]").exists()).toBe(false);
		expect(w.find(".wps-live").attributes("aria-live")).toBe("polite");
		expect(w.find(".wps-live").text()).toBe("⠿ Running 2 in parallel · 1 of 4 done");

		await w.setProps({ live: false });
		expect(w.find(".wps-live").exists()).toBe(false);
	});

	it("names the running row when there is no parallel work or label", () => {
		const w = mountStrip({
			plan: {
				tasks: [
					{ id: "1", title: "Inspect fields", status: "done" },
					{ id: "2", title: "Create the invoice", status: "running" },
				],
			},
			live: true,
		});
		expect(w.find(".wps-status").text()).toBe("⠿ Working through 2 steps · 1 of 2 done");
		expect(w.find(".wps-activity").text()).toBe("— Create the invoice");
	});

	it("expands and collapses the rows on click, keeping live labels", async () => {
		const w = mountStrip({ plan: parallelPlan, live: true, activity: { a: "Reading…" } });
		const line = w.find(".wps-heading");

		await line.trigger("click");
		expect(line.attributes("aria-expanded")).toBe("true");
		expect(w.findAll(".task-row")).toHaveLength(4);
		expect(labels(w)).toEqual(["Reading…"]);

		await line.trigger("click");
		expect(line.attributes("aria-expanded")).toBe("false");
		expect(w.find(".task-row").exists()).toBe(false);
	});

	it("keeps the paused, stopped and finished lines as they read", () => {
		const tasks = [
			{ id: "1", title: "A", status: "done" },
			{ id: "2", title: "B", status: "running" },
		];
		const heading = (props) => mountStrip({ plan: { tasks }, ...props }).find(".wps-heading");
		for (const [props, text] of [
			[{ live: false, waitingOn: "approval" }, "Waiting for your approval…"],
			[{ live: false, stopped: true }, "⊘ Stopped after 1 of 2 steps"],
			[{ live: false }, "✓ Completed 1 of 2 steps"],
		]) {
			const line = heading(props);
			expect(line.text()).toBe(text);
			expect(line.attributes("aria-expanded")).toBe("false");
			expect(line.find(".wps-activity").exists()).toBe(false);
		}
	});
});
