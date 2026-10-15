import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// The install state is module-level (the browser event fires before any
// component mounts), so each test loads a fresh copy of the module.
async function load({ userAgent = "Mozilla/5.0 (X11; Linux x86_64) Chrome/140", standalone = false } = {}) {
	vi.resetModules();
	vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(userAgent);
	window.matchMedia = vi.fn().mockReturnValue({ matches: standalone });
	const mod = await import("@/composables/usePwaInstall");
	mod.initPwaInstall();
	return mod;
}

function fireInstallPrompt(outcome = "accepted") {
	const event = new Event("beforeinstallprompt");
	event.prompt = vi.fn().mockResolvedValue(undefined);
	event.userChoice = Promise.resolve({ outcome });
	window.dispatchEvent(event);
	return event;
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("usePwaInstall", () => {
	it("offers nothing until the browser says the app can be installed", async () => {
		const { usePwaInstall } = await load();
		expect(usePwaInstall().canInstall.value).toBe(false);
		fireInstallPrompt();
		expect(usePwaInstall().canInstall.value).toBe(true);
		expect(usePwaInstall().needsInstructions.value).toBe(false);
	});

	it("shows the browser prompt once and reports the choice", async () => {
		const { usePwaInstall } = await load();
		const event = fireInstallPrompt("accepted");
		const install = usePwaInstall();
		expect(await install.promptInstall()).toBe(true);
		expect(event.prompt).toHaveBeenCalledTimes(1);
		// A prompt event works once; the item hides until the browser offers another.
		expect(install.canInstall.value).toBe(false);
	});

	it("hides once the app is installed", async () => {
		const { usePwaInstall } = await load();
		fireInstallPrompt();
		window.dispatchEvent(new Event("appinstalled"));
		expect(usePwaInstall().canInstall.value).toBe(false);
	});

	it("offers instructions on iPhone, which has no install prompt", async () => {
		const { usePwaInstall } = await load({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari" });
		expect(usePwaInstall().canInstall.value).toBe(true);
		expect(usePwaInstall().needsInstructions.value).toBe(true);
	});

	it("offers nothing when already running as the installed app", async () => {
		const { usePwaInstall } = await load({
			userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari",
			standalone: true,
		});
		fireInstallPrompt();
		expect(usePwaInstall().canInstall.value).toBe(false);
	});
});
