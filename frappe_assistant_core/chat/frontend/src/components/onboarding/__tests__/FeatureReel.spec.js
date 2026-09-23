import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import FeatureReel from "@/components/onboarding/FeatureReel.vue";
import { useUserStore } from "@/stores/userStore";

function mountReel(props = {}) {
	return mount(FeatureReel, {
		props,
		global: {
			stubs: {
				IntroMockup: true,
				KnowledgeMockup: true,
				VoiceMockup: true,
				PrivacyMockup: true,
				OutroMockup: true,
				FacoRobot: true,
			},
		},
	});
}

function setMatchMedia(reduce) {
	window.matchMedia = vi.fn().mockImplementation((q) => ({
		matches: q.includes("reduce") ? reduce : false,
		media: q,
		addEventListener: () => {},
		removeEventListener: () => {},
	}));
}

describe("FeatureReel", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		setMatchMedia(false);
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("renders five scenes when memory is enabled, including voice", () => {
		const store = useUserStore();
		store.memoryEnabled = true;
		store.workflowsEnabled = true;
		const wrapper = mountReel();
		expect(wrapper.findAll("[data-scene-pill]")).toHaveLength(5);
		const ids = wrapper.findAll("[data-scene-pill]").map((p) => p.attributes("data-scene-id"));
		expect(ids).toEqual(["intro", "knowledge", "voice", "privacy", "outro"]);
	});

	it("always shows the privacy scene advertising zero data retention", () => {
		const store = useUserStore();
		store.memoryEnabled = false;
		store.workflowsEnabled = false;
		const wrapper = mountReel();
		const ids = wrapper.findAll("[data-scene-pill]").map((p) => p.attributes("data-scene-id"));
		expect(ids).toContain("privacy");
	});

	it("hides the knowledge scene when memory app is not installed", () => {
		const store = useUserStore();
		store.memoryEnabled = false;
		const wrapper = mountReel();
		const ids = wrapper.findAll("[data-scene-pill]").map((p) => p.attributes("data-scene-id"));
		expect(ids).not.toContain("knowledge");
		expect(ids).toEqual(["intro", "voice", "privacy", "outro"]);
	});

	it("keeps voice but drops team and workflows from the reel", () => {
		const store = useUserStore();
		store.memoryEnabled = true;
		store.workflowsEnabled = true;
		const wrapper = mountReel();
		const ids = wrapper.findAll("[data-scene-pill]").map((p) => p.attributes("data-scene-id"));
		expect(ids).toContain("voice");
		expect(ids).not.toContain("team");
		expect(ids).not.toContain("workflows");
	});

	it("emits complete when the Skip intro button is clicked", async () => {
		const wrapper = mountReel();
		await wrapper.find("[data-skip]").trigger("click");
		expect(wrapper.emitted("complete")).toBeTruthy();
	});

	it("auto-advances through scenes and emits complete after the last scene", async () => {
		const store = useUserStore();
		store.memoryEnabled = true;
		const wrapper = mountReel();

		// intro 4500 + knowledge 5500 → past both at 10001 → voice (index 2)
		vi.advanceTimersByTime(10001);
		await flushPromises();
		expect(wrapper.vm.currentIndex).toBe(2);
		expect(wrapper.emitted("complete")).toBeFalsy();

		// voice 5500 + privacy 5000 + outro 4000
		vi.advanceTimersByTime(14500);
		await flushPromises();
		expect(wrapper.emitted("complete")).toBeTruthy();
	});

	it("pause stops the auto-advance timer", async () => {
		const wrapper = mountReel();
		await wrapper.find("[data-pause]").trigger("click");
		vi.advanceTimersByTime(60000);
		await flushPromises();
		expect(wrapper.emitted("complete")).toBeFalsy();
	});

	it("renders static stack layout when prefers-reduced-motion matches", () => {
		setMatchMedia(true);
		const wrapper = mountReel();
		expect(wrapper.find("[data-static-stack]").exists()).toBe(true);
		expect(wrapper.find("[data-skip]").exists()).toBe(false);
	});

	it("emits complete immediately when fewer than 2 scenes remain after gating", () => {
		const wrapper = mountReel({ minScenesRequired: 99 });
		expect(wrapper.emitted("complete")).toBeTruthy();
	});
});
