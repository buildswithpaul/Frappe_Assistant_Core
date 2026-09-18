<template>
	<div class="user-section" ref="userMenuRef">
		<!-- Expanded User Info -->
		<div v-if="!collapsed" class="user-dropdown-wrapper" @click="toggleUserMenu">
			<div class="user-info">
				<div class="user-avatar">
					{{ userInitial }}
					<span v-if="userStore.hasOutstanding" class="due-dot" :title="dueTitle" />
				</div>
				<div class="user-details">
					<div class="user-name">{{ userName }}</div>
				</div>
				<svg
					class="user-chevron"
					:class="{ 'rotate-180': isUserMenuOpen }"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M5 15l7-7 7 7"
					/>
				</svg>
			</div>
		</div>

		<!-- Collapsed User Avatar -->
		<div v-else class="user-avatar-collapsed" @click="toggleUserMenu">
			{{ userInitial }}
			<span v-if="userStore.hasOutstanding" class="due-dot" :title="dueTitle" />
		</div>

		<!-- User Dropdown Menu -->
		<div
			v-if="isUserMenuOpen"
			class="user-dropdown-menu"
			:class="{ 'collapsed-menu': collapsed }"
		>
			<div class="dropdown-header">
				<div class="dropdown-user-name">{{ userName }}</div>
				<div class="dropdown-user-email">{{ userEmail }}</div>
			</div>
			<hr class="dropdown-divider" />
			<button @click="handleSettings" class="dropdown-menu-item">
				<svg class="menu-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
					/>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
					/>
				</svg>
				Settings
				<span v-if="userStore.hasOutstanding" class="due-pill">{{ dueLabel }}</span>
			</button>
			<a
				:href="DOCS_URL"
				target="_blank"
				rel="noopener noreferrer"
				class="dropdown-menu-item"
				@click="closeUserMenu"
			>
				<svg class="menu-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
					/>
				</svg>
				Docs
			</a>
			<button @click="handleHelp" class="dropdown-menu-item">
				<svg class="menu-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				Help &amp; Feedback
			</button>
			<hr class="dropdown-divider" />
			<button @click="handleLogout" class="dropdown-menu-item">
				<svg class="menu-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
					/>
				</svg>
				Logout
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useUserStore } from "@/stores/userStore";
import { useSupportStore } from "@/stores/supportStore";
import { formatCurrency } from "@/composables/useFormatters";

defineProps({
	collapsed: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["open-settings"]);

const DOCS_URL = "https://fac-suite.com/";

// Admin-only by construction: the backend sends no outstanding to anyone who
// could not settle it, so a member never sees a dot they cannot clear.
const dueLabel = computed(() =>
	formatCurrency(userStore.outstanding?.amount || 0, userStore.outstanding?.currency || undefined)
);
const dueTitle = computed(() => `${dueLabel.value} outstanding`);

const userStore = useUserStore();
const supportStore = useSupportStore();
const isUserMenuOpen = ref(false);
const userMenuRef = ref(null);

// User info computed properties
const userName = computed(() => {
	if (!userStore.user) return "User";
	const email = userStore.user;
	return email.split("@")[0] || "User";
});

const userEmail = computed(() => userStore.user || "");

const userInitial = computed(() => {
	if (!userStore.user) return "?";
	return userStore.user.charAt(0).toUpperCase();
});

// User menu methods
function toggleUserMenu() {
	isUserMenuOpen.value = !isUserMenuOpen.value;
}

function closeUserMenu() {
	isUserMenuOpen.value = false;
}

function handleSettings(e) {
	e.stopPropagation();
	isUserMenuOpen.value = false;
	emit("open-settings");
}

function handleHelp(e) {
	e.stopPropagation();
	isUserMenuOpen.value = false;
	supportStore.open({ mode: "issue" });
}

async function handleLogout(e) {
	e.stopPropagation();
	isUserMenuOpen.value = false;
	try {
		await fetch("/api/method/logout", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": window.csrf_token || window.frappe?.csrf_token || "",
			},
			credentials: "same-origin",
		});
	} catch {
		// Even if the request fails, redirect to login
	}
	window.location.href = "/login";
}

function handleOutsideClick(event) {
	if (isUserMenuOpen.value && userMenuRef.value && !userMenuRef.value.contains(event.target)) {
		isUserMenuOpen.value = false;
	}
}

onMounted(() => {
	document.addEventListener("click", handleOutsideClick);
});

onUnmounted(() => {
	document.removeEventListener("click", handleOutsideClick);
});
</script>

<style scoped>
.user-avatar,
.user-avatar-collapsed {
	position: relative;
}

.due-dot {
	position: absolute;
	top: -2px;
	right: -2px;
	width: 0.5rem;
	height: 0.5rem;
	background: #dc2626;
	border: 2px solid var(--ql-surface, #fff);
	border-radius: 50%;
}

.due-pill {
	margin-left: auto;
	padding: 0.0625rem 0.375rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: #dc2626;
	background: rgba(220, 38, 38, 0.12);
	border-radius: 0.375rem;
}

.user-section {
	margin-top: auto;
	padding: 0.75rem;
	border-top: 1px solid var(--ql-border);
	background-color: var(--ql-surface);
	position: relative;
}

.user-dropdown-wrapper {
	cursor: pointer;
}

.user-info {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.5rem;
	border-radius: 0.5rem;
	transition: background-color 0.15s ease;
}

.user-info:hover {
	background-color: var(--ql-subtle);
}

.user-avatar {
	width: 2rem;
	height: 2rem;
	background-color: var(--ql-accent);
	color: white;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.875rem;
	font-weight: 600;
	flex-shrink: 0;
}

.user-avatar-collapsed {
	width: 2rem;
	height: 2rem;
	background-color: var(--ql-accent);
	color: white;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.875rem;
	font-weight: 600;
	margin: 0 auto;
	cursor: pointer;
}

.user-details {
	flex: 1;
	min-width: 0;
}

.user-name {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.user-chevron {
	width: 1rem;
	height: 1rem;
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
	flex-shrink: 0;
}

.user-chevron.rotate-180 {
	transform: rotate(180deg);
}

.user-dropdown-menu {
	position: absolute;
	bottom: 100%;
	left: 0.75rem;
	right: 0.75rem;
	margin-bottom: 0.5rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	z-index: 50;
	overflow: hidden;
}

.user-dropdown-menu.collapsed-menu {
	left: 3.5rem;
	right: auto;
	width: 200px;
}

.dropdown-header {
	padding: 0.75rem 1rem;
}

.dropdown-user-name {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.dropdown-user-email {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	margin-top: 0.125rem;
}

.dropdown-divider {
	margin: 0;
	border: none;
	border-top: 1px solid var(--ql-border);
}

.dropdown-menu-item {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	width: 100%;
	padding: 0.625rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: none;
	border: none;
	cursor: pointer;
	transition: background-color 0.15s ease;
	text-align: left;
	/* Docs is an <a> so middle-click and open-in-new-tab work; keep it looking
	   like its <button> siblings without depending on Tailwind's preflight. */
	text-decoration: none;
	box-sizing: border-box;
}

.dropdown-menu-item:hover {
	background-color: var(--ql-subtle);
}

.menu-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}
</style>
