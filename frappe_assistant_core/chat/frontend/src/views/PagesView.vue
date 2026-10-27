<template>
	<FullPageShell :title="__('Pages')">
		<div v-if="name" class="pages-view-panel">
			<PagePanel
				:name="name"
				:user="userStore.user || ''"
				:can-share="userStore.isAdmin"
				@close="router.push('/pages')"
				@share="share"
			/>
		</div>
		<div v-else class="pages-view-list">
			<p v-if="error" class="pages-view-error">{{ __("Your pages could not be listed.") }}</p>
			<PageList :pages="pages" @open="openPage" />
		</div>
	</FullPageShell>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import FullPageShell from "@/components/layout/FullPageShell.vue";
import PagePanel from "@/components/chat/pages/PagePanel.vue";
import PageList from "@/components/pages/PageList.vue";
import { usePagePanel } from "@/composables/usePagePanel";
import { usePagesStore } from "@/stores/pagesStore";
import { useUserStore } from "@/stores/userStore";
import { __ } from "@/utils/i18n";

const props = defineProps({
	name: { type: String, default: undefined },
});

const router = useRouter();
const userStore = useUserStore();
const pagesStore = usePagesStore();
const { pages, error } = storeToRefs(pagesStore);
const { open } = usePagePanel();

onMounted(() => pagesStore.load());

function openPage(name) {
	router.push({ name: "page", params: { name } });
}

// Sharing needs FACO's approval card, which lives in a chat. The dock opens on the page because
// the open page persists across the navigation, and the request waits in a new chat's composer.
function share() {
	const title = pages.value.find((p) => p.name === props.name)?.title || props.name;
	open(props.name);
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

.pages-view-error {
	margin-bottom: 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}
</style>
