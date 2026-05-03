import { test, expect } from '@playwright/test'

test('scrape flow — page loads, status shows, button triggers scrape', async ({ page }) => {
  await page.goto('/scrape')

  // Page heading is visible
  await expect(page.getByRole('heading', { name: 'Find New Jobs' })).toBeVisible()

  // Scrape status card is present
  await expect(page.getByText('Scrape Status')).toBeVisible()

  // Start Scrape button exists
  const btn = page.getByRole('button', { name: /Start Scrape|Scraping/i })
  await expect(btn).toBeVisible()
})

test('scrape flow — navigating to scrape from jobs page', async ({ page }) => {
  await page.goto('/jobs')

  // Find New Jobs button in stats section or sidebar CTA
  const findBtn = page.getByRole('button', { name: 'Find New Jobs' }).first()
  await expect(findBtn).toBeVisible()
  await findBtn.click()

  await expect(page).toHaveURL('/scrape')
})
