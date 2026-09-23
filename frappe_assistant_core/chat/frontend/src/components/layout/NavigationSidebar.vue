<template>
	<!-- Scrim must live in the same stacking context as the drawer. Teleporting
	     it to <body> put it above `.app-root` (position:fixed), so taps never
	     reached Chat / Settings / recent threads. -->
	<div
		v-if="layout.drawerOpen"
		class="nav-scrim"
		@click="layout.closeDrawer()"
	></div>

	<aside
		class="navigation-sidebar"
		:class="{ collapsed: collapsed, 'drawer-open': layout.drawerOpen }"
	>
		<!-- Logo Section -->
		<div class="sidebar-header">
			<div class="logo-section" v-if="!collapsed">
				<FacoRobot size="sm" show-arms show-shadow />
				<h2 class="logo-text">FACO</h2>
			</div>
			<div class="logo-collapsed" v-else>
				<FacoRobot size="sm" show-arms />
			</div>
		</div>

		<!-- Navigation Menu -->
		<NavMenu :collapsed="collapsed" @return-to-desk="returnToDesk" />

		<!-- Recent Chats Section — only on Chat view -->
		<ConversationsList
			v-if="!collapsed && isChatRoute"
			ref="conversationsListRef"
			:sessions="sessions"
			:archived-sessions="archivedSessions"
			:active-session-id="activeSessionId"
			:loading="loading"
			:show-new-chat="userReady"
			@select-session="$emit('session-selected', $event)"
			@new-session="$emit('new-chat')"
			@delete-session="$emit('delete-session', $event)"
			@continue-archived="$emit('continue-archived', $event)"
			@load-archived="$emit('load-archived')"
		/>

		<!-- User Section with Dropdown -->
		<UserDropdown :collapsed="collapsed" @open-settings="$emit('open-settings')" />
	</aside>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import { useUserStore } from "@/stores/userStore";
import { useLayoutStore } from "@/stores/layoutStore";
import NavMenu from "./NavMenu.vue";
import ConversationsList from "./ConversationsList.vue";
import UserDropdown from "./UserDropdown.vue";
import FacoRobot from "@/components/common/FacoRobot.vue";
import { writeHandoff } from "@/utils/sessionHandoff";

const userStore = useUserStore();
const userReady = computed(
	() => userStore.registrationStatus === "ready" && userStore.isUserSetupComplete
);

const props = defineProps({
	sessions: {
		type: Array,
		default: () => [],
	},
	activeSessionId: {
		type: String,
		default: null,
	},
	collapsed: {
		type: Boolean,
		default: false,
	},
	loading: {
		type: Boolean,
		default: false,
	},
	archivedSessions: {
		type: Array,
		default: () => [],
	},
});

defineEmits([
	"session-selected",
	"new-chat",
	"open-settings",
	"toggle-sidebar",
	"delete-session",
	"continue-archived",
	"load-archived",
]);

const conversationsListRef = ref(null);

const route = useRoute();

// Off-canvas drawer on mobile: close it whenever the route changes so tapping a
// nav item both navigates and dismisses the drawer.
const layout = useLayoutStore();
watch(() => route.fullPath, () => layout.closeDrawer());

// While the drawer is open: lock body scroll and close on Escape. Owned here so
// every view that renders the sidebar gets the behavior without per-view wiring.
function onDrawerKey(e) {
	if (e.key === "Escape") layout.closeDrawer();
}
watch(
	() => layout.drawerOpen,
	(open) => {
		document.body.style.overflow = open ? "hidden" : "";
		if (open) window.addEventListener("keydown", onDrawerKey);
		else window.removeEventListener("keydown", onDrawerKey);
	}
);
onBeforeUnmount(() => {
	document.body.style.overflow = "";
	window.removeEventListener("keydown", onDrawerKey);
	// A view unmounting mid-open (route change) must not strand the drawer flag
	// so the next view starts closed.
	layout.closeDrawer();
});

const isChatRoute = computed(() => route.path.startsWith("/chat") || route.path === "/");

function returnToDesk() {
	// Store current session for the widget on the desk to pick up.
	// Same-tab navigation only — sessionStorage scopes the hand-off to this
	// tab so other tabs don't inherit the session id, and the stamped owner
	// keeps it from surviving into a different login.
	writeHandoff("faco_widget_session", props.activeSessionId, userStore.user);
	// Navigate to Frappe desk
	window.location.href = "/app";
}
</script>

<style scoped>
.navigation-sidebar {
	display: flex;
	flex-direction: column;
	background-color: var(--ql-surface);
	border-right: 1px solid var(--ql-border);
	width: var(--ql-nav-width,260px);
	transition: width 0.2s ease;
	/* Fills .app-layout, which is already shorter than the viewport whenever a
	   notification banner is showing. A viewport height here would overflow it
	   and the route root's overflow:hidden would clip the user section. */
	height: 100%;
}

.navigation-sidebar.collapsed {
	width: var(--ql-nav-collapsed-width,60px);
}

.sidebar-header {
	display: flex;
	align-items: center;
	padding: 0.75rem;
	border-bottom: 1px solid var(--ql-border);
	height: var(--ql-topbar-height,56px);
	background-color: var(--ql-surface);
}

.logo-section {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.logo-text {
	font-size: 1.125rem;
	font-weight: 700;
	color: var(--ql-accent);
	line-height: 1.2;
}

.logo-collapsed {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 100%;
}

/* Scrim behind the drawer. Sibling of the aside (not a child) so the drawer's
   translateX does not clip it. z-index stays below the aside so menu taps win. */
.nav-scrim {
	position: fixed;
	inset: 0;
	z-index: 40;
	background: rgba(0, 0, 0, 0.45);
}

/* --- Mobile / tablet: off-canvas drawer (< 1024px) --- */
@media (max-width: 1023px) {
	.navigation-sidebar {
		position: fixed;
		top: 0;
		left: 0;
		z-index: 50;
		width: var(--ql-nav-width, 260px);
		max-width: 85vw;
		/* Same unit when closed and open — % → px does not interpolate, so
		   the drawer could stay translated off-screen after hamburger. */
		transform: translateX(-100%);
		transition: transform 0.25s ease;
	}
	/* On mobile the desktop "collapsed" (60px) form does not apply — the drawer
	   is always full width when open. */
	.navigation-sidebar.collapsed {
		width: var(--ql-nav-width, 260px);
	}
	.navigation-sidebar.drawer-open {
		transform: translateX(0%);
		box-shadow: 0 0 40px rgba(0, 0, 0, 0.25);
	}
}
</style>
