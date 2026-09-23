<template>
	<div
		class="connection-row"
		:class="{ 'needs-attention': needsAttention, 'is-managed': connection.managed }"
		data-test="connection-card"
	>
		<div class="connection-row__body">
			<div class="connection-row__identity">
				<h3 class="connection-row__name">{{ connection.server_name }}</h3>
				<span v-if="connection.managed" class="connection-row__pill" data-test="always-on">
					Always on
				</span>
			</div>

			<p class="connection-row__meta">
				<span class="connection-row__host" :title="connection.endpoint_url">{{ host }}</span>
				<span class="connection-row__sep" aria-hidden="true"></span>
				<span class="connection-row__status" :class="badgeClass" data-test="status">
					<span class="connection-row__dot" aria-hidden="true"></span>{{ statusLabel }}
				</span>
				<template v-if="hiddenCount">
					<span class="connection-row__sep" aria-hidden="true"></span>
					<span>{{ hiddenCount }} {{ hiddenCount === 1 ? "tool" : "tools" }} hidden</span>
				</template>
			</p>

			<!-- Test and Tools come last in source so they land on the right edge
			     of every row and form one aligned column down the ledger. The
			     actions that change a connection rather than inspect it sit
			     inboard and quieter — Remove is not a peer of Test. -->
			<div class="connection-row__actions">
				<template v-if="!connection.managed">
					<button
						type="button"
						class="connection-row__link"
						data-test="toggle"
						:disabled="busy"
						@click="$emit('toggle', connection.server_name)"
					>
						{{ isEnabled ? "Disable" : "Enable" }}
					</button>
					<!-- Only the hand-entered kinds have anything left to edit. A
					     wizard-built connection discovered its own authentication
					     and its tokens belong to the endpoint that issued them, so
					     the old form could only offer to break it. Tools and
					     Reconnect cover everything it can legitimately change. -->
					<button
						v-if="isHandEntered"
						type="button"
						class="connection-row__link"
						data-test="edit"
						:disabled="busy"
						@click="$emit('edit', connection.server_name)"
					>
						Edit
					</button>
					<button
						type="button"
						class="connection-row__link connection-row__link--danger"
						data-test="remove"
						:disabled="busy"
						@click="$emit('remove', connection.server_name)"
					>
						Remove
					</button>
					<span class="connection-row__divider" aria-hidden="true"></span>
				</template>

				<button
					type="button"
					class="connection-row__action"
					data-test="test"
					:disabled="busy"
					@click="$emit('test', connection.server_name)"
				>
					Test
				</button>
				<button
					type="button"
					class="connection-row__action"
					data-test="tools"
					:disabled="busy"
					@click="$emit('tools', connection.server_name)"
				>
					Tools
				</button>
			</div>
		</div>

		<!-- A connection that needs the user is the one thing on this page worth
		     raising your voice about. Everything healthy stays quiet so this
		     reads instantly. -->
		<div v-if="needsAttention" class="connection-row__attention">
			<p class="connection-row__attention-text">{{ attentionText }}</p>
			<button
				v-if="needsReauth"
				type="button"
				class="connection-row__reconnect"
				data-test="reconnect"
				:disabled="busy"
				@click="$emit('reconnect', connection.server_name)"
			>
				Reconnect
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	connection: { type: Object, required: true },
	busy: { type: Boolean, default: false },
});

defineEmits(["test", "toggle", "remove", "edit", "tools", "reconnect"]);

const isEnabled = computed(() => props.connection.enabled !== false);

// The edit form predates the wizard: it asks for an endpoint and an
// authentication type, which are exactly the two things a wizard-built
// connection must not have re-typed by hand. Its auth_type is not even among
// the form's options, so the field renders blank and one careless save would
// strand the stored tokens. Offer it only for connections that were typed in.
const isHandEntered = computed(() =>
	["None", "APIKey"].includes(props.connection.auth_type)
);

// AR sets this status when a refresh fails: the stored tokens are gone and
// only a fresh interactive authorization can restore the connection. Never the
// managed row — it keeps its own Frappe OAuth path and refreshes itself, so
// sending the user into a reconnect there offers a fix to a problem they
// cannot have and AR would refuse the reserved name anyway.
const needsReauth = computed(
	() => props.connection.status === "Token Expired" && !props.connection.managed
);

// Only raise the strip when the user can act. A managed row that reports an
// expired token recovers on its own; the status dot already says so.
const needsAttention = computed(
	() => needsReauth.value || props.connection.status === "Error"
);

const attentionText = computed(() => {
	if (needsReauth.value) {
		return "This connection's access has expired. Reconnect to restore it.";
	}
	return props.connection.error_message || "This connection is unreachable.";
});

// The address matters, but as an identity cue rather than a string to read —
// the full URL is on the title attribute for anyone who wants it.
const host = computed(() => {
	const url = props.connection.endpoint_url;
	if (!url) return "No endpoint set";
	try {
		return new URL(url).host;
	} catch {
		return url;
	}
});

const hiddenCount = computed(() => (props.connection.blocked_tools || []).length);

const statusLabel = computed(() => {
	if (!isEnabled.value) return "Off";
	if (props.connection.status === "Active") return "Connected";
	if (props.connection.status === "Token Expired") return "Access expired";
	return props.connection.status || "Unknown";
});

const badgeClass = computed(() => {
	if (!isEnabled.value) return "is-neutral";
	if (props.connection.status === "Active") return "is-active";
	if (props.connection.status === "Error") return "is-error";
	if (props.connection.status === "Token Expired") return "is-token-expired";
	return "is-neutral";
});
</script>

<style scoped>
.connection-row {
	background: var(--ql-surface);
}

/* The ERP itself, not a tool anyone chose to add — seated rather than raised so
   it reads as part of the furniture. */
.connection-row.is-managed {
	background: var(--ql-subtle);
}

.connection-row__body {
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	grid-template-areas:
		"identity actions"
		"meta     actions";
	align-items: center;
	gap: 3px var(--ql-space-6);
	padding: var(--ql-space-4) var(--ql-space-6);
	min-height: 68px;
}

.connection-row__identity {
	grid-area: identity;
	display: flex;
	align-items: center;
	gap: var(--ql-space-2);
	min-width: 0;
}

.connection-row__name {
	margin: 0;
	font-size: 0.9375rem;
	font-weight: 600;
	letter-spacing: -0.005em;
	color: var(--ql-text);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* Outlined rather than filled: this pill sits on the seated managed row, whose
   background is already --ql-subtle, so a filled one would disappear. */
.connection-row__pill {
	flex-shrink: 0;
	padding: 0 7px;
	border: 1px solid var(--ql-border-hover);
	border-radius: 9999px;
	font-size: 0.6875rem;
	font-weight: 500;
	line-height: 1.5rem;
	color: var(--ql-text-muted);
}

.connection-row__meta {
	grid-area: meta;
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: var(--ql-space-2);
	margin: 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	min-width: 0;
}

.connection-row__host {
	font-family: var(--ql-font-mono);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.connection-row__sep {
	width: 2px;
	height: 2px;
	border-radius: 50%;
	background: currentColor;
	opacity: 0.5;
}

.connection-row__status {
	display: inline-flex;
	align-items: center;
	gap: 5px;
}

.connection-row__dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: currentColor;
}

/* Healthy is the common case and says the least; it gets a dot, not a badge. */
.connection-row__status.is-active {
	color: var(--ql-success);
}

.connection-row__status.is-error {
	color: var(--ql-danger);
}

.connection-row__status.is-token-expired {
	color: var(--ql-warning);
}

.connection-row__status.is-neutral {
	color: var(--ql-text-muted);
}

.connection-row__actions {
	grid-area: actions;
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: var(--ql-space-2);
	justify-content: flex-end;
}

.connection-row__action {
	padding: 5px 11px;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-surface);
	font: inherit;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	cursor: pointer;
	transition: border-color 0.12s ease, color 0.12s ease;
}

.connection-row__action:hover:not(:disabled) {
	border-color: var(--ql-border-hover);
	color: var(--ql-text);
}

.connection-row__divider {
	width: 1px;
	height: 18px;
	margin: 0 var(--ql-space-1);
	background: var(--ql-border);
}

.connection-row__link {
	padding: 5px 2px;
	border: none;
	background: none;
	font: inherit;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: color 0.12s ease;
}

.connection-row__link:hover:not(:disabled) {
	color: var(--ql-text);
}

.connection-row__link--danger:hover:not(:disabled) {
	color: var(--ql-danger);
}

.connection-row__action:disabled,
.connection-row__link:disabled {
	opacity: 0.45;
	cursor: default;
}

.connection-row__attention {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: var(--ql-space-3);
	padding: var(--ql-space-3) var(--ql-space-6);
	background: color-mix(in srgb, var(--ql-warning) 8%, var(--ql-surface));
	border-top: 1px solid color-mix(in srgb, var(--ql-warning) 22%, transparent);
}

.connection-row.needs-attention .connection-row__body {
	padding-bottom: var(--ql-space-3);
}

.connection-row__attention-text {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.connection-row__reconnect {
	margin-left: auto;
	padding: 5px 12px;
	border: 1px solid var(--ql-warning);
	border-radius: var(--ql-radius-sm);
	background: none;
	font: inherit;
	font-size: 0.8125rem;
	color: var(--ql-warning);
	cursor: pointer;
}

.connection-row__reconnect:hover:not(:disabled) {
	background: color-mix(in srgb, var(--ql-warning) 12%, transparent);
}

@media (prefers-reduced-motion: reduce) {
	.connection-row__action,
	.connection-row__link {
		transition: none;
	}
}

@media (max-width: 640px) {
	.connection-row__body {
		grid-template-columns: minmax(0, 1fr);
		grid-template-areas:
			"identity"
			"meta"
			"actions";
		gap: var(--ql-space-2);
	}

	.connection-row__actions {
		justify-content: flex-start;
	}
}
</style>
