<template>
	<FullPageShell :title="__('Pages')">
		<template v-if="!name && loaded && pages.length" #actions>
			<PageSearch v-model="query" />
		</template>
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
			<p v-else-if="!loaded" class="pages-view-note">{{ __("Loading…") }}</p>
			<div v-else-if="!pages.length" class="pages-view-empty">
				<p>{{ __("No pages yet. Ask FACO to build one in chat.") }}</p>
				<router-link to="/chat">{{ __("Back to chat") }}</router-link>
			</div>
			<template v-else>
				<PageFilters :model-value="activeFilter" :counts="counts" @update:model-value="filter = $event" />
				<div v-if="!visible.length && query.trim()" class="pages-view-empty">
					<p>{{ __("No pages match “{0}”.", [query.trim()]) }}</p>
					<button type="button" class="pages-view-clear" @click="query = ''">
						{{ __("Clear search") }}
					</button>
				</div>
				<section
					v-for="section in sections"
					:key="section.key"
					class="pages-view-section"
					:aria-labelledby="`pages-section-${section.key}`"
				>
					<h2 :id="`pages-section-${section.key}`" class="pages-view-heading">
						{{ section.label }} <span class="pages-view-count">{{ section.pages.length }}</span>
					</h2>
					<div class="pages-view-grid">
						<PageCard v-for="page in section.pages" :key="page.name" :page="page" @open="openPage" />
					</div>
				</section>
			</template>
		</div>
	</FullPageShell>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import FullPageShell from "@/components/layout/FullPageShell.vue";
import PagePanel from "@/components/chat/pages/PagePanel.vue";
import PageCard from "@/components/pages/PageCard.vue";
import PageFilters from "@/components/pages/PageFilters.vue";
import PageSearch from "@/components/pages/PageSearch.vue";
import { countPages, groupPages, matchesFilter, searchPages } from "@/components/pages/pagesFilter";
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

const query = ref("");
const filter = ref("all");

const searched = computed(() => searchPages(pages.value, query.value));
const counts = computed(() => countPages(searched.value));
// A pill with no pages is hidden, so a selection that lost its pages falls back to All.
const activeFilter = computed(() => (counts.value[filter.value] ? filter.value : "all"));
const visible = computed(() => searched.value.filter((page) => matchesFilter(page, activeFilter.value)));
const sections = computed(() => {
	const { mine, shared } = groupPages(visible.value);
	return [
		{ key: "mine", label: __("Your pages"), pages: mine },
		{ key: "shared", label: __("Shared with you"), pages: shared },
	].filter((section) => section.pages.length);
});

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
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
}

@media (max-width: 767px) {
	.pages-view-list {
		padding: 1rem;
	}
}

.pages-view-note {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.pages-view-empty {
	padding: 3rem 1rem;
	text-align: center;
	color: var(--ql-text-muted);
}

.pages-view-empty a,
.pages-view-clear {
	color: var(--ql-accent);
	background: none;
	border: none;
	padding: 0;
	cursor: pointer;
	text-decoration: underline;
}

.pages-view-heading {
	margin-bottom: 0.75rem;
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.pages-view-count {
	margin-left: 0.25rem;
	font-weight: 400;
}

.pages-view-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
	gap: 16px;
}

@media (max-width: 640px) {
	.pages-view-grid {
		grid-template-columns: 1fr;
	}
}
</style>
