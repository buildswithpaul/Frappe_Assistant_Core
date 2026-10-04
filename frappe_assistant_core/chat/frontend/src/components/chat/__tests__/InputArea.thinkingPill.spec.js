import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import InputArea from "../InputArea.vue";
import { useModelStore } from "@/stores/modelStore";
import { useComposerModesStore } from "@/stores/composerModesStore";
import { useChatStore } from "@/stores/chatStore";

const REASONER = {
	model_id: "m1",
	tier: "standard",
	thinking_effective: true,
	reasoning_levels: ["off", "low", "high"],
};
const PLAIN = { model_id: "m2", tier: "standard", thinking_effective: false, reasoning_levels: ["off"] };

function mountArea() {
	return mount(InputArea, {
		global: { stubs: { MicButton: true, SlashMenu: true, AttachedFilePreview: true } },
	});
}

function pillText(wrapper) {
	return wrapper.find("[data-thinking-trigger] .pill-label").text();
}

describe("InputArea thinking pill", () => {
	let modes;
	let models;

	beforeEach(() => {
		localStorage.clear();
		setActivePinia(createPinia());
		modes = useComposerModesStore();
		models = useModelStore();
		modes.setEffort(useChatStore().currentSessionId, "high");
	});

	it("shows a plain label while the model list is still loading", () => {
		models.models = [];
		expect(pillText(mountArea())).toBe("Thinking");
	});

	it("names the level on a model that thinks", () => {
		models.models = [REASONER];
		models.selectedModel = "m1";
		expect(pillText(mountArea())).toBe("Thinking: High");
	});

	it("shows a plain label when the model cannot think", () => {
		models.models = [PLAIN];
		models.selectedModel = "m2";
		expect(pillText(mountArea())).toBe("Thinking");
	});
});
