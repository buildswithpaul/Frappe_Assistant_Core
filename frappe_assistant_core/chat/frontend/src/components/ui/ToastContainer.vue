<template>
	<Teleport to="body">
		<div class="toast-container" v-if="toasts.length > 0">
			<TransitionGroup name="toast">
				<div
					v-for="toast in toasts"
					:key="toast.id"
					class="toast-item"
					:class="`toast-${toast.type}`"
					@click="dismiss(toast.id)"
				>
					<svg
						v-if="toast.type === 'success'"
						class="toast-icon"
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
							d="M5 13l4 4L19 7"
						/>
					</svg>
					<svg
						v-else-if="toast.type === 'error'"
						class="toast-icon"
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
							d="M12 9v2m0 4h.01M12 3l9.66 16.59A1 1 0 0120.66 21H3.34a1 1 0 01-.87-1.41L12 3z"
						/>
					</svg>
					<svg
						v-else
						class="toast-icon"
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
							d="M13 16h-1v-4h-1m1-4h.01"
						/>
					</svg>
					<span class="toast-message">{{ toast.message }}</span>
				</div>
			</TransitionGroup>
		</div>
	</Teleport>
</template>

<script setup>
import { useToast } from "@/composables/useToast";

const { toasts, dismiss } = useToast();
</script>

<style scoped>
.toast-container {
	position: fixed;
	top: 1rem;
	right: 1rem;
	z-index: 10000;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	max-width: 360px;
}

.toast-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1rem;
	border-radius: 8px;
	font-size: 0.875rem;
	line-height: 1.4;
	cursor: pointer;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	transition: opacity 0.2s, transform 0.2s;
}

.toast-item:hover {
	opacity: 0.9;
}

.toast-icon {
	flex-shrink: 0;
}

.toast-message {
	flex: 1;
	min-width: 0;
}

.toast-success {
	background: #065f46;
	color: #d1fae5;
}

.toast-error {
	background: #991b1b;
	color: #fecaca;
}

.toast-info {
	background: #1e3a5f;
	color: #dbeafe;
}

/* Transition animations */
.toast-enter-active {
	transition: all 0.3s ease-out;
}

.toast-leave-active {
	transition: all 0.2s ease-in;
}

.toast-enter-from {
	opacity: 0;
	transform: translateX(100%);
}

.toast-leave-to {
	opacity: 0;
	transform: translateX(100%);
}
</style>
