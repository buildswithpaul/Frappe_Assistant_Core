<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="drawer-overlay"
			role="dialog"
			aria-modal="true"
			aria-label="Agent settings"
			@click.self="close"
		>
			<aside class="drawer">
				<header class="drawer-header">
					<h2 class="drawer-title">Agent Settings</h2>
					<button class="close-btn" title="Close" aria-label="Close" @click="close">
						<svg
							width="18"
							height="18"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
				</header>

				<div class="drawer-body">
					<!-- Runs as — the single most consequential setting: it decides
					     whose MCP tools every agent node can reach. -->
					<section class="runs-as" :class="{ unset: !form.default_user_id }">
						<span class="runs-as-label">Runs as</span>
						<strong class="runs-as-value">{{
							form.default_user_id || "Not set"
						}}</strong>
						<p class="runs-as-hint">
							{{
								form.default_user_id
									? "Agent nodes use this user's MCP servers and tools."
									: "Without a user, agent nodes run with no tools at all."
							}}
						</p>
						<div class="runs-as-controls">
							<input
								v-model.trim="form.default_user_id"
								class="field-input"
								placeholder="user@example.com"
							/>
							<button
								v-if="canUseMyAccount"
								class="link-btn"
								@click="form.default_user_id = currentUser"
							>
								Use my account
							</button>
						</div>
					</section>

					<div class="field">
						<label class="field-label">Default model</label>
						<select v-model="form.default_model_id" class="field-input">
							<option value="">Provider default</option>
							<optgroup v-for="group in modelGroups" :key="group.tier" :label="group.tier">
								<option v-for="m in group.models" :key="m.model_id" :value="m.model_id">
									{{ m.display_name || m.model_id }}
								</option>
							</optgroup>
						</select>
						<p class="field-hint">Used by any agent node that does not pick its own.</p>
					</div>

					<div class="field">
						<label class="field-label">On node failure</label>
						<select v-model="form.error_strategy" class="field-input">
							<option value="fail_fast">Fail fast — stop the run</option>
							<option value="retry">Retry — re-run the whole agent</option>
						</select>
					</div>

					<div class="field-row">
						<div class="field">
							<label class="field-label">Timeout (seconds)</label>
							<input
								v-model.number="form.timeout_seconds"
								type="number"
								min="30"
								max="3600"
								class="field-input"
							/>
						</div>
						<div class="field">
							<label class="field-label">Max retries</label>
							<input
								v-model.number="form.max_retries"
								type="number"
								min="0"
								max="5"
								class="field-input"
							/>
						</div>
					</div>

					<div class="field">
						<label class="field-label">Max node executions</label>
						<input
							v-model.number="form.max_node_executions"
							type="number"
							min="1"
							max="500"
							class="field-input"
						/>
						<p class="field-hint">
							Ceiling on how many nodes one run may execute — the guard against a
							loop.
						</p>
					</div>

					<p v-if="error" class="drawer-error">{{ error }}</p>
				</div>

				<footer class="drawer-footer">
					<button class="action-btn" @click="close">Cancel</button>
					<button class="action-btn primary" :disabled="isSaving" @click="save">
						{{ isSaving ? "Saving…" : "Save settings" }}
					</button>
				</footer>
			</aside>
		</div>
	</Teleport>
</template>

<script setup>
import { reactive, computed, watch } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	/** The AR Workflow record as returned by get_workflow. */
	workflow: { type: Object, default: null },
	models: { type: Array, default: () => [] },
	currentUser: { type: String, default: "" },
	isSaving: { type: Boolean, default: false },
	error: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "save"]);

const DEFAULTS = {
	default_user_id: "",
	default_model_id: "",
	error_strategy: "fail_fast",
	timeout_seconds: 600,
	max_retries: 0,
	max_node_executions: 50,
};

const form = reactive({ ...DEFAULTS });

// AR keys tenant users by email; a Frappe username like "Administrator" would
// never resolve, so it is not offered as a one-click default.
const canUseMyAccount = computed(() => props.currentUser.includes("@"));

const modelGroups = computed(() => {
	const groups = new Map();
	for (const m of props.models) {
		if (!m?.model_id) continue;
		const tier = m.tier || m.tier_name || "Other";
		if (!groups.has(tier)) groups.set(tier, { tier, rank: m.tier_rank ?? 999, models: [] });
		groups.get(tier).models.push(m);
	}
	return [...groups.values()].sort((a, b) => a.rank - b.rank);
});

watch(
	() => props.modelValue,
	(open) => {
		if (!open) return;
		const wf = props.workflow || {};
		for (const key of Object.keys(DEFAULTS)) {
			form[key] = wf[key] ?? DEFAULTS[key];
		}
		// Frappe Int columns are NOT NULL DEFAULT 0; a zero timeout is "unset",
		// not "no time at all".
		if (!form.timeout_seconds) form.timeout_seconds = DEFAULTS.timeout_seconds;
		if (!form.max_node_executions) form.max_node_executions = DEFAULTS.max_node_executions;
		if (form.error_strategy === "continue") form.error_strategy = "fail_fast";
	}
);

function close() {
	emit("update:modelValue", false);
}

function save() {
	emit("save", {
		default_user_id: form.default_user_id || "",
		default_model_id: form.default_model_id || "",
		error_strategy: form.error_strategy,
		timeout_seconds: Number(form.timeout_seconds) || DEFAULTS.timeout_seconds,
		max_retries: Number(form.max_retries) || 0,
		max_node_executions: Number(form.max_node_executions) || DEFAULTS.max_node_executions,
	});
}
</script>

<style scoped>
.drawer-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.4);
	display: flex;
	justify-content: flex-end;
	z-index: 1050;
}

.drawer {
	width: 100%;
	max-width: 24rem;
	height: 100%;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
	display: flex;
	flex-direction: column;
	box-shadow: -12px 0 40px rgba(0, 0, 0, 0.25);
}

.drawer-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
}

.drawer-title {
	margin: 0;
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}

.close-btn {
	display: flex;
	width: 28px;
	height: 28px;
	align-items: center;
	justify-content: center;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.drawer-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.25rem;
}

.runs-as {
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.75rem;
	margin-bottom: 1.25rem;
	background: var(--ql-subtle);
}

.runs-as.unset {
	border-color: var(--ql-warning);
}

.runs-as-label {
	display: block;
	font-size: 0.6875rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.025em;
	color: var(--ql-text-muted);
}

.runs-as-value {
	display: block;
	font-size: 0.9375rem;
	color: var(--ql-text);
	margin-top: 0.125rem;
	word-break: break-all;
}

.runs-as-hint {
	margin: 0.25rem 0 0.5rem;
	font-size: 0.6875rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
}

.runs-as-controls {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.link-btn {
	flex-shrink: 0;
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-accent);
	background: transparent;
	border: none;
	cursor: pointer;
	padding: 0;
	white-space: nowrap;
}

.field {
	margin-bottom: 1rem;
	flex: 1;
	min-width: 0;
}

.field-row {
	display: flex;
	gap: 0.75rem;
}

.field-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0.375rem;
}

.field-input {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	box-sizing: border-box;
}

.field-input:focus {
	border-color: var(--ql-accent);
}

.field-hint {
	margin: 0.25rem 0 0;
	font-size: 0.6875rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
}

.drawer-error {
	margin: 0.75rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-danger);
}

.drawer-footer {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	padding: 0.875rem 1.25rem;
	border-top: 1px solid var(--ql-border);
}

.action-btn {
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
}

.action-btn:hover {
	background: var(--ql-border);
}

.action-btn.primary {
	color: #fff;
	background: var(--ql-accent);
}

.action-btn.primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
