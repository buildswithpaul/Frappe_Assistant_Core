<template>
	<FullPageShell :title="__('Pages')">
		<div v-if="name" class="pages-view-panel">
			<PagePanel
				:name="name"
				:user="userStore.user || ''"
				:can-share="userStore.isAdmin"
				:back-label="__('Back to pages')"
				@close="router.push('/pages')"
				@share="share"
			/>
		</div>
		<div v-else class="pages-view-list">
			<p v-if="error" class="pages-view-note">{{ __("Your pages could not be listed.") }}</p>
			<PageList v-else-if="loaded" :pages="pages" @open="openPage" />
			<p v-else class="pages-view-note">{{ __("Loading…") }}</p>
		</div>
	</FullPageShell>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { onMounted, watch } from "vue";
import { useRouter } from "vue-router";

import FullPageShell from "@/components/layout/FullPageShell.vue";
import PagePanel from "@/components/chat/pages/PagePanel.vue";
import PageList from "@/components/pages/PageList.vue";
import { isNarrow, usePagePanel } from "@/composables/usePagePanel";
import { usePagesStore } from "@/stores/pagesStore";
import { useUserStore } from "@/stores/userStore";
import { __ } from "@/utils/i18n";

const props = defineProps({
	name: { type: String, default: undefined },
});

const router = useRouter();
const userStore = useUserStore();
const pagesStore = usePagesStore();
const { pages, error, loaded } = storeToRefs(pagesStore);
const { open } = usePagePanel();

// A deep link to one page only needs the list for its title; the list itself is refreshed on open.
onMounted(() => (props.name ? pagesStore.ensureLoaded() : pagesStore.load()));

// Going back from a page reuses this component, so onMounted does not run again.
watch(
	() => props.name,
	(name, previous) => {
		if (!name && previous) pagesStore.load();
	},
);

function openPage(name) {
	router.push({ name: "page", params: { name } });
}

// Sharing needs FACO's approval card, which lives in a chat. The dock opens on the page because
// the open page persists across the navigation, and the request waits in a new chat's composer.
// On a phone the dock would cover that composer, so the page is left closed there.
function share() {
	const title = pages.value.find((p) => p.name === props.name)?.title || props.name;
	if (!isNarrow()) open(props.name);
	router.push({
		path: "/chat",
		query: { prompt: __("Share my page “{0}” ({1}) with my team", [title, props.name]) },
	});
}
</script>

<style scoped>
.pages-view-panel {
	flex: 1;
	min-height: 0;
	display: flex;
	flex-direction: column;
}

.pages-view-panel > :deep(*) {
	flex: 1;
	min-height: 0;
}

.pages-view-list {
	padding: 1.5rem;
}

@media (max-width: 767px) {
	.pages-view-list {
		padding: 1rem;
	}
}

.pages-view-note {
	margin-bottom: 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}
</style>
