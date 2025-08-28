from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import re
import time
import os

# تنظیمات اولیه درایور
# تنظیمات Chrome
chrome_options = Options()
chrome_options.add_argument("--headless")  # برای اجرای بدون界面
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# استفاده از ChromeDriver Manager برای دانلود خودکار chromedriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

def extract_keywords(text):
    stop_words = {"تور", "هتل", "پرواز", "جزئیات", "مشاهده", "رزرو", "سفر", "به", "از"}
    words = re.findall(r'\b[\w\-]+\b', text.lower())
    return [word for word in words if word not in stop_words and len(word) > 2][:5]

def extract_price(card):
    try:
        price_container = card.find_element(By.CLASS_NAME, "result__item-price")
        price_num = price_container.find_element(By.CLASS_NAME, "fa-num").text.strip()
        price_unit = price_container.find_element(By.CSS_SELECTOR, ".result__item-price-items label").text.strip()
        return f"{price_num} {price_unit}"
    except Exception as e:
        print(f"Error extracting price: {e}")
        return "قیمت موجود نیست"

def scrape_items_from_current_page(category):
    items = []
    cards = driver.find_elements(By.CLASS_NAME, "result__item")

    for i, card in enumerate(cards):
        try:
            title = card.find_element(By.CLASS_NAME, "result__item-header-title").text.strip()
            location = card.find_element(By.CLASS_NAME, "result__item-location").text.strip() if card.find_elements(By.CLASS_NAME, "result__item-location") else ""
            link = card.get_attribute("href") or ""

            # Extract flight, duration, and dates from result__item-header-detail
            flight = ""
            duration_text = ""
            header_details = card.find_elements(By.CLASS_NAME, "result__item-header-detail")
            if header_details:
                detail_list_items = header_details[0].find_elements(By.TAG_NAME, "li")
                for li in detail_list_items:
                    text_content = li.text.strip()
                    
                    # Check for flight info (contains airline logo or specific text)
                    if li.find_elements(By.TAG_NAME, "img"):
                        flight = text_content
                    # Check for duration (contains moon icon)
                    elif li.find_elements(By.CLASS_NAME, "icon-moon"):
                        duration_text = text_content
                    # Check for dates (contains date icon)
                    elif li.find_elements(By.CLASS_NAME, "icon-date"):
                        dates_text = text_content
                        duration_text += f" -\n{dates_text}"
            if not flight:
                flight = "مشخص نشده"
            if category == "تورهای داخلی":
                keywords_text = f"{title}"
            else:
                keywords_text = f"{title} {location}"
                
            price = extract_price(card)

            items.append({
                "question": title,
                "answer": f"<a href='{link}' target='_blank'>مشاهده جزئیات</a>",
                "keywords": extract_keywords(keywords_text),
                "category": category,
                "flight": flight,
                "location": location,
                "duration": duration_text,
                "price": price              
            })
        except Exception as e:
            print(f"❌ خطا در پردازش آیتم {i+1} در دسته {category}: {e}")
            # Optionally, print the card's outer HTML for debugging
            # print(f"HTML کارت مشکل‌دار: {card.get_attribute('outerHTML')}")
    return items

def scrape_all_pages(category, initial_url, item_class_name="result__item", pagination_xpath="//ul[contains(@class, 'paging')]//a[text()='{page_num}']"):
    all_items = []
    current_page_num = 1
    
    try:
        driver.get(initial_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, item_class_name))
        )
        time.sleep(2) # Give some time for dynamic content to load
    except Exception as e:
        print(f"❌ خطا در بارگذاری صفحه اولیه {category} در {initial_url} (انتظار برای کلاس: {item_class_name}): {e}")
        return []

    while True:
        print(f"🔍 استخراج از صفحه {current_page_num} برای {category}...")
        all_items.extend(scrape_items_from_current_page(category))

        try:
            # Find the next page button using the provided pagination_xpath
            next_page_xpath = pagination_xpath.format(page_num=current_page_num + 1)
            next_page_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, next_page_xpath))
            )
            
            # Scroll to the button and click it
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_page_link)
            time.sleep(1) # Wait for scroll to complete
            driver.execute_script("arguments[0].click();", next_page_link)
            
            # Wait for the new page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, item_class_name))
            )
            time.sleep(2) # Give some time for dynamic content to load
            current_page_num += 1
        except Exception as e:
            print(f"ℹ️ صفحه بعدی برای {category} (XPath: {pagination_xpath.format(page_num=current_page_num + 1)}) یافت نشد یا خطایی رخ داد: {e}")
            break # No more pages or an error occurred

    return all_items

def scrape_single_article_page(article_url):
    # This function is no longer needed as we are extracting directly from the listing page.
    # Keeping it as a placeholder or for potential future use if detailed scraping is re-enabled.
    pass

# def scrape_hotels(category, url):
#     driver.get(url)
#     WebDriverWait(driver, 10).until(
#         EC.presence_of_element_located((By.CLASS_NAME, "js-best-package-select"))
#     )
#     time.sleep(1)

#     hotels = []

#     # لیست گزینه‌های داخل select (مثلاً استانبول، دبی)
#     select_element = driver.find_element(By.CLASS_NAME, "js-best-package-select")
#     options = select_element.find_elements(By.TAG_NAME, "option")

#     for option in options:
#         value = option.get_attribute("value")  # مثلاً "tab-1"
#         city = option.text.strip()             # مثلاً "استانبول"

#         # انتخاب گزینه
#         driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'))", select_element, value)
#         time.sleep(1)

#         # پیدا کردن آیتم‌های فعال این تب
#         tab_div = driver.find_element(By.ID, value)
#         hotel_cards = tab_div.find_elements(By.CLASS_NAME, "best-package__item")

#         for card in hotel_cards:
#             try:
#                 name = card.find_element(By.CLASS_NAME, "best-package__item-title").text.strip()
#                 score = card.find_element(By.CLASS_NAME, "best-package__item-rate").text.strip()
#                 img = card.find_element(By.CSS_SELECTOR, "picture source").get_attribute("data-srcset")
#                 alt = card.find_element(By.CSS_SELECTOR, "picture img").get_attribute("alt")

#                 hotels.append({
#                     "question": f"هتل {name} در {city}",
#                     "answer": f"<img src='{img}' alt='{alt}' width='150'><br>امتیاز: {score}",
#                     "keywords": extract_keywords(f"{name} {city} {score}"),
#                     "category": category,
#                     "location": city,
#                     "score": f"امتیاز {score}"
#                 })

#             except Exception as e:
#                 print("❌ خطا در استخراج هتل:", e)

#     return hotels

def crawl_blog_articles():
    print("\n🚀 در حال پردازش: مقالات بلاگ")
    blog_url = "https://www.atitravel.ir/blog/"
    articles = []

    try:
        driver.get(blog_url)
        # Wait for the main blog list container to be present
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "main.blog-list__main"))
        )
        time.sleep(2)
    except Exception as e:
        print(f"❌ خطا در بارگذاری صفحه بلاگ {blog_url} (انتظار برای CSS_SELECTOR: main.blog-list__main): {e}")
        return []

    current_page_num = 1
    while True:
        print(f"🔍 استخراج از صفحه {current_page_num} مقالات بلاگ...")
        
        # Find the main blog list section
        try:
            blog_main_section = driver.find_element(By.CSS_SELECTOR, "main.blog-list__main")
            # Use 'latest-topic__item' for the main list of articles within this section
            article_cards = blog_main_section.find_elements(By.CLASS_NAME, "latest-topic__item")
            for card in article_cards:
                try:
                    # Extract link and title directly from the card
                    link_element = card.find_element(By.CSS_SELECTOR, "a.latest-topic__item-title")
                    link = link_element.get_attribute("href")
                    full_title = link_element.text.strip()
                    
                    country_name = "نامشخص"
                    country_match = re.search(r'راهنمای سفر به (.+)', full_title)
                    if country_match:
                        country_name = country_match.group(1).strip()
                    else:
                        # Fallback if title doesn't match pattern
                        # Try to get from alt attribute of image or other text
                        try:
                            img_alt = card.find_element(By.TAG_NAME, "img").get_attribute("alt")
                            alt_match = re.search(r'راهنمای سفر به (.+)', img_alt)
                            if alt_match:
                                country_name = alt_match.group(1).strip()
                            else:
                                country_name = full_title.split()[-1] # Last word as a fallback
                        except:
                            country_name = full_title.split()[-1] # Last word as a fallback

                    if link and link not in [art['link'] for art in articles]: # Avoid re-processing already added articles
                        articles.append({
                            "question": f"راهنمای سفر به {country_name}",
                            "answer": f"<a href='{link}' target='_blank'>مشاهده مقاله {country_name}</a>",
                            "keywords": [country_name] if country_name != "نامشخص" else [],
                            "category": "مقالات",
                            "link": link
                        })
                        print(f"   ✅ مقاله اضافه شد: عنوان='{country_name}', لینک='{link}'")
                except Exception as e:
                    print(f"❌ خطا در استخراج لینک یا عنوان از آیتم 'latest-topic__item' در صفحه {current_page_num}: {e}")
        except Exception as e:
            print(f"⚠️ خطا در یافتن بخش اصلی بلاگ (main.blog-list__main) در صفحه {current_page_num}: {e}")

        # Also check for 'topic-card' elements in the "پیشنهاد می‌کنیم" section (if it exists outside the main list)
        featured_article_cards = driver.find_elements(By.CLASS_NAME, "topic-card")
        for card in featured_article_cards:
            try:
                link_element = card.find_element(By.TAG_NAME, "a")
                link = link_element.get_attribute("href")
                full_title = link_element.get_attribute("title") or link_element.text.strip()

                country_name = "نامشخص"
                country_match = re.search(r'راهنمای سفر به (.+)', full_title)
                if country_match:
                    country_name = country_match.group(1).strip()
                else:
                    country_name = full_title.split()[-1] # Last word as a fallback

                if link and link not in [art['link'] for art in articles]:
                    articles.append({
                        "question": f"راهنمای سفر به {country_name}",
                        "answer": f"<a href='{link}' target='_blank'>مشاهده مقاله {country_name}</a>",
                        "keywords": [country_name] if country_name != "نامشخص" else [],
                        "category": "مقالات",
                        "link": link
                    })
                    print(f"   ✅ مقاله اضافه شد: عنوان='{country_name}', لینک='{link}' (از topic-card)")
            except Exception as e:
                print(f"❌ خطا در استخراج لینک یا عنوان از آیتم 'topic-card' در صفحه {current_page_num}: {e}")

        if not articles: # Check if any articles were found on this page
            print(f"⚠️ هیچ لینک مقاله‌ای در صفحه {current_page_num} یافت نشد. پایان پیمایش بلاگ.")
            break
        
        # Return to the blog listing page to find the next pagination link
        driver.get(blog_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "main.blog-list__main"))
        )
        time.sleep(2)

        try:
            # The pagination class is 'pagination' for blog
            next_page_xpath = f"//ul[contains(@class, 'pagination')]//a[text()='{current_page_num + 1}']"
            next_page_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, next_page_xpath))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_page_link)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", next_page_link)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main.blog-list__main"))
            )
            time.sleep(2)
            current_page_num += 1
        except Exception as e:
            print(f"ℹ️ صفحه بعدی برای مقالات بلاگ (XPath: {next_page_xpath}) یافت نشد یا خطایی رخ داد: {e}")
            break
    return articles

def crawl_tours():
    base_url = "https://www.atitravel.ir"
    endpoints = {
        "تورهای خارجی": "/tours/external/",
        "تورهای داخلی": "/tours/internal/",
        # "هتل‌های خارجی": "/externalhotel/",
        # "هتل‌های داخلی": "/internalhotel/",
    }

    faqs = {}

    for category, endpoint in endpoints.items():
        url = base_url + endpoint
        # Use specific pagination XPATH for hotels if different, otherwise default 'paging'
        # Assuming hotels also use 'paging' for now, but can be adjusted if needed.
        try:    
            if "هتل" in category:
                pass
                # faqs[category] = scrape_hotels(category, url)
            else :
                faqs[category] = scrape_all_pages(category, url, "result__item")
        except Exception as e:
            print(f"❌ خطا در پردازش {category}: {e}")
            faqs[category] = []
    try:        
        # اضافه کردن مقالات بلاگ
        faqs["مقالات"] = crawl_blog_articles()
    except Exception as e:
        print(f"❌ خطا در پردازش مقالات بلاگ: {e}")

    # ذخیره در فایل
    with open('ati.json', 'w', encoding='utf-8') as f:
        json.dump({"faqs": faqs, "metadata": {"last_updated": time.strftime("%Y-%m-%d")}}, f, ensure_ascii=False, indent=4)

    driver.quit()
    print("✅ پردازش کامل شد و داده‌ها ذخیره شدند.")

# اجرا
if __name__ == "__main__":
    crawl_tours()

