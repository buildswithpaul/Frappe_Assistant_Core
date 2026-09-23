<template>
	<div class="confirmation">
		<div class="check">✓</div>
		<h3>{{ title }}</h3>
		<p v-if="ticketId">Ticket #{{ ticketId }} created.</p>
		<button v-if="ticketId" type="button" class="track-link"
			@click="$emit('track', ticketId)">Track your ticket →</button>
		<p v-if="!ticketId" class="thanks">Thanks — we read every one. If yours needs a reply, we'll open a ticket and you'll find it under Support.</p>
		<div class="actions">
			<button type="button" class="btn-primary" @click="$emit('done')">Done</button>
		</div>
	</div>
</template>

<script setup>
defineProps({
	title: { type: String, default: "Thanks!" },
	ticketId: { type: String, default: null },
});
defineEmits(["done", "track"]);
</script>

<style scoped>
.confirmation { text-align: center; padding: 1rem 0; color: var(--ql-text); }
.confirmation h3 { color: var(--ql-text); }
.check { font-size: 2rem; color: var(--ql-success); }
.track-link { display: inline-block; margin: 0.5rem 0; color: var(--ql-accent); background: none; border: none; cursor: pointer; font: inherit; padding: 0; }
.thanks { color: var(--ql-text-muted); }
.actions { margin-top: 1rem; }
.btn-primary { padding: 0.5rem 1.25rem; border-radius: var(--ql-radius-sm); border: none; background: var(--ql-accent); color: #fff; cursor: pointer; }
</style>
