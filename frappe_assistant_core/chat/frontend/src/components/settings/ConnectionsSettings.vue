<template>
	<div class="connections-settings">
		<header class="connections-header">
			<div class="connections-heading">
				<h2 class="connections-title">Connections</h2>
				<p class="connections-stat">{{ summary }}</p>
			</div>
			<button
				v-if="!formOpen"
				type="button"
				class="connections-add"
				data-test="add-connection"
				@click="openWizard()"
			>
				Add a connection
			</button>
		</header>

		<ConnectionForm
			v-if="formOpen"
			:key="editingConnection?.server_name ?? 'new'"
			:existing-names="existingNames"
			:initial="editingConnection"
			:saving="formSaving"
			@save="saveConnection"
			@cancel="closeForm"
		/>

		<p v-if="loadError" class="connections-notice">
			Couldn't load your connections.
			<button type="button" class="connections-retry" @click="reload">Try again</button>
		</p>

		<template v-else>
			<p v-if="loading" class="connections-notice">Loading…</p>
			<p v-else-if="arUnreachable" class="connections-notice">
				We couldn't reach your assistant runtime, so your connections are unavailable
				right now.
			</p>

			<div v-else-if="!connections.length" class="connections-blank">
				<h3 class="connections-blank__title">Nothing connected yet</h3>
				<p class="connections-blank__text">
					Give the assistant a tool to work with — paste an MCP endpoint and it
					checks the address, handles the sign-in, and shows you what the tool
					can do before anything is saved.
				</p>
			</div>

			<div v-else class="connections-ledger">
				<ConnectionCard
					v-for="connection in connections"
					:key="connection.server_name"
					:connection="connection"
					:busy="busy === connection.server_name"
					@test="testConnection"
					@toggle="toggleEnabled"
					@remove="requestRemove"
					@edit="openEditForm"
					@tools="openTools"
					@reconnect="openReconnect"
				/>
			</div>
		</template>

		<ExternalClientsPanel :endpoint-url="userStore.mcpEndpointUrl" />

		<ToolVisibilityModal
			v-if="toolsModalTarget"
			:key="toolsModalTarget"
			:server-name="toolsModalTarget"
			:tools="toolsModalTools"
			:tool-details="toolsModalDetails"
			:blocked="toolsModalBlocked"
			:preferences="toolsModalPreferences"
			:slug="toolsModalSlug"
			:managed="toolsModalManaged"
			:saving="toolsModalSaving"
			@save="saveToolVisibility"
			@close="closeTools"
		/>

		<ConnectWizard
			v-if="wizardOpen"
			:key="wizardHandle || wizardReauth || 'new'"
			:existing-names="connectedNames"
			:initial-handle="wizardHandle"
			:reauth-server-name="wizardReauth"
			@added="onWizardAdded"
			@close="closeWizard"
		/>

		<ConfirmModal
			:open="Boolean(removeTarget)"
			title="Remove this connection?"
			:message="removeTarget ? `This removes ${removeTarget} and its stored credentials. You'll need to add it again to reconnect.` : ''"
			confirm-label="Remove"
			destructive
			@confirm="confirmRemove"
			@cancel="cancelRemove"
		/>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "@/api/client";
import { useToast } from "@/composables/useToast";
import { useUserStore } from "@/stores/userStore";
import ConnectionCard from "./connections/ConnectionCard.vue";
import ConnectionForm from "./connections/ConnectionForm.vue";
import ToolVisibilityModal from "./connections/ToolVisibilityModal.vue";
import ExternalClientsPanel from "./connections/ExternalClientsPanel.vue";
import ConnectWizard from "./connections/ConnectWizard.vue";
import ConfirmModal from "@/components/common/ConfirmModal.vue";

const { showError, showSuccess } = useToast();
const userStore = useUserStore();
const route = useRoute();
const router = useRouter();

const wizardOpen = ref(false);
const wizardHandle = ref("");
const wizardReauth = ref("");

const connections = ref([]);
const arUnreachable = ref(false);
const loading = ref(true);
// A failed load is not an empty list: telling a user "no connections" after a
// 500 hides that the page never actually asked AR for the truth.
const loadError = ref(false);
const busy = ref(null);
const removeTarget = ref(null);

const formOpen = ref(false);
const editingConnection = ref(null);
const formSaving = ref(false);

const toolsModalTarget = ref(null);
const toolsModalTools = ref([]);
const toolsModalDetails = ref([]);
const toolsModalBlocked = ref([]);
const toolsModalPreferences = ref({});
const toolsModalSlug = ref("");
const toolsModalManaged = ref(false);
const toolsModalSaving = ref(false);

const connectedNames = computed(() => connections.value.map((c) => c.server_name));

// Says something only when there is something to say. "All working" is worth
// one glance; a count of what needs the user is worth acting on.
const summary = computed(() => {
	const total = connections.value.length;
	if (!total) return "What this assistant can reach";
	const unwell = connections.value.filter(
		(c) => c.status === "Error" || c.status === "Token Expired"
	).length;
	const noun = total === 1 ? "connection" : "connections";
	return unwell ? `${total} ${noun} · ${unwell} needs attention` : `${total} ${noun} · all working`;
});

// ConnectionForm rejects any name in this list as a duplicate with no
// self-exclusion of its own — when editing, the connection's own current
// name must be left out or every no-rename save falsely reads as a dupe.
const existingNames = computed(() => {
	const names = connectedNames.value;
	if (!editingConnection.value) return names;
	return names.filter((name) => name !== editingConnection.value.server_name);
});

async function reload() {
	loading.value = true;
	loadError.value = false;
	try {
		const data = await api.connections.list();
		connections.value = data?.connections || [];
		arUnreachable.value = Boolean(data?.ar_unreachable);
	} catch (err) {
		loadError.value = true;
		showError(err?.message || "Couldn't load your connections.");
	} finally {
		loading.value = false;
	}
}

async function testConnection(serverName) {
	busy.value = serverName;
	try {
		const result = await api.connections.test(serverName);
		if (result?.success) {
			const count = result.tool_count ?? (result.tools || []).length;
			showSuccess(`Reached ${serverName} — ${count} tool${count === 1 ? "" : "s"} available.`);
			if (connections.value.find((c) => c.server_name === serverName)?.status !== "Active") {
				await reload();
			}
		} else if (result?.needs_reauth) {
			// AR has just marked the row as expired, so reloading is what puts
			// the Reconnect button on screen.
			showError(`${serverName} needs reconnecting — its access has expired.`);
			await reload();
		} else {
			showError(result?.error || `Couldn't reach ${serverName}.`);
		}
	} catch (err) {
		showError(err?.message || `Couldn't reach ${serverName}.`);
	} finally {
		busy.value = null;
	}
}

async function toggleEnabled(serverName) {
	const connection = connections.value.find((c) => c.server_name === serverName);
	if (!connection) return;
	busy.value = serverName;
	try {
		await api.connections.setEnabled(serverName, connection.enabled === false);
		await reload();
	} catch (err) {
		showError(err?.message || `Couldn't update ${serverName}.`);
	} finally {
		busy.value = null;
	}
}

function requestRemove(serverName) {
	removeTarget.value = serverName;
}

function cancelRemove() {
	removeTarget.value = null;
}

async function confirmRemove() {
	const serverName = removeTarget.value;
	if (!serverName) return;
	removeTarget.value = null;
	busy.value = serverName;
	try {
		await api.connections.remove(serverName);
		showSuccess(`Removed ${serverName}.`);
		await reload();
	} catch (err) {
		showError(err?.message || `Couldn't remove ${serverName}.`);
	} finally {
		busy.value = null;
	}
}

// The wizard owns ADD; ConnectionForm keeps EDIT.
function openWizard() {
	closeForm();
	wizardHandle.value = "";
	wizardReauth.value = "";
	wizardOpen.value = true;
}

// A reconnect passes no URL. begin_mcp_reauth reads the endpoint off the row
// being re-authorized, so the wizard cannot retarget an existing connection at
// a different server, and the user is never asked to retype a URL they already
// registered.
function openReconnect(serverName) {
	closeForm();
	wizardHandle.value = "";
	wizardReauth.value = serverName;
	wizardOpen.value = true;
}

function closeWizard() {
	wizardOpen.value = false;
	wizardHandle.value = "";
	wizardReauth.value = "";
}

async function onWizardAdded() {
	closeWizard();
	await reload();
}

function openEditForm(serverName) {
	const connection = connections.value.find((c) => c.server_name === serverName);
	if (!connection) return;
	editingConnection.value = connection;
	formOpen.value = true;
}

function closeForm() {
	formOpen.value = false;
	editingConnection.value = null;
}

async function saveConnection(payload) {
	formSaving.value = true;
	try {
		// AR treats a blank api_key as "leave the existing one alone" — the same
		// call covers both create and edit, no branching needed here.
		await api.connections.add(payload);
		showSuccess(editingConnection.value ? "Connection updated." : "Connection added.");
		closeForm();
		await reload();
	} catch (err) {
		showError(err?.message || "Couldn't save that connection.");
	} finally {
		formSaving.value = false;
	}
}

async function openTools(serverName) {
	busy.value = serverName;
	toolsModalTarget.value = null;
	try {
		const result = await api.connections.test(serverName);
		if (!result?.success) {
			// An expired connection has tools; we just can't see them. Saying
			// "couldn't load tools" invites the user to doubt the server.
			if (result?.needs_reauth) {
				showError(`Reconnect ${serverName} to see its tools — its access has expired.`);
				await reload();
			} else {
				showError(result?.error || `Couldn't load tools for ${serverName}.`);
			}
			return;
		}
		const connection = connections.value.find((c) => c.server_name === serverName);
		// A successful probe may have refreshed a token AR had flagged as
		// expired. Re-read so the row stops offering a Reconnect it no longer
		// needs while the picker is open over it.
		if (connection && connection.status !== "Active") reload();
		toolsModalTools.value = result.tools || [];
		toolsModalDetails.value = result.tool_details || [];
		toolsModalBlocked.value = connection?.blocked_tools || [];
		toolsModalSlug.value = connection?.slug || "";
		toolsModalManaged.value = Boolean(connection?.managed);
		// Approval preferences live in AR against the model-visible tool name,
		// separately from this server's visibility list. A failure to read them
		// is not a reason to refuse the picker — it falls back to the defaults.
		try {
			const prefs = await api.tools.listPreferences();
			toolsModalPreferences.value = prefs?.preferences || {};
		} catch {
			toolsModalPreferences.value = {};
		}
		toolsModalTarget.value = serverName;
	} catch (err) {
		showError(err?.message || `Couldn't load tools for ${serverName}.`);
	} finally {
		busy.value = null;
	}
}

function closeTools() {
	toolsModalTarget.value = null;
}

async function saveToolVisibility({ server_name, blocked_tools, preferences = [] }) {
	toolsModalSaving.value = true;
	try {
		// Visibility first: it is the one that changes what the assistant is
		// shown at all, so if the preference writes fail the user is left with
		// the safer half applied rather than a tool exposed on a stale rule.
		await api.connections.setToolVisibility(server_name, blocked_tools);
		for (const { tool_name, preference } of preferences) {
			await api.tools.setPreference(tool_name, preference);
		}
		showSuccess("Tool permissions updated.");
		closeTools();
		await reload();
	} catch (err) {
		showError(err?.message || "Couldn't save tool permissions.");
	} finally {
		toolsModalSaving.value = false;
	}
}

onMounted(async () => {
	await reload();
	const handle = route.query.connect;
	if (!handle) return;
	// Reconstruct the modal the OAuth round trip left behind, then drop the
	// param: left in place, a refresh would resume a session already spent.
	wizardHandle.value = String(handle);
	wizardReauth.value = "";
	wizardOpen.value = true;
	const { connect, ...rest } = route.query;
	router.replace({ query: rest });
});
</script>

<style scoped>
.connections-settings {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-6);
	width: 100%;
	max-width: 1100px;
	padding: var(--ql-space-6);
}

.connections-header {
	display: flex;
	align-items: flex-end;
	gap: var(--ql-space-4);
}

.connections-heading {
	min-width: 0;
}

.connections-title {
	margin: 0;
	font-family: var(--ql-font-display, Georgia, "Source Serif 4", serif);
	font-size: 22px;
	line-height: 1.15;
	letter-spacing: -0.01em;
	color: var(--ql-text);
}

.connections-stat {
	margin: 3px 0 0;
	font-size: 12px;
	color: var(--ql-text-muted);
}

.connections-add {
	margin-left: auto;
	flex-shrink: 0;
	padding: 7px 14px;
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-accent);
	font: inherit;
	font-size: 0.8125rem;
	color: var(--ql-surface);
	cursor: pointer;
	transition: background 0.12s ease;
}

.connections-add:hover {
	background: var(--ql-accent-hover);
	border-color: var(--ql-accent-hover);
}

/* One ruled panel, not a deck of cards: these are entries in a ledger of what
   the assistant can reach, and reading down them should feel continuous. */
.connections-ledger {
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	overflow: hidden;
}

.connections-ledger > * + * {
	border-top: 1px solid var(--ql-border);
}

.connections-notice {
	margin: 0;
	font-size: 0.875rem;
	color: var(--ql-text-secondary);
}

.connections-blank {
	padding: var(--ql-space-12) var(--ql-space-6);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	background: var(--ql-surface);
	text-align: center;
}

.connections-blank__title {
	margin: 0;
	font-family: var(--ql-font-display, Georgia, "Source Serif 4", serif);
	font-size: 17px;
	color: var(--ql-text);
}

.connections-blank__text {
	max-width: 46ch;
	margin: var(--ql-space-2) auto 0;
	font-size: 0.8125rem;
	line-height: 1.6;
	color: var(--ql-text-muted);
}

.connections-retry {
	margin-left: 0.375rem;
	padding: 0;
	background: none;
	border: none;
	font: inherit;
	color: var(--ql-accent);
	cursor: pointer;
	text-decoration: underline;
}

@media (max-width: 640px) {
	.connections-settings {
		padding: var(--ql-space-4);
	}

	.connections-header {
		flex-wrap: wrap;
		align-items: flex-start;
	}

	.connections-add {
		margin-left: 0;
	}
}
</style>
