import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { useUserStore } from "@/stores/userStore";
import TemplateNeeds from "./TemplateNeeds.vue";
import TemplateSteps from "./TemplateSteps.vue";
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

describe("TemplateSteps", () => {
	// The shape of Weekly Collections Brief: the brief waits for the report and the analyst.
	const graph = {
		nodes: [
			{ id: "start", type: "input", label: "Start" },
			{ id: "fetch", type: "tool", label: "Accounts Receivable Summary", config: { tool_name: "generate_report" } },
			{ id: "analyse", type: "agent", label: "Collections analyst" },
			{ id: "report", type: "output", label: "Collections brief" },
			{ id: "gate", type: "transform", label: "Email?" },
			{ id: "check", type: "condition", label: "Has a recipient" },
			{ id: "email", type: "tool", label: "Send email", config: { tool_name: "send_email" } },
		],
		edges: [
			{ source: "start", target: "fetch" },
			{ source: "fetch", target: "analyse" },
			{ source: "fetch", target: "report" },
			{ source: "analyse", target: "report" },
			{ source: "analyse", target: "gate" },
			{ source: "gate", target: "check" },
			{ source: "check", target: "email", condition: "pass" },
		],
	};
	const stages = (g) =>
		mount(TemplateSteps, { props: { graphJson: JSON.stringify(g) } })
			.findAll("li.stage")
			.map((li) => li.findAll(".step-label").map((s) => s.text()));

	it("lists a step after every step it waits for", () => {
		expect(stages(graph)).toEqual([
			["Start"],
			["Accounts Receivable Summary"],
			["Collections analyst"],
			["Collections brief", "Email?"],
			["Has a recipient"],
			["Send email"],
		]);
	});

	it("says what each step does and where a check leads", () => {
		const text = mount(TemplateSteps, { props: { graphJson: graph } }).text();
		for (const s of ["Runs a report", "AI step", "Sends an email", "If yes: Send email", "If no: stops here"]) {
			expect(text).toContain(s);
		}
	});

	it("does not repeat a kind that is already the step's name", () => {
		const w = mount(TemplateSteps, { props: { graphJson: graph } });
		expect(w.findAll(".step")[0].text()).toBe("Start");
	});

	it("lists a cycle after everything else instead of hanging", () => {
		const cyclic = {
			nodes: [
				{ id: "a", type: "input", label: "A" },
				{ id: "b", type: "tool", label: "B" },
				{ id: "c", type: "tool", label: "C" },
			],
			edges: [
				{ source: "a", target: "b" },
				{ source: "b", target: "c" },
				{ source: "c", target: "b" },
			],
		};
		expect(stages(cyclic)).toEqual([["A"], ["B", "C"]]);
	});

	it("gives a huge graph a note instead of hundreds of steps", () => {
		const nodes = Array.from({ length: 200 }, (_, i) => ({ id: `n${i}`, type: "tool", label: `Step ${i}` }));
		const w = mount(TemplateSteps, { props: { graphJson: JSON.stringify({ nodes, edges: [] }) } });
		expect(w.findAll(".step")).toHaveLength(0);
		expect(w.find(".steps-note").text()).toContain("200");
	});

	it("renders nodes that share an id without key warnings", () => {
		const dup = { nodes: [{ id: "a", type: "tool" }, { id: "a", type: "tool" }], edges: [] };
		const w = mount(TemplateSteps, { props: { graphJson: JSON.stringify(dup) } });
		expect(w.findAll(".step")).toHaveLength(2);
	});

	it("shows a short note instead of crashing on a graph it cannot read", () => {
		const w = mount(TemplateSteps, { props: { graphJson: "{broken" } });
		expect(w.find("ol").exists()).toBe(false);
		expect(w.find(".steps-note").exists()).toBe(true);
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
