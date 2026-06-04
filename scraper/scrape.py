# Scraper for Decathlon product catalog
# This script will scrape Decathlon.fr and generate product markdown files for Astro content collection.

import requests
from bs4 import BeautifulSoup
import cloudscraper
import time
import json
import os
from urllib.parse import urljoin, urlparse
import re

# Configuration
BASE_URL = "https://www.decathlon.fr"
CATEGORIES_URL = f"{BASE_URL}/c/hp/tous-les-sports"
OUTPUT_DIR = "src/content/products"
AFFILIATE_ID = os.environ.get("DECATHLON_AFFILIATE_ID", "YOUR_SID_HERE")  # To be set via GitHub Secrets

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

def init_scraper():
    """Initialize a cloudscraper session to bypass basic Cloudflare protection."""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'mobile': False
        }
    )
    scraper.headers.update(HEADERS)
    return scraper

def get_categories(scraper):
    """Fetch main sports categories from Decathlon homepage."""
    print(f"Fetching categories from {CATEGORIES_URL}")
    try:
        response = scraper.get(CATEGORIES_URL, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    categories = []

    # Look for category links - this selector may need adjustment based on Decathlon's current HTML
    category_links = soup.find_all('a', href=re.compile(r'/c/'))
    for link in category_links[:20]:  # Limit to avoid too many categories
        href = link.get('href')
        text = link.get_text(strip=True)
        if href and text and len(text) > 2:
            full_url = urljoin(BASE_URL, href)
            categories.append({
                'name': text,
                'url': full_url
            })

    # Deduplicate by URL
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat['url'] not in seen:
            seen.add(cat['url'])
            unique_categories.append(cat)

    print(f"Found {len(unique_categories)} categories")
    return unique_categories

def get_products_from_category(scraper, category_url, category_name):
    """Scrape products from a category page."""
    print(f"  Scraping category: {category_name} ({category_url})")
    try:
        response = scraper.get(category_url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"    Error fetching category page: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    products = []

    # Look for product containers - adjust selectors as needed
    product_containers = soup.find_all('div', class_=re.compile(r'product')) or \
                         soup.find_all('article', class_=re.compile(r'product')) or \
                         soup.find_all('li', class_=re.compile(r'product'))

    # If the above doesn't work, try a more generic approach
    if not product_containers:
        product_containers = soup.find_all('a', href=re.compile(r'/p/'))

    for container in product_containers[:30]:  # Limit products per category for speed
        try:
            # Extract product link
            if container.name == 'a':
                product_link = container
            else:
                product_link = container.find('a', href=re.compile(r'/p/'))
            
            if not product_link:
                continue
                
            product_url = urljoin(BASE_URL, product_link.get('href'))
            
            # Extract product name
            name_elem = container.find(['h3', 'h2', 'span'], class_=re.compile(r'title|name')) or \
                       container.find('img', alt=True) or \
                       product_link
            product_name = name_elem.get_text(strip=True) if name_elem.get_text(strip=True) else \
                         (name_elem.get('alt') if name_elem.has_attr('alt') else '')
            
            if not product_name or len(product_name) < 3:
                continue

            # Extract price
            price_elem = container.find(class_=re.compile(r'price|cost'))
            price_text = price_elem.get_text(strip=True) if price_elem else ''
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(' ', '').replace(',', '.'))
            price = float(price_match.group()) if price_match else 0.0

            # Extract image
            img_elem = container.find('img')
            image_url = ''
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src') or ''
                if image_url and not image_url.startswith('http'):
                    image_url = urljoin(BASE_URL, image_url)

            # Extract product ID from URL or data attributes
            decathlon_id = ''
            id_match = re.search(r'/p/([^/]+)', product_url)
            if id_match:
                decathlon_id = id_match.group(1)
            else:
                # Try to find in data attributes
                id_elem = container.find(attrs={'data-product-id': True}) or \
                         container.find(attrs={'data-id': True})
                if id_elem:
                    decathlon_id = id_elem.get('data-product-id') or id_elem.get('data-id')

            # Build affiliate URL
            affiliate_url = f"{product_url}?SID={AFFILIATE_ID}&utm_source=princedumonde&utm_medium=affiliation&utm_campaign=catalogue"

            # Create product object
            product = {
                'decathlonId': decathlon_id or f"sample_{int(time.time())}",
                'title': product_name[:200],  # Limit title length
                'price': price,
                'image': image_url,
                'category': category_name,
                'sport': category_name.split()[0] if category_name else 'sport',
                'description': f"Découvrez le {product_name} chez Decathlon. Produit de qualité pour la pratique sportive.",
                'available': True,
                'affiliateUrl': affiliate_url
            }

            # Add old price if available (for discounts)
            old_price_elem = container.find(class_=re.compile(r'old-price|original-price'))
            if old_price_elem:
                old_price_text = old_price_elem.get_text(strip=True)
                old_price_match = re.search(r'[\d,]+\.?\d*', old_price_text.replace(' ', '').replace(',', '.'))
                if old_price_match:
                    old_price = float(old_price_match.group())
                    if old_price > price:
                        product['oldPrice'] = old_price

            products.append(product)

        except Exception as e:
            print(f"    Error parsing product: {e}")
            continue

        # Be respectful - small delay between product processing
        time.sleep(0.2)

    print(f"    Found {len(products)} products")
    return products

def save_product_as_markdown(product):
    """Save a single product as a markdown file in the products directory."""
    # Create a safe filename from the product ID or title
    safe_id = re.sub(r'[^\w\-_]', '_', product['decathlonId'])
    filename = f"{safe_id}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # Prepare frontmatter - escape quotes properly for YAML
    def escape_yaml_string(s):
        if not isinstance(s, str):
            s = str(s)
        # Escape backslashes first, then double quotes
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return s

    escaped_title = escape_yaml_string(product['title'])
    escaped_description = escape_yaml_string(product['description'])
    escaped_category = escape_yaml_string(product['category'])
    escaped_sport = escape_yaml_string(product['sport'])
    escaped_image = escape_yaml_string(product.get('image', ''))
    escaped_affiliate_url = escape_yaml_string(product['affiliateUrl'])

    frontmatter = [
        "---",
        f"title: \"{escaped_title}\"",
        f"decathlonId: \"{product['decathlonId']}\"",
        f"price: {product['price']}",
    ]
    
    if product.get('oldPrice'):
        frontmatter.append(f"oldPrice: {product['oldPrice']}")
    
    if product.get('image'):
        frontmatter.append(f"image: \"{escaped_image}\"")
    
    frontmatter.extend([
        f"category: \"{escaped_category}\"",
        f"sport: \"{escaped_sport}\"",
        f"description: \"{escaped_description}\"",
        f"available: {str(product['available']).lower()}",
        f"affiliateUrl: \"{escaped_affiliate_url}\"",
    ])
    
    # Add specs if any (empty for now)
    frontmatter.append("specs: {}")
    
    frontmatter.append("---")
    frontmatter.append("")  # Empty line after frontmatter
    frontmatter.append(product['description'])

    content = "\n".join(frontmatter)

    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"      Saved: {filename}")

def main():
    """Main scraping function."""
    print("Starting Decathlon scraper...")
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize scraper
    scraper = init_scraper()
    
    # Get categories
    categories = get_categories(scraper)
    
    if not categories:
        print("No categories found. Exiting.")
        return
    
    all_products = []
    
    # Scrape each category (limit to first 3 for testing)
    for category in categories[:3]:
        products = get_products_from_category(scraper, category['url'], category['name'])
        all_products.extend(products)
        # Delay between categories to be respectful
        time.sleep(2)
    
    # Save all products
    print(f"\nSaving {len(all_products)} products to markdown files...")
    for product in all_products:
        save_product_as_markdown(product)
    
    print("\nScraping complete!")

if __name__ == "__main__":
    main()