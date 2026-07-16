import { expect, test } from "@playwright/test";

import { USERS, gotoAs, login } from "./helpers";

// Multi-profil (capacités) : l'UI masque les actions non accordées et les vues
// protégées répondent fail-closed. L'API vérifie toujours ; l'UI ne fait que
// refléter les capacités du contexte.
test.describe("multi-profil (capacités)", () => {
  test("admin voit les actions de gestion (créer projet)", async ({ page, request }) => {
    const token = await login(request, USERS.adminA.email, USERS.adminA.password);
    await gotoAs(page, token, "/agent-control/projects");
    await expect(page.getByText("Projet Alpha E2E")).toBeVisible();
    await expect(page.getByRole("button", { name: /Nouveau projet/i })).toBeVisible();
  });

  test("viewer ne voit aucune action de gestion (pas de créer projet)", async ({
    page,
    request,
  }) => {
    const token = await login(request, USERS.viewer.email, USERS.viewer.password);
    await gotoAs(page, token, "/agent-control/projects");
    // Le viewer voit la liste (lecture) mais pas le bouton de création.
    await expect(page.getByRole("button", { name: /Nouveau projet/i })).toHaveCount(0);
  });

  test("viewer se voit refuser l'écran Coûts (view_costs absent)", async ({ page, request }) => {
    const token = await login(request, USERS.viewer.email, USERS.viewer.password);
    await gotoAs(page, token, "/agent-control/costs");
    // AcGuard cap="view_costs" → message de refus fail-closed.
    await expect(page.getByText(/Accès refusé/i)).toBeVisible();
  });

  test("admin accède à l'écran Coûts et à l'export CSV", async ({ page, request }) => {
    const token = await login(request, USERS.adminA.email, USERS.adminA.password);
    await gotoAs(page, token, "/agent-control/costs");
    await expect(page.getByRole("button", { name: /Exporter \(CSV\)/i })).toBeVisible();
  });
});
