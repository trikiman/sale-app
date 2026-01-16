---
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---

# UI / UX Tester Rules & Guidelines

These rules define how a UI/UX tester should test a web application (local or live), identify issues, and report them clearly in **BUG_REPORT.md**.

---

## 1. General Testing Principles

* Test **as a real user**, not as a developer
* Assume **nothing works until verified**
* Small issues matter (spacing, wording, loading, feedback)
* Consistency is critical across pages and devices
* If something feels confusing, it is a UX issue—even if it works

---

## 2. Environment Rules

### Local Environment (`http://localhost:5173`)

* Verify the app loads without console errors
* Check hot reload behavior (changes reflect without refresh)
* Ensure mock or test data is clearly identified
* Report any missing environment configuration

### Live Site

* Verify **real/live data** is displayed
* Check API responses for freshness and correctness
* Confirm environment-specific issues (prod vs local)
* Watch for caching or stale content

---

## 3. UI Testing Rules (Visual & Interaction)

### Layout & Design

* Alignment issues (off-center elements)
* Overlapping elements
* Broken grids or containers
* Inconsistent padding/margins
* Font size, weight, or color inconsistencies

### Responsiveness

* Test on:

  * Desktop
  * Tablet
  * Mobile
* No horizontal scrolling unless intended
* Buttons and inputs usable on touch screens

### Components

* Buttons:

  * Hover / active / disabled states
  * Click area size
* Inputs:

  * Placeholder visibility
  * Error & success states
* Modals:

  * Can be closed (ESC, click outside, close button)

---

## 4. UX Testing Rules (Experience & Flow)

### User Flow

* Is the next step obvious?
* Can a new user understand without instructions?
* Are actions reversible?

### Feedback & State

* Loading indicators for async actions
* Clear success/error messages
* No silent failures

### Accessibility (Basic)

* Text contrast readable
* Keyboard navigation works
* Focus states visible
* Labels associated with inputs

---

## 5. Error Handling Rules

* Validate forms (empty, invalid, edge cases)
* Friendly error messages (no raw system errors)
* Errors explain:

  * What happened
  * What the user should do next

---

## 6. Performance & Behavior

* Page load time feels reasonable
* No UI freezing during actions
* Smooth animations (no jank)
* Avoid unnecessary reloads

---

## 7. Cross-Browser Testing

Test at minimum:

* Chrome
* Safari (if possible)

Check for:

* CSS breaks
* Feature inconsistencies

---

## 8. BUG_REPORT.md Rules

Each bug **must** include:

```md
### Bug Title
Short and clear description

**Environment:**
- Local / Live
- Browser + version
- Device

**Steps to Reproduce:**
1. Go to ...
2. Click ...
3. Observe ...

**Expected Result:**
What should happen

**Actual Result:**
What actually happens

**Severity:**
- Critical / High / Medium / Low

**Notes (Optional):**
Screenshots, logs, ideas
```

---

## 9. Severity Guidelines

* **Critical** – App crash, data loss, blocked flow
* **High** – Major feature broken
* **Medium** – UX confusion, partial failure
* **Low** – Visual issues, minor polish

---

## 10. Tester Mindset Rules

* Be curious
* Try to break things
* Question unclear behavior
* Report even if unsure—mark as "UX Concern"

---

✅ Goal: **Make the product usable, clear, fast, and enjoyable**
