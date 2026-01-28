from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET', 'cafe-control-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

app = FastAPI(title="CaféControl API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== MODELS ==============

class UserRole:
    ADMIN = "admin"
    GERENTE = "gerente"
    CAJERO = "cajero"

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str = UserRole.CAJERO
    cafeteria_id: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class CafeteriaBase(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    is_active: bool = True

class CafeteriaCreate(CafeteriaBase):
    pass

class CafeteriaResponse(CafeteriaBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    model_config = ConfigDict(extra="ignore")
    id: str

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: str
    price: float
    cost: float
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    margin: float = 0.0
    created_at: str

class InventoryItemBase(BaseModel):
    product_id: str
    cafeteria_id: str
    quantity: float
    min_stock: float = 10.0
    unit: str = "unidad"

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemResponse(InventoryItemBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    product_name: Optional[str] = None
    cafeteria_name: Optional[str] = None
    is_low_stock: bool = False

class InventoryMovement(BaseModel):
    inventory_id: str
    quantity: float
    movement_type: str  # "entrada", "salida", "merma", "ajuste"
    reason: Optional[str] = None

class SupplierBase(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True

class SupplierCreate(SupplierBase):
    pass

class SupplierResponse(SupplierBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str

class PurchaseItemBase(BaseModel):
    product_id: str
    quantity: float
    unit_cost: float

class PurchaseBase(BaseModel):
    supplier_id: str
    cafeteria_id: str
    items: List[PurchaseItemBase]
    notes: Optional[str] = None

class PurchaseCreate(PurchaseBase):
    pass

class PurchaseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    supplier_id: str
    supplier_name: Optional[str] = None
    cafeteria_id: str
    cafeteria_name: Optional[str] = None
    items: List[dict]
    total: float
    notes: Optional[str] = None
    created_at: str
    created_by: Optional[str] = None

class SaleItemBase(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float

class SaleBase(BaseModel):
    cafeteria_id: str
    items: List[SaleItemBase]
    payment_method: str = "efectivo"
    clip_transaction_id: Optional[str] = None
    notes: Optional[str] = None

class SaleCreate(SaleBase):
    pass

class SaleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    cafeteria_id: str
    cafeteria_name: Optional[str] = None
    items: List[dict]
    subtotal: float
    tax: float
    total: float
    cost_total: float
    profit: float
    payment_method: str
    clip_transaction_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    created_by: Optional[str] = None

class DashboardStats(BaseModel):
    total_sales_today: float
    total_sales_month: float
    total_profit_today: float
    total_profit_month: float
    sales_count_today: int
    low_stock_alerts: int
    top_products: List[dict]
    sales_by_cafeteria: List[dict]
    sales_trend: List[dict]

# ============== AUTH HELPERS ==============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, email: str, role: str, cafeteria_id: Optional[str] = None) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "cafeteria_id": cafeteria_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def require_roles(allowed_roles: List[str]):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="No tienes permisos para esta acción")
        return current_user
    return role_checker

# ============== AUTH ROUTES ==============

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user: UserCreate):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    user_id = str(uuid.uuid4())
    user_dict = user.model_dump()
    user_dict["id"] = user_id
    user_dict["password"] = hash_password(user.password)
    user_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.insert_one(user_dict)
    
    token = create_token(user_id, user.email, user.role, user.cafeteria_id)
    return TokenResponse(
        token=token,
        user=UserResponse(id=user_id, email=user.email, name=user.name, role=user.role, cafeteria_id=user.cafeteria_id)
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Usuario desactivado")
    
    token = create_token(user["id"], user["email"], user["role"], user.get("cafeteria_id"))
    return TokenResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            cafeteria_id=user.get("cafeteria_id"),
            is_active=user.get("is_active", True)
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["user_id"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserResponse(**user)

# ============== USER ROUTES ==============

@api_router.get("/users", response_model=List[UserResponse])
async def get_users(current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    return [UserResponse(**u) for u in users]

@api_router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    user_id = str(uuid.uuid4())
    user_dict = user.model_dump()
    user_dict["id"] = user_id
    user_dict["password"] = hash_password(user.password)
    user_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.insert_one(user_dict)
    return UserResponse(id=user_id, email=user.email, name=user.name, role=user.role, cafeteria_id=user.cafeteria_id)

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user: UserBase, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.users.update_one({"id": user_id}, {"$set": user.model_dump()})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    return UserResponse(**updated)

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": "Usuario eliminado"}

# ============== CAFETERIA ROUTES ==============

@api_router.get("/cafeterias", response_model=List[CafeteriaResponse])
async def get_cafeterias(current_user: dict = Depends(get_current_user)):
    cafeterias = await db.cafeterias.find({}, {"_id": 0}).to_list(100)
    return [CafeteriaResponse(**c) for c in cafeterias]

@api_router.post("/cafeterias", response_model=CafeteriaResponse)
async def create_cafeteria(cafeteria: CafeteriaCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    cafeteria_id = str(uuid.uuid4())
    cafeteria_dict = cafeteria.model_dump()
    cafeteria_dict["id"] = cafeteria_id
    cafeteria_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.cafeterias.insert_one(cafeteria_dict)
    return CafeteriaResponse(**cafeteria_dict)

@api_router.put("/cafeterias/{cafeteria_id}", response_model=CafeteriaResponse)
async def update_cafeteria(cafeteria_id: str, cafeteria: CafeteriaBase, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.cafeterias.update_one({"id": cafeteria_id}, {"$set": cafeteria.model_dump()})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Cafetería no encontrada")
    updated = await db.cafeterias.find_one({"id": cafeteria_id}, {"_id": 0})
    return CafeteriaResponse(**updated)

@api_router.delete("/cafeterias/{cafeteria_id}")
async def delete_cafeteria(cafeteria_id: str, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.cafeterias.delete_one({"id": cafeteria_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cafetería no encontrada")
    return {"message": "Cafetería eliminada"}

# ============== CATEGORY ROUTES ==============

@api_router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(current_user: dict = Depends(get_current_user)):
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    return [CategoryResponse(**c) for c in categories]

@api_router.post("/categories", response_model=CategoryResponse)
async def create_category(category: CategoryCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    category_id = str(uuid.uuid4())
    category_dict = category.model_dump()
    category_dict["id"] = category_id
    
    await db.categories.insert_one(category_dict)
    return CategoryResponse(**category_dict)

@api_router.delete("/categories/{category_id}")
async def delete_category(category_id: str, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return {"message": "Categoría eliminada"}

# ============== PRODUCT ROUTES ==============

@api_router.get("/products", response_model=List[ProductResponse])
async def get_products(current_user: dict = Depends(get_current_user)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    result = []
    for p in products:
        margin = ((p["price"] - p["cost"]) / p["price"] * 100) if p["price"] > 0 else 0
        result.append(ProductResponse(**p, margin=round(margin, 2)))
    return result

@api_router.post("/products", response_model=ProductResponse)
async def create_product(product: ProductCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    product_id = str(uuid.uuid4())
    product_dict = product.model_dump()
    product_dict["id"] = product_id
    product_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.products.insert_one(product_dict)
    margin = ((product.price - product.cost) / product.price * 100) if product.price > 0 else 0
    return ProductResponse(**product_dict, margin=round(margin, 2))

@api_router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, product: ProductBase, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    result = await db.products.update_one({"id": product_id}, {"$set": product.model_dump()})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    updated = await db.products.find_one({"id": product_id}, {"_id": 0})
    margin = ((updated["price"] - updated["cost"]) / updated["price"] * 100) if updated["price"] > 0 else 0
    return ProductResponse(**updated, margin=round(margin, 2))

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto eliminado"}

# ============== INVENTORY ROUTES ==============

@api_router.get("/inventory", response_model=List[InventoryItemResponse])
async def get_inventory(cafeteria_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if cafeteria_id:
        query["cafeteria_id"] = cafeteria_id
    elif current_user["role"] == UserRole.GERENTE and current_user.get("cafeteria_id"):
        query["cafeteria_id"] = current_user["cafeteria_id"]
    
    inventory = await db.inventory.find(query, {"_id": 0}).to_list(1000)
    
    # Enrich with product and cafeteria names
    products = {p["id"]: p["name"] for p in await db.products.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    cafeterias = {c["id"]: c["name"] for c in await db.cafeterias.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    
    result = []
    for item in inventory:
        item["product_name"] = products.get(item["product_id"], "Desconocido")
        item["cafeteria_name"] = cafeterias.get(item["cafeteria_id"], "Desconocida")
        item["is_low_stock"] = item["quantity"] <= item["min_stock"]
        result.append(InventoryItemResponse(**item))
    
    return result

@api_router.post("/inventory", response_model=InventoryItemResponse)
async def create_inventory_item(item: InventoryItemCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    # Check if item already exists for this product-cafeteria combination
    existing = await db.inventory.find_one({
        "product_id": item.product_id,
        "cafeteria_id": item.cafeteria_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe inventario para este producto en esta cafetería")
    
    item_id = str(uuid.uuid4())
    item_dict = item.model_dump()
    item_dict["id"] = item_id
    item_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.inventory.insert_one(item_dict)
    
    # Get names
    product = await db.products.find_one({"id": item.product_id}, {"_id": 0, "name": 1})
    cafeteria = await db.cafeterias.find_one({"id": item.cafeteria_id}, {"_id": 0, "name": 1})
    
    return InventoryItemResponse(
        **item_dict,
        product_name=product["name"] if product else "Desconocido",
        cafeteria_name=cafeteria["name"] if cafeteria else "Desconocida",
        is_low_stock=item.quantity <= item.min_stock
    )

@api_router.post("/inventory/movement")
async def record_inventory_movement(movement: InventoryMovement, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    inventory_item = await db.inventory.find_one({"id": movement.inventory_id})
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Item de inventario no encontrado")
    
    new_quantity = inventory_item["quantity"]
    if movement.movement_type in ["entrada"]:
        new_quantity += movement.quantity
    elif movement.movement_type in ["salida", "merma"]:
        new_quantity -= movement.quantity
    else:  # ajuste
        new_quantity = movement.quantity
    
    if new_quantity < 0:
        raise HTTPException(status_code=400, detail="No hay suficiente stock")
    
    await db.inventory.update_one({"id": movement.inventory_id}, {"$set": {"quantity": new_quantity}})
    
    # Log movement
    movement_log = {
        "id": str(uuid.uuid4()),
        "inventory_id": movement.inventory_id,
        "quantity": movement.quantity,
        "movement_type": movement.movement_type,
        "reason": movement.reason,
        "previous_quantity": inventory_item["quantity"],
        "new_quantity": new_quantity,
        "created_by": current_user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.inventory_movements.insert_one(movement_log)
    
    return {"message": "Movimiento registrado", "new_quantity": new_quantity}

@api_router.get("/inventory/movements")
async def get_inventory_movements(inventory_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if inventory_id:
        query["inventory_id"] = inventory_id
    
    movements = await db.inventory_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return movements

# ============== SUPPLIER ROUTES ==============

@api_router.get("/suppliers", response_model=List[SupplierResponse])
async def get_suppliers(current_user: dict = Depends(get_current_user)):
    suppliers = await db.suppliers.find({}, {"_id": 0}).to_list(100)
    return [SupplierResponse(**s) for s in suppliers]

@api_router.post("/suppliers", response_model=SupplierResponse)
async def create_supplier(supplier: SupplierCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    supplier_id = str(uuid.uuid4())
    supplier_dict = supplier.model_dump()
    supplier_dict["id"] = supplier_id
    supplier_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.suppliers.insert_one(supplier_dict)
    return SupplierResponse(**supplier_dict)

@api_router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(supplier_id: str, supplier: SupplierBase, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    result = await db.suppliers.update_one({"id": supplier_id}, {"$set": supplier.model_dump()})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    updated = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    return SupplierResponse(**updated)

@api_router.delete("/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: str, current_user: dict = Depends(require_roles([UserRole.ADMIN]))):
    result = await db.suppliers.delete_one({"id": supplier_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"message": "Proveedor eliminado"}

# ============== PURCHASE ROUTES ==============

@api_router.get("/purchases", response_model=List[PurchaseResponse])
async def get_purchases(cafeteria_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if cafeteria_id:
        query["cafeteria_id"] = cafeteria_id
    elif current_user["role"] == UserRole.GERENTE and current_user.get("cafeteria_id"):
        query["cafeteria_id"] = current_user["cafeteria_id"]
    
    purchases = await db.purchases.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    
    # Enrich with names
    suppliers = {s["id"]: s["name"] for s in await db.suppliers.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    cafeterias = {c["id"]: c["name"] for c in await db.cafeterias.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    
    result = []
    for p in purchases:
        p["supplier_name"] = suppliers.get(p["supplier_id"], "Desconocido")
        p["cafeteria_name"] = cafeterias.get(p["cafeteria_id"], "Desconocida")
        result.append(PurchaseResponse(**p))
    
    return result

@api_router.post("/purchases", response_model=PurchaseResponse)
async def create_purchase(purchase: PurchaseCreate, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    purchase_id = str(uuid.uuid4())
    
    # Calculate total and enrich items
    total = 0
    enriched_items = []
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    
    for item in purchase.items:
        product = products.get(item.product_id)
        item_total = item.quantity * item.unit_cost
        total += item_total
        enriched_items.append({
            "product_id": item.product_id,
            "product_name": product["name"] if product else "Desconocido",
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "total": item_total
        })
        
        # Update inventory
        inv_item = await db.inventory.find_one({
            "product_id": item.product_id,
            "cafeteria_id": purchase.cafeteria_id
        })
        if inv_item:
            await db.inventory.update_one(
                {"id": inv_item["id"]},
                {"$inc": {"quantity": item.quantity}}
            )
    
    purchase_dict = {
        "id": purchase_id,
        "supplier_id": purchase.supplier_id,
        "cafeteria_id": purchase.cafeteria_id,
        "items": enriched_items,
        "total": total,
        "notes": purchase.notes,
        "created_by": current_user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.purchases.insert_one(purchase_dict)
    
    # Get names
    supplier = await db.suppliers.find_one({"id": purchase.supplier_id}, {"_id": 0, "name": 1})
    cafeteria = await db.cafeterias.find_one({"id": purchase.cafeteria_id}, {"_id": 0, "name": 1})
    
    return PurchaseResponse(
        **purchase_dict,
        supplier_name=supplier["name"] if supplier else "Desconocido",
        cafeteria_name=cafeteria["name"] if cafeteria else "Desconocida"
    )

# ============== SALES ROUTES ==============

@api_router.get("/sales", response_model=List[SaleResponse])
async def get_sales(
    cafeteria_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if cafeteria_id:
        query["cafeteria_id"] = cafeteria_id
    elif current_user["role"] in [UserRole.GERENTE, UserRole.CAJERO] and current_user.get("cafeteria_id"):
        query["cafeteria_id"] = current_user["cafeteria_id"]
    
    if start_date:
        query["created_at"] = {"$gte": start_date}
    if end_date:
        if "created_at" in query:
            query["created_at"]["$lte"] = end_date
        else:
            query["created_at"] = {"$lte": end_date}
    
    sales = await db.sales.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Enrich with cafeteria names
    cafeterias = {c["id"]: c["name"] for c in await db.cafeterias.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    
    result = []
    for s in sales:
        s["cafeteria_name"] = cafeterias.get(s["cafeteria_id"], "Desconocida")
        result.append(SaleResponse(**s))
    
    return result

@api_router.post("/sales", response_model=SaleResponse)
async def create_sale(sale: SaleCreate, current_user: dict = Depends(get_current_user)):
    sale_id = str(uuid.uuid4())
    
    # Calculate totals
    subtotal = sum(item.subtotal for item in sale.items)
    tax = subtotal * 0.16  # 16% IVA
    total = subtotal + tax
    
    # Calculate costs
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    cost_total = 0
    enriched_items = []
    
    for item in sale.items:
        product = products.get(item.product_id)
        item_cost = (product["cost"] if product else 0) * item.quantity
        cost_total += item_cost
        enriched_items.append({
            "product_id": item.product_id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
            "cost": item_cost
        })
        
        # Update inventory (reduce stock)
        await db.inventory.update_one(
            {"product_id": item.product_id, "cafeteria_id": sale.cafeteria_id},
            {"$inc": {"quantity": -item.quantity}}
        )
    
    profit = subtotal - cost_total
    
    sale_dict = {
        "id": sale_id,
        "cafeteria_id": sale.cafeteria_id,
        "items": enriched_items,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "total": round(total, 2),
        "cost_total": round(cost_total, 2),
        "profit": round(profit, 2),
        "payment_method": sale.payment_method,
        "clip_transaction_id": sale.clip_transaction_id,
        "notes": sale.notes,
        "created_by": current_user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.sales.insert_one(sale_dict)
    
    # Get cafeteria name
    cafeteria = await db.cafeterias.find_one({"id": sale.cafeteria_id}, {"_id": 0, "name": 1})
    
    return SaleResponse(**sale_dict, cafeteria_name=cafeteria["name"] if cafeteria else "Desconocida")

# ============== DASHBOARD / REPORTS ROUTES ==============

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(cafeteria_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)
    
    query = {}
    if cafeteria_id:
        query["cafeteria_id"] = cafeteria_id
    elif current_user["role"] in [UserRole.GERENTE, UserRole.CAJERO] and current_user.get("cafeteria_id"):
        query["cafeteria_id"] = current_user["cafeteria_id"]
    
    # Get all sales
    all_sales = await db.sales.find(query, {"_id": 0}).to_list(10000)
    
    # Filter by date
    today_str = today.isoformat()
    month_str = month_start.isoformat()
    
    today_sales = [s for s in all_sales if s["created_at"] >= today_str]
    month_sales = [s for s in all_sales if s["created_at"] >= month_str]
    
    total_sales_today = sum(s["total"] for s in today_sales)
    total_sales_month = sum(s["total"] for s in month_sales)
    total_profit_today = sum(s["profit"] for s in today_sales)
    total_profit_month = sum(s["profit"] for s in month_sales)
    
    # Low stock alerts
    inv_query = {}
    if cafeteria_id:
        inv_query["cafeteria_id"] = cafeteria_id
    
    inventory = await db.inventory.find(inv_query, {"_id": 0}).to_list(1000)
    low_stock_alerts = sum(1 for i in inventory if i["quantity"] <= i["min_stock"])
    
    # Top products
    product_sales = {}
    for sale in month_sales:
        for item in sale["items"]:
            pid = item["product_id"]
            if pid not in product_sales:
                product_sales[pid] = {"name": item["product_name"], "quantity": 0, "revenue": 0}
            product_sales[pid]["quantity"] += item["quantity"]
            product_sales[pid]["revenue"] += item["subtotal"]
    
    top_products = sorted(product_sales.values(), key=lambda x: x["revenue"], reverse=True)[:5]
    
    # Sales by cafeteria
    cafeterias = {c["id"]: c["name"] for c in await db.cafeterias.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    cafe_sales = {}
    for sale in month_sales:
        cid = sale["cafeteria_id"]
        if cid not in cafe_sales:
            cafe_sales[cid] = {"name": cafeterias.get(cid, "Desconocida"), "total": 0, "profit": 0}
        cafe_sales[cid]["total"] += sale["total"]
        cafe_sales[cid]["profit"] += sale["profit"]
    
    sales_by_cafeteria = list(cafe_sales.values())
    
    # Sales trend (last 7 days)
    sales_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        next_day_str = (day + timedelta(days=1)).isoformat()
        day_sales = [s for s in all_sales if day_str <= s["created_at"] < next_day_str]
        sales_trend.append({
            "date": day.strftime("%Y-%m-%d"),
            "day": day.strftime("%a"),
            "total": sum(s["total"] for s in day_sales),
            "profit": sum(s["profit"] for s in day_sales)
        })
    
    return DashboardStats(
        total_sales_today=round(total_sales_today, 2),
        total_sales_month=round(total_sales_month, 2),
        total_profit_today=round(total_profit_today, 2),
        total_profit_month=round(total_profit_month, 2),
        sales_count_today=len(today_sales),
        low_stock_alerts=low_stock_alerts,
        top_products=top_products,
        sales_by_cafeteria=sales_by_cafeteria,
        sales_trend=sales_trend
    )

@api_router.get("/reports/sales-comparison")
async def get_sales_comparison(current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)
    month_str = month_start.isoformat()
    
    sales = await db.sales.find({"created_at": {"$gte": month_str}}, {"_id": 0}).to_list(10000)
    cafeterias = await db.cafeterias.find({}, {"_id": 0}).to_list(100)
    
    comparison = []
    for cafe in cafeterias:
        cafe_sales = [s for s in sales if s["cafeteria_id"] == cafe["id"]]
        comparison.append({
            "cafeteria_id": cafe["id"],
            "cafeteria_name": cafe["name"],
            "total_sales": round(sum(s["total"] for s in cafe_sales), 2),
            "total_profit": round(sum(s["profit"] for s in cafe_sales), 2),
            "transaction_count": len(cafe_sales),
            "average_ticket": round(sum(s["total"] for s in cafe_sales) / len(cafe_sales), 2) if cafe_sales else 0
        })
    
    return comparison

@api_router.get("/reports/profit-analysis")
async def get_profit_analysis(cafeteria_id: Optional[str] = None, current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)
    month_str = month_start.isoformat()
    
    query = {"created_at": {"$gte": month_str}}
    if cafeteria_id:
        query["cafeteria_id"] = cafeteria_id
    
    sales = await db.sales.find(query, {"_id": 0}).to_list(10000)
    purchases = await db.purchases.find(query, {"_id": 0}).to_list(1000)
    
    total_revenue = sum(s["subtotal"] for s in sales)
    total_cost_of_goods = sum(s["cost_total"] for s in sales)
    total_purchases = sum(p["total"] for p in purchases)
    gross_profit = total_revenue - total_cost_of_goods
    
    return {
        "total_revenue": round(total_revenue, 2),
        "total_cost_of_goods": round(total_cost_of_goods, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_percent": round((gross_profit / total_revenue * 100) if total_revenue > 0 else 0, 2),
        "total_purchases": round(total_purchases, 2),
        "transaction_count": len(sales)
    }

# ============== CLIP INTEGRATION (MOCK) ==============

@api_router.post("/clip/sync")
async def sync_clip_transactions(current_user: dict = Depends(require_roles([UserRole.ADMIN, UserRole.GERENTE]))):
    """
    Mock endpoint for Clip POS integration.
    In production, this would connect to Clip's API to sync transactions.
    """
    return {
        "message": "Sincronización con Clip completada (MOCK)",
        "note": "Para integración real, configure las credenciales de Clip en developer.clip.mx",
        "transactions_synced": 0
    }

@api_router.get("/clip/status")
async def get_clip_status(current_user: dict = Depends(get_current_user)):
    """Check Clip integration status"""
    clip_api_key = os.environ.get("CLIP_API_KEY")
    return {
        "connected": bool(clip_api_key),
        "message": "Clip no configurado. Visite developer.clip.mx para obtener credenciales." if not clip_api_key else "Clip conectado"
    }

# ============== SEED DATA ==============

@api_router.post("/seed")
async def seed_data():
    """Seed initial data for demo purposes"""
    
    # Check if already seeded
    existing_cafes = await db.cafeterias.count_documents({})
    if existing_cafes > 0:
        return {"message": "Datos ya existentes"}
    
    # Create admin user
    admin_id = str(uuid.uuid4())
    admin = {
        "id": admin_id,
        "email": "admin@cafecontrol.com",
        "name": "Administrador",
        "password": hash_password("admin123"),
        "role": UserRole.ADMIN,
        "cafeteria_id": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(admin)
    
    # Create cafeterias
    cafeterias_data = [
        {"name": "Café Central", "address": "Av. Reforma 123, Centro", "phone": "555-0001"},
        {"name": "Café Norte", "address": "Av. Insurgentes Norte 456", "phone": "555-0002"},
        {"name": "Café Sur", "address": "Av. Universidad 789", "phone": "555-0003"}
    ]
    
    cafe_ids = []
    for cafe in cafeterias_data:
        cafe_id = str(uuid.uuid4())
        cafe_ids.append(cafe_id)
        await db.cafeterias.insert_one({
            **cafe,
            "id": cafe_id,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Create categories
    categories_data = [
        {"name": "Bebidas Calientes", "description": "Cafés, tés y bebidas calientes"},
        {"name": "Bebidas Frías", "description": "Frappés, smoothies y bebidas frías"},
        {"name": "Alimentos", "description": "Pasteles, sándwiches y snacks"},
        {"name": "Granos", "description": "Café en grano para venta"}
    ]
    
    cat_ids = []
    for cat in categories_data:
        cat_id = str(uuid.uuid4())
        cat_ids.append(cat_id)
        await db.categories.insert_one({"id": cat_id, **cat})
    
    # Create products
    products_data = [
        {"name": "Americano", "category_id": cat_ids[0], "price": 45.00, "cost": 8.00},
        {"name": "Latte", "category_id": cat_ids[0], "price": 55.00, "cost": 12.00},
        {"name": "Cappuccino", "category_id": cat_ids[0], "price": 55.00, "cost": 12.00},
        {"name": "Espresso", "category_id": cat_ids[0], "price": 35.00, "cost": 6.00},
        {"name": "Mocha", "category_id": cat_ids[0], "price": 65.00, "cost": 15.00},
        {"name": "Frappé Mocha", "category_id": cat_ids[1], "price": 75.00, "cost": 18.00},
        {"name": "Frappé Caramelo", "category_id": cat_ids[1], "price": 75.00, "cost": 18.00},
        {"name": "Smoothie Frutas", "category_id": cat_ids[1], "price": 65.00, "cost": 20.00},
        {"name": "Croissant", "category_id": cat_ids[2], "price": 45.00, "cost": 15.00},
        {"name": "Panini Jamón", "category_id": cat_ids[2], "price": 85.00, "cost": 35.00},
        {"name": "Cheesecake", "category_id": cat_ids[2], "price": 75.00, "cost": 25.00},
        {"name": "Café Grano 250g", "category_id": cat_ids[3], "price": 180.00, "cost": 80.00}
    ]
    
    prod_ids = []
    for prod in products_data:
        prod_id = str(uuid.uuid4())
        prod_ids.append(prod_id)
        await db.products.insert_one({
            **prod,
            "id": prod_id,
            "description": "",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Create inventory for each cafeteria
    for cafe_id in cafe_ids:
        for prod_id in prod_ids:
            await db.inventory.insert_one({
                "id": str(uuid.uuid4()),
                "product_id": prod_id,
                "cafeteria_id": cafe_id,
                "quantity": 50.0,
                "min_stock": 10.0,
                "unit": "unidad",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # Create suppliers
    suppliers_data = [
        {"name": "Proveedora de Café MX", "contact_name": "Juan Pérez", "phone": "555-1001"},
        {"name": "Lácteos del Valle", "contact_name": "María López", "phone": "555-1002"},
        {"name": "Panadería Artesanal", "contact_name": "Carlos García", "phone": "555-1003"}
    ]
    
    for supplier in suppliers_data:
        await db.suppliers.insert_one({
            **supplier,
            "id": str(uuid.uuid4()),
            "email": None,
            "address": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Create some sample sales
    import random
    for cafe_id in cafe_ids:
        for day_offset in range(7):
            num_sales = random.randint(5, 15)
            for _ in range(num_sales):
                sale_items = []
                num_items = random.randint(1, 4)
                selected_prods = random.sample(list(zip(prod_ids, products_data)), num_items)
                
                for pid, pdata in selected_prods:
                    qty = random.randint(1, 3)
                    sale_items.append({
                        "product_id": pid,
                        "product_name": pdata["name"],
                        "quantity": qty,
                        "unit_price": pdata["price"],
                        "subtotal": pdata["price"] * qty,
                        "cost": pdata["cost"] * qty
                    })
                
                subtotal = sum(i["subtotal"] for i in sale_items)
                cost_total = sum(i["cost"] for i in sale_items)
                tax = subtotal * 0.16
                
                sale_date = datetime.now(timezone.utc) - timedelta(days=day_offset, hours=random.randint(0, 12))
                
                await db.sales.insert_one({
                    "id": str(uuid.uuid4()),
                    "cafeteria_id": cafe_id,
                    "items": sale_items,
                    "subtotal": round(subtotal, 2),
                    "tax": round(tax, 2),
                    "total": round(subtotal + tax, 2),
                    "cost_total": round(cost_total, 2),
                    "profit": round(subtotal - cost_total, 2),
                    "payment_method": random.choice(["efectivo", "tarjeta", "clip"]),
                    "clip_transaction_id": None,
                    "notes": None,
                    "created_by": admin_id,
                    "created_at": sale_date.isoformat()
                })
    
    return {"message": "Datos de prueba creados exitosamente", "admin_credentials": {"email": "admin@cafecontrol.com", "password": "admin123"}}

# Root endpoint
@api_router.get("/")
async def root():
    return {"message": "CaféControl API v1.0"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
