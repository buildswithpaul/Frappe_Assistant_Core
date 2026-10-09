<template>
	<div class="access-denied-screen">
		<div class="access-denied-content">
			<div class="access-icon">
				<svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
					/>
				</svg>
			</div>
			<template v-if="reasonCode === 'assistant_disabled'">
				<h2 class="access-title">Assistant Access Is Off</h2>
				<p class="access-description">
					You're on the FACO team, but assistant access is turned off for your user, so
					FACO can't work with this site for you. Please contact your system administrator.
				</p>
				<div class="access-hint">
					Your admin can tick <strong>Enable Assistant Access</strong> on your User record
				</div>
			</template>
			<template v-else>
				<h2 class="access-title">FACO Access Required</h2>
				<p class="access-description">
					Your administrator hasn't added you to FACO yet. Please contact your system
					administrator to get access.
				</p>
				<div class="access-hint">
					Your admin can add you from <strong>Settings &rarr; Users</strong>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
defineProps({
	// "assistant_disabled" when seated but Enable Assistant Access is off;
	// null when the user has no seat.
	reasonCode: { type: String, default: null },
});
</script>

<style scoped>
.access-denied-screen {
	display: flex;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	padding: 2rem;
}

.access-denied-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	text-align: center;
	max-width: 400px;
	gap: 1rem;
}

.access-icon {
	color: var(--ql-text-muted);
	opacity: 0.6;
}

.access-title {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0;
}

.access-description {
	font-size: 0.9375rem;
	color: var(--ql-text-muted);
	line-height: 1.6;
	margin: 0;
}

.access-hint {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.75rem 1.25rem;
}

.access-hint strong {
	color: var(--ql-text);
}

/* Responsive */
@media (max-width: 640px) {
	.access-denied-screen {
		padding: 1.5rem;
	}

	.access-title {
		font-size: 1.25rem;
	}
}
</style>
