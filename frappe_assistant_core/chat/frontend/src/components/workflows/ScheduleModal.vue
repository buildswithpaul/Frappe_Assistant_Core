<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="modal-overlay"
			role="dialog"
			aria-modal="true"
			aria-label="Schedule agent"
			@click.self="close"
		>
			<div class="modal-content">
				<h2 class="modal-title">Schedule Agent</h2>
				<div class="modal-field">
					<label class="field-label">Cron Expression</label>
					<input
						v-model="localConfig.cron"
						class="field-input mono"
						placeholder="*/30 * * * *"
					/>
					<p class="schedule-hint">
						Examples: <code>*/30 * * * *</code> (every 30min),
						<code>0 9 * * 1-5</code> (weekdays 9am), <code>0 0 * * *</code> (daily
						midnight)
					</p>
				</div>
				<div class="modal-field">
					<label class="field-label">Timezone</label>
					<select v-model="localConfig.timezone" class="field-input">
						<option value="UTC">UTC</option>
						<option value="US/Eastern">US/Eastern</option>
						<option value="US/Central">US/Central</option>
						<option value="US/Pacific">US/Pacific</option>
						<option value="Europe/London">Europe/London</option>
						<option value="Europe/Berlin">Europe/Berlin</option>
						<option value="Asia/Kolkata">Asia/Kolkata</option>
						<option value="Asia/Tokyo">Asia/Tokyo</option>
						<option value="Asia/Shanghai">Asia/Shanghai</option>
						<option value="Australia/Sydney">Australia/Sydney</option>
					</select>
				</div>
				<div class="modal-field">
					<label class="field-label"
						>Default Input <span class="optional-label">(optional)</span></label
					>
					<textarea
						v-model="localConfig.defaultInput"
						class="field-input field-textarea mono"
						placeholder="Default input data for scheduled runs"
						rows="3"
					></textarea>
				</div>
				<div class="modal-field checkbox-field">
					<label class="checkbox-inline">
						<input type="checkbox" v-model="localConfig.enabled" />
						<span>Enable schedule</span>
					</label>
				</div>
				<div class="modal-actions">
					<button @click="close" class="action-btn">Cancel</button>
					<button
						@click="save"
						class="action-btn primary"
						:disabled="!localConfig.cron.trim() || isSaving"
					>
						{{ isSaving ? "Saving..." : "Save Schedule" }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { reactive, watch } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, required: true },
	config: { type: Object, required: true },
	isSaving: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "save"]);

const localConfig = reactive({
	cron: "",
	timezone: "UTC",
	defaultInput: "",
	enabled: true,
});

// Sync from parent config when modal opens
watch(
	() => props.modelValue,
	(open) => {
		if (open) {
			localConfig.cron = props.config.cron || "";
			localConfig.timezone = props.config.timezone || "UTC";
			localConfig.defaultInput = props.config.defaultInput || "";
			// `!== false` re-enabled a schedule hydrated from a Frappe Check int.
			localConfig.enabled = props.config.enabled === true;
		}
	}
);

function close() {
	emit("update:modelValue", false);
}

function save() {
	emit("save", { ...localConfig });
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1050;
	padding: 1rem;
}

.modal-content {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.5rem;
	width: 100%;
	max-width: 28rem;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 1.25rem;
}

.modal-field {
	margin-bottom: 1rem;
}

.field-label {
	display: block;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	margin-bottom: 0.375rem;
}

.field-input {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	box-sizing: border-box;
}

.field-input:focus {
	border-color: var(--ql-accent);
}
.field-input.mono {
	font-family: "SF Mono", Monaco, monospace;
}
.field-textarea {
	resize: vertical;
	min-height: 4rem;
	font-family: inherit;
}
.field-textarea.mono {
	font-family: "SF Mono", Monaco, monospace;
	font-size: 0.8125rem;
}

.modal-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: 1.25rem;
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.action-btn:hover {
	background-color: var(--ql-border);
}
.action-btn.primary {
	color: white;
	background-color: var(--ql-accent);
}
.action-btn.primary:hover {
	opacity: 0.9;
}
.action-btn.primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.schedule-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
	line-height: 1.4;
}

.schedule-hint code {
	background: var(--ql-subtle);
	padding: 0.0625rem 0.25rem;
	border-radius: 0.1875rem;
	font-size: 0.6875rem;
}

.optional-label {
	font-weight: 400;
	color: var(--ql-text-muted);
}

.checkbox-field {
	margin-top: 0.5rem;
}

.checkbox-inline {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	cursor: pointer;
}

.checkbox-inline input[type="checkbox"] {
	accent-color: var(--ql-accent);
}
</style>
