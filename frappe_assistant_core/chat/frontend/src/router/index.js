import { createRouter, createWebHistory } from "vue-router";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useUserStore } from "@/stores/userStore";

export async function requireAdmin(to, from, next) {
	const userStore = useUserStore();
	// Wait for the store to actually know. Guards run before App.vue mounts,
	// so on a cold load `isAdmin` is still its initial false and every admin
	// route bounced to Profile — invisible while these pages were only ever
	// reached by in-app navigation, obvious on a deep link like the return
	// from checkout.
	await userStore.ensureLoaded();
	if (userStore.isAdmin) {
		next();
	} else {
		next("/settings/profile");
	}
}

const routes = [
	{
		path: "/",
		redirect: "/chat",
	},
	{
		path: "/chat",
		name: "chat",
		component: () => import("@/views/ChatView.vue"),
	},
	{
		path: "/chat/:sessionId",
		name: "chat-session",
		component: () => import("@/views/ChatView.vue"),
		props: true,
	},
	{
		path: "/knowledge",
		name: "knowledge",
		component: () => import("@/views/KnowledgeBase.vue"),
	},
	{
		path: "/agents",
		name: "agents",
		component: () => import("@/views/WorkflowList.vue"),
	},
	{
		path: "/agents/:id",
		name: "agent-builder",
		component: () => import("@/views/WorkflowBuilder.vue"),
		props: true,
	},
	{ path: "/workflows", redirect: "/agents" },
	{ path: "/workflows/:id", redirect: (to) => ({ name: "agent-builder", params: { id: to.params.id } }) },
	{
		path: "/analytics",
		name: "analytics",
		component: () => import("@/views/AnalyticsView.vue"),
		beforeEnter: requireAdmin,
	},
	{
		path: "/settings",
		component: () => import("@/views/SettingsView.vue"),
		// No hard redirect: on phones /settings is a full-screen menu (SettingsView
		// shows the menu pane with no leaf); on tablet/desktop SettingsView forwards
		// to the first leaf on mount. Deep links to a leaf (/settings/privacy) work
		// unchanged on every width.
		children: [
			{
				path: "profile",
				name: "settings-profile",
				component: () => import("@/components/settings/ProfileSettings.vue"),
			},
			{
				path: "appearance",
				name: "settings-appearance",
				component: () => import("@/components/settings/AppearanceSettings.vue"),
			},
			{
				path: "privacy",
				name: "settings-privacy",
				component: () => import("@/components/settings/PrivacySettings.vue"),
			},
			{
				path: "my-tickets",
				name: "MyTickets",
				component: () => import("@/components/settings/MyTicketsSettings.vue"),
			},
			{
				path: "routing",
				name: "settings-routing",
				component: () => import("@/components/settings/RoutingSettings.vue"),
			},
			{
				path: "memory",
				name: "settings-memory",
				component: () => import("@/components/settings/MemorySettings.vue"),
			},
			{
				path: "users",
				name: "settings-users",
				component: () => import("@/components/settings/UsersSettings.vue"),
				beforeEnter: requireAdmin,
			},
			{
				path: "packs",
				name: "settings-packs",
				component: () => import("@/views/IndustryPacksSettings.vue"),
				beforeEnter: requireAdmin,
			},
			{
				path: "my-packs",
				name: "settings-my-packs",
				component: () => import("@/views/MyPacksView.vue"),
				beforeEnter: requireAdmin,
			},
			{
				path: "billing",
				name: "settings-billing",
				component: () => import("@/components/settings/BillingSettings.vue"),
				beforeEnter: requireAdmin,
			},
			{
				path: "workspace",
				name: "settings-workspace",
				component: () => import("@/components/settings/WorkspaceSettings.vue"),
				beforeEnter: requireAdmin,
			},
			// Redirects for retired paths
			{ path: "general", redirect: "/settings/profile" },
			{ path: "preferences", redirect: "/settings/profile" },
			{ path: "account", redirect: "/settings/workspace" },
		],
	},
	// Legacy billing routes now land on the new settings route.
	{
		path: "/billing",
		redirect: "/settings/billing",
	},
	{
		path: "/billing/plans",
		redirect: "/settings/billing",
	},
	{
		path: "/:pathMatch(.*)*",
		redirect: "/chat",
	},
];

const router = createRouter({
	history: createWebHistory("/copilot/"),
	routes,
});

// Non-members are walled out of the whole SPA; /chat renders the access screen.
router.beforeEach((to) => {
	const userStore = useUserStore();
	if (userStore.registrationStatus === "no_role" && to.path !== "/chat") {
		return "/chat";
	}
});

// Unsaved changes guard for workflow builder
router.beforeEach((to, from) => {
	if (from.name === "agent-builder") {
		const store = useWorkflowStore();
		if (store.isDirty) {
			return window.confirm("You have unsaved changes. Leave anyway?");
		}
	}
});

export default router;
