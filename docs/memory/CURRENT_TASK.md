# Current Task

## Status: Architecture Redesign
**Date**: 2026-02-21

### What's Done
- ✅ Cart API fixed (raw Cookie header, 16-field payload)
- ✅ Telegram bot "В корзину" button works
- ✅ `/test_cart` command added
- ✅ `run_app.bat` updated to start bot
- ✅ Architecture redesign planned and confirmed

### What's Next
1. Add "🌐 Открыть" button to Telegram notifications
2. Build web app login page (phone + SMS form)
3. Backend cart/auth API endpoints
4. Products page for web app
5. Serve web app from backend (drop separate frontend server)

### Architecture Summary
- **3 services**: Bot + Scheduler + Backend
- **Telegram**: notifications + "В корзину" + "Открыть сайт"
- **Web app**: browse products + add to cart + login
- **User goes to VkusVill ONLY to pay**
