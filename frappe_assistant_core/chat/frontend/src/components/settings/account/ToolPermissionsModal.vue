<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="tool-perms-modal">
				<div class="modal-header">
					<div class="modal-title">
						<h3>Tool Permissions</h3>
						<span v-if="server" class="modal-subtitle">{{ server.server_name }}</span>
					</div>
					<button class="modal-close-btn" @click="$emit('close')" aria-label="Close">
						&times;
					</button>
				</div>

				<div class="modal-body">
					<p class="modal-description">
						Control how this assistant uses each tool.
						<strong>Always Allow</strong> runs without asking.
						<strong>Ask</strong> prompts you before the action.
						<strong>Block</strong> refuses the tool entirely.
						By default, read-only tools (reading, listing, searching)
						run without asking, and tools that change data ask first.
					</p>

					<!-- Error toast — inline, dismissable, doesn't hide the tools list -->
					<div v-if="errorBanner" class="error-banner" role="alert">
						<svg
							class="error-banner-icon"
							width="16"
							height="16"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
							/>
						</svg>
						<span class="error-banner-text">{{ errorBanner }}</span>
						<button
							class="error-banner-close"
							@click="errorBanner = ''"
							aria-label="Dismiss"
						>
							&times;
						</button>
					</div>

					<!-- Bulk actions -->
					<div v-if="!loading && tools.length > 0" class="bulk-controls">
						<span class="bulk-label">Set all to:</span>
						<button
							v-for="option in OPTIONS"
							:key="`bulk-${option.value}`"
							:class="['bulk-btn', `bulk-${option.value}`]"
							:disabled="bulkApplying"
							@click="applyBulk(option.value)"
						>
							{{ option.label }}
						</button>
						<span v-if="bulkApplying" class="bulk-status">
							Applying… {{ bulkProgress.done }}/{{ bulkProgress.total }}
						</span>
					</div>

					<div v-if="loading" class="modal-loading-state">
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
						<span>Loading tools...</span>
					</div>

					<div v-else-if="tools.length === 0" class="modal-empty-state">
						No tools available for your account.
					</div>

					<div v-else class="tool-groups">
						<div
							v-for="group in groupedTools"
							:key="group.category"
							class="tool-group"
						>
							<h4 class="tool-group-heading">{{ group.category }}</h4>
							<div class="tool-list">
								<div v-for="tool in group.tools" :key="tool.name" class="tool-row">
									<div class="tool-info">
										<div class="tool-name-row">
											<span class="tool-name">{{ tool.name }}</span>
											<span
												v-if="tool.read_only && !preferences[tool.name]"
												class="tool-badge tool-badge-readonly"
											>
												Read-only · auto-allowed
											</span>
											<span
												v-else-if="tool.default_requires_approval"
												class="tool-badge"
											>
												Requires approval by default
											</span>
											<span v-if="savingTools[tool.name]" class="tool-saving"
												>Saving…</span
											>
											<span
												v-else-if="savedTools[tool.name]"
												class="tool-saved"
												>Saved</span
											>
										</div>
										<p v-if="tool.description" class="tool-description">
											{{ tool.description }}
										</p>
									</div>
									<div
										class="segmented-control"
										role="radiogroup"
										:aria-label="`Preference for ${tool.name}`"
									>
										<button
											v-for="option in OPTIONS"
											:key="option.value"
											role="radio"
											:aria-checked="
												preferenceFor(tool.name) === option.value
											"
											:class="[
												'segmented-option',
												`segmented-${option.value}`,
												{
													'is-active':
														preferenceFor(tool.name) === option.value,
												},
											]"
											:disabled="savingTools[tool.name]"
											@click="handleChange(tool.name, option.value)"
										>
											{{ option.label }}
										</button>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "@/api/client";

const props = defineProps({
	isOpen: { type: Boolean, required: true },
	server: { type: Object, default: null },
});

defineEmits(["close"]);

const OPTIONS = Object.freeze([
	{ value: "block", label: "Block" },
	{ value: "ask", label: "Ask" },
	{ value: "always_allow", label: "Always Allow" },
]);

const loading = ref(false);
const errorBanner = ref("");
const tools = ref([]);
const preferences = reactive({});
const savingTools = reactive({});
const savedTools = reactive({});
const bulkApplying = ref(false);
const bulkProgress = reactive({ done: 0, total: 0 });

function humanizeError(err) {
	// Frappe typically returns a JSON body with a nested `_server_messages`
	// array whose entries are JSON-encoded objects like {"message":"..."}.
	// Surface the message only — the full traceback is noise for the user.
	if (!err) return "Something went wrong. Please try again.";
	const raw = err.message || String(err);
	// Try to extract the server message out of a JSON error string.
	const match = raw.match(/"message":\s*"([^"\\]+(?:\\.[^"\\]*)*)"/);
	if (match && match[1]) {
		return match[1].replace(/\\"/g, '"').replace(/\\n/g, " ");
	}
	// Fallback: strip "API Error: 417 - " prefix and Python traceback noise.
	const cleaned = raw.replace(/^API Error:\s*\d+\s*-\s*/, "");
	if (cleaned.length > 200) return cleaned.slice(0, 200) + "…";
	return cleaned;
}

const groupedTools = computed(() => {
	const map = new Map();
	for (const tool of tools.value) {
		const key = tool.category || "General";
		if (!map.has(key)) map.set(key, []);
		map.get(key).push(tool);
	}
	return Array.from(map.entries())
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([category, items]) => ({ category, tools: items }));
});

// name -> tool, so preferenceFor can read the per-tool read_only flag.
const toolByName = computed(() => {
	const map = new Map();
	for (const tool of tools.value) map.set(tool.name, tool);
	return map;
});

// The effective default when the user has set no explicit preference:
// read-only tools auto-allow (matches AR's runtime gate), everything else asks.
function defaultPreferenceFor(toolName) {
	return toolByName.value.get(toolName)?.read_only ? "always_allow" : "ask";
}

function preferenceFor(toolName) {
	return preferences[toolName] || defaultPreferenceFor(toolName);
}

async function loadData() {
	loading.value = true;
	errorBanner.value = "";
	try {
		const [toolsResp, prefsResp] = await Promise.all([
			api.tools.listAvailable(),
			api.tools.listPreferences(),
		]);
		tools.value = toolsResp?.tools || [];
		const prefs = prefsResp?.preferences || {};
		// Reset reactive dict (clear stale entries, then refill)
		for (const key of Object.keys(preferences)) delete preferences[key];
		for (const [name, value] of Object.entries(prefs)) {
			preferences[name] = value;
		}
	} catch (err) {
		errorBanner.value = `Couldn't load tools — ${humanizeError(err)}`;
	} finally {
		loading.value = false;
	}
}

async function handleChange(toolName, preference) {
	const previous = preferences[toolName] || defaultPreferenceFor(toolName);
	if (previous === preference) return;

	preferences[toolName] = preference;
	savingTools[toolName] = true;
	delete savedTools[toolName];

	try {
		await api.tools.setPreference(toolName, preference);
		savedTools[toolName] = true;
		setTimeout(() => {
			delete savedTools[toolName];
		}, 1500);
	} catch (err) {
		// Revert on failure so the UI reflects the actual server state.
		preferences[toolName] = previous;
		errorBanner.value = `Couldn't save ${toolName} — ${humanizeError(err)}`;
	} finally {
		delete savingTools[toolName];
	}
}

async function applyBulk(preference) {
	if (bulkApplying.value || tools.value.length === 0) return;
	errorBanner.value = "";
	bulkApplying.value = true;
	bulkProgress.total = tools.value.length;
	bulkProgress.done = 0;

	// Snapshot previous so we can revert entries that fail.
	const previousByTool = {};
	for (const t of tools.value) {
		previousByTool[t.name] = preferences[t.name] || defaultPreferenceFor(t.name);
		preferences[t.name] = preference;
	}

	const failures = [];
	// Issue requests sequentially to avoid hammering the server and to keep
	// progress legible. ~30 tools × ~100ms = well under 5s in practice.
	// Always write rows on bulk apply — the user's intent is explicit
	// ("set everything to X"), even for tools whose current DB state is
	// already X. This makes preferences durable and visible in AR's audit.
	for (const t of tools.value) {
		try {
			await api.tools.setPreference(t.name, preference);
		} catch (err) {
			preferences[t.name] = previousByTool[t.name];
			failures.push(t.name);
		}
		bulkProgress.done += 1;
	}

	bulkApplying.value = false;
	if (failures.length > 0) {
		errorBanner.value = `Couldn't apply to ${failures.length} tool${
			failures.length === 1 ? "" : "s"
		}: ${failures.slice(0, 3).join(", ")}${failures.length > 3 ? "…" : ""}`;
	}
}

onMounted(() => {
	if (props.isOpen) loadData();
});

watch(
	() => props.isOpen,
	(open) => {
		if (open) loadData();
	}
);
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1200;
	padding: 1rem;
}

.tool-perms-modal {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	width: 100%;
	max-width: 720px;
	max-height: 90vh;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.modal-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
}

.modal-title h3 {
	margin: 0;
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}

.modal-subtitle {
	display: block;
	margin-top: 0.125rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary, var(--ql-text));
	opacity: 0.7;
}

.modal-close-btn {
	background: transparent;
	border: none;
	font-size: 1.5rem;
	line-height: 1;
	color: var(--ql-text);
	cursor: pointer;
	padding: 0 0.25rem;
	opacity: 0.6;
}
.modal-close-btn:hover {
	opacity: 1;
}

.modal-body {
	padding: 1rem 1.25rem;
	overflow-y: auto;
}

.modal-description {
	margin: 0 0 1rem 0;
	font-size: 0.8125rem;
	color: var(--ql-text);
	opacity: 0.8;
	line-height: 1.5;
}

.modal-loading-state,
.modal-empty-state {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 2rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	opacity: 0.7;
}

/* Inline error banner (toast-style, dismissable) */
.error-banner {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	padding: 0.625rem 0.75rem;
	margin-bottom: 0.75rem;
	background: rgba(220, 38, 38, 0.08);
	border: 1px solid rgba(220, 38, 38, 0.2);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	color: #b91c1c;
	line-height: 1.4;
}

.error-banner-icon {
	flex-shrink: 0;
	margin-top: 0.0625rem;
}

.error-banner-text {
	flex: 1;
	word-break: break-word;
}

.error-banner-close {
	flex-shrink: 0;
	background: transparent;
	border: none;
	color: inherit;
	font-size: 1.125rem;
	line-height: 1;
	cursor: pointer;
	opacity: 0.6;
	padding: 0 0.25rem;
}
.error-banner-close:hover {
	opacity: 1;
}

/* Bulk action controls */
.bulk-controls {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.625rem 0.75rem;
	margin-bottom: 0.875rem;
	background: rgba(0, 0, 0, 0.03);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	flex-wrap: wrap;
}

.bulk-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text);
	opacity: 0.75;
	margin-right: 0.125rem;
}

.bulk-btn {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.25rem;
	color: var(--ql-text);
	cursor: pointer;
	transition: all 0.15s ease;
}

.bulk-btn:hover:not(:disabled) {
	background: var(--ql-surface);
}
.bulk-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.bulk-block:hover:not(:disabled) {
	border-color: rgba(220, 38, 38, 0.4);
	color: #b91c1c;
}
.bulk-ask:hover:not(:disabled) {
	border-color: var(--ql-accent-soft);
	color: #2563eb;
}
.bulk-always_allow:hover:not(:disabled) {
	border-color: rgba(16, 185, 129, 0.4);
	color: #059669;
}

.bulk-status {
	margin-left: auto;
	font-size: 0.75rem;
	color: var(--ql-text);
	opacity: 0.7;
}

@media (prefers-color-scheme: dark) {
	.bulk-controls {
		background: rgba(255, 255, 255, 0.04);
	}
	.error-banner {
		background: rgba(220, 38, 38, 0.15);
		color: #fca5a5;
	}
}

.spinner {
	width: 20px;
	height: 20px;
	animation: spin 1s linear infinite;
}
@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.tool-group + .tool-group {
	margin-top: 1.25rem;
}

.tool-group-heading {
	margin: 0 0 0.5rem 0;
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text);
	opacity: 0.6;
}

.tool-list {
	display: flex;
	flex-direction: column;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.tool-row {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 1rem;
	padding: 0.75rem 0.875rem;
	border-bottom: 1px solid var(--ql-border);
}
.tool-row:last-child {
	border-bottom: none;
}

.tool-info {
	flex: 1;
	min-width: 0;
}

.tool-name-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	flex-wrap: wrap;
}

.tool-name {
	font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.tool-badge {
	font-size: 0.6875rem;
	font-weight: 500;
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	background: rgba(245, 158, 11, 0.12);
	color: #b45309;
}

.tool-badge-readonly {
	background: rgba(16, 185, 129, 0.12);
	color: #059669;
}

.tool-saving,
.tool-saved {
	font-size: 0.6875rem;
	color: var(--ql-text);
	opacity: 0.6;
}
.tool-saved {
	color: #059669;
	opacity: 1;
}

.tool-description {
	margin: 0.25rem 0 0 0;
	font-size: 0.75rem;
	color: var(--ql-text);
	opacity: 0.7;
	line-height: 1.4;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.segmented-control {
	display: inline-flex;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	overflow: hidden;
	flex-shrink: 0;
}

.segmented-option {
	background: transparent;
	border: none;
	border-right: 1px solid var(--ql-border);
	padding: 0.375rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text);
	cursor: pointer;
	opacity: 0.7;
	transition: all 0.15s ease;
}
.segmented-option:last-child {
	border-right: none;
}
.segmented-option:hover:not(:disabled) {
	opacity: 1;
	background: rgba(0, 0, 0, 0.03);
}
.segmented-option:disabled {
	cursor: not-allowed;
	opacity: 0.4;
}

.segmented-option.is-active {
	opacity: 1;
	font-weight: 600;
}
.segmented-block.is-active {
	background: rgba(220, 38, 38, 0.12);
	color: #b91c1c;
}
.segmented-ask.is-active {
	background: var(--ql-accent-soft);
	color: #2563eb;
}
.segmented-always_allow.is-active {
	background: rgba(16, 185, 129, 0.12);
	color: #059669;
}

@media (prefers-color-scheme: dark) {
	.segmented-option:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.05);
	}
	.tool-badge {
		background: rgba(245, 158, 11, 0.2);
		color: #fbbf24;
	}
	.tool-badge-readonly {
		background: rgba(16, 185, 129, 0.2);
		color: #34d399;
	}
}
</style>
