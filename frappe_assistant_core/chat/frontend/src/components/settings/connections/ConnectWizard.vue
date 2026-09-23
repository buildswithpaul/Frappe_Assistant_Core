<template>
	<WizardShell :eyebrow="eyebrow" :error="error" @close="requestClose">
		<EntryStep
			v-if="state === 'entry'"
			:busy="busy"
			:initial-url="endpointUrl"
			@check="handleCheck"
		/>

		<CheckingStep
			v-else-if="state === 'checking'"
			:steps="steps"
			:revealed="revealed"
			:running="busy"
			:host="endpointHost"
		/>

		<!-- Verdict first, checklist last. The rows are reassurance, not the
		     content of this step, so a clean run folds them behind a tally. -->
		<template v-else-if="state === 'needs_auth'">
			<AuthStep
				:server-info="serverInfo"
				:auth="auth"
				:redirect-uri="redirectUri"
				:authorize-url="authorizeUrl"
				:busy="busy"
				@connect="leaveForAuth"
				@credentials="submitCredentials"
			/>
			<PreflightSteps :steps="steps" :revealed="steps.length" collapsible />
		</template>

		<WizardOutcome
			v-else-if="state === 'away'"
			data-test="away"
			tone="waiting"
			title="Taking you to sign in"
			:detail="`Finish at ${awayTarget} and you'll land back here.`"
		/>

		<!-- Only settleAuthorized() sets state to 'review', and it commits a
		     reconnect before it gets there. So CapabilityReview's own
		     duplicate-name check never sees a name the user isn't changing. -->
		<CapabilityReview
			v-else-if="state === 'review'"
			:capabilities="capabilities"
			:suggested-name="suggestedName"
			:existing-names="existingNames"
			:saving="busy"
			@add="commit"
			@cancel="requestClose"
		/>

		<WizardOutcome
			v-else-if="state === 'added'"
			data-test="added"
			tone="done"
			:title="`${addedName} is connected`"
			detail="All its tools are on — narrow them from the connection's Tools button."
		/>

		<!-- Back leads to the URL field, which a reconnect has no use for:
		     AR takes the endpoint from the row, not from the user. Sits below
		     the shell's error slot, so a failed check reads message-then-exit. -->
		<template #footer>
			<button
				v-if="state === 'checking' && !busy && !reauthName"
				type="button"
				class="connect-wizard__back"
				data-test="back"
				@click="backToEntry"
			>
				<svg viewBox="0 0 12 12" class="connect-wizard__back-glyph" aria-hidden="true">
					<path d="M7 3 4 6l3 3" />
				</svg>
				Back
			</button>
		</template>
	</WizardShell>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api } from "@/api/client";
import WizardShell from "./wizard/WizardShell.vue";
import EntryStep from "./wizard/EntryStep.vue";
import PreflightSteps from "./wizard/PreflightSteps.vue";
import CheckingStep from "./wizard/CheckingStep.vue";
import AuthStep from "./wizard/AuthStep.vue";
import CapabilityReview from "./wizard/CapabilityReview.vue";
import WizardOutcome from "./wizard/WizardOutcome.vue";

const props = defineProps({
	existingNames: { type: Array, default: () => [] },
	initialUrl: { type: String, default: "" },
	initialHandle: { type: String, default: "" },
	reauthServerName: { type: String, default: "" },
	stepDelayMs: { type: Number, default: 90 },
});

const emit = defineEmits(["added", "close"]);

const state = ref("entry");
const endpointUrl = ref(props.initialUrl);
const handle = ref(props.initialHandle);
const steps = ref([]);
const revealed = ref(0);
const serverInfo = ref({});
const auth = ref({});
const redirectUri = ref("");
const authorizeUrl = ref("");
const capabilities = ref(null);
const addedName = ref("");
const error = ref("");
const busy = ref(false);
const committed = ref(false);

// What the SESSION says this flow is. `null` means no payload has spoken yet;
// "" means a payload said reauth_server_name was null, i.e. an ordinary add.
const payloadReauthName = ref(null);

let revealTimer = null;

const suggestedName = computed(() => serverInfo.value?.name || "");

// Precedence, explicitly: the payload is authoritative because AR resolves it
// from the session's own reauth_target, so it is right in any tab, on any
// device, after any reload. The prop is only a starting hint for a wizard
// ConnectionCard opened straight into reauth mode before the first round trip.
// Once a payload carries the key its value wins — including "" (not a
// reconnect). Only an absent key leaves the hint in charge.
const reauthName = computed(() =>
	payloadReauthName.value === null ? props.reauthServerName : payloadReauthName.value
);

// ---- Presentation only. Nothing below this comment steers the state machine.

// Names the flow, not the step — each step titles itself in the body.
const eyebrow = computed(() =>
	reauthName.value ? `Reconnect · ${reauthName.value}` : "New connection"
);

// The host alone, not the whole URL: it is the "am I talking to the right
// place" cue during the wait. Empty on a reconnect, where AR supplies the URL.
const endpointHost = computed(() => {
	try {
		return new URL(endpointUrl.value).host;
	} catch {
		return "";
	}
});

const awayTarget = computed(() => auth.value.authorization_server || "the authorization server");

function stopReveal() {
	if (revealTimer) {
		clearInterval(revealTimer);
		revealTimer = null;
	}
}

function revealSteps(rows, instant) {
	stopReveal();
	steps.value = rows || [];
	revealed.value = 0;
	if (!steps.value.length) return;
	if (instant || props.stepDelayMs <= 0) {
		revealed.value = steps.value.length;
		return;
	}
	revealTimer = setInterval(() => {
		revealed.value += 1;
		if (revealed.value >= steps.value.length) stopReveal();
	}, props.stepDelayMs);
}

function applyPayload(payload, instant = false) {
	const preflight = payload?.preflight || {};
	revealSteps(preflight.steps, instant);
	serverInfo.value = preflight.server_info || {};
	auth.value = preflight.auth || {};
	redirectUri.value = payload?.redirect_uri || redirectUri.value;
	authorizeUrl.value = payload?.authorize_url || "";
	if (payload?.handle) handle.value = payload.handle;
	// Presence, not truthiness: a payload that carries the key and sets it to
	// null is telling us this is an add, and that answer outranks the prop.
	if (payload && "reauth_server_name" in payload) {
		payloadReauthName.value = payload.reauth_server_name || "";
	}
}

function validateUrl(url) {
	let parsed;
	try {
		parsed = new URL(url);
	} catch {
		return "Enter a valid endpoint URL.";
	}
	if (parsed.protocol !== "https:") {
		return "The endpoint URL must start with https://.";
	}
	return "";
}

// EntryStep only trims and hands the string up; this is where it turns into
// the canonical "current URL" so a bounce back to `entry` after a failed
// begin, or a manual-credentials retry, both see the same value.
function handleCheck(url) {
	endpointUrl.value = url;
	start();
}

async function start(credentials = null) {
	const url = endpointUrl.value.trim();
	const message = validateUrl(url);
	if (message) {
		error.value = message;
		return;
	}
	error.value = "";
	busy.value = true;
	state.value = "checking";
	try {
		const payload = await api.connections.beginConnect(
			url,
			credentials?.client_id ?? null,
			credentials?.client_secret ?? null
		);
		applyPayload(payload);
		await routeAfterPreflight();
	} catch (err) {
		error.value = err?.message || "Couldn't reach that server.";
		state.value = "entry";
	} finally {
		busy.value = false;
	}
}

async function startReauth() {
	error.value = "";
	busy.value = true;
	state.value = "checking";
	try {
		// Not beginConnect. Only the reauth endpoint sets reauth_target on the
		// session, and only reauth_target makes commit refresh the existing row
		// in place; the add path would refuse the name the user is not changing.
		// It sends no endpoint URL either — AR reads that from the row, so a
		// reconnect cannot silently retarget a connection at a different server.
		// The prop is the only source here by definition: no session exists yet,
		// so there is no payload to outrank it. From the response onward the
		// payload's reauth_server_name takes over.
		const payload = await api.connections.beginReauth(props.reauthServerName);
		applyPayload(payload);
		await routeAfterPreflight();
	} catch (err) {
		// Stay in `checking`: the preflight rows and the error belong together,
		// and falling back to `entry` would hand a reconnect a blank URL field.
		error.value = err?.message || "Couldn't start that reconnection.";
	} finally {
		busy.value = false;
	}
}

async function routeAfterPreflight() {
	const failure = (steps.value || []).find((s) => s.status === "fail");
	if (failure) {
		// A failed step is the end of the road, and its next_action is a
		// concrete instruction — never a traceback.
		error.value = failure.next_action || failure.detail || "That server didn't pass the checks.";
		return;
	}
	if ((auth.value.scheme || "none") === "none") {
		// Part 3 already marked the session Authorized and probed it during
		// begin — there is no round trip to wait for.
		await loadReview();
		return;
	}
	state.value = "needs_auth";
}

// The ONLY route into the review step, so the reauth check cannot be bypassed
// by one caller and honoured by another. A reconnect never reaches
// CapabilityReview, which is what keeps its client-side duplicate-name check
// off a name the user is not changing.
async function settleAuthorized(session) {
	capabilities.value = session?.capabilities || null;
	// Re-authorization has nothing new to review — the connection, its name and
	// its tool filters already exist, and AR updates that row in place through
	// the session's reauth_target. Checked before capabilities: a reconnect does
	// not need a fresh capability probe to be allowed to refresh its tokens.
	if (reauthName.value) {
		await commit({ server_name: reauthName.value });
		return;
	}
	if (!capabilities.value) {
		error.value = "We couldn't read what that server offers.";
		return;
	}
	state.value = "review";
}

async function loadReview() {
	busy.value = true;
	try {
		const session = await api.connections.getConnectSession(handle.value);
		if (session?.status === "Failed") {
			error.value = session.error_message || "That connection couldn't be completed.";
			state.value = "entry";
			return;
		}
		// No applyPayload here: the begin payload already set the preflight rows
		// and reauth_server_name, and re-applying would snap the reveal cursor to
		// the end mid-animation.
		await settleAuthorized(session);
	} catch (err) {
		error.value = err?.message || "Couldn't read that connect session.";
	} finally {
		busy.value = false;
	}
}

async function resume() {
	busy.value = true;
	state.value = "checking";
	try {
		// The deep link carries only the handle — but the session itself knows
		// whether it is a reconnect, because AR set reauth_target on it and Part 3
		// returns that as reauth_server_name. applyPayload reads it, so this works
		// in a different tab, on a different device, or with storage blocked.
		const session = await api.connections.getConnectSession(handle.value);
		endpointUrl.value = session?.endpoint_url || endpointUrl.value;
		applyPayload(session, true);
		if (session?.status === "Failed") {
			error.value = session.error_message || "That connection couldn't be completed.";
			state.value = "entry";
			return;
		}
		if (session?.status === "Committed") {
			// server_name is written onto the session by commit_connect, so it
			// is the authoritative name for an already-finished flow.
			committed.value = true;
			addedName.value = session.server_name || reauthName.value || "";
			state.value = "added";
			return;
		}
		if (session?.status === "Authorized") {
			await settleAuthorized(session);
			return;
		}
		// "Preflight" and "Awaiting Auth" both mean the round trip has not
		// completed. Title Case with spaces — the doctype Select values verbatim.
		state.value = "needs_auth";
	} catch (err) {
		error.value = err?.message || "That sign-in link has expired. Start again.";
		state.value = "entry";
	} finally {
		busy.value = false;
	}
}

function leaveForAuth() {
	// authorize_url is stored on the session as Small Text and returned by
	// _session_payload, so a resumed flow has a real link here, not null.
	if (!authorizeUrl.value) {
		error.value = "That server didn't give us a sign-in link.";
		return;
	}
	// Nothing to park before the tab leaves. The reconnect intent lives on the
	// session as reauth_target, and comes back as reauth_server_name on whatever
	// tab or device reopens the deep link.
	state.value = "away";
	window.location.assign(authorizeUrl.value);
}

async function submitCredentials(credentials) {
	// The DCR-less session was opened without credentials; re-begin rather than
	// patch it, and drop the old one so it isn't left holding a PKCE verifier.
	if (handle.value) {
		try {
			await api.connections.abandonConnect(handle.value);
		} catch {
			// It expires on its own within the session TTL.
		}
		handle.value = "";
	}
	await start(credentials);
}

async function commit({ server_name }) {
	busy.value = true;
	try {
		// One call for both modes: AR branches on the session's reauth_target,
		// updating the existing row in place or inserting a new one.
		await api.connections.commitConnect(handle.value, server_name);
		committed.value = true;
		addedName.value = server_name;
		error.value = "";
		state.value = "added";
		emit("added", server_name);
	} catch (err) {
		error.value = err?.message || "Couldn't add that connection.";
	} finally {
		busy.value = false;
	}
}

function backToEntry() {
	error.value = "";
	state.value = "entry";
}

function requestClose() {
	if (handle.value && !committed.value) {
		api.connections.abandonConnect(handle.value).catch(() => {});
	}
	emit("close");
}

onMounted(() => {
	if (props.initialHandle) {
		resume();
		return;
	}
	// A reconnect needs no URL — AR takes it from the row — so it is gated on
	// the server name alone.
	if (props.reauthServerName) {
		startReauth();
	}
});

onBeforeUnmount(stopReveal);
</script>

<style scoped>
.connect-wizard__back {
	display: inline-flex;
	align-items: center;
	align-self: flex-start;
	gap: 0.25rem;
	padding: 0;
	background: none;
	border: none;
	font: inherit;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-secondary);
	cursor: pointer;
}

.connect-wizard__back:hover {
	color: var(--ql-text);
}

.connect-wizard__back-glyph {
	width: 0.75rem;
	height: 0.75rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.6;
	stroke-linecap: round;
	stroke-linejoin: round;
}
</style>
