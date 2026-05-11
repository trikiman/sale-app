---
created: 2026-05-13T01:15:00Z
title: Add trash/remove button to cart panel items
area: ui
priority: P3
files:
  - miniapp/src/CartPanel.jsx
  - backend/main.py (cart/remove endpoint already exists)
---

## Problem

In the MiniApp cart panel, each item row shows name, price, quantity, but there's **no visible way to remove an item directly from the cart view**. User has to either:
- Navigate back to the main page, find the product card, decrement the stepper to 0.
- OR go to vkusvill.ru and remove it there.

User-reported 2026-05-13: "also possible to add trash button where u can press and remove item from this ui?"

## Solution

Add a small trash icon (🗑️ or a proper SVG) to the right side of each cart item row in `CartPanel.jsx`. Click fires `POST /api/cart/remove` with the product's id.

Backend already has the remove endpoint (`CartRemoveRequest` → `VkusVillCart.remove`). This is frontend-only wiring:

```jsx
<button
  className="cart-item-remove"
  aria-label="Удалить"
  onClick={() => handleRemove(item.id)}
  disabled={removing.has(item.id)}
>
  🗑️
</button>
```

Where `handleRemove` calls `POST /api/cart/remove` with `{user_id, product_id}`, shows a brief spinner in the trash button, then refreshes the cart list on success.

Error handling: if the remove fails, leave the item visible with a red border flash + toast. Don't optimistically hide the row.

## Acceptance

- [ ] Every cart item row has a visible trash button on the right side.
- [ ] Tapping it removes the item from VkusVill cart + refreshes the panel.
- [ ] Optimistic UI: button disables + shows spinner during the request.
- [ ] On error: button re-enables, row stays visible, toast shows the reason.
- [ ] Works for items with quantity > 1 too (removes the whole row, not decrement-by-one).
- [ ] No regression on the existing stepper-to-zero remove path on the main page.

## Candidate for

v1.23 — small UI polish, ~30 LOC frontend + zero backend. Can also ship as a `/gsd-quick` task independent of v1.23 if desired.
