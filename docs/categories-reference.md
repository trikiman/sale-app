# VkusVill Product Categories Reference

## Overview

This document defines all possible product categories for the VkusVill Mini App, based on VkusVill's actual catalog structure.

---

## Category List

| Emoji | Category (RU) | Category (EN) | Description |
|-------|---------------|---------------|-------------|
| 🥬 | Овощи | Vegetables | Fresh vegetables, greens, herbs |
| 🍎 | Фрукты | Fruits | Fresh fruits, berries |
| 🥩 | Мясо | Meat | Fresh meat, poultry, minced meat |
| 🐟 | Рыба | Fish | Fresh fish, seafood |
| 🥛 | Молочка | Dairy | Milk, cheese, yogurt, eggs |
| 🍞 | Хлеб | Bakery | Bread, pastries, baked goods |
| ❄️ | Заморозка | Frozen | Frozen foods, ice cream |
| 🥤 | Напитки | Beverages | Juices, sodas, water, tea, coffee |
| 🛒 | Бакалея | Pantry | Oil, cereals, pasta, sauces, canned goods |
| 🥨 | Закуски | Snacks | Chips, olives, nuts, dried fruits |
| 🍰 | Сладости | Sweets | Candy, chocolate, cookies |
| 🥗 | Готовая еда | Ready Meals | Salads, prepared dishes, sandwiches |
| 💄 | Косметика | Cosmetics | Skincare, bath products, hygiene |
| 🧹 | Хозтовары | Household | Cleaning supplies, home goods |
| 🐾 | Зоотовары | Pet Supplies | Pet food, pet accessories |
| 👶 | Детское | Baby | Baby food, diapers, baby care |
| 📦 | Другое | Other | Fallback for unknown categories |

---

## Detailed Category Examples

### 🥬 Овощи (Vegetables)
- Томаты (сливка, черри, розовые)
- Огурцы (короткоплодные, длинноплодные)
- Перец болгарский
- Картофель
- Морковь
- Капуста (белокочанная, цветная, брокколи)
- Кабачки, баклажаны
- Лук, чеснок
- Зелень (укроп, петрушка, базилик, салат)

### 🍎 Фрукты (Fruits)
- Яблоки
- Бананы
- Апельсины, мандарины
- Лимоны, лаймы
- Груши
- Виноград
- Авокадо
- Клубника, малина, голубика
- Манго, киви, гранат

### 🥩 Мясо (Meat)
- Говядина (стейки, фарш, вырезка)
- Свинина (шея, карбонад, ребра)
- Курица (филе, бедра, крылья)
- Индейка
- Колбасы, сосиски
- Паштеты
- Субпродукты (печень, сердце)

### 🐟 Рыба (Fish & Seafood)
- Лосось, форель, семга
- Треска, минтай
- Креветки, мидии
- Сельдь, скумбрия
- Икра
- Крабовые палочки
- Морской коктейль

### 🥛 Молочка (Dairy)
- Молоко
- Кефир, ряженка
- Йогурты
- Творог
- Сметана
- Сыры (твердые, мягкие, творожные)
- Масло сливочное
- Яйца

### 🍞 Хлеб (Bakery)
- Хлеб (белый, ржаной, цельнозерновой)
- Батон
- Булочки
- Лаваш, лепешки
- Круассаны
- Торты, пирожные

### ❄️ Заморозка (Frozen)
- Пельмени, вареники
- Блинчики
- Пицца замороженная
- Овощи замороженные
- Мороженое
- Замороженные ягоды
- Замороженная рыба

### 🥤 Напитки (Beverages)
- Соки
- Морсы
- Газировка (Вкус-Кола, лимонад)
- Вода
- Чай, кофе
- Квас
- Молочные коктейли

### 🛒 Бакалея (Pantry)
- Масло растительное
- Крупы (рис, гречка, овсянка)
- Макароны
- Соусы, кетчуп, майонез
- Консервы (горох, кукуруза, фасоль)
- Специи
- Мука, сахар

### 🥨 Закуски (Snacks)
- Оливки, маслины
- Орехи (арахис, кешью, миндаль)
- Сухофрукты
- Чипсы, сухарики
- Снеки

### 🍰 Сладости (Sweets)
- Шоколад
- Конфеты
- Печенье, вафли
- Зефир, пастила
- Мед, варенье

### 🥗 Готовая еда (Ready Meals)
- Салаты
- Супы
- Гарниры
- Сэндвичи
- Роллы

### 💄 Косметика (Cosmetics)
- Бомбочки для ванны
- Крема, лосьоны
- Шампуни, гели
- Зубные пасты
- Дезодоранты

### 🧹 Хозтовары (Household)
- Губки, салфетки
- Моющие средства
- Пакеты

### 🐾 Зоотовары (Pet Supplies)
- Корм для собак (сухой, влажный)
- Корм для кошек
- Лакомства для животных
- Аксессуары

### 👶 Детское (Baby)
- Детское питание (пюре, каши)
- Подгузники
- Детская косметика

---

## Emoji Lookup Table (for App.jsx)

```javascript
const CATEGORY_EMOJIS = {
  'Овощи': '🥬',
  'Фрукты': '🍎',
  'Мясо': '🥩',
  'Рыба': '🐟',
  'Молочка': '🥛',
  'Хлеб': '🍞',
  'Заморозка': '❄️',
  'Напитки': '🥤',
  'Бакалея': '🛒',
  'Закуски': '🥨',
  'Сладости': '🍰',
  'Готовая еда': '🥗',
  'Косметика': '💄',
  'Хозтовары': '🧹',
  'Зоотовары': '🐾',
  'Детское': '👶',
  'Другое': '📦',
}

const getCategoryEmoji = (category) => CATEGORY_EMOJIS[category] || '📦'
```

---

## Scraper Category Extraction

Categories should be extracted directly from VkusVill product pages using:

```javascript
// From data-layer attribute on product cards
const categoryEl = card.querySelector('[class*="datalayer-catalog-list-category"]')
let category = categoryEl?.textContent?.split('//')[0]?.trim() || 'Другое'
```

This ensures categories match VkusVill's actual taxonomy instead of keyword guessing.

---

## Notes

- Categories are dynamic and generated from actual product data
- The "Другое" (Other) category is a fallback for unrecognized categories
- New categories from VkusVill will automatically appear in the app
- Emoji assignments are based on the lookup table above
