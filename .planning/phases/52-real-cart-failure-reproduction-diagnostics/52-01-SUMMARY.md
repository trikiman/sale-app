# Summary: Plan 52-01 — Reproduce Real Cart Failure and False Reentry Data

## Outcome

Phase 52 confirmed both user-reported bugs with live evidence.

### Cart Findings

- The frontend shell and `/api/products` were healthy; the break was in cart truth
- The live backend returned `source_unavailable` for `/api/cart/items` on an authenticated guest while direct upstream cart AJAX calls still worked
- A direct `basket_add.php` call on EC2 succeeded in about 2.6 seconds, proving the upstream add path itself was not fundamentally broken
- The old cart client spent too much time in stale-session refresh / transport failure paths before reaching the real add/read work

### History Findings

- The production `sale_sessions` table contained thousands of short-gap duplicate sessions
- Example products such as `100069` had dozens of yellow sessions split by ~5 minute gaps, which is exactly the fake-restock shape the user described

## Evidence Used

- Live `https://vkusvillsale.vercel.app/api/cart/*` calls for guest `guest_5l4qwlrwizdmo86af87`
- EC2 direct `basket_recalc.php` and `basket_add.php` requests using real cookies
- Production `salebot.db` queries over `sale_sessions`

## Result

Phase 52 passed: the bugs were reproduced and the next fixes were based on observed production behavior.
