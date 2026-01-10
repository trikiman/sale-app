"""
VkusVill Playwright-based Scraper
Uses browser automation for authenticated scraping
"""
import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from bs4 import BeautifulSoup

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

import config


def get_weight_emoji(weight_grams: int) -> str:
    """Get emoji based on product weight in grams"""
    if weight_grams <= 0:
        return "📦"
    elif weight_grams <= 500:
        return "🥄"  # small
    elif weight_grams <= 1000:
        return "🍽️"  # medium
    elif weight_grams <= 3000:
        return "🥡"  # big
    elif weight_grams <= 5000:
        return "📦"  # bulk
    else:
        return "🛒"  # huge


def get_stock_emoji(stock_count: int) -> str:
    """Get emoji based on stock count"""
    if stock_count <= 0:
        return "❌"  # sold out
    elif stock_count <= 2:
        return "🔴"  # almost gone
    elif stock_count <= 5:
        return "🟠"  # low
    elif stock_count <= 10:
        return "🟡"  # medium
    elif stock_count <= 15:
        return "🟢"  # good
    else:
        return "✅"  # plenty


def parse_weight_from_name(name: str) -> Tuple[int, str]:
    """
    Parse weight from product name
    Returns (weight_in_grams, weight_string)
    """
    # Match patterns like "200 г", "1.3 кг", "500 мл", etc.
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(г|кг|мл|л)\b', name, re.IGNORECASE)
    if match:
        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2).lower()
        
        if unit == 'кг' or unit == 'л':
            grams = int(value * 1000)
            weight_str = f"{value} {unit}"
        else:
            grams = int(value)
            weight_str = f"{int(value)} {unit}"
        
        return grams, weight_str
    
    # Match "X шт" for piece count
    match = re.search(r'(\d+)\s*шт', name, re.IGNORECASE)
    if match:
        return 0, f"{match.group(1)} шт"
    
    return 0, ""


def categorize_product(name: str, category_raw: str) -> str:
    """Categorize product into main categories for grouping"""
    name_lower = name.lower()
    cat_lower = category_raw.lower()
    
    # Define category keywords
    categories = {
        "🥩 МЯСО": ["мясо", "говядин", "свинин", "курин", "индейк", "кролик", "бедро", "филе", "фарш", "котлет", "люля", "стейк", "эскалоп", "ветчин", "бужен", "колбас", "сосиск", "сардель", "фрикадел"],
        "🐟 РЫБА": ["рыба", "морепродукт", "креветк", "кальмар", "лосось", "форель", "сельдь", "скумбри", "кета", "дорадо"],
        "🥛 МОЛОЧКА": ["молоч", "йогурт", "кефир", "творог", "сметан", "сыр", "масло сливоч"],
        "🥗 САЛАТЫ": ["салат", "винегрет", "оливье"],
        "🍲 СУПЫ": ["суп", "борщ", "щи", "солянк"],
        "🍳 ГОТОВАЯ ЕДА": ["готов", "курица с", "печень по", "шаурма", "сэндвич", "клаб", "онигири", "заливное"],
        "🍰 ДЕСЕРТЫ": ["торт", "пирожн", "эклер", "брауни", "десерт", "профитрол", "рулет", "желе", "морковн"],
        "🥐 ВЫПЕЧКА": ["пирож", "рогалик", "блинчик", "выпечк"],
        "🥚 ЯЙЦА": ["яйц"],
        "🐱 КОРМ": ["корм"],
    }
    
    for cat_name, keywords in categories.items():
        for kw in keywords:
            if kw in name_lower or kw in cat_lower:
                return cat_name
    
    return "📦 ДРУГОЕ"


@dataclass
class Product:
    """Represents a VkusVill product"""
    id: str
    name: str
    url: str
    current_price: float
    original_price: Optional[float]
    discount_percent: int
    category: str
    is_green_price: bool
    image_url: Optional[str] = None
    weight_grams: int = 0
    weight_str: str = ""
    stock_count: int = 0
    main_category: str = ""
    
    def __post_init__(self):
        # Parse weight from name if not set
        if not self.weight_str:
            self.weight_grams, self.weight_str = parse_weight_from_name(self.name)
        # Set main category for grouping
        if not self.main_category:
            self.main_category = categorize_product(self.name, self.category)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Product):
            return self.id == other.id
        return False
    
    @property
    def weight_emoji(self) -> str:
        return get_weight_emoji(self.weight_grams)
    
    @property
    def stock_emoji(self) -> str:
        return get_stock_emoji(self.stock_count)
    
    @property
    def formatted_line(self) -> str:
        """Format product as a single line for grouped message"""
        weight_part = f", {self.weight_str}" if self.weight_str else ""
        stock_part = f" [{self.stock_count}шт]" if self.stock_count > 0 else ""
        
        return (
            f"{self.weight_emoji}{self.stock_emoji} {self.name}{weight_part}\n"
            f"    {self.original_price:.0f}₽ → <b>{self.current_price:.0f}₽</b> (-{self.discount_percent}%){stock_part}"
        )
    
    @property
    def formatted_message(self) -> str:
        """Format product for Telegram message (full format)"""
        emoji = "🟢" if self.is_green_price else "🏷️"
        weight_part = f" ({self.weight_str})" if self.weight_str else ""
        stock_part = f"\n📊 В наличии: {self.stock_count} шт" if self.stock_count > 0 else ""
        
        lines = [
            f"{self.weight_emoji}{self.stock_emoji} <b>{self.name}</b>{weight_part}",
            f"💰 <s>{self.original_price:.0f}₽</s> → <b>{self.current_price:.0f}₽</b>" if self.original_price else f"💰 <b>{self.current_price:.0f}₽</b>",
            f"📉 Скидка: <b>-{self.discount_percent}%</b>{stock_part}",
            f"📁 {self.category}",
            f"🔗 <a href='{self.url}'>Открыть</a>"
        ]
        
        return "\n".join(lines)


def format_products_grouped(products: List[Product]) -> str:
    """Format products grouped by category for a summary message"""
    # Group by main category
    groups: Dict[str, List[Product]] = {}
    for p in products:
        if p.main_category not in groups:
            groups[p.main_category] = []
        groups[p.main_category].append(p)
    
    # Build message
    lines = [
        f"🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b>",
        f"📦 {len(products)} товаров | -40%",
        ""
    ]
    
    # Sort categories
    category_order = ["🥩 МЯСО", "🐟 РЫБА", "🥛 МОЛОЧКА", "🥗 САЛАТЫ", "🍲 СУПЫ", "🍳 ГОТОВАЯ ЕДА", "🍰 ДЕСЕРТЫ", "🥐 ВЫПЕЧКА", "🥚 ЯЙЦА", "🐱 КОРМ", "📦 ДРУГОЕ"]
    
    for cat in category_order:
        if cat in groups:
            prods = groups[cat]
            lines.append(f"━━━━━━━━━━━━━━━━━━")
            lines.append(f"<b>{cat}</b> ({len(prods)})")
            lines.append(f"━━━━━━━━━━━━━━━━━━")
            
            for p in prods[:10]:  # Limit per category
                lines.append(p.formatted_line)
                lines.append("")
            
            if len(prods) > 10:
                lines.append(f"...и ещё {len(prods) - 10}")
                lines.append("")
    
    return "\n".join(lines)


class PlaywrightScraper:
    """Scrapes VkusVill using Playwright browser automation"""
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._initialized = False
        self._storage_path = os.path.join(os.path.dirname(config.DATABASE_PATH), "browser_state.json")
    
    async def initialize(self):
        """Initialize the browser"""
        if self._initialized:
            return
        
        print("Initializing Playwright browser...")
        
        self._playwright = await async_playwright().start()
        
        # Use Chromium in headless mode
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Check for saved browser state
        if os.path.exists(self._storage_path):
            print(f"Loading saved browser state from {self._storage_path}")
            self._context = await self._browser.new_context(
                storage_state=self._storage_path,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        else:
            print("Creating new browser context (no saved state)")
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        
        self._page = await self._context.new_page()
        self._initialized = True
        print("Browser initialized")
    
    async def save_state(self):
        """Save browser state for future sessions"""
        if self._context:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            await self._context.storage_state(path=self._storage_path)
            print(f"Browser state saved to {self._storage_path}")
    
    async def close(self):
        """Close the browser"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        print("Browser closed")
    
    async def is_logged_in(self) -> bool:
        """Check if we're logged into VkusVill"""
        await self.initialize()
        
        try:
            await self._page.goto(config.VKUSVILL_BASE_URL + "/cart/", wait_until="networkidle", timeout=30000)
            
            # Check for login indicators
            content = await self._page.content()
            
            # If we see green prices or personal discounts, we're logged in
            if "Зелёные ценники" in content or "Ваши скидки" in content:
                print("Session is authenticated")
                return True
            
            # Check for login button
            if 'data-auth="login"' in content or "Войти" in content:
                print("Session requires login")
                return False
            
            return False
            
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False
    
    def _parse_price(self, price_str: Optional[str]) -> Optional[float]:
        """Parse price string to float"""
        if not price_str:
            return None
        
        clean = re.sub(r'[^\d.,]', '', price_str.replace(',', '.'))
        
        try:
            return float(clean)
        except (ValueError, TypeError):
            return None
    
    async def fetch_green_prices_from_modal(self) -> List[Product]:
        """Fetch ALL green price products with REAL stock counts using fast JavaScript method"""
        await self.initialize()
        
        print("Fetching green prices with stock counts from modal...")
        
        try:
            await self._page.goto(
                config.VKUSVILL_BASE_URL + "/cart/",
                wait_until="networkidle",
                timeout=30000
            )
            
            await self._page.wait_for_timeout(2000)
            
            # Scroll to find green prices section
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._page.wait_for_timeout(1000)
            
            # Click the "show all" button to open modal
            try:
                await self._page.click("#js-Delivery__Order-green-show-all", timeout=5000)
                await self._page.wait_for_timeout(2000)
            except:
                print("Could not find 'show all' button")
                return []
            
            # Scroll inside modal, click "Показать ещё" to load ALL products, then extract
            result = await self._page.evaluate("""
                (async () => {
                    const scrollContainer = document.getElementById('js-modal-cart-prods-scroll');
                    if (!scrollContainer) return { error: 'Modal not found' };
                    
                    // First, click "Показать ещё" (Load More) button until all products are loaded
                    for (let i = 0; i < 20; i++) {
                        // Scroll down to reveal the button
                        scrollContainer.scrollTop = scrollContainer.scrollHeight;
                        await new Promise(r => setTimeout(r, 500));
                        
                        // Find and click the "Load More" button
                        const loadMoreBtn = document.querySelector('.js-prods-modal-load-more');
                        if (loadMoreBtn && loadMoreBtn.offsetParent !== null) {
                            loadMoreBtn.click();
                            await new Promise(r => setTimeout(r, 1000)); // Wait for products to load
                        } else {
                            break; // No more products to load
                        }
                    }
                    
                    // Now scroll back to top and extract ALL products
                    scrollContainer.scrollTop = 0;
                    await new Promise(r => setTimeout(r, 500));
                    
                    // Scroll through to ensure all images are loaded
                    for (let i = 0; i < 10; i++) {
                        scrollContainer.scrollTop += 2000;
                        await new Promise(r => setTimeout(r, 200));
                    }
                    
                    // Extract ALL products (with images)
                    const products = [];
                    const cards = scrollContainer.querySelectorAll('.ProductCard');
                    
                    cards.forEach((card, index) => {
                        const nameEl = card.querySelector('.ProductCard__link');
                        const name = nameEl ? nameEl.innerText.trim() : '';
                        const url = nameEl ? nameEl.getAttribute('href') : '';
                        
                        // Parse prices from text
                        const text = card.innerText;
                        const priceMatches = text.match(/([\d\s]+)\s*руб/g) || [];
                        let currentPrice = '';
                        let oldPrice = '';
                        
                        if (priceMatches.length >= 2) {
                            currentPrice = priceMatches[0].replace(/руб|\\s/g, '').trim();
                            oldPrice = priceMatches[1].replace(/руб|\\s/g, '').trim();
                        } else if (priceMatches.length === 1) {
                            currentPrice = priceMatches[0].replace(/руб|\\s/g, '').trim();
                        }
                        
                        // Get category from data layer
                        const catEl = card.querySelector('.js-datalayer-catalog-list-category');
                        const category = catEl ? catEl.innerText.trim() : '';
                        
                        // Get image
                        const imgEl = card.querySelector('img');
                        const imageUrl = imgEl ? imgEl.src : '';
                        
                        products.push({
                            name,
                            url: url ? 'https://vkusvill.ru' + url : '',
                            currentPrice,
                            oldPrice,
                            category,
                            imageUrl,
                            stock: 0  // Will be filled later
                        });
                    });
                    
                    // Click ALL add-to-cart buttons at once to reveal stock counts
                    const addButtons = scrollContainer.querySelectorAll('.CartButton__content--add');
                    for (const btn of addButtons) {
                        btn.click();
                    }
                    
                    // Wait for all cart operations to complete
                    await new Promise(r => setTimeout(r, 3000));
                    
                    return { count: products.length, products };
                })()
            """)
            
            if 'error' in result:
                print(f"Error: {result['error']}")
                return []
            
            # Now fetch stock counts from the cart page
            await self._page.wait_for_timeout(1000)
            
            # Close modal to see cart
            try:
                await self._page.keyboard.press("Escape")
                await self._page.wait_for_timeout(500)
            except:
                pass
            
            # Extract stock counts from cart items
            stock_data = await self._page.evaluate("""
                (() => {
                    const stocks = {};
                    const products = document.querySelectorAll('.HProductCard');
                    products.forEach(p => {
                        const nameEl = p.querySelector('.HProductCard__Title');
                        const stockEl = p.querySelector('.js-delivery__basket--row__maxq');
                        if (nameEl && stockEl) {
                            const name = nameEl.textContent.trim();
                            const stock = stockEl.textContent.trim();
                            stocks[name] = stock;
                        }
                    });
                    return stocks;
                })()
            """)
            
            if 'error' in result:
                print(f"Error: {result['error']}")
                return []
            
            products = []
            for p in result.get('products', []):
                try:
                    current_price = self._parse_price(p['currentPrice'])
                    original_price = self._parse_price(p['oldPrice'])
                    
                    if current_price is None:
                        continue
                    
                    discount = 40
                    if original_price and original_price > current_price:
                        discount = int(round((1 - current_price / original_price) * 100))
                    
                    # Generate ID from URL
                    url = p['url']
                    product_id = re.search(r'/(\d+)', url)
                    product_id = product_id.group(1) if product_id else f"unknown_{hash(p['name'])}"
                    
                    # Parse category
                    category = p['category']
                    if '//' in category:
                        category = category.split('//')[-1].strip()
                    
                    # Get stock count from stock_data
                    stock_count = 0
                    product_name = p['name']
                    if product_name in stock_data:
                        stock_str = stock_data[product_name]
                        # Parse stock count (can be "9" or "0.87" for kg)
                        stock_match = re.search(r'([\d.,]+)', stock_str)
                        if stock_match:
                            try:
                                stock_count = int(float(stock_match.group(1).replace(',', '.')))
                            except:
                                stock_count = 1
                    
                    products.append(Product(
                        id=product_id,
                        name=p['name'],
                        url=url,
                        current_price=current_price,
                        original_price=original_price,
                        discount_percent=discount,
                        category=category or "Без категории",
                        is_green_price=True,
                        image_url=p.get('imageUrl', ''),
                        stock_count=stock_count
                    ))
                except Exception as e:
                    print(f"Error parsing product: {e}")
                    continue
            
            print(f"Found {len(products)} green price products with stock counts")
            
            return products
            
        except Exception as e:
            print(f"Error fetching from modal: {e}")
            return []
    
    async def fetch_green_prices_from_cart(self) -> List[Product]:
        """Fetch green price products - now uses modal for full list"""
        return await self.fetch_green_prices_from_modal()
    
    async def fetch_all_green_prices(self) -> List[Product]:
        """Fetch all green price products"""
        products = await self.fetch_green_prices_from_modal()
        
        # Save browser state after successful scrape
        await self.save_state()
        
        print(f"Total green price products: {len(products)}")
        return products


# Global scraper instance
_scraper_instance: Optional[PlaywrightScraper] = None


def get_scraper() -> PlaywrightScraper:
    """Get or create the global scraper instance"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = PlaywrightScraper()
    return _scraper_instance


async def close_scraper():
    """Close the global scraper instance"""
    global _scraper_instance
    if _scraper_instance is not None:
        await _scraper_instance.close()
        _scraper_instance = None
