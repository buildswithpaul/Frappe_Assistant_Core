<template>
	<div>
		<h3 class="section-title">Connected Services</h3>

		<div class="setting-group">
			<!-- Loading State -->
			<div v-if="loadingServers" class="loading-servers">
				<svg class="spinner" viewBox="0 0 24 24">
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="3"
						fill="none"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="3"
						fill="none"
						stroke-linecap="round"
					/>
				</svg>
				<span>Loading services...</span>
			</div>

			<!-- No Servers Connected -->
			<div v-else-if="mcpServers.length === 0" class="no-servers">
				<div class="info-icon">
					<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</div>
				<p>No services connected</p>
				<button class="btn-connect" @click="$emit('connect')" :disabled="isConnecting">
					<svg v-if="isConnecting" class="spinner-small" viewBox="0 0 24 24">
						<circle
							cx="12"
							cy="12"
							r="10"
							stroke="currentColor"
							stroke-width="3"
							fill="none"
							opacity="0.25"
						/>
						<path
							d="M12 2a10 10 0 0 1 10 10"
							stroke="currentColor"
							stroke-width="3"
							fill="none"
							stroke-linecap="round"
						/>
					</svg>
					<span v-else>Connect Frappe</span>
				</button>
			</div>

			<!-- Server List -->
			<div v-else class="server-list">
				<div
					v-for="server in mcpServers"
					:key="server.server_name"
					:class="['server-card', { 'is-broken': isBroken(server) }]"
				>
					<!-- Header: status dot + name + host -->
					<div class="server-head">
						<span
							:class="['status-dot', getServerStatusClass(server)]"
							:title="getServerStatusLabel(server)"
						></span>
						<div class="server-head-text">
							<span class="server-name">{{ server.server_name }}</span>
							<span class="server-host">{{ hostOf(server.endpoint_url) }}</span>
						</div>
						<span :class="['server-status-badge', getServerStatusClass(server)]">
							{{ getServerStatusLabel(server) }}
						</span>
					</div>

					<!-- Stat row: tool counts + token expiry -->
					<div class="server-stats">
						<span class="stat" :title="'Tools available on this server'">
							<svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M5 7h14M5 12h14M5 17h10"
								/>
							</svg>
							<template v-if="toolsLoading">Loading tools…</template>
							<template v-else-if="toolCount !== null">{{ toolCount }} tools</template>
							<template v-else>Tools unavailable</template>
						</span>
						<span
							v-if="!toolsLoading && toolCount"
							class="stat stat-split"
							:title="'Read-only tools run without asking; others ask first'"
						>
							<span class="dot-allow"></span>{{ readOnlyCount }} auto-allowed
							<span class="dot-ask"></span>{{ askCount }} ask
						</span>
						<span
							v-if="connectedLabel(server)"
							class="stat"
							:title="server.connected_at || ''"
						>
							<svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 8v4l3 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z"
								/>
							</svg>
							{{ connectedLabel(server) }}
						</span>
					</div>

					<!-- Broken-connection Warning -->
					<div v-if="isBroken(server)" class="broken-warning">
						<svg
							class="warning-icon"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
						<span>{{
							server.error_message ||
							"This connection isn't working. The assistant can't run actions on this server until you reconnect."
						}}</span>
					</div>

					<div class="server-actions">
						<button
							v-if="isBroken(server)"
							class="btn-reconnect"
							@click="$emit('reconnect', server.server_name)"
							:disabled="isReconnecting"
						>
							<svg v-if="isReconnecting" class="spinner-small" viewBox="0 0 24 24">
								<circle
									cx="12"
									cy="12"
									r="10"
									stroke="currentColor"
									stroke-width="3"
									fill="none"
									opacity="0.25"
								/>
								<path
									d="M12 2a10 10 0 0 1 10 10"
									stroke="currentColor"
									stroke-width="3"
									fill="none"
									stroke-linecap="round"
								/>
							</svg>
							<span v-else>Reconnect</span>
						</button>
						<button
							v-else
							class="btn-manage-tools"
							@click="openToolPermissions(server)"
						>
							<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
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
							Manage tools
						</button>
						<button
							class="btn-disconnect"
							@click="$emit('disconnect', server.server_name)"
							:disabled="isDisconnecting"
							title="Remove this server"
						>
							Disconnect
						</button>
					</div>
				</div>
			</div>

			<!-- Success/Error Messages -->
			<div v-if="successMessage" class="success-message">
				<svg class="message-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M5 13l4 4L19 7"
					/>
				</svg>
				{{ successMessage }}
			</div>

			<div v-if="errorMessage" class="error-message">
				<svg class="message-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
				{{ errorMessage }}
			</div>
		</div>

		<ToolPermissionsModal
			:is-open="toolPermsOpen"
			:server="toolPermsServer"
			@close="closeToolPermissions"
		/>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import ToolPermissionsModal from "./ToolPermissionsModal.vue";

defineProps({
	mcpServers: {
		type: Array,
		default: () => [],
	},
	loadingServers: {
		type: Boolean,
		default: false,
	},
	isConnecting: {
		type: Boolean,
		default: false,
	},
	isReconnecting: {
		type: Boolean,
		default: false,
	},
	isDisconnecting: {
		type: Boolean,
		default: false,
	},
	successMessage: {
		type: String,
		default: "",
	},
	errorMessage: {
		type: String,
		default: "",
	},
});

defineEmits(["connect", "reconnect", "disconnect"]);

// Tool catalog — fetched once so each server card can show its tool count and
// the read-only/ask split. Tools are the same for every connected server (they
// all hit this Frappe site's MCP endpoint), so a single fetch suffices.
const toolsLoading = ref(false);
const toolCount = ref(null);
const readOnlyCount = ref(0);

const askCount = computed(() =>
	toolCount.value === null ? 0 : Math.max(0, toolCount.value - readOnlyCount.value)
);

async function loadToolStats() {
	toolsLoading.value = true;
	try {
		const resp = await api.tools.listAvailable();
		const list = resp?.tools || [];
		toolCount.value = list.length;
		readOnlyCount.value = list.filter((t) => t.read_only).length;
	} catch {
		// Non-fatal: the card just shows "Tools unavailable".
		toolCount.value = null;
	} finally {
		toolsLoading.value = false;
	}
}

onMounted(loadToolStats);

// AR sends Title Case status values ("Active" / "Inactive" / "Error" /
// "Token Expired"), so every comparison here folds case.
const BROKEN_STATUSES = new Set(["error", "token expired"]);

function statusKey(server) {
	return String(server.status || "").toLowerCase();
}

function isBroken(server) {
	return BROKEN_STATUSES.has(statusKey(server));
}

function getServerStatusClass(server) {
	if (isBroken(server)) return "status-broken";
	if (statusKey(server) === "active") return "status-active";
	return "status-inactive";
}

function getServerStatusLabel(server) {
	return server.status || "Unknown";
}

// Show just the host (mysite.com), not the full /api/method/... URL.
function hostOf(url) {
	if (!url) return "";
	try {
		return new URL(url).host;
	} catch {
		return url.replace(/^https?:\/\//, "").split("/")[0] || url;
	}
}

// When the user linked this server. Deliberately not the OAuth token expiry —
// that is a rolling 1h refresh clock AR rewrites on use, so it reads months
// stale on idle-but-healthy connections and means nothing to a user.
function parseDate(raw) {
	if (!raw) return null;
	const parsed = new Date(raw.includes("T") ? raw : raw.replace(" ", "T"));
	return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function connectedLabel(server) {
	const when = parseDate(server.connected_at);
	if (!when) return "";
	return `Connected ${when.toLocaleDateString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
	})}`;
}

// Tool permissions modal state — local to this section since it's only
// consumed here and shouldn't leak out as another @emit upward.
const toolPermsOpen = ref(false);
const toolPermsServer = ref(null);

function openToolPermissions(server) {
	toolPermsServer.value = server;
	toolPermsOpen.value = true;
}

function closeToolPermissions() {
	toolPermsOpen.value = false;
	// Keep server reference for exit transition; cleared on next open.
}
</script>

<style scoped>
.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 1rem;
}

.setting-group {
	margin-bottom: 1.5rem;
}

.loading-servers {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
	padding: 1rem;
}

.no-servers {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 1.5rem;
	background: var(--ql-bg);
	border: 1px dashed var(--ql-border);
	border-radius: 0.5rem;
	text-align: center;
}

.no-servers .info-icon {
	width: 2rem;
	height: 2rem;
	color: var(--ql-text-muted);
}

.no-servers p {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.btn-connect {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.btn-connect:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.btn-connect:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.server-list {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.server-card {
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.625rem;
	padding: 1rem 1.125rem;
	transition: border-color 0.15s ease;
}

.server-card.is-broken {
	border-color: rgba(239, 68, 68, 0.35);
}

/* Header row: status dot + name/host + status badge */
.server-head {
	display: flex;
	align-items: center;
	gap: 0.625rem;
}

.status-dot {
	width: 0.5rem;
	height: 0.5rem;
	border-radius: 9999px;
	flex-shrink: 0;
}

.status-dot.status-active {
	background: #22c55e;
	box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}
.status-dot.status-broken {
	background: #ef4444;
	box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.18);
}
.status-dot.status-inactive {
	background: #9ca3af;
	box-shadow: 0 0 0 3px rgba(156, 163, 175, 0.18);
}

.server-head-text {
	display: flex;
	flex-direction: column;
	min-width: 0;
	flex: 1;
}

.server-name {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	line-height: 1.2;
}

.server-host {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.server-status-badge {
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.1875rem 0.5rem;
	border-radius: 9999px;
	flex-shrink: 0;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

/* Stat row: tool count, read-only/ask split, expiry */
.server-stats {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 0.375rem 1rem;
	margin-top: 0.75rem;
	padding-top: 0.75rem;
	border-top: 1px solid var(--ql-border);
}

.stat {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.stat-icon {
	width: 0.875rem;
	height: 0.875rem;
	flex-shrink: 0;
	opacity: 0.8;
}

.stat-split {
	gap: 0.25rem;
}

.dot-allow,
.dot-ask {
	display: inline-block;
	width: 0.4375rem;
	height: 0.4375rem;
	border-radius: 9999px;
	margin-right: 0.125rem;
}
.dot-allow {
	background: #22c55e;
}
.dot-ask {
	background: #f59e0b;
	margin-left: 0.375rem;
}

.status-active {
	background: rgba(34, 197, 94, 0.1);
	color: #16a34a;
}

.status-broken {
	background: rgba(239, 68, 68, 0.1);
	color: #dc2626;
}

.status-inactive {
	background: rgba(107, 114, 128, 0.1);
	color: #6b7280;
}

.broken-warning {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	padding: 0.75rem;
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.375rem;
	margin-top: 0.75rem;
	font-size: 0.75rem;
	color: #dc2626;
}

.broken-warning .warning-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}

.server-actions {
	display: flex;
	gap: 0.5rem;
	margin-top: 0.875rem;
}

.btn-icon {
	width: 0.875rem;
	height: 0.875rem;
	flex-shrink: 0;
}

.btn-reconnect {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.btn-reconnect:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.btn-reconnect:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.btn-manage-tools {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-manage-tools:hover {
	background: rgba(0, 0, 0, 0.04);
	border-color: var(--ql-text);
}

.btn-disconnect {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-disconnect:hover:not(:disabled) {
	color: #dc2626;
	border-color: rgba(239, 68, 68, 0.3);
	background: rgba(239, 68, 68, 0.05);
}

.btn-disconnect:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.warning-icon {
	width: 1.25rem;
	height: 1.25rem;
	flex-shrink: 0;
	color: #ca8a04;
}

.spinner {
	width: 1rem;
	height: 1rem;
	animation: spin 1s linear infinite;
}

.spinner-small {
	width: 0.875rem;
	height: 0.875rem;
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

.success-message,
.error-message {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1rem;
	border-radius: 0.5rem;
	margin-top: 1rem;
	font-size: 0.875rem;
	word-break: break-word;
	overflow-wrap: anywhere;
}

.success-message {
	background: rgba(34, 197, 94, 0.1);
	border: 1px solid rgba(34, 197, 94, 0.3);
	color: #16a34a;
}

.error-message {
	background: rgba(239, 68, 68, 0.1);
	border: 1px solid rgba(239, 68, 68, 0.3);
	color: #dc2626;
}

.message-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}
</style>
