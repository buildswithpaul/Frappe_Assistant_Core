import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

import { assertHostedCheckoutUrl } from "./hostedCheckout";

const SRC = resolve(__dirname, "../..");

function sourceFiles(dir) {
	return readdirSync(dir).flatMap((entry) => {
		const path = join(dir, entry);
		if (statSync(path).isDirectory()) return sourceFiles(path);
		return /\.(js|ts|vue)$/.test(entry) && !/\.spec\.js$/.test(entry) ? [path] : [];
	});
}

describe("the gateway never loads on this site", () => {
	// A payment gateway is onboarded against one declared website. This app
	// is served from a different domain for every customer, so a gateway
	// script here is a payment page at an address we never declared — which
	// is exactly what the hosted checkout exists to stop. A single reinstated
	// import would undo it silently, so assert against the source itself.
	it("no source file pulls in the Razorpay checkout script", () => {
		const offenders = sourceFiles(SRC).filter((path) =>
			readFileSync(path, "utf8").includes("checkout.razorpay.com"),
		);
		expect(offenders).toEqual([]);
	});

	it("no source file constructs a gateway widget", () => {
		const offenders = sourceFiles(SRC).filter((path) =>
			/new\s+window\.Razorpay|new\s+Razorpay\b/.test(readFileSync(path, "utf8")),
		);
		expect(offenders).toEqual([]);
	});
});

describe("assertHostedCheckoutUrl", () => {
	it("accepts the https link our backend hands us", () => {
		expect(assertHostedCheckoutUrl("https://pay.example/checkout?token=a")).toBe(
			"https://pay.example/checkout?token=a",
		);
	});

	it("refuses plain http, which a network can rewrite", () => {
		expect(() => assertHostedCheckoutUrl("http://pay.example/checkout")).toThrow(/https/);
	});

	it("allows loopback over http so the flow is testable in development", () => {
		expect(assertHostedCheckoutUrl("http://localhost:8000/checkout?token=a")).toContain(
			"localhost:8000",
		);
	});

	it("refuses something that is not a URL at all", () => {
		expect(() => assertHostedCheckoutUrl("javascript:alert(1)")).toThrow();
	});
});
