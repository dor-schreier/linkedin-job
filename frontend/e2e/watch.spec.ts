import { test, expect } from '@playwright/test'

test('watch flow — rules page loads', async ({ page }) => {
  await page.goto('/watch-rules')
  await expect(page.getByRole('heading', { name: 'Watch Rules' })).toBeVisible()
  await expect(page.getByText('Add Watch Rule')).toBeVisible()
})

test('watch flow — add a keyword watch rule', async ({ page }) => {
  await page.goto('/watch-rules')

  // Fill the value field
  const valueInput = page.getByLabel('Value')
  await valueInput.fill('playwright-test-rule')

  // Submit
  await page.getByRole('button', { name: 'Add' }).click()

  // Rule appears in the list
  await expect(page.getByText('playwright-test-rule')).toBeVisible()
})

test('watch flow — matches page loads and shows header', async ({ page }) => {
  await page.goto('/watch-matches')
  await expect(page.getByRole('heading', { name: 'Watch Matches' })).toBeVisible()
})
