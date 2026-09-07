<template>
	<div v-if="show" class="modal-backdrop" @click.self="$emit('close')">
		<div class="modal-box">
			<h3 class="modal-title">Report Template</h3>
			<p class="modal-desc">Flag this template for review by our moderation team.</p>

			<div class="form-group">
				<label class="form-label">Reason</label>
				<select v-model="reason" class="form-select">
					<option value="">Select a reason...</option>
					<option value="Spam">Spam</option>
					<option value="Offensive Content">Offensive Content</option>
					<option value="Malicious">Malicious</option>
					<option value="Broken">Broken</option>
					<option value="Copyright">Copyright</option>
					<option value="Other">Other</option>
				</select>
			</div>

			<div class="form-group">
				<label class="form-label">Details <span class="optional">(optional)</span></label>
				<textarea
					v-model="details"
					class="form-textarea"
					rows="3"
					placeholder="Provide additional context..."
				></textarea>
			</div>

			<div class="modal-actions">
				<button @click="$emit('close')" class="btn-cancel">Cancel</button>
				<button @click="submit" class="btn-submit" :disabled="!reason || isSubmitting">
					{{ isSubmitting ? "Submitting..." : "Submit Report" }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { useWorkflowStore } from "@/stores/workflowStore";

const props = defineProps({
	show: { type: Boolean, default: false },
	templateName: { type: String, default: "" },
});

const emit = defineEmits(["close", "reported"]);

const store = useWorkflowStore();
const reason = ref("");
const details = ref("");
const isSubmitting = ref(false);

async function submit() {
	if (!reason.value || isSubmitting.value) return;
	isSubmitting.value = true;
	try {
		await store.reportTemplate(props.templateName, reason.value, details.value || null);
		emit("reported");
		emit("close");
		reason.value = "";
		details.value = "";
	} catch {
		// Error already set in store
	} finally {
		isSubmitting.value = false;
	}
}
</script>

<style scoped>
.modal-backdrop {
	position: fixed;
	inset: 0;
	z-index: 1050;
	background: rgba(0, 0, 0, 0.4);
	display: flex;
	align-items: center;
	justify-content: center;
}
.modal-box {
	background: var(--ql-surface);
	border-radius: 0.75rem;
	padding: 1.5rem;
	width: 100%;
	max-width: 400px;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}
.modal-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.25rem;
}
.modal-desc {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0 0 1rem;
}
.form-group {
	margin-bottom: 0.875rem;
}
.form-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.25rem;
}
.optional {
	font-weight: 400;
	color: var(--ql-text-muted);
}
.form-select,
.form-textarea {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-bg);
	color: var(--ql-text);
}
.form-textarea {
	resize: vertical;
	font-family: inherit;
}
.modal-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: 1rem;
}
.btn-cancel {
	padding: 0.4375rem 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}
.btn-submit {
	padding: 0.4375rem 0.875rem;
	font-size: 0.8125rem;
	color: white;
	background: var(--ql-danger);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}
.btn-submit:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
</style>
