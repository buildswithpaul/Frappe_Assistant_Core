<template>
	<div class="upgrade-banner">
		<div class="upgrade-banner-icon">
			<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 10V3L4 14h7v7l9-11h-7z"
				/>
			</svg>
		</div>
		<div class="upgrade-banner-text">
			<strong>
				You've reached your plan's user limit ({{ maxUsers }}
				{{ maxUsers === 1 ? "seat" : "seats" }}).
			</strong>
			<span>Upgrade to add more team members.</span>
		</div>
		<button class="upgrade-banner-btn" @click="$emit('upgrade')">View plans</button>
	</div>
</template>

<script setup>
defineProps({
	maxUsers: { type: Number, required: true },
});
defineEmits(["upgrade"]);
</script>

<style scoped>
.upgrade-banner {
	display: flex;
	align-items: center;
	gap: 0.875rem;
	padding: 0.875rem 1rem;
	margin-top: 1rem;
	background: linear-gradient(
		135deg,
		rgba(245, 158, 11, 0.08) 0%,
		rgba(245, 158, 11, 0.04) 100%
	);
	border: 1px solid rgba(245, 158, 11, 0.25);
	border-radius: 0.75rem;
}

.upgrade-banner-icon {
	flex-shrink: 0;
	width: 2rem;
	height: 2rem;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(245, 158, 11, 0.15);
	border-radius: 0.5rem;
	color: #f59e0b;
}

.upgrade-banner-icon svg {
	width: 1.125rem;
	height: 1.125rem;
}

.upgrade-banner-text {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	font-size: 0.8125rem;
}

.upgrade-banner-text strong {
	color: var(--ql-text);
	font-weight: 600;
}

.upgrade-banner-text span {
	color: var(--ql-text-muted);
}

.upgrade-banner-btn {
	flex-shrink: 0;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.upgrade-banner-btn:hover {
	background: var(--ql-accent-hover);
}
</style>
