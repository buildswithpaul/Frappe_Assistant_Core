<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { __ } from "@/utils/i18n";
import { useDiscoveryStore } from "@/stores/discoveryStore";
import FacoRobot from "@/components/common/FacoRobot.vue";
import StoryPlayer from "@/components/stories/StoryPlayer.vue";
import YourFacPanel from "./YourFacPanel.vue";
import { ringSegments } from "./discoveryRules";

/**
 * The FAC bot at the top of the rail: the only bot on screen. A coloured ring while a What's new
 * story is waiting (tap = watch it); otherwise the Your FAC ring, one colour per power, (tap = the powers panel);
 * with both switched off, or nothing from AR, it is the plain home link it always was.
 */
const router = useRouter();
const discovery = useDiscoveryStore();

const R = 21;
const CIRC = 2 * Math.PI * R;

const mode = computed(() => {
	if (discovery.waitingStory) return "story";
	if (discovery.showProgress) return "progress";
	return "home";
});
const segments = computed(() =>
	ringSegments(discovery.powers, discovery.state.used, { circ: CIRC, gap: 3 })
);
const label = computed(() => {
	if (mode.value === "story") return __("What's new: {0}", [discovery.waitingStory.title || ""]);
	const { done, total } = discovery.progress;
	return __("Your FAC: {0} of {1} tried", [done, total]);
});

function onClick() {
	if (mode.value === "story") discovery.openStory();
	else if (discovery.panelOpen) discovery.closePanel();
	else discovery.openPanel();
}

function onTry(id) {
	discovery.tryPower(id, router);
}

function openSettings() {
	discovery.closePanel();
	router.push("/settings/home");
}
</script>

<template>
	<router-link v-if="mode === 'home'" to="/chat" class="rail-bot" :aria-label="__('FACO home')" :title="__('FACO')">
		<FacoRobot size="sm" show-arms />
	</router-link>
	<button
		v-else
		type="button"
		class="rail-bot"
		:class="[`is-${mode}`, { unlocked: discovery.justUnlocked }]"
		:aria-label="label"
		:title="label"
		:aria-expanded="mode === 'progress' ? discovery.panelOpen : undefined"
		data-test="rail-bot"
		@click="onClick"
	>
		<svg class="bot-ring" viewBox="0 0 48 48" aria-hidden="true">
			<template v-if="mode === 'progress'">
				<g data-test="rail-bot-progress">
					<circle
						v-for="s in segments"
						:key="s.id"
						class="ring-seg"
						:class="{ done: s.done }"
						cx="24"
						cy="24"
						:r="R"
						:stroke-dasharray="s.dasharray"
						:stroke-dashoffset="s.dashoffset"
						:style="{ '--power-color': s.color }"
					/>
				</g>
			</template>
			<circle v-else class="ring-story" cx="24" cy="24" :r="R" />
		</svg>
		<FacoRobot size="sm" show-arms />
		<span v-if="mode === 'story'" class="bot-new">{{ __("NEW") }}</span>
	</button>

	<YourFacPanel
		v-if="mode === 'progress' && discovery.panelOpen"
		:powers="discovery.powers"
		:used="discovery.state.used"
		:progress="discovery.progress"
		@try="onTry"
		@close="discovery.closePanel()"
		@settings="openSettings"
	/>
	<StoryPlayer :story="discovery.story" @close="discovery.closeStory()" />
</template>

<style scoped>
.rail-bot {
	position: relative; display: flex; align-items: center; justify-content: center;
	width: 2.75rem; height: 2.75rem; padding: 0; border: 0; border-radius: 50%; background: none; cursor: pointer;
}
.rail-bot:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
.bot-ring { position: absolute; inset: 0; width: 100%; height: 100%; transform: rotate(-90deg); pointer-events: none; }
.bot-ring circle { fill: none; stroke-width: 3; }
.ring-seg { stroke: var(--ql-subtle); transition: stroke 0.4s ease; }
.ring-seg.done { stroke: var(--power-color); }
.ring-story { stroke: var(--ql-accent); }
.is-story .bot-ring { animation: story-spin 6s linear infinite; }
.is-story .ring-story { stroke-dasharray: 10 4; }
.bot-new {
	position: absolute; bottom: -4px; left: 50%; transform: translateX(-50%); padding: 0 4px; border-radius: 6px;
	background: var(--ql-accent); color: #fff; font-size: 8.5px; font-weight: 800; letter-spacing: 0.04em; line-height: 13px;
}
.unlocked { animation: bot-pop 0.6s ease 2; }
@keyframes story-spin { to { transform: rotate(270deg); } }
@keyframes bot-pop { 50% { transform: scale(1.12); } }
@media (prefers-reduced-motion: reduce) {
	.is-story .bot-ring, .unlocked { animation: none; }
	.ring-seg { transition: none; }
}
</style>
