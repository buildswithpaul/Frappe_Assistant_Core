<template>
	<Teleport to="body">
		<Transition name="chunk-fade">
			<div v-if="doc" class="chunk-backdrop" @click.self="$emit('close')">
				<Transition name="chunk-slide">
					<div v-if="doc" class="chunk-panel">
						<div class="chunk-header">
							<div class="chunk-header-info">
								<h3 class="chunk-doc-name">{{ doc.file_name }}</h3>
								<span class="chunk-doc-meta">
									{{ doc.document_type }} &middot; {{ total }} chunks
								</span>
							</div>
							<button
								class="chunk-close-btn"
								title="Close"
								aria-label="Close"
								@click="$emit('close')"
							>
								<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M6 18L18 6M6 6l12 12"
									/>
								</svg>
							</button>
						</div>

						<div class="chunk-search">
							<input
								v-model="search"
								class="chunk-search-input"
								type="text"
								placeholder="Search within chunks…"
								@keyup.enter="reload"
							/>
							<button class="chunk-search-btn" @click="reload">Search</button>
						</div>

						<div class="chunk-body">
							<div v-if="loading && chunks.length === 0" class="chunk-loading">
								<div class="loading-spinner"></div>
								<p>Loading chunks…</p>
							</div>
							<div v-else-if="chunks.length === 0" class="chunk-empty">
								<p>No chunks found.</p>
							</div>
							<template v-else>
								<ChunkCard
									v-for="c in chunks"
									:key="c.chunk_id"
									:chunk="c"
								/>
								<button
									v-if="hasMore()"
									class="chunk-load-more"
									:disabled="loading"
									@click="loadMore"
								>
									{{ loading ? "Loading…" : "Load more" }}
								</button>
							</template>
						</div>
					</div>
				</Transition>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from "vue";
import { api } from "@/api/client";
import ChunkCard from "./ChunkCard.vue";

const props = defineProps({
	doc: { type: Object, default: null },
});
const emit = defineEmits(["close"]);

const chunks = ref([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const search = ref("");
const PAGE = 20;

function hasMore() {
	return offset.value < total.value;
}

async function fetchPage(reset) {
	if (!props.doc?.document_id) return;
	loading.value = true;
	try {
		const res = await api.documents.listChunks(props.doc.document_id, {
			search: search.value || null,
			limit: PAGE,
			offset: reset ? 0 : offset.value,
		});
		const incoming = res?.chunks || [];
		total.value = res?.total || 0;
		if (reset) {
			chunks.value = incoming;
			offset.value = incoming.length;
		} else {
			chunks.value = chunks.value.concat(incoming);
			offset.value += incoming.length;
		}
	} catch {
		if (reset) chunks.value = [];
	} finally {
		loading.value = false;
	}
}

function reload() {
	offset.value = 0;
	fetchPage(true);
}
function loadMore() {
	fetchPage(false);
}

watch(
	() => props.doc,
	(newDoc) => {
		search.value = "";
		offset.value = 0;
		chunks.value = [];
		total.value = 0;
		if (newDoc) fetchPage(true);
	},
	{ immediate: true }
);

function handleKeydown(e) {
	if (e.key === "Escape" && props.doc) emit("close");
}
onMounted(() => document.addEventListener("keydown", handleKeydown));
onUnmounted(() => document.removeEventListener("keydown", handleKeydown));
</script>

<style scoped>
.chunk-backdrop {
	position: fixed;
	inset: 0;
	z-index: 1050;
	background-color: rgba(0, 0, 0, 0.4);
	backdrop-filter: blur(4px);
	display: flex;
	justify-content: flex-end;
}
.chunk-panel {
	width: 560px;
	max-width: 100%;
	height: 100%;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
	display: flex;
	flex-direction: column;
	box-shadow: -8px 0 24px rgba(0, 0, 0, 0.12);
}
.chunk-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
}
.chunk-doc-name {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.chunk-doc-meta {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
.chunk-close-btn {
	width: 2rem;
	height: 2rem;
	padding: 0.375rem;
	background: none;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	border-radius: 0.375rem;
}
.chunk-close-btn svg {
	width: 100%;
	height: 100%;
}
.chunk-close-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}
.chunk-search {
	display: flex;
	gap: 0.5rem;
	padding: 0.75rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
}
.chunk-search-input {
	flex: 1;
	padding: 0.4rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-bg);
	color: var(--ql-text);
	font-size: 0.8125rem;
}
.chunk-search-btn {
	border: 1px solid var(--ql-border);
	background: none;
	color: var(--ql-text);
	border-radius: 0.375rem;
	padding: 0.4rem 0.75rem;
	font-size: 0.8125rem;
	cursor: pointer;
}
.chunk-search-btn:hover {
	background: var(--ql-subtle);
}
.chunk-body {
	flex: 1;
	overflow: auto;
	padding: 1rem 1.25rem;
	scrollbar-width: thin;
	scrollbar-color: var(--ql-border) transparent;
}
.chunk-loading,
.chunk-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	height: 100%;
	gap: 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}
.loading-spinner {
	width: 2rem;
	height: 2rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}
@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
.chunk-load-more {
	width: 100%;
	border: 1px solid var(--ql-border);
	background: none;
	color: var(--ql-text);
	border-radius: 0.375rem;
	padding: 0.5rem;
	font-size: 0.8125rem;
	cursor: pointer;
	margin-top: 0.5rem;
}
.chunk-load-more:hover:not(:disabled) {
	background: var(--ql-subtle);
}
.chunk-load-more:disabled {
	opacity: 0.6;
	cursor: default;
}
.chunk-fade-enter-active,
.chunk-fade-leave-active {
	transition: opacity 0.2s ease;
}
.chunk-fade-enter-from,
.chunk-fade-leave-to {
	opacity: 0;
}
.chunk-slide-enter-active {
	transition: transform 0.25s ease-out;
}
.chunk-slide-leave-active {
	transition: transform 0.2s ease-in;
}
.chunk-slide-enter-from,
.chunk-slide-leave-to {
	transform: translateX(100%);
}
@media (max-width: 768px) {
	.chunk-panel {
		width: 100%;
	}
}
</style>
