import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import ProjectContext from "@/components/projects/ProjectContext.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const stubs = {
	ProjectInstructions: { template: "<div data-test='instructions' />" },
	ProjectDocuments: { template: "<div data-test='project-documents' />" },
	ProjectMemory: { template: "<div data-test='project-memory' />" },
};

const mountCtx = (props) =>
	mount(ProjectContext, {
		props: { projectId: "p1", instructions: "", saveInstructions: async () => {}, ...props },
		global: { stubs },
	});

const order = (w) => w.findAll("[data-test]").map((n) => n.attributes("data-test"));

describe("ProjectContext", () => {
	it("stacks Instructions, Documents and Memory in that order", () => {
		const w = mountCtx({ documentsEnabled: true, memoryEnabled: true });
		expect(order(w)).toEqual(["instructions", "project-documents", "project-memory"]);
	});

	it("hides Documents when its gate is off", () => {
		const w = mountCtx({ documentsEnabled: false, memoryEnabled: true });
		expect(order(w)).toEqual(["instructions", "project-memory"]);
	});

	it("hides Memory when its gate is off", () => {
		const w = mountCtx({ documentsEnabled: true, memoryEnabled: false });
		expect(order(w)).toEqual(["instructions", "project-documents"]);
	});
});
