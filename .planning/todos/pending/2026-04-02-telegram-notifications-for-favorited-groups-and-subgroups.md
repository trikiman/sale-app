---
created: 2026-04-02T03:24:41.693Z
title: Telegram notifications for favorited groups and subgroups
area: bot
files:
  - bot/notifier.py
  - backend/main.py
---

## Problem

Telegram notifications currently work for individual product favorites — when a favorited product goes on sale, the user gets a Telegram message. But there's no way to subscribe to an entire group or subgroup (e.g., "Готовая еда" or "Салаты") so that any new sale in that category triggers a notification.

## Solution

After group/subgroup favorites are implemented in v1.7 (UI filter shortcuts), extend the notification system to check favorited groups/subgroups and send Telegram alerts for any product in those categories that goes on sale. Requires:
- DB table to store user→group/subgroup favorites (may already exist from v1.7)
- Notifier logic to check group/subgroup favorites alongside product favorites
- Dedup to avoid double-notifying if both a product AND its group are favorited
