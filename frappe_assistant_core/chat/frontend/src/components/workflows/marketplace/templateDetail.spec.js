import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { useUserStore } from "@/stores/userStore";
import TemplateNeeds from "./TemplateNeeds.vue";
import TemplateMiniGraph from "./TemplateMiniGraph.vue";
import TemplateDetailFooter from "./TemplateDetailFooter.vue";
import TemplateDetailBody from "./TemplateDetailBody.vue";

describe("TemplateNeeds", () => {
	it("lists modules, reports, tools, writes and the ERPNext floor", () => {
		const w = mount(TemplateNeeds, {
			props: {
				requires: {
					modules: ["Accounts"],
					reports: ["Accounts Receivable Summary"],
					tools: ["generate_report"],
					write_tools: ["send_email"],
					min_erpnext: "15",
				},
			},
		});
		const text = w.text();
		for (const s of [
			"Accounts",
			"Accounts Receivable Summary",
			"generate_report",
			"send_email",
			"ERPNext 15",
		]) {
			expect(text).toContain(s);
		}
		expect(w.find(".needs-writes").text()).toContain("approval");
	});

	it("falls back to the legacy tool list", () => {
		const w = mount(TemplateNeeds, {
			props: { requires: null, fallbackTools: ["list_documents"] },
		});
		expect(w.text()).toContain("list_documents");
	});

	it("renders nothing when there is nothing to say", () => {
		const w = mount(TemplateNeeds, { props: { requires: "{bad", fallbackTools: [] } });
		expect(w.html()).toBe("<!--v-if-->");
	});
});

describe("TemplateMiniGraph", () => {
	const graph = {
		nodes: [
			{ id: "in", type: "input", label: "Start" },
			{ id: "t", type: "tool", label: "Run AR report" },
			{ id: "out", type: "output", label: "Brief" },
		],
		edges: [
			{ source: "in", target: "t" },
			{ source: "t", target: "out" },
		],
	};

	it("draws every node and edge, read-only", () => {
		const w = mount(TemplateMiniGraph, { props: { graphJson: JSON.stringify(graph) } });
		expect(w.findAll("rect.mini-node")).toHaveLength(3);
		expect(w.findAll("path.mini-edge")).toHaveLength(2);
		expect(w.get("svg").attributes("role")).toBe("img");
		expect(w.text()).toContain("Run AR report");
	});

	it("lays out nodes that arrive piled at the origin", () => {
		const piled = {
			nodes: graph.nodes.map((n) => ({ ...n, position: { x: 0, y: 0 } })),
			edges: graph.edges,
		};
		const w = mount(TemplateMiniGraph, { props: { graphJson: JSON.stringify(piled) } });
		const xs = new Set(w.findAll("rect.mini-node").map((r) => r.attributes("x")));
		expect(xs.size).toBe(3);
	});

	it("shows a short note instead of crashing on a graph it cannot read", () => {
		const w = mount(TemplateMiniGraph, { props: { graphJson: "{broken" } });
		expect(w.find("svg").exists()).toBe(false);
		expect(w.find(".mini-graph-note").exists()).toBe(true);
	});
});

describe("TemplateDetailFooter", () => {
	beforeEach(() => setActivePinia(createPinia()));

	const mountFooter = (template, admin) => {
		// Production reaches isAdmin through userStore.loadUser (can_use_faco -> is_admin).
		useUserStore().isAdmin = admin;
		return mount(TemplateDetailFooter, { props: { template } });
	};

	it("disables Use for a non-admin on a Workflow listing and says why", async () => {
		const w = mountFooter({ name: "L-1", listing_type: "Workflow" }, false);
		const use = w.get(".btn-primary");
		expect(use.attributes("disabled")).toBeDefined();
		expect(w.find(".use-hint").text()).toContain("administrator");
		await use.trigger("click");
		expect(w.emitted("use")).toBeUndefined();
	});

	it("lets an admin use a Workflow listing", async () => {
		const w = mountFooter({ name: "L-1", listing_type: "Workflow" }, true);
		expect(w.find(".use-hint").exists()).toBe(false);
		await w.get(".btn-primary").trigger("click");
		expect(w.emitted("use")).toHaveLength(1);
	});

	it("keeps Use open to everyone for a Prompt listing", () => {
		const w = mountFooter({ name: "L-2", listing_type: "Prompt" }, false);
		expect(w.get(".btn-primary").attributes("disabled")).toBeUndefined();
	});
});

describe("TemplateDetailBody", () => {
	it("shows needs, the graph and variable labels, and exposes the rating hooks", () => {
		setActivePinia(createPinia());
		const w = mount(TemplateDetailBody, {
			props: {
				template: {
					name: "L-1",
					template_name: "Weekly Collections Brief",
					requires: '{"modules":["Accounts"]}',
					graph_json: JSON.stringify({ nodes: [{ id: "a", type: "tool", label: "Step A" }], edges: [] }),
					variables_schema: JSON.stringify({ to: { label: "Send to", description: "Recipient" } }),
				},
			},
		});
		expect(w.text()).toContain("Accounts");
		expect(w.text()).toContain("Step A");
		expect(w.text()).toContain("Send to");
		expect(typeof w.vm.resetForm).toBe("function");
		expect(typeof w.vm.onRatingComplete).toBe("function");
	});
});
