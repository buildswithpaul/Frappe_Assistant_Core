import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ref } from "vue";
import ProfileSettings from "../ProfileSettings.vue";
import { usePreferences } from "@/composables/usePreferences";

vi.mock("@/composables/useProfileData", () => ({
	useProfileData: () => ({
		loading: ref(false),
		saving: ref(false),
		error: ref(null),
		successMessage: ref(null),
		displayName: ref(""),
		jobTitle: ref(""),
		department: ref(""),
		about: ref(""),
		customInstructions: ref(""),
		locale: ref(""),
		timezone: ref(""),
		isDirty: ref(false),
		aboutLength: ref(0),
		loadProfile: vi.fn(),
		saveProfile: vi.fn(),
	}),
}));

function mountSettings() {
	return mount(ProfileSettings, {
		global: { stubs: { LanguageSelect: true } },
	});
}

function widthToggle(wrapper) {
	const row = wrapper
		.findAll(".setting-item")
		.find((item) => item.find(".setting-label").text() === "Wide chat layout");
	return row.find("input[type='checkbox']");
}

describe("ProfileSettings — Wide chat layout toggle", () => {
	beforeEach(() => {
		localStorage.clear();
		const { preferences } = usePreferences();
		preferences.chatWidth = "wide";
	});

	it("renders the toggle in the Display section, checked when wide", () => {
		const wrapper = mountSettings();
		expect(widthToggle(wrapper).element.checked).toBe(true);
	});

	it("switches to cozy and persists on toggle off", async () => {
		const wrapper = mountSettings();
		await widthToggle(wrapper).setValue(false);
		const { preferences } = usePreferences();
		expect(preferences.chatWidth).toBe("cozy");
		expect(JSON.parse(localStorage.getItem("faco-preferences")).chatWidth).toBe("cozy");
	});

	it("switches back to wide on toggle on", async () => {
		const { preferences } = usePreferences();
		preferences.chatWidth = "cozy";
		const wrapper = mountSettings();
		expect(widthToggle(wrapper).element.checked).toBe(false);
		await widthToggle(wrapper).setValue(true);
		expect(preferences.chatWidth).toBe("wide");
	});
});
