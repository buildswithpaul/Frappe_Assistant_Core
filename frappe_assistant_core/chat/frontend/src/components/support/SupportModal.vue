<template>
	<div v-if="store.isOpen" class="support-overlay" @click.self="onClose">
		<div class="support-modal" role="dialog" aria-modal="true" aria-label="Help and Feedback">
			<header class="modal-head">
				<h2>Help &amp; Feedback</h2>
				<button type="button" class="close" aria-label="Close" @click="onClose">×</button>
			</header>

			<template v-if="!confirmation">
				<div class="mode-toggle" role="tablist">
					<button type="button" :class="{ active: store.mode === 'issue' }"
						@click="store.mode = 'issue'">Report an issue</button>
					<button type="button" :class="{ active: store.mode === 'feedback' }"
						@click="store.mode = 'feedback'">Give feedback</button>
				</div>

				<IssueForm v-if="store.mode === 'issue'"
					:conversation-id="store.conversationId"
					:environment="environment"
					:submitting="submitting"
					@submit="onSubmitIssue" @cancel="onClose" />

				<FeedbackForm v-else
					:submitting="submitting"
					@submit="onSubmitFeedback" @cancel="onClose" />
			</template>

			<SupportConfirmation v-else
				:title="confirmation.title"
				:ticket-id="confirmation.ticketId"
				@done="onClose"
				@track="onTrack" />
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { collectEnvironment, loadServerEnvironment } from "@/utils/collectEnvironment";
import { useSupportStore } from "@/stores/supportStore";
import { useModelStore } from "@/stores/modelStore";
import IssueForm from "./support/IssueForm.vue";
import FeedbackForm from "./support/FeedbackForm.vue";
import SupportConfirmation from "./support/SupportConfirmation.vue";

const store = useSupportStore();
const toast = useToast();
const modelStore = useModelStore();
const router = useRouter();

const submitting = ref(false);
const confirmation = ref(null);

const serverEnvironment = ref({});

const environment = computed(() =>
	collectEnvironment(serverEnvironment.value, {
		model: modelStore.currentModelId || "unknown",
	})
);

// Versions cost a round-trip, so pay for it only once the user opens the modal.
watch(
	() => store.isOpen,
	(open) => {
		if (open) {
			loadServerEnvironment().then((env) => {
				serverEnvironment.value = env || {};
			});
		}
	},
	{ immediate: true }
);

function onClose() {
	confirmation.value = null;
	submitting.value = false;
	store.close();
}

function onTrack(ticketId) {
	onClose();
	router.push({ path: "/settings/my-tickets", query: { ticket: ticketId } });
}

async function onSubmitIssue(payload) {
	submitting.value = true;
	try {
		const res = await api.support.createTicket({
			subject: payload.subject,
			description: payload.description,
			category: payload.category,
			conversationId: payload.conversationId,
			environment: payload.environment,
			attachmentIds: payload.attachmentIds,
		});
		confirmation.value = {
			title: "Thanks — we got your report",
			ticketId: res?.ticket_id || null,
		};
	} catch (err) {
		toast.showError(err?.message || "Couldn't submit your ticket. Please try again.");
	} finally {
		submitting.value = false;
	}
}

async function onSubmitFeedback(payload) {
	submitting.value = true;
	try {
		await api.support.submitFeedback({
			rating: payload.rating,
			comment: payload.comment,
			category: payload.category,
			conversationId: store.conversationId,
			environment: environment.value,
		});
		confirmation.value = {
			title: "Thanks for your feedback",
			ticketId: null,
		};
	} catch (err) {
		toast.showError(err?.message || "Couldn't submit your feedback. Please try again.");
	} finally {
		submitting.value = false;
	}
}
</script>

<style scoped>
.support-overlay {
	position: fixed; inset: 0; background: rgba(16, 24, 40, 0.5);
	display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.support-modal {
	background: var(--ql-surface); color: var(--ql-text); border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl); width: min(520px, 92vw);
	max-height: 88vh; overflow-y: auto; padding: 1.25rem; box-shadow: 0 20px 48px rgba(0, 0, 0, 0.25);
}
.modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
.modal-head h2 { margin: 0; font-size: 1.1rem; color: var(--ql-text); }
.close { background: none; border: none; font-size: 1.5rem; cursor: pointer; line-height: 1; color: var(--ql-text-muted); }
.close:hover { color: var(--ql-text); }
.mode-toggle { display: flex; gap: 0.25rem; background: var(--ql-subtle); padding: 0.25rem; border-radius: var(--ql-radius-md); margin-bottom: 1rem; }
.mode-toggle button { flex: 1; padding: 0.4rem; border: none; background: none; border-radius: var(--ql-radius-sm); cursor: pointer; font: inherit; color: var(--ql-text-secondary); }
.mode-toggle button.active { background: var(--ql-surface); color: var(--ql-text); font-weight: 600; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12); }
</style>
