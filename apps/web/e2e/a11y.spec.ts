import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { USERS, gotoAs, login } from "./helpers";

// Accessibilité automatisée (axe-core, WCAG 2.0/2.1 A & AA) sur les écrans clés
// d'Agent Control. Gate : aucune violation `critical`. Les violations `serious`
// sont journalisées (attachées au rapport) sans bloquer, pour suivi.
const PAGES: Array<{ label: string; path: string }> = [
  { label: "dashboard", path: "/agent-control" },
  { label: "agents", path: "/agent-control/agents" },
  { label: "projects", path: "/agent-control/projects" },
  { label: "costs", path: "/agent-control/costs" },
];

for (const { label, path } of PAGES) {
  test(`a11y sans violation critique — ${label}`, async ({ page, request }, testInfo) => {
    const token = await login(request, USERS.adminA.email, USERS.adminA.password);
    await gotoAs(page, token, path);
    // Attend que le contenu principal soit rendu (données API chargées).
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const bySeverity = (impact: string) =>
      results.violations.filter((v) => v.impact === impact);
    const critical = bySeverity("critical");
    const serious = bySeverity("serious");

    await testInfo.attach(`axe-${label}.json`, {
      body: JSON.stringify(
        { critical, serious: serious.map((v) => ({ id: v.id, nodes: v.nodes.length })) },
        null,
        2,
      ),
      contentType: "application/json",
    });

    expect(
      critical,
      `violations critiques a11y sur ${label}: ${critical.map((v) => v.id).join(", ")}`,
    ).toEqual([]);
  });
}
