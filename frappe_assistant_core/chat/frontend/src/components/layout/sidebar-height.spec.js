import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (p) => readFileSync(join(__dirname, p), "utf8");

// The app shell (App.vue) is a fixed full-viewport flex column with
// NotificationHost as a sibling above <router-view>. When a banner is showing,
// every route root is therefore shorter than the viewport by the banner's height.
//
// Route roots survive that on their own: they sit in a COLUMN flex container,
// where `height` is the main size and flexbox shrinks it to fit. The sidebar
// does not — it sits in a ROW container, where `height` is the cross size and an
// explicit value overrides `align-items: stretch`, so nothing shrinks it. A
// viewport-pinned height there overflows `.app-layout`, whose `overflow: hidden`
// silently clips the bottom (measured: user section 41px below the fold).
//
// jsdom injects no scoped CSS, so `getComputedStyle` cannot see this. The guard
// has to be on the source text.
describe("sidebar fills its parent, not the viewport", () => {
	it("does not pin .navigation-sidebar to viewport height", () => {
		const base = read("./NavigationSidebar.vue").match(
			/\.navigation-sidebar\s*\{([\s\S]*?)\}/
		);
		expect(base).not.toBeNull();
		expect(base[1]).not.toMatch(/height:\s*100vh/);
		expect(base[1]).toMatch(/height:\s*100%/);
	});

	it("keeps every route root shorter than the viewport when a banner shows", () => {
		// `overflow: hidden` on the route root is what makes the clip silent, so
		// each root must also leave the viewport height to the app shell alone.
		for (const view of [
			"../../views/ChatView.vue",
			"../../views/SettingsView.vue",
			"../../views/AnalyticsView.vue",
			"../../views/KnowledgeBase.vue",
			"../../views/WorkflowList.vue",
		]) {
			const block = read(view).match(/\.app-layout\s*\{([\s\S]*?)\}/);
			expect(block, view).not.toBeNull();
			expect(block[1], view).toMatch(/overflow:\s*hidden/);
			expect(block[1], view).toMatch(/height:\s*100%/);
			expect(block[1], view).not.toMatch(/height:\s*100(vh|dvh|svh)/);
		}
	});

	it("pins viewport height on the app shell, not ChatView", () => {
		const app = read("../../App.vue");
		expect(app).toMatch(/\.app-root\s*\{/);
		expect(app).toMatch(/position:\s*fixed/);
		expect(app).not.toMatch(/\bh-screen\b/);
		const chat = read("../../views/ChatView.vue");
		expect(chat).not.toMatch(/height:\s*100vh/);
		expect(chat).not.toMatch(/height:\s*100dvh/);
	});

	it("does not collapse the Chat drawer on phones — that hid nav labels and recent chats", () => {
		const init = read("../../composables/useChatViewInit.js");
		const actions = read("../../composables/useChatSessionActions.js");
		expect(init).not.toMatch(/sidebarCollapsed\.value\s*=\s*true/);
		expect(actions).not.toMatch(/sidebarCollapsed\.value\s*=\s*true/);
	});

	it("keeps ChatView as a flex shell at drawer widths so the transcript can scroll", () => {
		const src = read("../../views/ChatView.vue");
		expect(src).toMatch(/@media \(max-width: 1023px\)/);
		const mobile = src.match(/@media \(max-width: 1023px\) \{([\s\S]*?)\n\/\* Let the chat column/);
		expect(mobile).not.toBeNull();
		expect(mobile[1]).not.toMatch(/display:\s*block/);
		expect(mobile[1]).toMatch(/composer-dock-enter[\s\S]*padding-bottom:\s*0\.5rem/);
	});

	it("lets the chat column shrink on tablet tab-mode widths, not only phones", () => {
		const src = read("../../views/ChatView.vue");
		const main = src.match(/\.main-content\s*\{([\s\S]*?)\}/);
		const area = src.match(/\.chat-area\s*\{([\s\S]*?)\}/);
		expect(main?.[1]).toMatch(/min-height:\s*0/);
		expect(area?.[1]).toMatch(/min-height:\s*0/);
		const app = read("../../App.vue");
		expect(app).toMatch(/useVisualViewportFrame/);
		expect(app).toMatch(/100svh/);
	});

	it("lets Settings pages scroll on phone and tablet (bounded overflow)", () => {
		const src = read("../../views/SettingsView.vue");
		const content = src.match(/\.settings-content\s*\{([\s\S]*?)\}/);
		expect(content?.[1]).toMatch(/position:\s*absolute/);
		expect(content?.[1]).toMatch(/overflow-y:\s*auto/);
		expect(content?.[1]).toMatch(/-webkit-overflow-scrolling:\s*touch/);
		expect(content?.[1]).not.toMatch(/overflow-x:\s*hidden/);
		expect(src).not.toMatch(/\.settings-shell\.mobile-drill\s*\{\s*display:\s*block/);
		expect(src).toMatch(/@media \(max-width: 1023px\)/);
	});

	it("keeps the drawer scrim under the sidebar so menu taps land", () => {
		const src = read("./NavigationSidebar.vue");
		expect(src).not.toMatch(/<Teleport/);
		expect(src).toMatch(/z-index:\s*40/);
		expect(src).toMatch(/z-index:\s*50/);
	});
});
