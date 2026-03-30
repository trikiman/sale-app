---
phase: 4
plan: 1
title: "Fix stock=99 placeholder and parse_stock docstring"
wave: 1
depends_on: []
files_modified:
  - utils.py
requirements:
  - SCRP-08
autonomous: true
---

<objective>
Verify and fix that no green product shows stock=99 placeholder after scraping.
</objective>

<tasks>
<task id="4.1.1">
<title>Fix misleading parse_stock docstring</title>
<action>Update docstring to match actual return values (1, not 99)</action>
<acceptance_criteria>
- Docstring correctly documents return values
- parse_stock returns 1 for "В наличии" without number, not 99
</acceptance_criteria>
</task>
</tasks>

<verification>
1. parse_stock("В наличии") returns 1, not 99
2. scrape_green_data.py has 6 filters against stock=99  
</verification>
