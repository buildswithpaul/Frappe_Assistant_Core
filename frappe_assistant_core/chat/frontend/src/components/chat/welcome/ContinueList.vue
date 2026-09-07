<template>
	<div v-if="sessions.length" class="cl">
		<div class="cl-label">Pick up where you left off</div>
		<button
			v-for="s in sessions"
			:key="s.session_id"
			type="button"
			class="cl-row"
			@click="$emit('open', s.session_id)"
		>
			<span class="cl-icon" aria-hidden="true">↩</span>
			<span class="cl-body">
				<span class="cl-preview">“{{ s.preview }}”</span>
				<span class="cl-meta">Continue · {{ relativeTimeLabel(s.last_activity) }}</span>
			</span>
		</button>
	</div>
</template>

<script setup>
import { relativeTimeLabel } from "@/components/chat/welcomeGreeting";

defineProps({ sessions: { type: Array, default: () => [] } });
defineEmits(["open"]);
</script>

<style scoped>
.cl { display: flex; flex-direction: column; gap: 8px; text-align: left; }
.cl-label {
	font-size: 10px; font-weight: 600; text-transform: uppercase;
	letter-spacing: 0.08em; color: var(--ql-text-muted); margin-bottom: 1px;
}
.cl-row {
	display: flex; align-items: center; gap: 11px; width: 100%;
	background: var(--ql-surface); border: 1px solid var(--ql-border);
	border-radius: 10px; padding: 11px 13px; cursor: pointer; text-align: left;
	transition: border-color 0.15s ease;
}
.cl-row:hover { border-color: var(--ql-border-hover); }
.cl-icon {
	width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
	display: inline-flex; align-items: center; justify-content: center;
	font-size: 13px; background: var(--ql-accent-soft); color: var(--ql-accent);
}
.cl-body { min-width: 0; display: flex; flex-direction: column; }
.cl-preview {
	font-size: 12.5px; font-weight: 600; color: var(--ql-text);
	white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cl-meta { font-size: 11.5px; color: var(--ql-text-muted); margin-top: 1px; }
</style>
