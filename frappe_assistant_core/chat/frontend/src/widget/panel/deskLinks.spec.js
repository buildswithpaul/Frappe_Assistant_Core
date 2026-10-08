import { describe, it, expect } from "vitest";
import { deskRouteFor } from "./deskLinks.js";

describe("deskRouteFor", () => {
	it("maps /app and /desk paths to route segments", () => {
		expect(deskRouteFor("/app/sales-invoice/INV-1")).toEqual(["sales-invoice", "INV-1"]);
		expect(deskRouteFor("/desk/sales-invoice/INV%2F1")).toEqual(["sales-invoice", "INV/1"]);
	});

	it("accepts an absolute same-origin URL", () => {
		expect(deskRouteFor(`${window.location.origin}/desk/todo`)).toEqual(["todo"]);
	});

	it("leaves other origins, other paths and bare prefixes to the browser", () => {
		expect(deskRouteFor("https://evil.example/app/todo")).toBeNull();
		expect(deskRouteFor("/copilot/chat")).toBeNull();
		expect(deskRouteFor("/app/")).toBeNull();
		expect(deskRouteFor("/application/x")).toBeNull();
		expect(deskRouteFor("")).toBeNull();
	});

	it("leaves a link with a query string to a normal navigation so no filter is lost", () => {
		expect(deskRouteFor("/app/todo?status=Open")).toBeNull();
	});
});
