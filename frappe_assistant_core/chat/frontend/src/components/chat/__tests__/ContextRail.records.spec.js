import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import ContextRail from "../ContextRail.vue";
import { deriveArtifacts } from "@/utils/contextArtifacts";

const mountRail = (blocks) =>
	mount(ContextRail, { props: { artifacts: deriveArtifacts(blocks), live: false } });

const created = (result) => ({
	type: "tool_call",
	id: "t1",
	tool_name: "create_document",
	status: "success",
	input: { doctype: "Server Script", data: { script: "x" } },
	result,
});

describe("ContextRail records", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("record chip links when result has url", () => {
		const wrapper = mountRail([created({ name: "Discount limit", url: "/desk/server-script/Discount%20limit" })]);
		const link = wrapper.find("a.rail-chip");
		expect(link.attributes("href")).toBe("/desk/server-script/Discount%20limit");
		expect(link.attributes("target")).toBe("_blank");
		expect(link.attributes("rel")).toBe("noopener");
	});

	it("record chip without url stays a label", () => {
		const wrapper = mountRail([created('{"name":"Discount limit","ur')]);
		expect(wrapper.find("a.rail-chip").exists()).toBe(false);
		expect(wrapper.find(".rail-chip-label").text()).toBe("Server Script");
	});

	it("never links an unsafe url", () => {
		const wrapper = mountRail([created({ name: "X", url: "javascript:alert(1)" })]);
		expect(wrapper.find("a.rail-chip").exists()).toBe(false);
	});

	it("create chip shows the created name from result", () => {
		const wrapper = mountRail([created({ name: "Discount limit", url: "/desk/server-script/Discount%20limit" })]);
		expect(wrapper.find(".rail-chip-label").text()).toBe("Server Script: Discount limit");
	});
});

describe("ContextRail open link", () => {
	beforeEach(() => setActivePinia(createPinia()));

	const field = (result) => ({
		type: "tool_call",
		id: "f1",
		tool_name: "create_document",
		status: "success",
		input: { doctype: "Custom Field", data: { dt: "Customer" } },
		result,
	});

	it("offers a link to a new form of the doctype the change applies to", () => {
		const wrapper = mountRail([field({ name: "Customer-po", url: "/desk/custom-field/Customer-po", applies_to: { doctype: "Customer", url: "/desk/customer/new" } })]);
		const link = wrapper.find("a.rail-chip-open");
		expect(link.text()).toBe("Open a new Customer");
		expect(link.attributes("href")).toBe("/desk/customer/new");
		expect(link.attributes("target")).toBe("_blank");
		expect(link.attributes("rel")).toBe("noopener");
	});

	it("has no link without applies_to or with an unsafe url", () => {
		expect(mountRail([field({ name: "Customer-po" })]).find("a.rail-chip-open").exists()).toBe(false);
		const unsafe = field({ name: "Customer-po", applies_to: { doctype: "Customer", url: "javascript:alert(1)" } });
		expect(mountRail([unsafe]).find("a.rail-chip-open").exists()).toBe(false);
	});
});

describe("ContextRail pending interaction", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("question interaction labelled as question", () => {
		const question = "Which warehouse should the discount rule apply to, and for which customers exactly?";
		const wrapper = mountRail([
			{ type: "interaction", id: "q1", status: "pending", interactionType: "confirm", tool_name: "ask_user", question, input: {} },
		]);
		expect(wrapper.find(".rail-approval-count").text()).toBe("1 question waiting");
		expect(wrapper.find(".rail-approval-title").text()).toBe(question.slice(0, 60));
		expect(wrapper.text()).not.toContain("Ask User");
	});

	it("approval interaction keeps its approval wording", () => {
		const wrapper = mountRail([
			{ type: "interaction", id: "a1", status: "pending", interactionType: "approval", tool_name: "create_document", input: {} },
		]);
		expect(wrapper.find(".rail-approval-count").text()).toBe("1 approval waiting");
		expect(wrapper.find(".rail-approval-title").text()).toBe("Create Document");
	});
});
