import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

vi.mock("@/composables/useProfileData", async () => {
	const { ref, computed } = await vi.importActual("vue");
	const state = {
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
		aboutLength: computed(() => 0),
		loadProfile: vi.fn(),
		saveProfile: vi.fn(),
		discardChanges: vi.fn(),
	};
	return { useProfileData: () => state };
});

import { matchedRouteKey } from "vue-router";
import { useProfileData } from "@/composables/useProfileData";
import ProfileSettings from "../ProfileSettings.vue";

const state = useProfileData();
let wrapper = null;
let routeRecord = null;

// Stand in for the <router-view> record so onBeforeRouteLeave registers for real
// and the guard it installs can be exercised.
function mountProfile() {
	routeRecord = { leaveGuards: new Set(), updateGuards: new Set() };
	wrapper = mount(ProfileSettings, {
		global: {
			stubs: { LanguageSelect: true },
			provide: { [matchedRouteKey]: { value: routeRecord } },
		},
	});
	return wrapper;
}

const leaveGuard = () => [...routeRecord.leaveGuards][0];

function pressSave({ meta = false, ctrl = false } = {}) {
	window.dispatchEvent(
		new KeyboardEvent("keydown", { key: "s", metaKey: meta, ctrlKey: ctrl, cancelable: true })
	);
}

beforeEach(() => {
	state.loading.value = false;
	state.saving.value = false;
	state.error.value = null;
	state.successMessage.value = null;
	state.isDirty.value = false;
	state.saveProfile.mockClear();
	state.discardChanges.mockClear();
});

afterEach(() => {
	wrapper?.unmount();
	wrapper = null;
});

describe("ProfileSettings — sticky save bar", () => {
	it("is absent while the form is clean — nothing is pending", () => {
		expect(mountProfile().find(".save-bar").exists()).toBe(false);
	});

	it("appears as soon as the form is dirty", async () => {
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();

		const bar = w.find(".save-bar");
		expect(bar.exists()).toBe(true);
		expect(bar.text()).toContain("Unsaved changes");
	});

	it("saves on click", async () => {
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();

		await w.find(".save-btn").trigger("click");
		expect(state.saveProfile).toHaveBeenCalledTimes(1);
	});

	it("discards on click", async () => {
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();

		await w.find(".discard-btn").trigger("click");
		expect(state.discardChanges).toHaveBeenCalledTimes(1);
	});

	it("stays visible while saving, with the button locked", async () => {
		const w = mountProfile();
		state.saving.value = true;
		await w.vm.$nextTick();

		const btn = w.find(".save-btn");
		expect(btn.exists()).toBe(true);
		expect(btn.attributes("disabled")).toBeDefined();
		expect(btn.text()).toContain("Saving");
	});

	it("reports success in the bar instead of a banner above the fold", async () => {
		const w = mountProfile();
		state.successMessage.value = "Profile saved";
		await w.vm.$nextTick();

		expect(w.find(".save-bar").text()).toContain("Profile saved");
	});

	it("saves on Cmd+S and Ctrl+S while dirty", async () => {
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();

		pressSave({ meta: true });
		pressSave({ ctrl: true });
		expect(state.saveProfile).toHaveBeenCalledTimes(2);
	});

	it("leaves Cmd+S alone while the form is clean", () => {
		mountProfile();
		pressSave({ meta: true });
		expect(state.saveProfile).not.toHaveBeenCalled();
	});

	it("stops listening for Cmd+S once unmounted", async () => {
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();
		w.unmount();
		wrapper = null;

		pressSave({ meta: true });
		expect(state.saveProfile).not.toHaveBeenCalled();
	});
});

describe("ProfileSettings — unsaved-changes guard", () => {
	afterEach(() => vi.unstubAllGlobals());

	it("lets navigation through when the form is clean", () => {
		mountProfile();
		expect(leaveGuard()()).toBe(true);
	});

	it("asks before dropping unsaved edits, and blocks on cancel", async () => {
		const confirm = vi.fn().mockReturnValue(false);
		vi.stubGlobal("confirm", confirm);
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();

		expect(leaveGuard()()).toBe(false);
		expect(confirm).toHaveBeenCalledOnce();
	});

	it("allows the navigation when the user confirms", async () => {
		vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
		const w = mountProfile();
		state.isDirty.value = true;
		await w.vm.$nextTick();

		expect(leaveGuard()()).toBe(true);
	});
});

describe("ProfileSettings — scope after the Appearance split", () => {
	it("keeps only the three server-backed sections", () => {
		const titles = mountProfile()
			.findAll(".section-title")
			.map((t) => t.text());
		expect(titles).toEqual(["About You", "AI Instructions", "Language & Region"]);
	});

	it("no longer renders the per-browser display toggles", () => {
		expect(mountProfile().findAll(".setting-item")).toHaveLength(0);
	});
});
