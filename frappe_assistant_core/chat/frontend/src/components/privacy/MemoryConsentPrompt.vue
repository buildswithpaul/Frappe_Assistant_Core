<template>
	<div v-if="open" class="consent-backdrop" @keydown.esc="decideLater">
		<div
			class="consent-modal"
			role="dialog"
			aria-modal="true"
			aria-labelledby="memory-consent-title"
			aria-describedby="memory-consent-body"
		>
			<h3 id="memory-consent-title" class="title">Keep AI memory on?</h3>

			<div id="memory-consent-body" class="body">
				<p>
					When you set up FAC Chat, AI memory was switched on for you instead of
					asking first. We've paused it until you decide.
				</p>
				<p>
					With memory on, FACO remembers preferences and facts from your
					conversations to give better answers. You can change this any time in
					Settings → Privacy.
				</p>
			</div>

			<p v-if="error" class="error" role="alert">{{ error }}</p>

			<div class="actions">
				<button class="btn link" type="button" :disabled="saving" @click="decideLater">
					Decide later
				</button>
				<span class="spacer" />
				<button class="btn ghost danger" type="button" :disabled="saving" @click="answer(false)">
					Turn off and delete memories
				</button>
				<button
					ref="keepButton"
					class="btn primary"
					type="button"
					:disabled="saving"
					@click="answer(true)"
				>
					Keep memory on
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { logger } from "@/utils/logger";

const userStore = useUserStore();
const { memoryEnabled, memoryConsentPending } = storeToRefs(userStore);

// "Decide later" hides the prompt for this page load only; memory stays paused.
const dismissed = ref(false);
const saving = ref(false);
const error = ref("");
const keepButton = ref(null);

const open = computed(() => memoryEnabled.value && memoryConsentPending.value && !dismissed.value);

watch(
	open,
	async (isOpen) => {
		if (!isOpen) return;
		await nextTick();
		keepButton.value?.focus();
	},
	{ immediate: true },
);

function decideLater() {
	if (!saving.value) dismissed.value = true;
}

async function answer(keep) {
	saving.value = true;
	error.value = "";
	try {
		await userStore.confirmMemoryConsent(keep);
	} catch (err) {
		logger.warn("Memory consent confirmation failed:", err);
		error.value = "Couldn't save your choice. Please try again.";
	} finally {
		saving.value = false;
	}
}
</script>

<style scoped>
.consent-backdrop {
	position: fixed;
	inset: 0;
	background: rgba(15, 23, 42, 0.55);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
	padding: 1rem;
}

.consent-modal {
	width: 100%;
	max-width: 560px;
	background: var(--ql-surface, var(--ql-bg));
	border: 1px solid var(--ql-border);
	border-radius: 1rem;
	padding: 1.75rem 1.5rem 1.5rem;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35);
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 600;
	color: var(--ql-text);
}

.body {
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
	font-size: 0.875rem;
	line-height: 1.5;
	color: var(--ql-text-muted);
}

.body p {
	margin: 0;
}

.error {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-danger);
}

.actions {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.25rem;
}

.spacer {
	flex: 1;
}

.btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 600;
	border-radius: 0.5rem;
	cursor: pointer;
	border: 1px solid transparent;
	transition: opacity 0.15s ease, background-color 0.15s ease;
}

.btn:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}

.btn.primary {
	background: var(--ql-accent);
	color: white;
}

.btn.primary:hover:not(:disabled) {
	opacity: 0.92;
}

.btn.ghost {
	background: transparent;
	color: var(--ql-text);
	border-color: var(--ql-border);
}

.btn.ghost:hover:not(:disabled) {
	background: var(--ql-subtle);
}

.btn.ghost.danger {
	color: var(--ql-danger);
}

.btn.link {
	background: transparent;
	color: var(--ql-text-muted);
	padding-left: 0;
	padding-right: 0;
}

.btn.link:hover:not(:disabled) {
	color: var(--ql-text);
}

@media (max-width: 600px) {
	.spacer {
		display: none;
	}

	.actions .btn {
		flex: 1 1 100%;
	}

	.actions .btn.link {
		order: 3;
	}
}
</style>
