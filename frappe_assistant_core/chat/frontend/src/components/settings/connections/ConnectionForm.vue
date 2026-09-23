<template>
	<form class="connection-form" @submit.prevent="submit">
		<label class="connection-form__field">
			<span class="connection-form__label">Name</span>
			<input
				v-model="name"
				data-test="name"
				type="text"
				class="connection-form__input"
				placeholder="Acme CRM"
				autocomplete="off"
				:disabled="isEditing"
			/>
			<span v-if="isEditing" class="connection-form__hint">
				The name can't be changed after a connection is added. Remove and
				re-add it under a new name instead.
			</span>
		</label>

		<label class="connection-form__field">
			<span class="connection-form__label">Endpoint URL</span>
			<input
				v-model="endpointUrl"
				data-test="url"
				type="text"
				class="connection-form__input"
				placeholder="https://example.com/api/method/mcp"
				autocomplete="off"
			/>
			<span class="connection-form__hint">
				Must be a Streamable HTTP MCP endpoint. SSE-only servers are not supported yet.
			</span>
		</label>

		<label class="connection-form__field">
			<span class="connection-form__label">Authentication</span>
			<select v-model="authType" data-test="auth-type" class="connection-form__input">
				<option value="None">None</option>
				<option value="APIKey">API Key</option>
			</select>
		</label>

		<template v-if="authType === 'APIKey'">
			<label class="connection-form__field">
				<span class="connection-form__label">API Key</span>
				<input
					v-model="apiKey"
					data-test="api-key"
					type="password"
					class="connection-form__input"
					autocomplete="off"
				/>
				<span v-if="isEditing" class="connection-form__hint">
					Leave blank to keep the key already on file.
				</span>
			</label>

			<label class="connection-form__field">
				<span class="connection-form__label">Header name</span>
				<input
					v-model="apiKeyHeader"
					data-test="api-key-header"
					type="text"
					class="connection-form__input"
					placeholder="Authorization"
					autocomplete="off"
				/>
			</label>
		</template>

		<p v-if="error" class="connection-form__error" role="alert">{{ error }}</p>

		<div class="connection-form__actions">
			<button type="submit" class="connection-form__save" :disabled="saving">
				{{ saving ? "Saving…" : isEditing ? "Save changes" : "Add connection" }}
			</button>
			<button
				type="button"
				class="connection-form__cancel"
				:disabled="saving"
				@click="$emit('cancel')"
			>
				Cancel
			</button>
		</div>
	</form>
</template>

<script setup>
import { computed, ref } from "vue";

const RESERVED_NAME = "Main Frappe Site";

const props = defineProps({
	existingNames: { type: Array, default: () => [] },
	initial: { type: Object, default: null },
	saving: { type: Boolean, default: false },
});

const emit = defineEmits(["save", "cancel"]);

const isEditing = computed(() => Boolean(props.initial));

const name = ref(props.initial?.server_name ?? "");
const endpointUrl = ref(props.initial?.endpoint_url ?? "");
const authType = ref(props.initial?.auth_type ?? "None");
const apiKey = ref("");
const apiKeyHeader = ref(props.initial?.api_key_header ?? "");
const error = ref("");

function validate(serverName, url) {
	if (!serverName) {
		return "Give this connection a name.";
	}
	// Exact, case-sensitive match — AR grants managed status only when
	// server_name is precisely this string, so a near-miss here is not a
	// security concern and must not be flagged as one.
	if (serverName === RESERVED_NAME) {
		return `"${RESERVED_NAME}" is reserved for your managed Frappe site connection. Choose a different name.`;
	}
	if (props.existingNames.includes(serverName)) {
		return `You already have a connection named "${serverName}".`;
	}

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

function submit() {
	// Validate the exact strings this call is about to emit — not the raw,
	// untrimmed ref values — so the reserved-name and duplicate checks can
	// never be bypassed by a value that differs only in whitespace from
	// what actually gets sent.
	const serverName = name.value.trim();
	const endpoint = endpointUrl.value.trim();

	const message = validate(serverName, endpoint);
	if (message) {
		error.value = message;
		return;
	}

	error.value = "";
	const payload = {
		server_name: serverName,
		endpoint_url: endpoint,
		auth_type: authType.value,
	};
	if (authType.value === "APIKey") {
		payload.api_key = apiKey.value;
		payload.api_key_header = apiKeyHeader.value.trim() || "Authorization";
	}

	emit("save", payload);
}
</script>

<style scoped>
.connection-form {
	display: flex;
	flex-direction: column;
	gap: 0.875rem;
	padding: 1rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	background: var(--ql-surface);
}

.connection-form__field {
	display: flex;
	flex-direction: column;
	gap: 0.3125rem;
}

.connection-form__label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
}

.connection-form__input {
	padding: 0.5rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-bg);
	color: var(--ql-text);
	font: inherit;
	font-size: 0.8125rem;
}

.connection-form__hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.connection-form__error {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-danger);
}

.connection-form__actions {
	display: flex;
	gap: 0.5rem;
	margin-top: 0.25rem;
}

.connection-form__save {
	padding: 0.4375rem 0.875rem;
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-accent);
	color: var(--ql-bg);
	font: inherit;
	font-size: 0.8125rem;
	cursor: pointer;
}

.connection-form__save:disabled {
	opacity: 0.5;
	cursor: default;
}

.connection-form__cancel {
	padding: 0.4375rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: none;
	color: var(--ql-text-secondary);
	font: inherit;
	font-size: 0.8125rem;
	cursor: pointer;
}

.connection-form__cancel:disabled {
	opacity: 0.5;
	cursor: default;
}
</style>
