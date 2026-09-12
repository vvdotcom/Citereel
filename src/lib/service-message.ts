/** Current UI wording for known service messages from older workers.
 * Do not rewrite customer content, source URLs, resource IDs or saved receipts.
 */
export function serviceMessage(message: string): string {
  return message
    .replaceAll("Use the Launchpad web application.", "Use the Citereel web application.")
    .replaceAll("Launchpad cannot record this page automatically", "Citereel cannot record this page automatically");
}
