import json
import re
import time

from playwright.sync_api import sync_playwright

QUERY = "businesses on проспект Президента Грушевсько"

def safe_text(page, selector, nth=0):
    locator = page.locator(selector)
    return locator.nth(nth).inner_text().strip() if locator.count() > nth else None

def format_phone(phone_text):
    if not phone_text:
        return None
    digits = re.sub(r"[^\d+]", "", phone_text)
    if digits.startswith("0"):
        digits = "+38" + digits
    return digits

def parse_reviews_count(text):
    if not text:
        return None
    match = re.search(r"(\d+)", text.replace(",", ""))
    return int(match.group(1)) if match else None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.google.com/maps", timeout=60000)
    page.wait_for_selector("#searchboxinput", timeout=15000)

    page.fill("#searchboxinput", QUERY)
    page.keyboard.press("Enter")
    time.sleep(2)

    visited_links = set()
    results = []

    while True:
        cards = page.locator('div.Nv2PK')
        total_cards = cards.count()
        something_clicked = False

        for i in range(total_cards):
            card = cards.nth(i)
            maps_link_preview = card.get_attribute("href") or ""
            if maps_link_preview in visited_links:
                continue

            try:
                card.scroll_into_view_if_needed()
                card.click()
                page.wait_for_selector("h1.DUwDvf.lfPIob", timeout=10000)
                time.sleep(1)
            except Exception:
                continue

            name = safe_text(page, "h1.DUwDvf.lfPIob")
            rating = safe_text(page, "span.MW4etd")
            reviews_text = safe_text(page, 'button[jsaction*="reviews"]')
            reviews = parse_reviews_count(reviews_text)
            phone = format_phone(safe_text(page, 'button[data-item-id^="phone"]'))
            website = page.locator('a[data-item-id="authority"]').get_attribute("href") \
                if page.locator('a[data-item-id="authority"]').count() else None
            maps_link = page.url

            if maps_link not in visited_links:
                visited_links.add(maps_link)
                results.append({
                    "position": len(visited_links),
                    "name": name,
                    # "maps_link": maps_link,
                    "rating": rating,
                    "reviews": reviews,
                    "phone": phone,
                    "website": website,
                    "Сюди бажано зайти": True if (reviews and reviews < 5) else False or len(visited_links) > 20
                })
                print(results[-1])
                something_clicked = True

        if not something_clicked:
            # Скролимо, якщо нових карток не клікнули
            page.evaluate("""
                const feed = document.querySelector('div[role="feed"]');
                if(feed) feed.scrollTop = feed.scrollHeight;
            """)
            time.sleep(2)
            if cards.count() == len(visited_links):
                break

    browser.close()

    # Зберігаємо результати в JSON
    with open("google_maps_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"\nЗбережено {len(results)} записів у google_maps_results.json")
