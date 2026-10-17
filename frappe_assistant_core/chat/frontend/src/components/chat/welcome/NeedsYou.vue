<template>
	<section v-if="loaded && !(failed && !items.length)" class="ny" :class="`ny--${variant}`">
		<h2 class="ny-heading">{{ __("Needs you") }}</h2>
		<p v-if="!items.length" class="ny-empty">{{ emptyText || __("Nothing is waiting on you right now.") }}</p>
		<ul v-else class="ny-items">
			<li v-for="item in items" :key="item.id" class="ny-item" :class="`ny-item--${item.tone}`">
				<button type="button" class="ny-main" @click="activate(item)">
					<span class="ny-source">
						<span class="ny-dot" aria-hidden="true"></span>
						<span v-if="variant === 'cards'" class="ny-source-label">{{ item.source }}</span>
					</span>
					<span class="ny-body">
						<span class="ny-headline">
							<span class="ny-count">{{ item.count }}</span>
							<span class="ny-title">{{ item.title }}</span>
						</span>
						<span v-if="item.detail && variant === 'cards'" class="ny-detail">{{ item.detail }}</span>
						<span v-if="item.ask || item.href" class="ny-ask">
							{{ item.action || item.ask || __("Open") }} →
						</span>
					</span>
				</button>
				<button
					v-if="item.dismissible"
					type="button"
					class="ny-dismiss"
					:aria-label="__('Dismiss')"
					:title="__('Dismiss')"
					@click="$emit('dismiss', item.id)"
				>
					✕
				</button>
			</li>
		</ul>
	</section>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	items: { type: Array, default: () => [] },
	loaded: { type: Boolean, default: false },
	failed: { type: Boolean, default: false },
	emptyText: { type: String, default: "" },
	variant: { type: String, default: "cards", validator: (v) => ["cards", "list"].includes(v) },
});

const emit = defineEmits(["ask", "navigate", "dismiss"]);

function activate(item) {
	if (item.href) emit("navigate", item.href);
	else emit("ask", item.ask);
}
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
.ny-main:focus-visible, .ny-dismiss:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: -2px; }
.ny-dismiss {
	display: flex; align-items: center; justify-content: center;
	min-width: 44px; min-height: 44px; padding: 0;
	background: transparent; border: none; border-radius: inherit;
	font-size: 13px; color: var(--ql-text-muted); cursor: pointer;
}
.ny-dismiss:hover { color: var(--ql-text); background: var(--ql-subtle); }
</style>
