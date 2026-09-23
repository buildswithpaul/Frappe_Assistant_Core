<template>
	<div class="app-layout">
		<NavigationSidebar
			:collapsed="navCollapsed"
			@open-settings="$router.push('/settings')"
			@toggle-sidebar="navCollapsed = !navCollapsed"
		/>

		<main class="main-content">
			<!-- Drawer-width top bar so the app nav drawer is reachable from settings
			     (settings has no other top bar with a hamburger). Shown whenever the
			     app sidebar is off-canvas (< 1024px). -->
			<header v-if="isMobile || isTablet" class="settings-topbar">
				<button
					class="sidebar-toggle-btn"
					@click="onHamburger()"
					aria-label="Open navigation"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 6h16M4 12h16M4 18h16"
						/>
					</svg>
				</button>
				<span class="settings-topbar-title">{{ isLeaf ? leafTitle : "Settings" }}</span>
			</header>

			<div class="settings-shell" :class="{ 'mobile-drill': isMobile }">
				<SettingsSidebar v-if="showMenu" class="settings-menu-pane" />
				<section v-if="showContent" class="settings-content">
					<button
						v-if="isMobile && isLeaf"
						class="settings-back"
						@click="$router.push('/settings')"
					>
						<span aria-hidden="true">‹</span> Settings
					</button>
					<div class="settings-inner">
						<router-view v-slot="{ Component }">
							<component :is="Component" />
						</router-view>
					</div>
				</section>
			</div>
		</main>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import SettingsSidebar from "@/components/settings/layout/SettingsSidebar.vue";
import { useIsMobile } from "@/composables/useIsMobile";
import { useNavToggle } from "@/composables/useNavToggle";

const navCollapsed = ref(false);
const route = useRoute();
const router = useRouter();
const { isMobile, isTablet } = useIsMobile();
const { onHamburger } = useNavToggle();

// On a leaf route (e.g. /settings/profile) show content; at the bare index show
// the menu. On desktop/tablet both panes always show (classic 2/3-pane).
const isLeaf = computed(() => route.path !== "/settings" && route.path !== "/settings/");
const showMenu = computed(() => !isMobile.value || !isLeaf.value);
const showContent = computed(() => !isMobile.value || isLeaf.value);

// Title shown in the mobile top bar for the active leaf.
const leafTitles = {
	profile: "Profile",
	appearance: "Appearance",
	privacy: "Privacy & Data",
	"my-tickets": "Support",
	memory: "Memory",
	routing: "Model routing",
	users: "Users",
	packs: "Industry Packs",
	"my-packs": "My Packs",
	billing: "Billing",
	workspace: "Workspace",
};
const leafTitle = computed(() => {
	const seg = route.path.split("/")[2] || "";
	return leafTitles[seg] || "Settings";
});

// Desktop/tablet keep the old default-landing behaviour: the bare /settings
// forwards to the first leaf. Phones stay on the menu. Re-run if the width
// crosses the breakpoint while sitting on /settings.
function forwardIfWide() {
	if (!isMobile.value && !isLeaf.value) {
		router.replace("/settings/profile");
	}
}
onMounted(forwardIfWide);
watch(isMobile, forwardIfWide);
</script>

<style scoped>
.app-layout {
	display: flex;
	height: 100%;
	min-height: 0;
	overflow: hidden;
}
.main-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	min-width: 0;
	min-height: 0;
}
/* Pin both panes to the shell's box. Grid/flex min-height:auto still lets the
   pane grow with Profile/Billing/etc., and the app shell then clips it — iOS
   never gets a bounded overflow:auto, so the page cannot scroll. Absolute fill
   gives the same definite height chat uses for the transcript. */
.settings-shell {
	position: relative;
	flex: 1 1 0%;
	min-width: 0;
	min-height: 0;
	overflow: hidden;
	background-color: var(--ql-bg);
}
.settings-menu-pane {
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	width: 240px;
	min-height: 0;
	overflow-y: auto;
	-webkit-overflow-scrolling: touch;
	touch-action: pan-y;
}
/* The scroll container is FULL WIDTH so its scrollbar hugs the true right edge
   of the page (natural), instead of floating inset at the edge of a capped box. */
.settings-content {
	position: absolute;
	top: 0;
	right: 0;
	bottom: 0;
	left: 240px;
	min-width: 0;
	min-height: 0;
	overflow-y: auto;
	-webkit-overflow-scrolling: touch;
	touch-action: pan-y;
	background-color: var(--ql-bg);
}
/* The inner wrapper carries the content cap — fills the width up to a comfortable
   reading limit, anchored to the sub-nav (not centered), with side padding. */
.settings-inner {
	max-width: 1160px;
	padding: 32px 40px;
}
/* cap individual form fields so text inputs never stretch edge-to-edge */
.settings-inner :deep(.field),
.settings-inner :deep(.field-grid) {
	max-width: 640px;
}

/* Mobile top bar (drawer access + current section title). */
.settings-topbar {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	height: var(--ql-topbar-height, 56px);
	padding: 0 0.75rem;
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-surface);
	flex-shrink: 0;
}
.settings-topbar-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.sidebar-toggle-btn {
	flex-shrink: 0;
	padding: 0.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
}
.sidebar-toggle-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

/* At drawer widths the app nav is position:fixed. Keep this shell a column
   flex so the settings panes still receive a bounded height (same as ChatView). */
@media (max-width: 1023px) {
	.app-layout {
		position: relative;
	}
	.main-content {
		width: 100%;
	}
}

/* Phone (<768): one pane at a time, full width. Do not use display:block —
   the pane would grow with content while ancestors clip with overflow:hidden. */
@media (max-width: 767px) {
	.settings-shell.mobile-drill .settings-menu-pane,
	.settings-shell.mobile-drill .settings-content {
		left: 0;
		right: 0;
		width: auto;
	}
	.settings-inner {
		padding: 1rem;
	}
	.settings-back {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		min-height: 44px;
		padding: 0 0.5rem;
		background: none;
		border: none;
		color: var(--ql-accent);
		font-size: 0.9375rem;
		cursor: pointer;
	}
}
@media (min-width: 768px) {
	.settings-back {
		display: none;
	}
}
</style>
