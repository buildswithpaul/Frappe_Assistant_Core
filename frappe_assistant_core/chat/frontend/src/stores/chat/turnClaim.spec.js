import { describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

import { createTurnClaim } from "./turnClaim";

// Open Full Assistant hands a running widget turn to the chat app (#34535): the claim says the
// chat app now answers that conversation's browser calls.
function setup(answer = { claimed: true }) {
	const currentSessionId = ref(null);
	const claim = vi.fn(async () => (answer instanceof Error ? Promise.reject(answer) : answer));
	return { currentSessionId, claim, turnClaim: createTurnClaim({ claim, currentSessionId }) };
}

describe("createTurnClaim", () => {
	it("holds the conversation once the server claims its running turn, and it opens", async () => {
		const { currentSessionId, claim, turnClaim } = setup();
		expect(await turnClaim.claimLiveTurn("s1")).toBe(true);
		expect(claim).toHaveBeenCalledWith("s1");
		// The hand-over lands on a fresh page: the claim resolves before the conversation opens.
		expect(turnClaim.isClaimedLiveTurn("s1")).toBe(false);
		currentSessionId.value = "s1";
		await nextTick();
		expect(turnClaim.isClaimedLiveTurn("s1")).toBe(true);
	});

	it("holds nothing when the server finds no running turn of the caller's", async () => {
		const { currentSessionId, turnClaim } = setup({ claimed: false });
		currentSessionId.value = "s1";
		expect(await turnClaim.claimLiveTurn("s1")).toBe(false);
		expect(turnClaim.isClaimedLiveTurn("s1")).toBe(false);
	});

	it("holds nothing when the claim fails", async () => {
		const { currentSessionId, turnClaim } = setup(new Error("offline"));
		currentSessionId.value = "s1";
		expect(await turnClaim.claimLiveTurn("s1")).toBe(false);
		expect(turnClaim.isClaimedLiveTurn("s1")).toBe(false);
	});

	it("lets go when this tab moves to another conversation", async () => {
		const { currentSessionId, turnClaim } = setup();
		currentSessionId.value = "s1";
		await turnClaim.claimLiveTurn("s1");
		currentSessionId.value = "s2";
		await nextTick();
		currentSessionId.value = "s1";
		await nextTick();
		expect(turnClaim.isClaimedLiveTurn("s1")).toBe(false);
	});

	it("lets go when this tab sends a turn of its own", async () => {
		const { currentSessionId, turnClaim } = setup();
		currentSessionId.value = "s1";
		await turnClaim.claimLiveTurn("s1");
		turnClaim.releaseClaim();
		expect(turnClaim.isClaimedLiveTurn("s1")).toBe(false);
	});
});
