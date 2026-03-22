from fastapi import FastAPI, Query, HTTPException, Response, status
from pydantic import BaseModel, Field
from typing import Optional, List

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Welcome to QuickBite Food Delivery"}

menu = [
    {"id": 1, "name": "Margherita Pizza", "price": 299, "category": "Pizza", "is_available": True},
    {"id": 2, "name": "Veg Burger", "price": 149, "category": "Burger", "is_available": True},
    {"id": 3, "name": "Coke", "price": 59, "category": "Drink", "is_available": True},
    {"id": 4, "name": "Brownie", "price": 99, "category": "Dessert", "is_available": True},
    {"id": 5, "name": "Cheese Pizza", "price": 399, "category": "Pizza", "is_available": False},
    {"id": 6, "name": "Fries", "price": 129, "category": "Snack", "is_available": True}
]

orders = []
order_counter = 1
cart = []

@app.get("/menu")
def get_menu():
    return {"menu": menu, "total": len(menu)}

@app.get("/menu/summary")
def summary():
    available = [m for m in menu if m["is_available"]]
    categories = list(set(m["category"] for m in menu))
    return {
        "total": len(menu),
        "available": len(available),
        "unavailable": len(menu) - len(available),
        "categories": categories
    }

@app.get("/menu/search")
def search(keyword: str):
    result = [m for m in menu if keyword.lower() in m["name"].lower() or keyword.lower() in m["category"].lower()]
    if not result:
        return {"message": "No items found"}
    return {"results": result, "total_found": len(result)}

class OrderRequest(BaseModel):
    customer_name: str = Field(..., min_length=2)
    item_id: int
    quantity: int = Field(..., gt=0, le=20)
    delivery_address: str = Field(..., min_length=10)
    order_type: str = "delivery"

def find_item(item_id):
    return next((i for i in menu if i["id"] == item_id), None)

def calculate_bill(price, quantity, order_type):
    total = price * quantity
    if order_type == "delivery":
        total += 30
    return total

@app.post("/orders")
def create_order(order: OrderRequest):
    global order_counter
    item = find_item(order.item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not item["is_available"]:
        raise HTTPException(status_code=400, detail="Item not available")

    total = calculate_bill(item["price"], order.quantity, order.order_type)

    new_order = {
        "order_id": order_counter,
        "customer_name": order.customer_name,
        "item": item["name"],
        "quantity": order.quantity,
        "total_price": total
    }

    orders.append(new_order)
    order_counter += 1

    return new_order

@app.get("/orders")
def get_orders():
    return {"orders": orders, "total_orders": len(orders)}

@app.get("/menu/filter")
def filter_menu(category: str = None, max_price: int = None, is_available: bool = None):
    result = menu

    if category is not None:
        result = [m for m in result if m["category"].lower() == category.lower()]

    if max_price is not None:
        result = [m for m in result if m["price"] <= max_price]

    if is_available is not None:
        result = [m for m in result if m["is_available"] == is_available]

    return {"items": result, "count": len(result)}

class NewItem(BaseModel):
    name: str
    price: int
    category: str
    is_available: bool = True

@app.post("/menu")
def add_item(item: NewItem, response: Response):
    for m in menu:
        if m["name"].lower() == item.name.lower():
            response.status_code = 400
            return {"error": "Item already exists"}

    new_id = max(m["id"] for m in menu) + 1

    new_item = {
        "id": new_id,
        "name": item.name,
        "price": item.price,
        "category": item.category,
        "is_available": item.is_available
    }

    menu.append(new_item)
    response.status_code = 201
    return new_item

@app.put("/menu/{item_id}")
def update_item(item_id: int, price: int = None, is_available: bool = None):
    item = find_item(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if price is not None:
        item["price"] = price

    if is_available is not None:
        item["is_available"] = is_available

    return item

@app.delete("/menu/{item_id}")
def delete_item(item_id: int):
    item = find_item(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    menu.remove(item)
    return {"message": "Item deleted"}

@app.post("/cart/add")
def add_to_cart(item_id: int, quantity: int = 1):
    item = find_item(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not item["is_available"]:
        raise HTTPException(status_code=400, detail="Item not available")

    for c in cart:
        if c["item_id"] == item_id:
            c["quantity"] += quantity
            c["subtotal"] = c["quantity"] * c["price"]
            return {"message": "Cart updated", "cart_item": c}

    cart_item = {
        "item_id": item_id,
        "name": item["name"],
        "price": item["price"],
        "quantity": quantity,
        "subtotal": item["price"] * quantity
    }

    cart.append(cart_item)
    return {"message": "Added to cart", "cart_item": cart_item}

@app.get("/cart")
def view_cart():
    if not cart:
        return {"message": "Cart is empty"}

    total = sum(c["subtotal"] for c in cart)

    return {
        "items": cart,
        "item_count": len(cart),
        "grand_total": total
    }

@app.delete("/cart/{item_id}")
def remove_cart(item_id: int):
    for c in cart:
        if c["item_id"] == item_id:
            cart.remove(c)
            return {"message": "Removed"}
    return {"error": "Item not in cart"}

class Checkout(BaseModel):
    customer_name: str
    delivery_address: str

@app.post("/cart/checkout")
def checkout(data: Checkout):
    global order_counter

    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    placed = []
    total = 0

    for c in cart:
        order = {
            "order_id": order_counter,
            "customer_name": data.customer_name,
            "item": c["name"],
            "quantity": c["quantity"],
            "total_price": c["subtotal"]
        }
        orders.append(order)
        placed.append(order)
        total += c["subtotal"]
        order_counter += 1

    cart.clear()

    return {
        "orders_placed": placed,
        "grand_total": total
    }

@app.get("/menu/sort")
def sort_menu(sort_by: str = "price", order: str = "asc"):
    if sort_by not in ["price", "name", "category"]:
        return {"error": "Invalid sort_by"}

    reverse = True if order == "desc" else False

    sorted_menu = sorted(menu, key=lambda x: x[sort_by], reverse=reverse)

    return {
        "sort_by": sort_by,
        "order": order,
        "items": sorted_menu
    }

@app.get("/menu/page")
def paginate(page: int = 1, limit: int = 3):
    start = (page - 1) * limit
    data = menu[start:start + limit]

    total_pages = (len(menu) + limit - 1) // limit

    return {
        "page": page,
        "limit": limit,
        "total": len(menu),
        "total_pages": total_pages,
        "items": data
    }

@app.get("/orders/search")
def search_orders(customer_name: str):
    result = [o for o in orders if customer_name.lower() in o["customer_name"].lower()]
    if not result:
        return {"message": "No orders found"}
    return {"orders": result}

@app.get("/menu/browse")
def browse(keyword: str = None, sort_by: str = "price", order: str = "asc", page: int = 1, limit: int = 4):
    result = menu

    if keyword:
        result = [m for m in result if keyword.lower() in m["name"].lower()]

    reverse = True if order == "desc" else False
    result = sorted(result, key=lambda x: x[sort_by], reverse=reverse)

    total = len(result)
    start = (page - 1) * limit
    result = result[start:start + limit]

    total_pages = (total + limit - 1) // limit

    return {
        "keyword": keyword,
        "page": page,
        "limit": limit,
        "total_found": total,
        "total_pages": total_pages,
        "items": result
    }

@app.get("/menu/{item_id}")
def get_item(item_id: int):
    for item in menu:
        if item["id"] == item_id:
            return item
    return {"error": "Item not found"}
