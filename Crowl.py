from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import re
import time
import os

# تنظیمات اولیه درایور
# استفاده از مسیر نسبی برای chromedriver.exe
script_dir = os.path.dirname(__file__)
chromedriver_path = os.path.join(script_dir, 'chromedriver-win64', 'chromedriver.exe')
service = Service(chromedriver_path)
options = webdriver.ChromeOptions()
# برای بررسی بهتر خطاها headless رو موقتا غیرفعال کن
#options.add_argument("--headless=new")
driver = webdriver.Chrome(service=service, options=options)

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
    article_data = {
        "country_name": "",
        "brief_info": {},
        "full_content": "",
        "keywords": []
    }
    try:
        driver.get(article_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "blog__main"))
        )
        time.sleep(2) # Give time for content to load

        # Extract country name from title
        try:
            title_element = driver.find_element(By.CLASS_NAME, "blog__title")
            full_title = title_element.text.strip()
            # Assuming country name is the last word in the title, or part of it
            country_match = re.search(r'راهنمای سفر به (.+)', full_title)
            if country_match:
                article_data["country_name"] = country_match.group(1).strip()
            else:
                # Fallback to breadcrumb if title doesn't match pattern
                breadcrumb_elements = driver.find_elements(By.CSS_SELECTOR, ".breadcrumb li a")
                if len(breadcrumb_elements) > 1:
                    article_data["country_name"] = breadcrumb_elements[-1].text.strip()
                else:
                    article_data["country_name"] = full_title.split()[-1] # Last word as a fallback
        except Exception as e:
            print(f"⚠️ خطا در استخراج نام کشور از {article_url}: {e}")
            article_data["country_name"] = "نامشخص"

        # Extract brief information table
        try:
            brief_info_header = driver.find_element(By.XPATH, "//h2[contains(., 'اطلاعات اجمالی')]")
            table = brief_info_header.find_element(By.XPATH, "./following-sibling::table[1]")
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) == 2:
                    key = cols[0].text.strip()
                    value = cols[1].text.strip()
                    article_data["brief_info"][key] = value
        except Exception as e:
            print(f"⚠️ خطا در استخراج اطلاعات اجمالی از {article_url}: {e}")

        # Extract full content
        try:
            full_content_element = driver.find_element(By.CLASS_NAME, "blog__detail")
            article_data["full_content"] = full_content_element.text.strip()
        except Exception as e:
            print(f"⚠️ خطا در استخراج محتوای کامل از {article_url}: {e}")

        # Add country name to keywords
        if article_data["country_name"] and article_data["country_name"] not in article_data["keywords"]:
            article_data["keywords"].append(article_data["country_name"])

    except Exception as e:
        print(f"❌ خطا در بارگذاری یا پردازش صفحه مقاله {article_url}: {e}")
    return article_data

def crawl_blog_articles():
    print("\n🚀 در حال پردازش: مقالات بلاگ")
    blog_url = "https://www.atitravel.ir/blog/"
    all_article_links = []
    articles = []

    # --- فاز ۱: بارگذاری تمام مقالات با کلیک روی "مشاهده مطالب بیشتر" ---
    try:
        driver.get(blog_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "js-topic-list")) # Wait for the container
        )
        time.sleep(2)
    except Exception as e:
        print(f"❌ خطا در بارگذاری صفحه بلاگ {blog_url}: {e}")
        return []

    while True:
        try:
            # Find the "Load More" button
            load_more_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'مشاهده مطالب بیشتر')]"))
            )
            print("🔍 دکمه 'مشاهده مطالب بیشتر' یافت شد. در حال کلیک...")
            # Scroll to the button and click it
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", load_more_button)
            # Wait for new content to load
            time.sleep(3) # Give it a few seconds for the new items to appear
        except Exception as e:
            print(f"ℹ️ دکمه 'مشاهده مطالب بیشتر' یافت نشد یا دیگر قابل کلیک نیست. پایان بارگذاری.")
            break

    # --- فاز ۲: جمع‌آوری تمام لینک‌های مقالات از صفحه ---
    print("\n✅ بارگذاری تمام شد. در حال جمع‌آوری لینک‌ها...")
    try:
        # Find all article links now that the page is fully loaded
        topic_list = driver.find_element(By.ID, "js-topic-list")
        article_items = topic_list.find_elements(By.CLASS_NAME, "latest-topic__item")
        for item in article_items:
            try:
                # The link is on the title
                link_element = item.find_element(By.CLASS_NAME, "latest-topic__item-title")
                link = link_element.get_attribute("href")
                if link and link not in all_article_links:
                    all_article_links.append(link)
            except Exception as e:
                print(f"❌ خطا در استخراج لینک از یک آیتم مقاله: {e}")
        
        print(f"   🔗 تعداد کل لینک‌های یافت شده: {len(all_article_links)}")

    except Exception as e:
        print(f"⚠️ خطا در جمع‌آوری لینک‌ها پس از بارگذاری کامل: {e}")
        return []


    # --- فاز ۳: استخراج جزئیات از هر لینک جمع‌آوری شده ---
    print(f"\n✅ جمع‌آوری لینک‌ها تمام شد. تعداد کل لینک‌ها برای استخراج: {len(all_article_links)}")
    for i, link in enumerate(all_article_links):
        print(f"   ➡️ ({i+1}/{len(all_article_links)}) در حال استخراج جزئیات از: {link}")
        detailed_data = scrape_single_article_page(link)
        
        country_name = detailed_data.get("country_name", "نامشخص")
        
        # ساختاردهی خروجی بر اساس فرمت درخواستی
        question = f"راهنمای سفر به {country_name}"
        answer = f"<a href='{link}' target='_blank'>مشاهده مقاله {country_name}</a>"
        keywords = [country_name] if country_name != "نامشخص" else []

        articles.append({
            "question": question,
            "answer": answer,
            "keywords": keywords,
            "category": "مقالات",
            "link": link
        })
        print(f"   ✅ مقاله اضافه شد: عنوان='{question}'")

    return articles

def extract_currency_data():
    print("🔍 در حال استخراج قیمت ارزها از tgju.org...")
    
    url = "https://www.tgju.org/currency"
    currency_list = []
    
    try:
        driver.get(url)
        # منتظر بارگذاری جدول ارزها بمان
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.data-table.market-table tbody tr"))
        )
        time.sleep(2)
        
        # پیدا کردن تمام ردیف‌های جدول ارزها
        currency_rows = driver.find_elements(By.CSS_SELECTOR, "table.data-table.market-table tbody tr")
        target_currencies = ["دلار", "یورو", "پوند انگلیس"]
        
        for row in currency_rows:
            try:
                # استخراج نام ارز
                currency_name = row.find_element(By.TAG_NAME, "th").text.strip()
                
                # فقط ارزهای مورد نظر را پردازش کن
                if currency_name in target_currencies  :
                    # استخراج قیمت فعلی
                    current_price = row.find_element(By.CSS_SELECTOR, "td.nf").text.strip()
                    
                    currency_list.append({
                        "name": currency_name,
                        "current_price": current_price
                    })
                    print(f"✅ {currency_name}: {current_price}")
                    
            except Exception as e:
                print(f"❌ خطا در پردازش ردیف ارز: {e}")
                continue
                
    except Exception as e:
        print(f"❌ خطا در بارگذاری صفحه ارز: {e}")
        return []
     # تبدیل فرمت داده‌ها
    converted_rates = convert_currency_format(currency_list)
    
    return converted_rates

def convert_currency_format(currency_list):
    """
    لیستی از دیکشنری‌های ارز را به فرمت مورد نظر تبدیل می‌کند
    
    ورودی: [{"name": "دلار", "current_price": "1,027,000"}, ...]
    خروجی: {"USD": 1027000, "EUR": 1203400, "GBP": 1386600}
    """
    currency_mapping = {
        "دلار": "USD",
        "یورو": "EUR", 
        "پوند انگلیس": "GBP",
        "پوند": "GBP"
    }
    
    result = {}
    
    for currency in currency_list:
        try:
            persian_name = currency.get("name", "")
            price_str = currency.get("current_price", "0")
            
            # تبدیل نام فارسی به انگلیسی
            english_code = currency_mapping.get(persian_name)
            if english_code:
                # پاکسازی و تبدیل قیمت به عدد
                cleaned_price = price_str.replace(',', '').replace('٬', '').strip()
                price_number = int(cleaned_price)
                
                result[english_code] = price_number
                print(f"✅ {persian_name} ({english_code}): {price_number}")
            else:
                print(f"⚠️ نام ارز '{persian_name}' در mapping وجود ندارد")
                
        except Exception as e:
            print(f"❌ خطا در تبدیل ارز {currency}: {e}")
    
    # اطمینان از وجود همه ارزهای مورد نیاز
    for currency_code in ["USD", "EUR", "GBP"]:
        if currency_code not in result:
            print(f"⚠️ ارز {currency_code} پیدا نشد، مقدار 0 تنظیم می‌شود")
            result[currency_code] = 0
    return result
    
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
        
    try:
        faqs['currency_rates'] = extract_currency_data()
    except  Exception as e:   
        print("⚠️ هیچ داده ارزی استخراج نشد.") 

    # ذخیره در فایل
    with open('ati-currency.json', 'w', encoding='utf-8') as f:
        json.dump({"faqs": faqs, "metadata": {"last_updated": time.strftime("%Y-%m-%d")}}, f, ensure_ascii=False, indent=4)

    driver.quit()
    print("✅ پردازش کامل شد و داده‌ها ذخیره شدند.")

# اجرا
if __name__ == "__main__":
    crawl_tours()



