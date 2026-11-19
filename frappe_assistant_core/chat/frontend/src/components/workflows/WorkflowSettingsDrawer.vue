<template>
	<Teleport :to="teleportTarget">
		<div
			v-if="modelValue"
			class="drawer-overlay"
			role="dialog"
			aria-modal="true"
			aria-label="Advanced settings"
			@click.self="close"
		>
			<aside class="drawer">
				<header class="drawer-header">
					<h2 class="drawer-title">Advanced settings</h2>
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
import { reactive, watch } from "vue";
import { useTeleportTarget } from "@/composables/useTeleportTarget";

const teleportTarget = useTeleportTarget();

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	/** The AR Workflow record as returned by get_workflow. */
	workflow: { type: Object, default: null },
	isSaving: { type: Boolean, default: false },
	error: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "save"]);

const DEFAULTS = {
	error_strategy: "fail_fast",
	timeout_seconds: 600,
	max_retries: 0,
	max_node_executions: 50,
};

const form = reactive({ ...DEFAULTS });

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
