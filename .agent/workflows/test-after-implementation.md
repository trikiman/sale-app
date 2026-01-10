---
description: Always run unit tests after implementing a feature
---

# Test After Implementation

## VkusVill Scraping Rules

> [!CAUTION]
> **ALL scraping MUST be automated via Python bot** - NOT done manually by the assistant!
> The user needs this to work independently without the assistant present.
> Fix the Python scraper to work correctly, don't do manual browser scraping.

> [!IMPORTANT]
> After loading `vkusvill.ru/cart/`, **WAIT AT LEAST 5 SECONDS** before interacting with the green prices section. It loads slowly!

> [!WARNING]
> If green products count is **less than 5-10**, the count badge (`js-vv-tizers-section__link-text`) **DISAPPEARS**. 
> In this case, **COUNT THE VISIBLE PRODUCT CARDS** in the "Зелёные ценники" section directly.

> [!TIP]
> To get **actual stock**, click "В корзину" and look for "В наличии: X кг/шт" text - NOT the quantity selector!

1. **Write a simple test** to verify the feature works
2. **Run the test** using browser_subagent or command line
3. **If test FAILS** - fix the bug and re-test
4. **Repeat until test PASSES**
5. Only then notify the user of completion

## Example Test Types

- **UI Test**: Use browser_subagent to verify displayed values match expected
- **API Test**: Run a script that checks response data
- **Count Verification**: Check that counts/totals are correct
- **Integration Test**: Verify data flows through the system

## Test Report Format

Always report:
- Expected result
- Actual result
- PASS or FAIL
- If FAIL: what was fixed and re-test result
