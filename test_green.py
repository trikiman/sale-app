import sys, asyncio
sys.path.insert(0, '/home/ubuntu/saleapp')
import scrape_green

async def main():
    try:
        products, success = await scrape_green.scrape_green_prices_async()
        print(f"RESULT: {len(products)} products, success={success}")
        if products:
            for p in products[:5]:
                print(f"  - {p.get('name','')[:40]} | stock={p.get('stock')} | price={p.get('currentPrice')}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
