"""
FastAPI Backend for VkusVill Mini App
Serves product data and handles favorites
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database

app = FastAPI(title="VkusVill Mini App API", version="1.0.0")

# CORS for mini app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()

# Data paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROPOSALS_PATH = os.path.join(DATA_DIR, "proposals.json")


# Pydantic models
class Product(BaseModel):
    id: str
    name: str
    url: str
    currentPrice: str
    oldPrice: str
    image: str
    stock: float
    unit: str
    category: str
    type: str  # green, red, yellow


class ProductsResponse(BaseModel):
    updatedAt: str
    products: List[Product]


class FavoriteRequest(BaseModel):
    product_id: str
    product_name: str


class FavoriteResponse(BaseModel):
    product_id: str
    product_name: str
    is_favorite: bool


# Endpoints

@app.get("/")
def root():
    """Health check"""
    return {"status": "ok", "message": "VkusVill Mini App API"}


@app.get("/products", response_model=ProductsResponse)
def get_products():
    """Get all products from JSON file"""
    try:
        if not os.path.exists(PROPOSALS_PATH):
            raise HTTPException(status_code=404, detail="Products data not found")
        
        with open(PROPOSALS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON data")


@app.get("/favorites/{user_id}")
def get_favorites(user_id: int):
    """Get user's favorite products"""
    favorites = db.get_user_favorite_products(user_id)
    return {
        "user_id": user_id,
        "favorites": [{"product_id": f.product_id, "product_name": f.product_name} for f in favorites]
    }


@app.post("/favorites/{user_id}", response_model=FavoriteResponse)
def toggle_favorite(user_id: int, request: FavoriteRequest):
    """Toggle favorite status for a product"""
    # Ensure user exists
    db.upsert_user(user_id)
    
    # Check if already favorited
    favorites = db.get_user_favorite_products(user_id)
    is_favorited = any(f.product_id == request.product_id for f in favorites)
    
    if is_favorited:
        # Remove from favorites
        db.remove_favorite_product(user_id, request.product_id)
        return FavoriteResponse(
            product_id=request.product_id,
            product_name=request.product_name,
            is_favorite=False
        )
    else:
        # Add to favorites
        db.add_favorite_product(user_id, request.product_id, request.product_name)
        return FavoriteResponse(
            product_id=request.product_id,
            product_name=request.product_name,
            is_favorite=True
        )


@app.delete("/favorites/{user_id}/{product_id}")
def remove_favorite(user_id: int, product_id: str):
    """Remove a product from favorites"""
    success = db.remove_favorite_product(user_id, product_id)
    return {"success": success, "product_id": product_id}


@app.post("/sync")
def sync_products():
    """Sync products from JSON to database (mark as seen)"""
    try:
        if not os.path.exists(PROPOSALS_PATH):
            return {"success": False, "message": "No products file found"}
        
        with open(PROPOSALS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        products = data.get('products', [])
        new_count = 0
        
        for product in products:
            is_new = db.mark_product_seen(product['id'])
            if is_new:
                new_count += 1
        
        return {
            "success": True,
            "total_products": len(products),
            "new_products": new_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/new-products")
def get_new_products():
    """Get products that haven't been notified yet"""
    try:
        if not os.path.exists(PROPOSALS_PATH):
            return {"new_products": []}
        
        with open(PROPOSALS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        products = data.get('products', [])
        product_ids = [p['id'] for p in products]
        
        new_ids = db.get_new_products(product_ids)
        new_products = [p for p in products if p['id'] in new_ids]
        
        return {"new_products": new_products, "count": len(new_products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
