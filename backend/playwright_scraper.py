import asyncio
import os
import random
from playwright.async_api import async_playwright
from backend import utils

class PlaywrightJobScraper:
    async def scrape(self, base_url: str, search: str, location: str, date_range: int):
        is_headless = utils.getenv_bool("HEADLESS")
        base_url = utils.ensure_url_has_scheme(base_url)
        pages = int(os.getenv("PAGES", 1))      
        jobs = []
        
        async with async_playwright() as p:
            print(f"Launching Playwright browser...")    

            # headless is set to False, but headless is forced backend through args
            # this fingerprint bypasses Cloudflare
            browser = await p.chromium.launch(headless=is_headless, args=[
                "--headless=new",
                "--disable-gpu",
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled"
            ])
            context = await browser.new_context(
                viewport={"width":1920, "height":1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                            (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            target_url = utils.build_url(base_url, search, location, date_range)  
            for i in range(pages):
                try:
                    print(f"Scraping page {i + 1}/{pages}...")    
                    print(f"URL: {target_url}")
                    await page.goto(target_url, wait_until="domcontentloaded")
                    try:
                        await page.wait_for_selector("div.job_seen_beacon", timeout=10000)
                    except:
                        print(f"No job cards found on page {i+1}")
                        break
                                        
                    cards = await page.query_selector_all("div.job_seen_beacon")
                    print("Cards found:", len(cards))

                    for card in cards:
                        title_el = await card.query_selector("h2.jobTitle span")
                        company_el = await card.query_selector("[data-testid='company-name']")
                        location_el = await card.query_selector("[data-testid='text-location']")
                        salary_el = await card.query_selector("li[data-testid='attribute_snippet_testid salary-snippet-container']")
                        link_el = await card.query_selector("h2.jobTitle a")

                        title = await title_el.evaluate("(el) => el.innerText") if title_el else None
                        company = await company_el.evaluate("(el) => el.innerText") if company_el else None
                        job_location = await location_el.evaluate("(el) => el.innerText") if location_el else None
                        salary = await salary_el.evaluate("(el) => el.innerText") if salary_el else None
                        job_url = await link_el.evaluate("(el) => el.href") if link_el else None

                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": job_location,
                            "salary": salary,
                            "url": job_url
                        })
                    
                    next_page = i + 2
                    has_next = await page.query_selector(f"[aria-label='{next_page}']")
                    
                    has_next = None # NOT SCRAPING MULTIPLE PAGES FOR NOW
                    
                    if i < pages - 1 and has_next:
                        start = (i + 1) * 10
                        print(f"Going to next page. Start: {start}")
                        current_url = page.url
                        target_url = utils.update_start_param(current_url, start)
                        await asyncio.sleep(random.uniform(2, 4))
                    else:
                        break

                except Exception as e:
                    print(e)
                    break
        
            print("Total jobs:", len(jobs))
            await browser.close()
        return jobs