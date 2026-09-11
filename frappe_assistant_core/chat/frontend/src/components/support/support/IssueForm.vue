<template>
	<form class="issue-form" @submit.prevent="onSubmit">
		<label class="field">
			<span>Subject</span>
			<input v-model.trim="subject" type="text" maxlength="140"
				placeholder="Brief summary" required />
		</label>

		<label class="field">
			<span>Category</span>
			<select v-model="category">
				<option value="Bug">Bug</option>
				<option value="Issue">Issue</option>
				<option value="Question">Question</option>
			</select>
		</label>

		<label class="field">
			<span>Details</span>
			<textarea v-model.trim="description" rows="5"
				placeholder="What happened? What did you expect?" required />
		</label>

		<div class="field" @paste="attachments.handlePaste">
			<span>Attachments</span>
			<AttachmentPicker
				:files="attachments.files.value"
				:disabled="submitting"
				@add="attachments.addFiles"
				@remove="attachments.removeFile"
				@retry="attachments.retryFile"
			/>
		</div>

		<div v-if="conversationId" class="field-check-group">
			<label class="field-check">
				<input v-model="includeConversation" type="checkbox" />
				<span>Include this conversation</span>
			</label>
			<p class="field-check-hint">
				Attaches a transcript of this chat to your ticket so support can see
				what happened.
			</p>
		</div>

		<EnvironmentDisclosure :environment="environment" />

		<div class="actions">
			<button type="button" class="btn-ghost" @click="$emit('cancel')">Cancel</button>
			<button type="submit" class="btn-primary" :disabled="submitting">
				{{ submitting ? "Submitting…" : "Submit" }}
			</button>
		</div>
	</form>
</template>

<script setup>
import { ref } from "vue";
import EnvironmentDisclosure from "./EnvironmentDisclosure.vue";
import AttachmentPicker from "./AttachmentPicker.vue";
import { useTicketAttachments } from "@/composables/useTicketAttachments.js";

const props = defineProps({
	conversationId: { type: String, default: null },
	environment: { type: Object, required: true },
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["submit", "cancel"]);

const subject = ref("");
const category = ref("Bug");
const description = ref("");
const includeConversation = ref(false);
const attachments = useTicketAttachments();

function onSubmit() {
	emit("submit", {
		subject: subject.value,
		description: description.value,
		category: category.value,
		conversationId:
			includeConversation.value && props.conversationId ? props.conversationId : null,
		environment: props.environment,
		attachmentIds: attachments.consumeAttachmentIds(),
	});
}
</script>

<style scoped>
.issue-form { display: flex; flex-direction: column; gap: 0.75rem; }
.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field span { font-size: 0.85rem; font-weight: 600; color: var(--ql-text-secondary); }
.field input, .field select, .field textarea {
	padding: 0.5rem; border: 1px solid var(--ql-border); border-radius: var(--ql-radius-sm); font: inherit;
	background: var(--ql-surface); color: var(--ql-text);
}
.field input::placeholder, .field textarea::placeholder { color: var(--ql-text-muted); }
.field input:focus, .field select:focus, .field textarea:focus { outline: none; border-color: var(--ql-accent); }
.field-check-group { display: flex; flex-direction: column; gap: 0.15rem; }
.field-check { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; color: var(--ql-text-secondary); }
.field-check-hint { margin: 0 0 0 1.6rem; font-size: 0.78rem; color: var(--ql-text-muted); }
.actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }
.btn-primary { padding: 0.5rem 1rem; border-radius: var(--ql-radius-sm); border: none; background: var(--ql-accent); color: #fff; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: default; }
.btn-ghost { padding: 0.5rem 1rem; border-radius: var(--ql-radius-sm); border: 1px solid var(--ql-border); background: none; color: var(--ql-text-secondary); cursor: pointer; }
</style>
