import { deskHost } from "./deskHost.js";

/** The page the widget runs on: Desk unless bootEmbedded() chose another host. */
let current = null;

export function setHost(host) {
	current = host;
}

export function getHost() {
	return current || deskHost;
}
