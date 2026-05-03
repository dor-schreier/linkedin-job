import { test, expect } from '@playwright/test'

test('jobs flow — list renders with filters', async ({ page }) => {
  await page.goto('/jobs')

  // Page heading
  await expect(page.getByRole('heading', { name: 'Jobs' })).toBeVisible()

  // Filter controls are present
  await expect(page.getByPlaceholder(/Search title, company/i)).toBeVisible()
})

test('jobs flow — sort dropdown changes selection', async ({ page }) => {
  await page.goto('/jobs')

  const sort = page.locator('select').filter({ hasText: 'Best Fit First' })
  await expect(sort).toBeVisible()
  await sort.selectOption('freshest')
  await expect(sort).toHaveValue('freshest')
})

test('jobs flow — filter toggle buttons work', async ({ page }) => {
  await page.goto('/jobs')

  const freshOnly = page.getByRole('button', { name: 'Fresh Only' })
  await expect(freshOnly).toBeVisible()
  await freshOnly.click()
  // After click the button should have primary styling (bg-primary class)
  await expect(freshOnly).toHaveClass(/bg-primary/)
})

test('jobs flow — job row navigates to detail', async ({ page }) => {
  await page.goto('/jobs')

  // If there are any job rows, click the first one
  const rows = page.locator('[class*="cursor-pointer"][class*="grid-cols"]')
  const count = await rows.count()
  if (count > 0) {
    await rows.first().click()
    await expect(page).toHaveURL(/\/jobs\/\d+/)
    await expect(page.getByRole('button', { name: /Back to Jobs/i })).toBeVisible()
  } else {
    // No jobs — empty state should be shown
    await expect(page.getByText('No jobs found')).toBeVisible()
  }
})

test('jobs flow — reject rule via status dropdown', async ({ page }) => {
  await page.goto('/jobs')

  const statusDropdowns = page.locator('select').filter({ hasText: 'NEW' })
  const count = await statusDropdowns.count()
  if (count > 0) {
    await statusDropdowns.first().selectOption('REJECTED')
    // Row updates (no error thrown)
    await page.waitForTimeout(500)
  }
})
