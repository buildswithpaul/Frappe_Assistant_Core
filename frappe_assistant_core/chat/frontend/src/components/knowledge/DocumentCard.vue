<template>
	<div
		class="document-card"
		:class="{ clickable: !!doc.document_id }"
		@click="doc.document_id && $emit('preview', doc)"
	>
		<div class="card-inner">
			<div class="card-header">
				<span
					class="type-badge"
					:class="'badge-' + formatType(doc.document_type).toLowerCase()"
				>
					{{ formatType(doc.document_type) }}
				</span>
				<span class="visibility-pill" :class="'vis-' + (doc.visibility || 'public')">
					<svg
						v-if="!doc.visibility || doc.visibility === 'public'"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						class="vis-pill-icon"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
					<svg
						v-else-if="doc.visibility === 'private'"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						class="vis-pill-icon"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
						/>
					</svg>
					<svg
						v-else
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						class="vis-pill-icon"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
						/>
					</svg>
					{{ capitalizeFirst(doc.visibility || "public") }}
				</span>

				<div class="card-actions" @click.stop>
					<button
						ref="triggerRef"
						class="actions-trigger"
						@click="toggleActions"
						title="Actions"
						aria-label="Document actions"
					>
						<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 12h.01M12 12h.01M19 12h.01"
							/>
						</svg>
					</button>
					<Teleport to="body">
						<Transition name="dropdown-fade">
							<div
								v-if="showActions"
								class="actions-dropdown"
								:class="{ 'drop-up': dropUp }"
								:style="menuStyle"
								v-click-outside="closeActions"
							>
							<a
								v-if="doc.document_id"
								:href="downloadUrl"
								class="dropdown-item"
								@click.stop="closeActions"
							>
								<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
									/>
								</svg>
								Download
							</a>
							<button
								v-if="doc.is_owner"
								class="dropdown-item"
								@click.stop="
									$emit('manage-access', doc);
									closeActions();
								"
							>
								<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
									/>
								</svg>
								Manage access
							</button>
							<button
								v-if="doc.is_owner || isAdmin"
								class="dropdown-item danger"
								@click.stop="
									$emit('delete', doc);
									closeActions();
								"
							>
								<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
									/>
								</svg>
								Delete
							</button>
							</div>
						</Transition>
					</Teleport>
				</div>
			</div>

			<h4 class="card-name" :title="doc.file_name">{{ doc.file_name }}</h4>

			<div class="card-footer">
				<span
					class="status-indicator"
					:class="'status-' + getStatusClass(doc.embedding_status)"
				>
					<span class="status-dot"></span>
					{{ getStatusLabel(doc.embedding_status) }}
				</span>
				<span class="meta-sep">&middot;</span>
				<span class="meta-text">{{ formatFileSizeMb(doc.file_size_mb) }}</span>
				<span class="meta-sep">&middot;</span>
				<span class="meta-text">{{ formatRelativeTime(doc.created_at) }}</span>
				<template v-if="doc.uploaded_by">
					<span class="meta-sep">&middot;</span>
					<span class="meta-text owner">{{
						doc.is_owner ? "You" : doc.uploaded_by
					}}</span>
				</template>
			</div>

			<div
				v-if="doc.embedding_status === 'Failed' && doc.processing_error"
				class="error-hint"
			>
				{{ doc.processing_error }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { formatRelativeTime, formatFileSizeMb } from "@/composables/useFormatters";
import { api } from "@/api/client";

const props = defineProps({
	doc: { type: Object, required: true },
	isAdmin: { type: Boolean, default: false },
});

defineEmits(["preview", "delete", "manage-access"]);

const showActions = ref(false);
const dropUp = ref(false);
const triggerRef = ref(null);
const menuStyle = ref({});

// Menu width and estimated height (≤3 items ~36px each + padding). Width is
// fixed so we can right-align the menu to the trigger; height only decides
// flip direction, it does not size the menu.
const MENU_WIDTH = 168;
const MENU_HEIGHT_EST = 150;

// The menu is teleported to <body> and positioned with position:fixed so NO
// ancestor overflow can clip it — the card grid sits inside a scroll container
// (ListPageShell, overflow:auto) and main (overflow:hidden), both of which
// would otherwise cut a bottom-row card's menu. We anchor to the trigger's
// viewport rect and flip above it only when the viewport itself lacks room.
function positionMenu() {
	const rect = triggerRef.value?.getBoundingClientRect();
	if (!rect) return;
	const gap = 4;
	const spaceBelow = window.innerHeight - rect.bottom;
	dropUp.value = spaceBelow < MENU_HEIGHT_EST;

	// Right-align the menu's right edge to the trigger's right edge, clamped to
	// stay on-screen.
	let left = rect.right - MENU_WIDTH;
	left = Math.max(8, Math.min(left, window.innerWidth - MENU_WIDTH - 8));

	menuStyle.value = dropUp.value
		? { left: `${left}px`, bottom: `${window.innerHeight - rect.top + gap}px` }
		: { left: `${left}px`, top: `${rect.bottom + gap}px` };
}

function toggleActions() {
	if (showActions.value) {
		closeActions();
		return;
	}
	positionMenu();
	showActions.value = true;
}

function closeActions() {
	showActions.value = false;
}

function handleOutsideClick(e) {
	if (showActions.value) {
		closeActions();
	}
}

// A fixed-position menu can't follow a scrolling card, so dismiss it when the
// page scrolls (capture phase catches the inner scroll container too).
function handleScroll() {
	if (showActions.value) closeActions();
}

onMounted(() => {
	document.addEventListener("click", handleOutsideClick, true);
	window.addEventListener("scroll", handleScroll, true);
	window.addEventListener("resize", closeActions);
});
onUnmounted(() => {
	document.removeEventListener("click", handleOutsideClick, true);
	window.removeEventListener("scroll", handleScroll, true);
	window.removeEventListener("resize", closeActions);
});

const downloadUrl = computed(() =>
	props.doc?.document_id ? api.documents.getDownloadUrl(props.doc.document_id) : null
);

function capitalizeFirst(str) {
	return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatType(type) {
	if (!type) return "?";
	const t = type.toLowerCase();
	if (t === "pdf") return "PDF";
	if (t === "markdown") return "MD";
	if (t === "text") return "TXT";
	return type;
}

function getStatusClass(status) {
	if (status === "Completed") return "ready";
	if (status === "Processing") return "processing";
	if (status === "Pending") return "pending";
	if (status === "Failed") return "failed";
	return "pending";
}

function getStatusLabel(status) {
	if (status === "Completed") return "Ready";
	if (status === "Processing") return "Processing";
	if (status === "Pending") return "Queued";
	if (status === "Failed") return "Failed";
	return status || "Unknown";
}
</script>

<style scoped>
.document-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
	position: relative;
}

.document-card:hover {
	border-color: var(--ql-accent);
	box-shadow: 0 4px 16px rgba(15, 110, 92, 0.08);
	transform: translateY(-1px);
}

.document-card.clickable {
	cursor: pointer;
}

.card-inner {
	padding: 0.75rem 1rem 0.75rem;
}

/* Header: type badge + visibility pill + actions */
.card-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-bottom: 0.5rem;
}

/* Small neutral file-type chip (replaces the old red/blue accents) */
.type-badge {
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.05em;
	text-transform: uppercase;
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
	border: 1px solid var(--ql-border);
}

/* Visibility pill */
.visibility-pill {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.625rem;
	font-weight: 500;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.vis-pill-icon {
	width: 0.6875rem;
	height: 0.6875rem;
}

.visibility-pill.vis-public {
	background: rgba(30, 122, 82, 0.1);
	color: var(--ql-success);
}

.visibility-pill.vis-private {
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.visibility-pill.vis-shared {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

/* Actions dropdown */
.card-actions {
	margin-left: auto;
	position: relative;
}

.actions-trigger {
	width: 1.5rem;
	height: 1.5rem;
	padding: 0.125rem;
	background: none;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	border-radius: 0.375rem;
	opacity: 0;
	transition: opacity 0.15s ease, background-color 0.15s ease, color 0.15s ease;
	display: flex;
	align-items: center;
	justify-content: center;
}

.actions-trigger svg {
	width: 100%;
	height: 100%;
}

.document-card:hover .actions-trigger {
	opacity: 1;
}

.actions-trigger:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

/* Teleported to <body> and fixed-positioned (top/left/bottom set inline from
   the trigger's rect) so no ancestor overflow can clip it. Width is fixed to
   match MENU_WIDTH in the script so right-alignment to the trigger is exact. */
.actions-dropdown {
	position: fixed;
	width: 168px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
	z-index: 1000;
	padding: 0.25rem;
	display: flex;
	flex-direction: column;
}

.dropdown-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: none;
	border: none;
	text-align: left;
	cursor: pointer;
	border-radius: 0.375rem;
	text-decoration: none;
	transition: background-color 0.1s ease;
}

.dropdown-item svg {
	width: 0.875rem;
	height: 0.875rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
}

.dropdown-item:hover {
	background: var(--ql-subtle);
}

.dropdown-item.danger:hover {
	background: rgba(180, 69, 58, 0.1);
	color: var(--ql-danger);
}

.dropdown-item.danger:hover svg {
	color: var(--ql-danger);
}

.dropdown-fade-enter-active {
	transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-fade-leave-active {
	transition: opacity 0.1s ease, transform 0.1s ease;
}
.dropdown-fade-enter-from {
	opacity: 0;
	transform: translateY(-4px);
}
.dropdown-fade-leave-to {
	opacity: 0;
	transform: translateY(-2px);
}
/* When the menu opens upward, slide it in from below instead of above so the
   motion reads as "rising" toward the trigger. */
.actions-dropdown.drop-up.dropdown-fade-enter-from {
	transform: translateY(4px);
}
.actions-dropdown.drop-up.dropdown-fade-leave-to {
	transform: translateY(2px);
}

/* Filename */
.card-name {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	margin: 0 0 0.5rem;
}

/* Footer: single inline row of metadata */
.card-footer {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	flex-wrap: wrap;
}

.meta-sep {
	color: var(--ql-border);
	user-select: none;
}

.meta-text {
	white-space: nowrap;
}

.meta-text.owner {
	overflow: hidden;
	text-overflow: ellipsis;
	max-width: 100px;
}

/* Status indicator */
.status-indicator {
	display: inline-flex;
	align-items: center;
	gap: 0.3125rem;
	font-weight: 500;
	white-space: nowrap;
}

.status-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	flex-shrink: 0;
}

.status-ready {
	color: var(--ql-success);
}
.status-ready .status-dot {
	background: var(--ql-success);
}

.status-processing {
	color: var(--ql-warning);
}
.status-processing .status-dot {
	background: var(--ql-warning);
	animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
	0%,
	100% {
		opacity: 1;
		transform: scale(1);
	}
	50% {
		opacity: 0.5;
		transform: scale(0.8);
	}
}

.status-pending {
	color: var(--ql-text-muted);
}
.status-pending .status-dot {
	background: var(--ql-text-muted);
}

.status-failed {
	color: var(--ql-danger);
}
.status-failed .status-dot {
	background: var(--ql-danger);
}

/* Error hint */
.error-hint {
	font-size: 0.6875rem;
	color: var(--ql-danger);
	margin-top: 0.375rem;
	line-height: 1.4;
	overflow: hidden;
	text-overflow: ellipsis;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
}

/* List view variant styles are applied from the parent (KnowledgeBase.vue)
   using :deep() selectors on .documents-grid.list-view */
</style>
