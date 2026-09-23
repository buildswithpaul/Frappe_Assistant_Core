<template>
	<!-- Connection Status: subtle dot for brief disconnects, banner only when all retries fail -->
	<Transition name="fade">
		<div
			v-if="connectionVisible && !socketError"
			class="connection-dot"
			title="Reconnecting..."
		>
			<span class="dot pulsing"></span>
		</div>
	</Transition>
	<Transition name="slide">
		<div v-if="socketError" class="connection-banner">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<span>{{ socketError }}</span>
			<button @click="$emit('retry')" class="retry-btn">Retry</button>
		</div>
	</Transition>

	<!-- Error Banner -->
	<div v-if="error" class="error-banner">
		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
			/>
		</svg>
		<span>{{ error }}</span>
		<button @click="$emit('dismiss-error')" class="dismiss-btn" aria-label="Dismiss error">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M6 18L18 6M6 6l12 12"
				/>
			</svg>
		</button>
	</div>

	<!-- Reconnect Banner: shown when AR's auto-refresh fails (e.g. revoked
	     OAuth client). Soft-degrade — user keeps the chat UI and reconnects
	     with one click instead of being bounced to UserSetup. -->
	<div v-if="needsReconnect" class="connection-banner">
		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
			/>
		</svg>
		<span>Your session needs to be reconnected.</span>
		<button @click="$emit('reconnect')" class="retry-btn" :disabled="reconnecting">
			{{ reconnecting ? "Reconnecting..." : "Reconnect" }}
		</button>
	</div>
</template>

<script setup>
defineProps({
	connectionVisible: { type: Boolean, default: false },
	socketError: { type: String, default: null },
	error: { type: String, default: null },
	needsReconnect: { type: Boolean, default: false },
	reconnecting: { type: Boolean, default: false },
});

defineEmits(["retry", "dismiss-error", "reconnect"]);
</script>

<style scoped>
/* Subtle connection dot — shows after 3s of sustained disconnect */
.connection-dot {
	position: absolute;
	top: 0.75rem;
	right: 0.75rem;
	z-index: 10;
}

.dot {
	display: block;
	width: 8px;
	height: 8px;
	border-radius: 50%;
	background-color: #f59e0b;
}

.dot.pulsing {
	animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
	0%,
	100% {
		opacity: 1;
		transform: scale(1);
	}
	50% {
		opacity: 0.4;
		transform: scale(0.8);
	}
}

/* Connection and Error Banners */
.connection-banner,
.error-banner {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	word-break: break-word;
	overflow-wrap: anywhere;
}

.connection-banner {
	background-color: #fef3c7;
	color: #92400e;
	border-bottom: 1px solid #fcd34d;
}

.error-banner {
	background-color: #fee2e2;
	color: #991b1b;
	border-bottom: 1px solid #fca5a5;
}

.dismiss-btn,
.retry-btn {
	margin-left: auto;
	padding: 0.25rem 0.5rem;
	border-radius: 0.25rem;
	opacity: 0.7;
	transition: opacity 0.15s;
	font-size: 0.75rem;
	cursor: pointer;
}

.retry-btn {
	background: rgba(146, 64, 14, 0.15);
	border: 1px solid rgba(146, 64, 14, 0.3);
	color: inherit;
}

.dismiss-btn:hover,
.retry-btn:hover {
	opacity: 1;
}

/* Transition: fade for dot */
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}

/* Transition: slide for banner */
.slide-enter-active,
.slide-leave-active {
	transition: transform 0.3s ease, opacity 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
	transform: translateY(-100%);
	opacity: 0;
}

/* Dark mode adjustments */
[data-theme="dark"] .connection-dot .dot {
	background-color: #fbbf24;
}

[data-theme="dark"] .connection-banner {
	background-color: rgba(251, 191, 36, 0.15);
	color: #fbbf24;
	border-bottom-color: rgba(251, 191, 36, 0.3);
}

[data-theme="dark"] .retry-btn {
	background: rgba(251, 191, 36, 0.15);
	border-color: rgba(251, 191, 36, 0.3);
}

[data-theme="dark"] .error-banner {
	background-color: rgba(239, 68, 68, 0.15);
	color: #f87171;
	border-bottom-color: rgba(239, 68, 68, 0.3);
}
</style>
