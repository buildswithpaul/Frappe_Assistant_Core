import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { startHostedCheckout } from "@/composables/_billing/hostedCheckout";
import { seatChargeRequired } from "@/components/settings/users/memberHelpers";

/**
 * Add-user flow for UsersSettings.
 *
 * Owns three concerns:
 *   - Listing available users to add (search + load).
 *   - Deciding whether adding triggers a prorated seat charge (gateway-specific).
 *   - Driving the gateway widget / redirect, then finalizing the user record.
 *
 * Kept out of UsersSettings.vue because the gateway branching makes the
 * imperative flow long (~200 lines) and hard to scan alongside the rest of
 * the page's state.
 *
 * Returns refs for state + functions wired to the existing template handlers.
 * The caller provides the messaging refs (`actionError`, `successMessage`)
 * and the post-success refresh callbacks so this composable doesn't have to
 * know about the page's wider state.
 *
 * One flow drives BOTH add-user and invite, because the seat-check and
 * seat-purchase branching is identical — inviting a teammate over the
 * included seats triggers the SAME prorated charge an immediate add would.
 * The committed action is derived from the selected user object: a user
 * carrying a `userRole` is a pending invite (`inviteUser`), otherwise it's a
 * direct add (`addUser`). Deriving from the payload (not a per-instance
 * closure) keeps the Stripe redirect round-trip correct too — the persisted
 * `userRole` survives the bounce and the single return handler finalizes
 * with the right action. No duplicate billing math, no second flow instance.
 */
function isInvite(user) {
	return !!user?.userRole;
}

function commitUser(user) {
	return isInvite(user)
		? api.users.inviteUser(user.user_id, user.userRole)
		: api.users.addUser(user.user_id);
}

function successVerbFor(user) {
	return isInvite(user) ? "invited" : "added";
}

function failVerbFor(user) {
	return isInvite(user) ? "invite" : "add";
}

/**
 * True if `userId` already exists as an AR Tenant User (any status). Used
 * only by the post-payment finalize path: when a paid seat settles, AR's
 * payment handler creates the Pending member itself, so the browser's own
 * finalize call can lose a race against it and come back "already a
 * member". That collision is proof the seat is filled, not proof the
 * finalize failed. Checking real membership -- instead of matching AR's
 * error wording -- keeps this correct even if that message changes.
 *
 * The generous limit mirrors `getAvailableUsers`' page size for the same
 * existence check, so a freshly-created row (no `last_activity` yet, sorted
 * last) doesn't fall off the page on a large team.
 */
async function memberAlreadyExists(userId) {
	try {
		const result = await api.users.list(null, 500, 0);
		return (result?.users || []).some((u) => u.user_id === userId);
	} catch {
		return false;
	}
}

export function useAddUserFlow({
	userLimit,
	actionError,
	successMessage,
	clearMessageAfterDelay,
	refreshUsers,
	refreshLimit,
}) {
	const availableUsers = ref([]);
	const loadingAvailableUsers = ref(false);
	const addingUser = ref(false);
	const seatPurchaseConfirm = ref(null);

	// Pure loader: fetches the site-users picker and populates
	// availableUsers/loadingAvailableUsers. The modal that consumes this owns
	// its own open/close state (see InviteModal), so this stays a data concern.
	async function loadAvailableUsers() {
		loadingAvailableUsers.value = true;
		try {
			const result = await api.users.getAvailableUsers();
			availableUsers.value = result.users || [];
		} catch (e) {
			logger.error("Failed to load available users:", e);
			availableUsers.value = [];
		} finally {
			loadingAvailableUsers.value = false;
		}
	}

	async function selectUserToAdd(user) {
		const limit = userLimit.value;
		if (!limit) {
			await doAddUser(user);
			return;
		}

		// Hard cap reached -- block entirely
		if (!limit.is_unlimited && limit.remaining <= 0) {
			actionError.value = `User limit reached (${limit.max_users} users). Upgrade to a higher plan to add more.`;
			return;
		}

		// Check if adding this user would exceed included seats (needs seat
		// purchase). The decision is `seatChargeRequired` (shared with
		// InviteModal's notice so the two never disagree). `currentActive` is
		// kept locally because the preview payload below needs the seat count.
		const currentActive = limit.active_users || 0;

		if (seatChargeRequired(limit)) {
			try {
				const preview = await api.billing.previewSeatCharge();
				// An unsettled renewal quotes no pricing at all — a stalled
				// cycle leaves zero days remaining, so a modal here would
				// offer the seat for 0.00 and AR would then refuse to sell
				// it. Surface the reason instead of a figure nobody can act
				// on. Checked before `pricing`, which is absent in this case.
				if (preview?.pricing?.renewal_outstanding) {
					actionError.value =
						preview.pricing.blocked_reason ||
						"Your last renewal payment hasn't gone through yet.";
					clearMessageAfterDelay("error");
					return;
				}
				if (preview?.success && preview.pricing) {
					const p = preview.pricing;
					seatPurchaseConfirm.value = {
						...user,
						newSeatCount: (limit.paid_seats ?? currentActive) + 1,
						proratedRate: p.prorated_rate,
						tax: p.tax,
						total: p.total,
						daysRemaining: p.days_remaining,
						daysInCycle: p.days_in_cycle,
						currency: p.currency,
						perUserPrice: p.per_user_price,
						taxRatePercent: p.tax_rate_percent,
						components: p.components || [],
						// Credits are prorated by the same fraction as the
						// price, so the modal quotes both or the admin plans
						// the rest of the cycle around a full month they
						// didn't buy.
						creditsPerUser: p.credits_per_user,
						creditsGranted: p.credits_granted,
					};
				} else {
					actionError.value = preview?.error || "Failed to calculate seat charge";
					clearMessageAfterDelay("error");
				}
			} catch (e) {
				actionError.value = e.message || "Failed to calculate seat charge";
				clearMessageAfterDelay("error");
			}
			return;
		}

		await doAddUser(user);
	}

	async function confirmAddUser() {
		if (!seatPurchaseConfirm.value) return;
		addingUser.value = true;
		actionError.value = "";
		successMessage.value = "";
		try {
			// The seat charge is taken on FAC Cloud, not here — a gateway is
			// onboarded against one declared website and this app runs on a
			// different domain for every customer. Everything the old pre-flight
			// reported (no charge due, mandate cap exceeded) is decided there
			// when the page opens and shown on it.
			//
			// Leave the marker first: the user is registered on THIS site once
			// they come back, and the round-trip is the only thing between the
			// two halves. The same marker already carried the Stripe flow.
			localStorage.setItem(
				"faco_seat_pending",
				JSON.stringify({
					user_id: seatPurchaseConfirm.value.user_id,
					full_name: seatPurchaseConfirm.value.full_name || "",
					// Preserved so an invite (vs. add) finalizes with its role
					// after the round-trip. Undefined for adds.
					userRole: seatPurchaseConfirm.value.userRole,
				}),
			);

			const back = new URL(window.location.href);
			back.searchParams.set("seat_purchase", "1");
			await startHostedCheckout(
				"Seat",
				{
					// Who the seat is for, so AR can create the member itself
					// when the payment settles. `invited_by` is stamped from
					// the verified session on the FAC side (Task 2), never
					// sent from the browser.
					user_id: seatPurchaseConfirm.value.user_id,
					user_role: seatPurchaseConfirm.value.userRole,
				},
				back.toString(),
			);
			return;
		} catch (e) {
			actionError.value = e.message || "Failed to add user";
			clearMessageAfterDelay("error");
			seatPurchaseConfirm.value = null;
		} finally {
			addingUser.value = false;
		}
	}

	async function finalizeSeatAddition(user) {
		try {
			const result = await commitUser(user);
			if (result.success || (await memberAlreadyExists(user.user_id))) {
				successMessage.value = `${user.full_name || user.user_id} ${successVerbFor(user)} successfully`;
				clearMessageAfterDelay("success");
				await Promise.all([refreshUsers(), refreshLimit()]);
			} else {
				actionError.value =
					result.error || "Seat charged but failed to complete. Contact support.";
				clearMessageAfterDelay("error");
			}
		} catch (e) {
			actionError.value = e.message || `Failed to ${failVerbFor(user)} user`;
			clearMessageAfterDelay("error");
		} finally {
			seatPurchaseConfirm.value = null;
		}
	}

	async function doAddUser(user) {
		addingUser.value = true;
		actionError.value = "";
		successMessage.value = "";
		try {
			const result = await commitUser(user);
			if (result.success) {
				successMessage.value = `${user.full_name || user.user_id} ${successVerbFor(user)} successfully`;
				clearMessageAfterDelay("success");
				await Promise.all([refreshUsers(), refreshLimit()]);
			} else {
				actionError.value = result.error || `Failed to ${failVerbFor(user)} user`;
				clearMessageAfterDelay("error");
			}
		} catch (e) {
			actionError.value = e.message || `Failed to ${failVerbFor(user)} user`;
			clearMessageAfterDelay("error");
		} finally {
			addingUser.value = false;
		}
	}

	/**
	 * Stripe redirects back here after a seat-purchase Checkout Session.
	 * The webhook adds the seat itself; we just register the user once we
	 * see we returned from a successful checkout.
	 */
	async function handleStripeSeatReturn() {
		const params = new URLSearchParams(window.location.search);
		if (params.get("seat_purchase") !== "1") return;

		const pendingRaw = localStorage.getItem("faco_seat_pending");
		localStorage.removeItem("faco_seat_pending");
		// Strip the marker query params so a refresh doesn't re-trigger.
		params.delete("seat_purchase");
		params.delete("session_id");
		const cleanQuery = params.toString();
		window.history.replaceState(
			{},
			"",
			window.location.pathname + (cleanQuery ? `?${cleanQuery}` : ""),
		);

		if (!pendingRaw) return;

		let pending;
		try {
			pending = JSON.parse(pendingRaw);
		} catch {
			return;
		}
		if (!pending?.user_id) return;

		addingUser.value = true;
		try {
			await finalizeSeatAddition(pending);
		} finally {
			addingUser.value = false;
		}
	}

	/**
	 * Entry point for the Invites tab. Tags the selected user as an invite
	 * (carrying the chosen role) then runs it through the SAME seat-check +
	 * seat-purchase path an add uses. Over included seats → prorated charge
	 * preview → on confirm, `inviteUser` (not `addUser`) is committed.
	 * `user` is the available-user record `{ user_id, full_name }`.
	 */
	async function startInvite(user, userRole) {
		await selectUserToAdd({ ...user, userRole });
	}

	return {
		availableUsers,
		loadingAvailableUsers,
		addingUser,
		seatPurchaseConfirm,
		loadAvailableUsers,
		confirmAddUser,
		handleStripeSeatReturn,
		startInvite,
	};
}
