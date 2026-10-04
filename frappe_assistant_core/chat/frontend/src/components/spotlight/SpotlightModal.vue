<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { renderNotificationMarkdown } from "@/utils/markdown";
import SpotlightMedia from "./SpotlightMedia.vue";
import SpotlightQuotaArt from "./SpotlightQuotaArt.vue";

const FOCUSABLE = "button, [href], video[controls]";

const props = defineProps({ content: { type: Object, default: null } });
const emit = defineEmits(["primary", "secondary", "dismiss"]);

const cardRef = ref(null);
const primaryRef = ref(null);
const mediaFailed = ref(false);
let openerEl = null;
const titleId = computed(() => `spotlight-title-${props.content?.id || "x"}`);
const bodyHtml = computed(() => (props.content?.body ? renderNotificationMarkdown(props.content.body) : ""));
const hasMedia = computed(() => !!props.content?.media && !mediaFailed.value);

watch(
	() => props.content?.id,
	async (id) => {
		mediaFailed.value = false;
		if (!id) {
			if (openerEl?.isConnected) openerEl.focus();
			openerEl = null;
			return;
		}
		openerEl ??= document.activeElement;
		await nextTick();
		primaryRef.value?.focus();
	},
	{ immediate: true }
);

function onKeydown(e) {
	if (e.key === "Escape") {
		emit("dismiss");
		return;
	}
	if (e.key !== "Tab" || !cardRef.value) return;
	const focusables = cardRef.value.querySelectorAll(FOCUSABLE);
	if (!focusables.length) return;
	const first = focusables[0];
	const last = focusables[focusables.length - 1];
	if (e.shiftKey && document.activeElement === first) {
		e.preventDefault();
		last.focus();
	} else if (!e.shiftKey && document.activeElement === last) {
		e.preventDefault();
		first.focus();
	}
}
</script>

<template>
	<Teleport to="body">
		<Transition name="spot">
			<div v-if="content" class="spot-overlay" data-test="spotlight-overlay" @click.self="emit('dismiss')">
				<div
					ref="cardRef"
					class="spot-card"
					:class="{ 'is-text-only': !hasMedia }"
					data-test="spotlight-card"
					role="dialog"
					tabindex="-1"
					aria-modal="true"
					:aria-labelledby="titleId"
					@keydown="onKeydown"
				>
					<div class="spot-text">
						<span v-if="content.eyebrow" class="spot-eyebrow">{{ content.eyebrow }}</span>
						<h2 :id="titleId" class="spot-title">{{ content.title }}</h2>
						<div v-if="bodyHtml" class="spot-body" v-html="bodyHtml"></div>
						<ul v-if="content.highlights?.length" class="spot-highlights">
							<li v-for="(h, i) in content.highlights" :key="i" data-test="spotlight-highlight">
								<span class="spot-hl-icon" aria-hidden="true">✦</span><span>{{ h }}</span>
							</li>
						</ul>
						<div class="spot-actions">
							<button ref="primaryRef" class="spot-primary" data-test="spotlight-primary" @click="emit('primary')">
								{{ content.primary.label }}
							</button>
							<button
								v-if="content.secondary"
								class="spot-secondary"
								data-test="spotlight-secondary"
								@click="emit('secondary')"
							>
								{{ content.secondary.label }}
							</button>
						</div>
					</div>
					<div v-if="hasMedia" class="spot-visual">
						<SpotlightQuotaArt v-if="content.media.art === 'quota'" :percent="content.threshold || 80" />
						<SpotlightMedia v-else :media="content.media" @failed="mediaFailed = true" />
					</div>
					<button class="spot-close" aria-label="Close" @click="emit('dismiss')">✕</button>
				</div>
			</div>
		</Transition>
	</Teleport>
</template>

<style scoped>
.spot-overlay {
	position: fixed;
	inset: 0;
	z-index: 1000;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
	background: rgba(0, 0, 0, 0.55);
	overflow-y: auto;
}
.spot-card {
	position: relative;
	display: grid;
	grid-template-columns: 1fr 1fr;
	width: calc(100vw - 32px);
	max-width: 920px;
	max-height: calc(100vh - 32px);
	overflow: hidden;
	border-radius: 20px;
	background: var(--ql-surface);
	color: var(--ql-text);
	box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
}
.spot-card:focus { outline: none; }
.spot-card.is-text-only {
	grid-template-columns: 1fr;
	max-width: 520px;
}
.spot-text {
	display: flex;
	flex-direction: column;
	gap: 16px;
	padding: 40px;
	overflow-y: auto;
}
.spot-eyebrow {
	align-self: flex-start;
	padding: 4px 10px;
	border-radius: 999px;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	font-size: 12px;
	font-weight: 600;
}
.spot-title {
	margin: 0;
	font-family: var(--ql-font-display, inherit);
	font-size: 32px;
	line-height: 1.15;
	font-weight: 600;
	color: var(--ql-text);
}
.spot-body {
	font-size: 16px;
	line-height: 1.5;
	color: var(--ql-text-muted);
}
.spot-body :deep(p) { margin: 0 0 8px; }
.spot-body :deep(p:last-child) { margin-bottom: 0; }
.spot-body :deep(a) { color: var(--ql-accent); }
.spot-body :deep(strong) { color: var(--ql-text); }
.spot-highlights {
	list-style: none;
	margin: 0;
	padding: 0;
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	overflow: hidden;
}
.spot-highlights li {
	display: flex;
	gap: 12px;
	align-items: flex-start;
	padding: 12px 16px;
	font-size: 15px;
	color: var(--ql-text);
}
.spot-highlights li + li { border-top: 1px solid var(--ql-border); }
.spot-hl-icon { color: var(--ql-accent); }
.spot-actions {
	display: flex;
	flex-direction: column;
	gap: 8px;
	margin-top: auto;
	padding-top: 8px;
}
.spot-primary,
.spot-secondary {
	width: 100%;
	padding: 12px 16px;
	border: 0;
	border-radius: 12px;
	font-size: 15px;
	font-weight: 600;
	cursor: pointer;
}
.spot-primary { background: var(--ql-text); color: var(--ql-bg); }
.spot-primary:hover { opacity: 0.9; }
.spot-secondary { background: var(--ql-subtle); color: var(--ql-text-secondary); }
.spot-secondary:hover { color: var(--ql-text); }
.spot-primary:focus-visible,
.spot-secondary:focus-visible,
.spot-close:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}
.spot-visual { min-height: 0; overflow: hidden; }
.spot-close {
	position: absolute;
	top: 12px;
	right: 12px;
	width: 36px;
	height: 36px;
	border: 0;
	border-radius: 50%;
	background: var(--ql-surface);
	color: var(--ql-text);
	font-size: 16px;
	cursor: pointer;
	box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

@media (max-width: 719px) {
	.spot-card,
	.spot-card.is-text-only {
		grid-template-columns: 1fr;
		overflow-y: auto;
	}
	.spot-visual {
		order: -1;
		max-height: 40vh;
	}
	.spot-text { padding: 24px; overflow-y: visible; }
}

@media (prefers-reduced-motion: no-preference) {
	.spot-enter-active { transition: opacity 200ms ease; }
	.spot-leave-active { transition: opacity 150ms ease; }
	.spot-enter-from,
	.spot-leave-to { opacity: 0; }
	.spot-enter-active .spot-card {
		animation: spot-card-in 260ms cubic-bezier(0.2, 0.8, 0.2, 1);
	}
	@keyframes spot-card-in {
		from { transform: translateY(12px) scale(0.98); }
		to { transform: none; }
	}
}
</style>
