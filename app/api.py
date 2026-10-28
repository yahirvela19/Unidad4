from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cargar_csv import load_fixture
from app.domain import (
    InvalidOrderTransition, InvalidOrderData, OrderItemLimitExceeded,
)

app = FastAPI(title="TechStore U4")
orders = load_fixture()


# --- Cuerpos de petición (DTO) ---
class ShipRequest(BaseModel):
    tracking_number: str

class CancelRequest(BaseModel):
    reason: str


# --- Funciones de apoyo (no contienen reglas de negocio) ---
def get_order_or_404(order_id: str):
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="No existe")
    return order


def run_domain_action(action):
    """Ejecuta una operación del dominio y traduce sus excepciones a HTTP."""
    try:
        action()
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (InvalidOrderData, OrderItemLimitExceeded) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def order_to_dto(order):
    return {
        "id": order.id,
        "status": order.status.value,
        "customer_id": order.customer.id,
        "units": order.units,
        "total": str(order.total.amount),
        "currency": order.total.currency,
        "events": [e.name for e in order.events],
    }


# --- Endpoints ---
@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return order_to_dto(get_order_or_404(order_id))


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str):
    order = get_order_or_404(order_id)
    run_domain_action(order.confirm)
    return order_to_dto(order)


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, body: ShipRequest):
    order = get_order_or_404(order_id)
    run_domain_action(lambda: order.ship(body.tracking_number))
    return order_to_dto(order)


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, body: CancelRequest):
    order = get_order_or_404(order_id)
    run_domain_action(lambda: order.cancel(body.reason))
    return order_to_dto(order)
