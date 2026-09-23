<template>
	<div v-if="vacant > 0" class="vacant-banner" data-test="vacant-banner">
		<div class="vacant-copy">
			<span class="vacant-headline">
				{{ assigned }} of {{ paid }} seats assigned
			</span>
			<span class="vacant-detail">
				You're paying for {{ vacant }}
				{{ vacant === 1 ? "seat" : "seats" }} nobody is using. Invite
				someone to fill {{ vacant === 1 ? "it" : "them" }}, or release
				{{ vacant === 1 ? "it" : "them" }} to lower your next bill.
			</span>
		</div>
		<button
			class="vacant-release"
			data-test="release-seat"
			:disabled="!canRelease || releasing"
			:title="canRelease ? '' : `Your plan includes a minimum of ${minUsers} seats.`"
			@click="$emit('release')"
		>
			{{ releasing ? "Releasing…" : "Release a seat" }}
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	userLimit: { type: Object, default: null },
	releasing: { type: Boolean, default: false },
});

defineEmits(["release"]);

// All three are null on a flat plan — a tenant downgraded off a per-user
// plan keeps a stale user_count, and showing it as seats invents capacity.
const paid = computed(() => props.userLimit?.paid_seats ?? 0);
const assigned = computed(() => props.userLimit?.assigned_seats ?? 0);
const vacant = computed(() =>
	props.userLimit?.is_per_user ? (props.userLimit?.vacant_seats ?? 0) : 0,
);
const minUsers = computed(() => props.userLimit?.min_users ?? 1);

// The backend clamps at the plan minimum and refuses anyway; disabling the
// button just means the admin is not told "no" after clicking.
const canRelease = computed(() => paid.value > minUsers.value);
</script>

<style scoped>
.vacant-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
	flex-wrap: wrap;
	padding: 0.875rem 1rem;
	margin-top: 0.75rem;
	border: 1px solid rgba(234, 179, 8, 0.35);
	background: rgba(234, 179, 8, 0.06);
	border-radius: 0.5rem;
}

.vacant-copy {
	display: flex;
	flex-direction: column;
	gap: 0.2rem;
	min-width: 16rem;
	flex: 1;
}

.vacant-headline {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}

.vacant-detail {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.vacant-release {
	padding: 0.4rem 0.85rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}

.vacant-release:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
</style>
