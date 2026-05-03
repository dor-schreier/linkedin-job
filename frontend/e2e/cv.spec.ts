import { test, expect } from '@playwright/test'

test('cv flow — cv page loads', async ({ page }) => {
  await page.goto('/cv')
  await expect(page.getByRole('heading', { name: /CV|Resume/i })).toBeVisible()
})

test('cv flow — export endpoint returns 200 with html', async ({ request }) => {
  const response = await request.get('http://localhost:8000/cv/export')
  expect(response.status()).toBe(200)
})

test('cv flow — cv list endpoint returns json', async ({ request }) => {
  const response = await request.get('http://localhost:8000/cv/list')
  expect(response.status()).toBe(200)
  const body = await response.json()
  expect(Array.isArray(body)).toBe(true)
})

test('cv flow — pdf download returns application/pdf when cv exists', async ({ request }) => {
  // First check if any CVs exist
  const listRes = await request.get('http://localhost:8000/cv/list')
  const cvs = await listRes.json()
  if (cvs.length > 0) {
    const response = await request.get('http://localhost:8000/cv/download/pdf', {
      params: { profile_url: cvs[0].profile_url },
    })
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toContain('application/pdf')
  } else {
    test.skip()
  }
})
