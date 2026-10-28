import pytest
from fastapi.testclient import TestClient

import app.api as api
from cargar_csv import load_fixture


@pytest.fixture(autouse=True)
def datos_limpios(monkeypatch):
    """Cada prueba arranca con los 16 pedidos en DRAFT (el estado vive en memoria)."""
    monkeypatch.setattr(api, "orders", load_fixture())


@pytest.fixture
def client():
    return TestClient(api.app)


def test_get_pedido_existente(client):
    r = client.get("/orders/O001")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "DRAFT" and body["units"] == 4
    assert body["total"] == "2100.00" and body["events"] == []


def test_get_pedido_inexistente_404(client):
    assert client.get("/orders/NOEXISTE").status_code == 404


def test_confirmar_inexistente_404(client):
    assert client.post("/orders/NOEXISTE/confirm").status_code == 404


def test_confirmar_ok_200(client):
    r = client.post("/orders/O013/confirm")
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"
    assert r.json()["events"] == ["OrderConfirmed"]


def test_confirmar_dos_veces_409(client):
    client.post("/orders/O013/confirm")
    r = client.post("/orders/O013/confirm")
    assert r.status_code == 409
    assert client.get("/orders/O013").json()["events"] == ["OrderConfirmed"]


def test_confirmar_pedido_vacio_422(client):
    assert client.post("/orders/O007/confirm").status_code == 422


def test_confirmar_cliente_inactivo_422(client):
    assert client.post("/orders/O003/confirm").status_code == 422


def test_enviar_sin_guia_422(client):
    client.post("/orders/O012/confirm")
    r = client.post("/orders/O012/ship", json={"tracking_number": ""})
    assert r.status_code == 422
    assert client.get("/orders/O012").json()["status"] == "CONFIRMED"


def test_enviar_sin_cuerpo_422(client):
    client.post("/orders/O012/confirm")
    assert client.post("/orders/O012/ship", json={}).status_code == 422


def test_enviar_ok(client):
    client.post("/orders/O012/confirm")
    r = client.post("/orders/O012/ship", json={"tracking_number": "GUIA-1"})
    assert r.status_code == 200 and r.json()["status"] == "SHIPPED"


def test_enviar_desde_draft_409(client):
    r = client.post("/orders/O012/ship", json={"tracking_number": "GUIA-1"})
    assert r.status_code == 409


def test_cancelar_desde_shipped_409(client):
    client.post("/orders/O014/confirm")
    client.post("/orders/O014/ship", json={"tracking_number": "GUIA-1"})
    r = client.post("/orders/O014/cancel", json={"reason": "cambio de opinión"})
    assert r.status_code == 409
    assert client.get("/orders/O014").json()["status"] == "SHIPPED"


def test_cancelar_sin_motivo_422(client):
    client.post("/orders/O014/confirm")
    r = client.post("/orders/O014/cancel", json={"reason": " "})
    assert r.status_code == 422


def test_cancelar_ok(client):
    client.post("/orders/O014/confirm")
    r = client.post("/orders/O014/cancel", json={"reason": "ya no lo quiero"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


def test_openapi_documenta_los_endpoints(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    rutas = r.json()["paths"]
    for ruta in ["/orders/{order_id}", "/orders/{order_id}/confirm",
                 "/orders/{order_id}/ship", "/orders/{order_id}/cancel"]:
        assert ruta in rutas
    assert client.get("/docs").status_code == 200
