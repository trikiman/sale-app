---
created: 2026-04-06T06:40:16.136Z
title: Clarify stale banner freshness vs updated time
area: api
files:
  - backend/main.py:805-876
  - miniapp/src/App.jsx:1099-1435
---

## Problem

The MiniApp can show `Обновлено: 09:36` and still display the stale warning banner, which looks wrong to the user. The backend computes `dataStale` from per-color source file freshness (`green_products.json`, `red_products.json`, `yellow_products.json`) with a 10-minute threshold, while the UI's `updatedAt` label shows the latest merged payload time. This means a recent merge timestamp can appear alongside a stale-source warning, but the screen does not explain that difference clearly.

## Solution

Make the freshness model understandable in the UI. Options to evaluate:

- Align the header label with the same per-source freshness basis as the banner.
- Surface which source is stale and how old it is directly next to the warning.
- Adjust copy so users understand that "updated" means latest merge time, not that every color source is fresh.
- Verify whether the current 10-minute source-stale threshold is still the right threshold for the green/red/yellow cadence after v1.10.
