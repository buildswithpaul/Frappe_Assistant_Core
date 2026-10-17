import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import InputArea from "../InputArea.vue";

const mountArea = (props = {}) =>
	mount(InputArea, {
		props,
		global: { stubs: { MicButton: true, SlashMenu: true, AttachedFilePreview: true } },
	});
const placeholder = (w) => w.find("textarea").attributes("placeholder");

describe("InputArea placeholder prop", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("keeps the default when none is given", () => {
		expect(placeholder(mountArea())).toBe("Ask me anything…");
	});

	it("replaces the idle placeholder", () => {
		expect(placeholder(mountArea({ placeholder: "Ask about this Customer…" }))).toBe("Ask about this Customer…");
	});

	it("does not override the streaming or question states", () => {
		expect(placeholder(mountArea({ placeholder: "X", isStreaming: true }))).toContain("Assistant is responding");
		expect(placeholder(mountArea({ placeholder: "X", interactionMode: "question" }))).toBe("Type your answer…");
	});
});
