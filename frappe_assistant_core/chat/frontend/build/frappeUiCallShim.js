/**
 * The only frappe-ui export the shared stores use (chatStore's resume path).
 * The widget build aliases "frappe-ui" here so frappe-ui and reka-ui never
 * enter the Desk bundle. Importing any other name from "frappe-ui" in widget
 * code fails the build with a missing-export error — intended.
 */
import { baseCall } from "../src/api/_core.js";

export const call = (method, args = {}) => baseCall(method, args);
