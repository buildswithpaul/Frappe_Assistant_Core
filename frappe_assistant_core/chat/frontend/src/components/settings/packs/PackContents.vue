<template>
	<div class="pack-contents">
		<button class="pack-head" :aria-expanded="expanded" @click="toggle">
			<div class="pack-head-main">
				<span class="pack-name">{{ pack.display_name }}</span>
				<span :class="['ownership-badge', badgeClass]">{{ acquisitionLabel }}</span>
			</div>
			<p v-if="pack.description" class="pack-desc">{{ pack.description }}</p>
			<div class="pack-meta">
				<span class="count mono">{{ pack.prompt_count || 0 }}</span> prompt templates
				<span class="dot">·</span>
				<span class="count mono">{{ pack.skill_count || 0 }}</span> skills
				<span class="chevron" :class="{ open: expanded }" aria-hidden="true">▾</span>
			</div>
		</button>

		<div v-if="expanded" class="pack-body">
			<p v-if="state.loading" class="pc-status">Loading contents…</p>
			<p v-else-if="state.error" class="pc-status pc-error">Couldn’t load contents.</p>
			<template v-else>
				<div v-if="state.prompts.length" class="pc-group">
					<div class="pc-group-label">Prompt templates</div>
					<div v-for="p in state.prompts" :key="p.prompt_id" class="pc-row">
						<span class="pc-row-title">{{ p.title }}</span>
						<span v-if="p.category" class="pc-row-meta">{{ p.category }}</span>
					</div>
				</div>
				<div v-if="state.skills.length" class="pc-group">
					<div class="pc-group-label">Skills</div>
					<div v-for="s in state.skills" :key="s.skill_id" class="pc-row">
						<span class="pc-row-title">{{ s.title }}</span>
						<span v-if="s.skill_type" class="pc-row-meta">{{ s.skill_type }}</span>
					</div>
				</div>
				<p v-if="!state.prompts.length && !state.skills.length" class="pc-status">
					This pack has no prompts or skills yet.
				</p>
			</template>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { usePacksStore } from "@/stores/packsStore";

const props = defineProps({ pack: { type: Object, required: true } });

const packsStore = usePacksStore();
const expanded = ref(false);

const state = computed(
	() => packsStore.contents[props.pack.pack_id] || { prompts: [], skills: [], loading: false, error: null },
);

function toggle() {
	expanded.value = !expanded.value;
	if (expanded.value) packsStore.loadContents(props.pack.pack_id);
}

const badgeClass = computed(() => {
	const a = props.pack.acquisition;
	if (a === "free_grant") return "free-grant";
	if (a === "purchased") return "purchased";
	if (a === "admin_grant") return "gifted";
	return "";
});
const acquisitionLabel = computed(() => {
	const a = props.pack.acquisition;
	if (a === "free_grant") return "Free Pack";
	if (a === "purchased") return "Purchased";
	if (a === "admin_grant") return "Gifted";
	return a || "";
});
</script>

<style scoped>
.pack-contents {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	overflow: hidden;
}
.pack-head {
	display: block;
	width: 100%;
	text-align: left;
	background: none;
	border: none;
	padding: 14px 16px;
	cursor: pointer;
}
.pack-head:hover { background: var(--ql-subtle); }
.pack-head-main {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
}
.pack-name { font-weight: 600; color: var(--ql-text); }
.pack-desc {
	margin: 6px 0 0;
	font-size: 13px;
	color: var(--ql-text-secondary);
}
.pack-meta {
	margin-top: 8px;
	font-size: 12px;
	color: var(--ql-text-muted);
	display: flex;
	align-items: center;
	gap: 6px;
}
.count { color: var(--ql-text); font-weight: 600; }
.mono { font-variant-numeric: tabular-nums; }
.dot { color: var(--ql-border); }
.chevron {
	margin-left: auto;
	transition: transform 0.15s ease;
	color: var(--ql-text-muted);
}
.chevron.open { transform: rotate(180deg); }
.ownership-badge {
	padding: 4px 8px;
	border-radius: 4px;
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
}
.ownership-badge.free-grant { background: rgba(30, 122, 82, 0.12); color: var(--ql-success); }
.ownership-badge.purchased { background: var(--ql-accent-soft); color: var(--ql-accent); }
.ownership-badge.gifted { background: var(--ql-gold-soft); color: var(--ql-warning); }
.pack-body {
	padding: 4px 16px 14px;
	border-top: 1px solid var(--ql-border);
}
.pc-status { font-size: 13px; color: var(--ql-text-muted); margin: 12px 0 0; }
.pc-error { color: var(--ql-danger); }
.pc-group { margin-top: 14px; }
.pc-group-label {
	font-size: 11px;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text-muted);
	margin-bottom: 6px;
}
.pc-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 7px 0;
	border-bottom: 1px solid var(--ql-border);
}
.pc-row:last-child { border-bottom: none; }
.pc-row-title { font-size: 13px; color: var(--ql-text); }
.pc-row-meta { font-size: 12px; color: var(--ql-text-muted); flex-shrink: 0; }
</style>
