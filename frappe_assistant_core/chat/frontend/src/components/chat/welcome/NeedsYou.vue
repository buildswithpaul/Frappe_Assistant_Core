<template>
	<section v-if="loaded && !(failed && !items.length && !notes.length)" ref="root" class="ny" :class="`ny--${variant}`">
		<h2 class="ny-heading">{{ __("Needs you") }}</h2>
		<p v-if="hideFailed" class="ny-note" role="alert">
			{{ __("Couldn't hide that card. Try again.") }}
		</p>
		<p v-if="!rows.length" class="ny-empty">{{ emptyText || __("Nothing is waiting on you right now.") }}</p>
		<ul v-else class="ny-items">
			<template v-for="row in rows" :key="row.key">
				<li v-if="row.note" class="ny-note" role="status" :data-note="row.note.id">
					<span>{{ __("Hidden. Bring it back in Settings → Home page.") }}</span>
					<button type="button" class="ny-note-link" @click="$emit('open-settings')">
						{{ __("Open settings") }}
					</button>
				</li>
				<li
					v-else
					class="ny-item"
					:class="[`ny-item--${row.item.tone}`, { 'ny-item--dismissible': row.item.dismissible }]"
					@keydown.esc="closeMenu(true)"
					@focusout="onFocusOut"
				>
					<button type="button" class="ny-main" @click="activate(row.item)">
						<span class="ny-source">
							<span class="ny-dot" aria-hidden="true"></span>
							<span v-if="variant === 'cards'" class="ny-source-label">{{ row.item.source }}</span>
						</span>
						<span class="ny-body">
							<span class="ny-headline">
								<span class="ny-count">{{ row.item.count }}</span>
								<span class="ny-title">{{ row.item.title }}</span>
							</span>
							<span v-if="row.item.detail && variant === 'cards'" class="ny-detail">{{ row.item.detail }}</span>
							<span v-if="row.item.ask || row.item.href" class="ny-ask">
								{{ row.item.action || row.item.ask || __("Open") }} →
							</span>
						</span>
					</button>
					<button
						v-if="row.item.dismissible"
						type="button"
						class="ny-icon-btn ny-dismiss"
						:aria-label="__('Dismiss')"
						:title="__('Dismiss')"
						@click="$emit('dismiss', row.item.id)"
					>
						✕
					</button>
					<button
						type="button"
						class="ny-icon-btn ny-options"
						aria-haspopup="menu"
						:aria-expanded="openMenuId === row.item.id"
						:aria-label="__('More options for {0}', [row.item.title])"
						:title="__('More options for {0}', [row.item.title])"
						@click.stop="toggleMenu(row.item.id)"
					>
						⋯
					</button>
					<div v-if="openMenuId === row.item.id" class="ny-menu" role="menu" @click.stop>
						<button type="button" class="ny-menu-item" role="menuitem" @click="hide(row)">
							{{ __("Don't show this on my home") }}
						</button>
					</div>
				</li>
			</template>
		</ul>
	</section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { __ } from "@/utils/i18n";

const NOTE_LIFETIME_MS = 6000;

const props = defineProps({
	items: { type: Array, default: () => [] },
	loaded: { type: Boolean, default: false },
	failed: { type: Boolean, default: false },
	emptyText: { type: String, default: "" },
	hideFailed: { type: Boolean, default: false },
	variant: { type: String, default: "cards", validator: (v) => ["cards", "list"].includes(v) },
});

const emit = defineEmits(["ask", "navigate", "dismiss", "hide", "open-settings"]);

const root = ref(null);
const openMenuId = ref(null);
// A hidden card leaves `items` at once; its note keeps the slot it had until it times out.
const pendingNotes = ref([]);
const timers = new Map();

// A card that comes back (the hide request failed) takes its note with it.
const notes = computed(() => pendingNotes.value.filter((note) => !props.items.some((i) => i.id === note.id)));

const rows = computed(() => {
	const list = props.items.map((item) => ({ key: item.id, item }));
	for (const note of notes.value) {
		list.splice(Math.min(note.index, list.length), 0, { key: `note-${note.id}`, note });
	}
	return list;
});

function activate(item) {
	closeMenu();
	if (item.href) emit("navigate", item.href);
	else emit("ask", item.ask);
}

function toggleMenu(id) {
	openMenuId.value = openMenuId.value === id ? null : id;
	if (openMenuId.value === null) return;
	nextTick(() => root.value?.querySelector(".ny-menu-item")?.focus());
}

function closeMenu(restoreFocus = false) {
	const wasOpen = openMenuId.value !== null;
	const toggle = root.value?.querySelector(".ny-options[aria-expanded='true']");
	openMenuId.value = null;
	if (restoreFocus && wasOpen) toggle?.focus();
}

function hide(row) {
	const id = row.item.id;
	const index = rows.value.findIndex((r) => r.key === row.key);
	closeMenu();
	// One note per card: hiding it again replaces the earlier note and restarts its clock.
	clearTimeout(timers.get(id));
	pendingNotes.value = [...pendingNotes.value.filter((note) => note.id !== id), { id, index }];
	timers.set(
		id,
		setTimeout(() => {
			pendingNotes.value = pendingNotes.value.filter((note) => note.id !== id);
			timers.delete(id);
		}, NOTE_LIFETIME_MS)
	);
	emit("hide", id);
}

// Focus must not fall to the page when the hidden card's menu item disappears.
watch(
	() => notes.value.length,
	async (count, before) => {
		if (count <= before) return;
		await nextTick();
		const newest = notes.value.at(-1);
		const noteRow = [...(root.value?.querySelectorAll("[data-note]") ?? [])].find(
			(el) => el.dataset.note === newest.id
		);
		noteRow?.querySelector(".ny-note-link")?.focus();
	}
);

function onFocusOut(event) {
	// Safari and Firefox on macOS do not focus a clicked button (relatedTarget is null); an outside
	// click is closed by onDocumentClick, so a null target must not close and then reopen the menu.
	if (openMenuId.value !== null && event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) closeMenu();
}

function onDocumentClick() {
	if (openMenuId.value !== null) closeMenu();
}
onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => {
	document.removeEventListener("click", onDocumentClick);
	timers.forEach(clearTimeout);
	timers.clear();
});
</script>

<style scoped>
.ny { width: 100%; }
.ny-heading {
	margin: 0 0 var(--ql-space-2);
	font-size: var(--ql-label-size);
	font-weight: 600;
	letter-spacing: var(--ql-label-tracking);
	text-transform: uppercase;
	color: var(--ql-text-muted);
}
.ny-empty { margin: 0; font-size: 13px; color: var(--ql-text-muted); }
.ny-items { display: grid; gap: var(--ql-space-2); margin: 0; padding: 0; list-style: none; }
.ny--cards .ny-items { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--ql-space-3); }
.ny-item {
	position: relative; display: flex; align-items: stretch;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
	transition: border-color 0.15s ease;
}
.ny-item:hover { border-color: var(--ql-border-hover); }
.ny--list .ny-item { border-radius: var(--ql-radius-lg); }
.ny-main {
	display: flex; flex-direction: column; gap: var(--ql-space-2); flex: 1; min-width: 0;
	min-height: 44px; padding: var(--ql-space-3) var(--ql-space-4);
	background: transparent; border: none; border-radius: inherit;
	font-family: var(--ql-font-sans); text-align: left; color: var(--ql-text); cursor: pointer;
}
.ny--list .ny-main { flex-direction: row; align-items: flex-start; gap: var(--ql-space-3); padding: var(--ql-space-2) var(--ql-space-3); }
.ny-source { display: flex; align-items: center; gap: var(--ql-space-2); }
.ny--list .ny-source { padding-top: 6px; }
.ny-source-label { font-size: 11px; font-weight: 500; color: var(--ql-text-muted); }
.ny-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ql-text-muted); flex: none; }
.ny-item--danger .ny-dot { background: var(--ql-danger); }
.ny-item--warning .ny-dot { background: var(--ql-warning); }
.ny-body { display: flex; flex-direction: column; gap: var(--ql-space-1); min-width: 0; }
.ny-headline { display: flex; align-items: baseline; gap: var(--ql-space-2); }
.ny-count { font-family: var(--ql-font-display); font-size: 28px; line-height: 1.1; font-weight: 500; }
.ny-title { font-size: 14px; font-weight: 500; }
.ny--list .ny-count { font-family: var(--ql-font-sans); font-size: 14px; font-weight: 700; }
.ny-detail {
	font-size: 12px; color: var(--ql-text-secondary); overflow: hidden;
	display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2;
}
.ny-ask { font-size: 12px; font-weight: 600; color: var(--ql-accent); }
.ny-main:hover .ny-ask { color: var(--ql-accent-hover); }
.ny-main:focus-visible, .ny-icon-btn:focus-visible, .ny-menu-item:focus-visible, .ny-note-link:focus-visible {
	outline: 2px solid var(--ql-accent); outline-offset: -2px;
}
/* Both icon buttons sit in the card's top-right corner, level with the source label; the visible
   glyph is small but the 44px box is the hit area. The card's text reserves room for them. */
.ny-icon-btn {
	position: absolute; top: 0; right: 0; z-index: 1;
	display: flex; align-items: center; justify-content: center;
	width: 44px; height: 44px; padding: 0;
	background: transparent; border: none; border-radius: var(--ql-radius-lg);
	font-size: 13px; color: var(--ql-text-muted); cursor: pointer;
}
.ny-icon-btn:hover { color: var(--ql-text); background: var(--ql-subtle); }
.ny-dismiss { right: 44px; }
.ny-options { font-size: 18px; line-height: 1; }
.ny-item .ny-source { padding-right: 44px; }
.ny-item--dismissible .ny-source { padding-right: 88px; }
.ny--list .ny-main { padding-right: 44px; }
.ny--list .ny-item--dismissible .ny-main { padding-right: 88px; }
.ny-menu {
	position: absolute; top: 40px; right: var(--ql-space-1); z-index: 10;
	min-width: min(200px, calc(100% - var(--ql-space-2))); padding: var(--ql-space-1);
	background: var(--ql-surface); border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}
.ny-menu-item {
	display: block; width: 100%; min-height: 44px; padding: var(--ql-space-2) var(--ql-space-3);
	background: transparent; border: none; border-radius: var(--ql-radius-md);
	font-family: var(--ql-font-sans); font-size: 13px; text-align: left; color: var(--ql-text); cursor: pointer;
}
.ny-menu-item:hover { background: var(--ql-subtle); }
.ny-note {
	display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 0;
	min-height: 44px; padding: var(--ql-space-2) var(--ql-space-4);
	font-size: 13px; color: var(--ql-text-muted);
}
.ny-note-link {
	min-height: 44px; padding: 0; background: transparent; border: none;
	font-family: var(--ql-font-sans); font-size: 13px; font-weight: 600; color: var(--ql-accent); cursor: pointer;
}
.ny-note-link:hover { color: var(--ql-accent-hover); }
</style>
