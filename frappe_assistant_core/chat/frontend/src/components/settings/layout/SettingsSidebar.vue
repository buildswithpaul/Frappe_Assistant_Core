<template>
	<nav class="settings-sidebar" aria-label="Settings navigation">
		<div class="sidebar-header">
			<button class="back-btn" @click="goBack" aria-label="Back">
				<svg
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					class="back-icon"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
				</svg>
				<span>Back</span>
			</button>
			<h2 class="sidebar-title">Settings</h2>
		</div>

		<div v-for="group in visibleGroups" :key="group.id" class="sidebar-group">
			<div class="group-label">{{ group.label }}</div>
			<template v-for="item in group.items" :key="item.to || item.label">
				<router-link
					v-if="item.to"
					:to="item.to"
					class="sidebar-link"
					active-class="is-active"
				>
					<component :is="item.icon" class="link-icon" />
					<span>{{ item.label }}</span>
				</router-link>
				<button
					v-else
					type="button"
					class="sidebar-link sidebar-action"
					@click="item.action"
				>
					<component :is="item.icon" class="link-icon" />
					<span>{{ item.label }}</span>
				</button>
			</template>
		</div>
	</nav>
</template>

<script setup>
import { computed, h } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores/userStore";
import { useTourStore } from "@/stores/tourStore";

const router = useRouter();
const userStore = useUserStore();
const tourStore = useTourStore();

function goBack() {
	if (window.history.length > 1) router.back();
	else router.push("/chat");
}

// Icon factories — match the modal's visual vocabulary so navigation
// feels familiar after the migration.
const ProfileIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
		}),
	]);
const BillingIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z",
		}),
	]);
const UsersIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z",
		}),
	]);
const MemoryIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
		}),
	]);
const RoutingIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M4 6h6l4 6h6M4 18h6l2-3M18 3l3 3-3 3M18 15l3 3-3 3",
		}),
	]);
const ConnectionsIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M13.828 10.172a4 4 0 010 5.656l-3 3a4 4 0 01-5.656-5.656l1.5-1.5M10.172 13.828a4 4 0 010-5.656l3-3a4 4 0 015.656 5.656l-1.5 1.5",
		}),
	]);
const PacksIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M12.89 1.45l8 4A2 2 0 0122 7.24v9.53a2 2 0 01-1.11 1.79l-8 4a2 2 0 01-1.79 0l-8-4a2 2 0 01-1.1-1.8V7.24a2 2 0 011.11-1.79l8-4a2 2 0 011.78 0z",
		}),
		h("polyline", { points: "2.32 6.16 12 11 21.68 6.16" }),
		h("line", { x1: "12", y1: "22.76", x2: "12", y2: "11" }),
	]);
const AppearanceIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M4 5a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2H6a2 2 0 01-2-2V5zM8 21h8m-4-5v5",
		}),
	]);
const PrivacyIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
		}),
	]);
const TicketIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 010 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 010-4V7a2 2 0 00-2-2H5z",
		}),
	]);
const AccountIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z",
		}),
	]);
const TourIcon = () =>
	h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 2 }, [
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z",
		}),
		h("path", {
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
			d: "M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
		}),
	]);

const visibleGroups = computed(() => {
	const groups = [];

	// Personal — always visible
	const personalItems = [
		{ to: "/settings/profile", label: "Profile", icon: ProfileIcon },
		{ to: "/settings/appearance", label: "Appearance", icon: AppearanceIcon },
		{ to: "/settings/privacy", label: "Privacy & Data", icon: PrivacyIcon },
	];
	personalItems.push({ to: "/settings/my-tickets", label: "Support", icon: TicketIcon });
	if (userStore.memoryEnabled) {
		personalItems.push({ to: "/settings/memory", label: "Memory", icon: MemoryIcon });
	}
	// Personal, not Workspace: only an admin can change these rules, but every
	// member is governed by them and needs somewhere to read them.
	personalItems.push({
		to: "/settings/routing", label: "Model routing", icon: RoutingIcon,
	});
	personalItems.push({
		to: "/settings/connections", label: "Connections", icon: ConnectionsIcon,
	});
	groups.push({ id: "personal", label: "Personal", items: personalItems });

	// Workspace — admin only
	if (userStore.isAdmin) {
		const workspaceItems = [];
		if (userStore.billingEnabled) {
			workspaceItems.push({ to: "/settings/users", label: "Users", icon: UsersIcon });
		}
		workspaceItems.push({ to: "/settings/packs", label: "Industry Packs", icon: PacksIcon });
		workspaceItems.push({ to: "/settings/my-packs", label: "My Packs", icon: PacksIcon });
		if (userStore.billingEnabled) {
			workspaceItems.push({ to: "/settings/billing", label: "Billing", icon: BillingIcon });
		}
		workspaceItems.push({ to: "/settings/workspace", label: "Workspace", icon: AccountIcon });
		groups.push({ id: "workspace", label: "Workspace", items: workspaceItems });
	}

	// Help — action items (not routes). Tour replays the cinematic intro.
	groups.push({
		id: "help",
		label: "Help",
		items: [{ label: "Replay tour", icon: TourIcon, action: () => tourStore.open() }],
	});

	return groups;
});
</script>

<style scoped>
.settings-sidebar {
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
	padding: 1.25rem 0.875rem;
	background-color: var(--ql-bg);
	border-right: 1px solid var(--ql-border);
	height: 100%;
	min-height: 0;
	overflow-y: auto;
	-webkit-overflow-scrolling: touch;
	touch-action: pan-y;
}
.sidebar-header {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	padding: 0 0.5rem;
}
.back-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.4rem;
	padding: 0.3rem 0.5rem;
	font-size: 0.8rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	align-self: flex-start;
	transition: color 0.15s ease, background-color 0.15s ease;
}
.back-btn:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}
.back-icon {
	width: 1rem;
	height: 1rem;
}
.sidebar-title {
	font-size: 1.05rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0;
	line-height: 1;
}
.sidebar-group {
	display: flex;
	flex-direction: column;
	gap: 0.2rem;
}
.group-label {
	font-size: 0.7rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	padding: 0 0.75rem;
	margin-bottom: 0.2rem;
}
.sidebar-link {
	display: flex;
	align-items: center;
	gap: 0.7rem;
	padding: 0.55rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	text-decoration: none;
	border-radius: 0.5rem;
	transition: background-color 0.15s ease, color 0.15s ease;
}
.sidebar-link:hover {
	background-color: var(--ql-subtle);
}
.sidebar-link.is-active {
	background-color: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.sidebar-action {
	width: 100%;
	background: none;
	border: none;
	cursor: pointer;
	text-align: left;
	font: inherit;
}
.link-icon {
	width: 1.1rem;
	height: 1.1rem;
	flex-shrink: 0;
}
/* Tablet (768–1023): keep the classic vertical sub-nav; the app nav is a drawer
   so there's room for the 2-pane settings layout. */

/* Phone (<768): full-screen vertical menu list with comfortable tap rows. The
   SettingsView mobile top bar already shows Back/section title, so the sidebar's
   own header is hidden here to avoid duplication. */
@media (max-width: 767px) {
	.settings-sidebar {
		width: 100%;
		border-right: none;
		padding: 0.5rem 0.75rem 1rem;
	}
	.sidebar-header {
		display: none;
	}
	.sidebar-link {
		min-height: 48px;
		padding: 0.75rem;
		font-size: 0.9375rem;
	}
}
</style>
