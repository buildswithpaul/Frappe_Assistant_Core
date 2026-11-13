<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { __ } from "@/utils/i18n";
import { useDiscoveryStore } from "@/stores/discoveryStore";
import FacoRobot from "@/components/common/FacoRobot.vue";
import YourFacPanel from "./YourFacPanel.vue";
import { ringSegments } from "./discoveryRules";

/**
 * The FAC bot at the top of the rail: the only bot on screen. The Your FAC ring, one colour per
 * power (tap = the powers panel); with progress switched off, or no powers from AR, it is the plain
 * home link it always was.
 */
const router = useRouter();
const discovery = useDiscoveryStore();

const R = 21;
const CIRC = 2 * Math.PI * R;

const mode = computed(() => (discovery.showProgress ? "progress" : "home"));
const segments = computed(() =>
	ringSegments(discovery.powers, discovery.state.used, { circ: CIRC, gap: 3 })
);
const label = computed(() => {
	const { done, total } = discovery.progress;
	return __("Your FAC: {0} of {1} tried", [done, total]);
});

function onClick() {
	if (discovery.panelOpen) discovery.closePanel();
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
		:class="{ unlocked: discovery.justUnlocked }"
		:aria-label="label"
		:title="label"
		:aria-expanded="discovery.panelOpen"
		data-test="rail-bot"
		@click="onClick"
	>
		<svg class="bot-ring" viewBox="0 0 48 48" aria-hidden="true">
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
		</svg>
		<FacoRobot size="sm" show-arms />
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
.unlocked { animation: bot-pop 0.6s ease 2; }
@keyframes bot-pop { 50% { transform: scale(1.12); } }
@media (prefers-reduced-motion: reduce) {
	.unlocked { animation: none; }
	.ring-seg { transition: none; }
}
</style>
