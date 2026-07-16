import { expect, test } from "@playwright/test";

import { USERS, gotoAs, login } from "./helpers";

// Isolation multi-tenant (ADR-0003) : un utilisateur ne voit JAMAIS, dans l'UI,
// la moindre donnée d'un autre tenant. Deux installations distinctes, données
// reconnaissables par mot-clé (Alpha = tenant local, Beta = tenant e2e-tenant-b).
test.describe("isolation multi-tenant (aucune fuite UI)", () => {
  test("admin A voit ses agents (Alpha) et jamais ceux de B (Beta)", async ({ page, request }) => {
    const token = await login(request, USERS.adminA.email, USERS.adminA.password);
    await gotoAs(page, token, "/agent-control/agents");
    await expect(page.getByText("Alpha Agent E2E")).toBeVisible();
    await expect(page.getByText("Beta Agent E2E")).toHaveCount(0);
  });

  test("admin B voit ses agents (Beta) et jamais ceux de A (Alpha)", async ({ page, request }) => {
    const token = await login(request, USERS.adminB.email, USERS.adminB.password);
    await gotoAs(page, token, "/agent-control/agents");
    await expect(page.getByText("Beta Agent E2E")).toBeVisible();
    await expect(page.getByText("Alpha Agent E2E")).toHaveCount(0);
  });

  test("les projets sont isolés par tenant", async ({ page, request }) => {
    const tokenA = await login(request, USERS.adminA.email, USERS.adminA.password);
    await gotoAs(page, tokenA, "/agent-control/projects");
    await expect(page.getByText("Projet Alpha E2E")).toBeVisible();
    await expect(page.getByText("Projet Beta E2E")).toHaveCount(0);
  });

  test("admin B ne voit pas les projets de A", async ({ page, request }) => {
    const tokenB = await login(request, USERS.adminB.email, USERS.adminB.password);
    await gotoAs(page, tokenB, "/agent-control/projects");
    await expect(page.getByText("Projet Beta E2E")).toBeVisible();
    await expect(page.getByText("Projet Alpha E2E")).toHaveCount(0);
  });
});
