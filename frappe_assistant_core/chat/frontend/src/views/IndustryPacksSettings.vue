<template>
	<div class="packs-settings">
		<EmptyState
			v-if="!store.loading && !eligible.length"
			title="No industry packs available"
			description="Your current plan doesn't include any industry packs yet. Upgrade to unlock curated prompts and skills for your industry."
		/>
		<ListPageShell v-else>
			<template #header>
				<ListHeaderBand
					title="Industry Packs"
					:stat="`${eligible.length} pack${eligible.length === 1 ? '' : 's'} on your plan · free to enable`"
				/>
			</template>
			<PackCard
				v-for="pack in eligible"
				:key="pack.pack_id"
				:pack="pack"
				@toggle="onToggle"
			/>
		</ListPageShell>
		<div v-if="store.loading" class="ql-loading">Loading…</div>
	</div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import PackCard from "@/components/settings/packs/PackCard.vue";
import ListPageShell from "@/components/common/list/ListPageShell.vue";
import ListHeaderBand from "@/components/common/list/ListHeaderBand.vue";
import EmptyState from "@/components/common/list/EmptyState.vue";
import { usePacksStore } from "@/stores/packsStore";

const store = usePacksStore();

onMounted(() => store.load());

const eligible = computed(() => store.items.filter((p) => p.eligible));

async function onToggle({ pack_id, enabled }) {
	try {
		await store.setEnabled(pack_id, enabled);
	} catch (e) {
		window.alert(`Failed to update pack: ${e?.message || e}`);
	}
}
</script>

<style scoped>
.packs-settings {
	display: flex;
	flex-direction: column;
	min-height: 100%;
	background: var(--ql-bg);
}
.ql-loading {
	color: var(--ql-text-muted);
	padding: 48px;
	text-align: center;
}
</style>
