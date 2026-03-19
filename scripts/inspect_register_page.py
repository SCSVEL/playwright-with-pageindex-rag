import asyncio
from playwright.async_api import async_playwright


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://practice.expandtesting.com/register", wait_until="domcontentloaded")

        data = await page.evaluate(
            """() => {
                const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
                    id: i.id,
                    name: i.name,
                    type: i.type,
                    placeholder: i.placeholder,
                    ariaLabel: i.getAttribute('aria-label')
                }));
                const buttons = Array.from(document.querySelectorAll('button, input[type=submit]')).map(b => ({
                    tag: b.tagName.toLowerCase(),
                    id: b.id,
                    name: b.name,
                    text: (b.textContent || '').trim(),
                    value: b.value,
                    type: b.type
                }));
                return { inputs, buttons };
            }"""
        )

        print(data)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
