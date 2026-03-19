import asyncio
import time
from playwright.async_api import async_playwright


async def main() -> None:
    username = f"autouser_{int(time.time())}"
    password = "P@ssw0rd123!"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://practice.expandtesting.com/register", wait_until="domcontentloaded")

        await page.fill("#username", username)
        await page.fill("#password", password)
        await page.fill("#confirmPassword", password)
        await page.get_by_role("button", name="Register").click()

        await page.wait_for_timeout(1500)
        print("URL:", page.url)

        body_text = await page.locator("body").inner_text()
        print("BODY_SNIPPET:", body_text[:400])

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
