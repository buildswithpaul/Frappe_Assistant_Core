<template>
	<Teleport to="body">
		<div v-if="modelValue" class="modal-overlay" @click.self="close">
			<div class="modal-content">
				<div class="modal-header">
					<h2 class="modal-title">New Blank Agent</h2>
					<button @click="close" class="close-btn" title="Close" aria-label="Close">
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
				</div>
				<BlankWorkflowForm
					:visible="modelValue"
					:is-busy="isBusy"
					@cancel="close"
					@create="handleCreate"
				/>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref } from "vue";
import { storeToRefs } from "pinia";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useUserStore } from "@/stores/userStore";
import { logger } from "@/utils/logger";
import BlankWorkflowForm from "./BlankWorkflowForm.vue";

defineProps({
	modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "created"]);

const workflowStore = useWorkflowStore();
const { user } = storeToRefs(useUserStore());
const isBusy = ref(false);

async function handleCreate({ name, description }) {
	if (isBusy.value) return;
	isBusy.value = true;
	try {
		// Seed "Runs as" with the creator so agent nodes have MCP tools from the
		// first save. AR keys tenant users by email, so a non-email Frappe
		// username (Administrator) is left unset rather than stored wrong.
		const defaultUserId = user.value?.includes("@") ? user.value : null;
		const result = await workflowStore.createWorkflow(name, description, { defaultUserId });
		emit("update:modelValue", false);
		if (result?.name) emit("created", result.name);
	} catch (err) {
		logger.error("Failed to create workflow:", err);
	} finally {
		isBusy.value = false;
	}
}

function close() {
	emit("update:modelValue", false);
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
	width: 100%;
	max-width: 28rem;
	max-height: 85vh;
	display: flex;
	flex-direction: column;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.close-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
</style>
