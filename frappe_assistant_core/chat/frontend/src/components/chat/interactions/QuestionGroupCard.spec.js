import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

import QuestionGroupCard from "./QuestionGroupCard.vue";

// Three parallel ask_user calls, as the stream delivers them: one pending card each.
function questions() {
	return [
		{
			id: "q1",
			type: "interaction",
			interactionType: "single_select",
			status: "pending",
			question: "Which company should the report cover?",
			options: ["Northwind Demo Co", "Southwind Ltd"],
			interrupts: [{ id: "i1" }],
		},
		{
			id: "q2",
			type: "interaction",
			interactionType: "multi_select",
			status: "pending",
			question: "Which columns?",
			options: ["Customer", "Amount", "Due date"],
			interrupts: [{ id: "i2" }],
		},
		{
			id: "q3",
			type: "interaction",
			interactionType: "confirm",
			status: "pending",
			question: "Include draft invoices?",
			interrupts: [{ id: "i3" }],
		},
	];
}

function mountGroup(blocks = questions(), props = {}) {
	return mount(QuestionGroupCard, { props: { blocks, ...props }, attachTo: document.body });
}

const pill = (wrapper, label) => wrapper.findAll(".pill").find((p) => p.text().includes(label));
const sendButton = (wrapper) => wrapper.find(".qg-send");
const answeredRow = (wrapper, id) => wrapper.find(`[data-question-id="${id}"] .qg-done`);

async function answerAll(wrapper) {
	await pill(wrapper, "Northwind Demo Co").trigger("click");
	await wrapper.find('[data-question-id="q2"] input[value="Amount"]').setValue(true);
	await wrapper.find('[data-question-id="q2"] .submit-btn').trigger("click");
	await wrapper.findAll('[data-question-id="q3"] .ql-btn').find((b) => b.text() === "No").trigger("click");
}

describe("QuestionGroupCard", () => {
	it("says how many questions there are and opens only the first", () => {
		const wrapper = mountGroup();
		expect(wrapper.find(".qg-title").text()).toBe("3 questions");
		expect(wrapper.findAll(".qg-open")).toHaveLength(1);
		expect(wrapper.find('[data-question-id="q1"] .qg-open').exists()).toBe(true);
		expect(wrapper.find(".qg-count").text()).toBe("0 of 3 answered");
	});

	it("folds an answered question into a line with the answer and opens the next", async () => {
		const wrapper = mountGroup();
		await pill(wrapper, "Northwind Demo Co").trigger("click");

		const row = answeredRow(wrapper, "q1");
		expect(row.find(".qg-a").text()).toBe("Northwind Demo Co");
		expect(row.find(".qg-change").exists()).toBe(true);
		expect(wrapper.find('[data-question-id="q2"] .qg-open').exists()).toBe(true);
		expect(wrapper.find(".qg-count").text()).toBe("1 of 3 answered");
	});

	it("sends nothing and keeps Send disabled until every question has an answer", async () => {
		const wrapper = mountGroup();
		await pill(wrapper, "Northwind Demo Co").trigger("click");
		expect(sendButton(wrapper).attributes("disabled")).toBeDefined();
		expect(wrapper.emitted("approve")).toBeUndefined();
	});

	it("reopens a question with its answer still selected when Change is pressed", async () => {
		const wrapper = mountGroup();
		await pill(wrapper, "Northwind Demo Co").trigger("click");
		await answeredRow(wrapper, "q1").find(".qg-change").trigger("click");

		expect(wrapper.find('[data-question-id="q1"] .qg-open').exists()).toBe(true);
		expect(pill(wrapper, "Northwind Demo Co").classes()).toContain("selected");
	});

	it("sends every answer, one decision per question in order, when Send is pressed", async () => {
		const wrapper = mountGroup();
		await answerAll(wrapper);
		expect(wrapper.find(".qg-count").text()).toBe("3 of 3 answered");

		await sendButton(wrapper).trigger("click");

		expect(wrapper.emitted("approve")).toEqual([
			["q1", [{ interruptId: "i1", response: "Northwind Demo Co" }]],
			["q2", [{ interruptId: "i2", response: ["Amount"] }]],
			["q3", [{ interruptId: "i3", response: "no" }]],
		]);
	});

	it("moves focus to the next question after an answer", async () => {
		const wrapper = mountGroup();
		await pill(wrapper, "Northwind Demo Co").trigger("click");
		await new Promise((resolve) => setTimeout(resolve));
		const next = wrapper.find('[data-question-id="q2"]').element;
		expect(next.contains(document.activeElement)).toBe(true);
		wrapper.unmount();
	});

	it("shows a read-only record once the answers are in", () => {
		const blocks = questions().map((b, i) => ({
			...b,
			status: "answered",
			userResponse: ["Northwind Demo Co", ["Customer", "Amount"], "yes"][i],
		}));
		const wrapper = mountGroup(blocks);

		expect(wrapper.findAll(".qg-a").map((a) => a.text())).toEqual([
			"Northwind Demo Co",
			"Customer, Amount",
			"Yes",
		]);
		expect(wrapper.find(".qg-change").exists()).toBe(false);
		expect(wrapper.find(".qg-send").exists()).toBe(false);
	});

	it("locks Change and Send while the answers are being sent", async () => {
		const wrapper = mountGroup();
		await answerAll(wrapper);
		await wrapper.setProps({ submitting: true });
		expect(sendButton(wrapper).attributes("disabled")).toBeDefined();
		expect(wrapper.find(".qg-change").exists()).toBe(false);
	});
});
