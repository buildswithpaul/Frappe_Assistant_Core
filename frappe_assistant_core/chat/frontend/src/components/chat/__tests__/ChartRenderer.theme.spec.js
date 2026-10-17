import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("vue-echarts", () => ({
	default: {
		name: "VChart",
		props: ["option", "autoresize"],
		template: "<div class='v-chart-stub' />",
	},
}));

import ChartRenderer from "@/components/chat/ChartRenderer.vue";

const ExpandableStub = { name: "ExpandableArtifact", template: "<div><slot /></div>" };

// quiet-ledger.css sets these on <html data-theme="dark"> in the dark theme.
const DARK = {
	"--ql-text": "#F2EFE6",
	"--ql-text-secondary": "#B7B2A4",
	"--ql-text-muted": "#8A857C",
	"--ql-border": "#2E2C22",
	"--ql-surface": "#1E1D16",
};

function chartOption(config, attachTo) {
	const w = mount(ChartRenderer, {
		props: { config },
		attachTo,
		global: { stubs: { ExpandableArtifact: ExpandableStub } },
	});
	return flushPromises().then(() => w.findComponent({ name: "VChart" }).props("option"));
}

const PIE = {
	type: "pie",
	title: "Sales Share by Company",
	data: { categories: ["WoodCraft", "PierSight"], series: [{ name: "Sales", values: [75, 25] }] },
};

describe("ChartRenderer follows the page theme", () => {
	beforeEach(() => {
		const root = document.documentElement;
		root.setAttribute("data-theme", "dark");
		for (const [name, value] of Object.entries(DARK)) root.style.setProperty(name, value);
	});

	afterEach(() => {
		const root = document.documentElement;
		root.removeAttribute("data-theme");
		for (const name of Object.keys(DARK)) root.style.removeProperty(name);
	});

	// Live-bug repro (MSG-2026-00872): unthemed, ECharts gave pie labels dark
	// text with a white halo, which on the dark surface read as smeared bold.
	it("draws pie labels in the theme text colour with no halo", async () => {
		const label = (await chartOption(PIE)).series[0].label;
		expect(label.color).toBe(DARK["--ql-text"]);
		expect(label.textBorderWidth).toBe(0);
	});

	it("themes the title, legend and axes", async () => {
		const option = await chartOption({
			type: "bar",
			title: "Monthly Sales",
			data: { categories: ["Jun", "Jul"], series: [{ name: "Sales", values: [238, 216] }] },
		});
		expect(option.title.textStyle.color).toBe(DARK["--ql-text"]);
		expect(option.legend.textStyle.color).toBe(DARK["--ql-text-secondary"]);
		expect(option.xAxis.axisLabel.color).toBe(DARK["--ql-text-muted"]);
		expect(option.yAxis.splitLine.lineStyle.color).toBe(DARK["--ql-border"]);
	});
});

// The Desk widget mounts the same components in a shadow root, and its build
// retargets the theme tokens from :root to :host — so on a Desk page <html>
// carries no --ql-* values and only the host does (widget/panel/main.js).
describe("ChartRenderer inside the Desk widget's shadow root", () => {
	let host;

	beforeEach(() => {
		document.documentElement.setAttribute("data-theme", "dark");
		host = document.createElement("div");
		host.setAttribute("data-theme", "dark");
		for (const [name, value] of Object.entries(DARK)) host.style.setProperty(name, value);
		document.body.appendChild(host);
	});

	afterEach(() => {
		host.remove();
		document.documentElement.removeAttribute("data-theme");
	});

	it("reads the theme from the host, not from <html>", async () => {
		const mountPoint = document.createElement("div");
		host.attachShadow({ mode: "open" }).appendChild(mountPoint);
		const label = (await chartOption(PIE, mountPoint)).series[0].label;
		expect(label.color).toBe(DARK["--ql-text"]);
	});
});
