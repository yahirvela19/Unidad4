import dataclasses
from decimal import Decimal

import pytest

from app.domain import (
    Customer, DomainEvent, InvalidOrderData, InvalidOrderTransition, Money,
    Order, OrderItem, OrderItemLimitExceeded, OrderStatus,
)
from app.specifications import (
    ActivePromotionSpec, MinimumAmountSpec, MinimumUnitsSpec, VIPCustomerSpec,
    discount_rate,
)
from cargar_csv import load_fixture


@pytest.fixture
def orders():
    return load_fixture()          # datos limpios en cada prueba


def estado_y_eventos(order):
    return order.status, len(order.events)


# ---------- Money ----------
def test_money_negativo():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-1"))


def test_money_no_finito():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("NaN"))


def test_money_es_inmutable():
    m = Money(Decimal("100"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.amount = Decimal("1")


def test_money_se_compara_por_valor():
    assert Money(Decimal("100"), "MXN") == Money(Decimal("100"), "MXN")


def test_money_add_devuelve_nuevo_objeto():
    a, b = Money(Decimal("100")), Money(Decimal("50"))
    assert a.add(b) == Money(Decimal("150"))
    assert a.amount == Decimal("100") and b.amount == Decimal("50")


def test_money_add_monedas_distintas():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("1"), "MXN").add(Money(Decimal("1"), "USD"))


# ---------- OrderItem ----------
@pytest.mark.parametrize("qty", [0, -1])
def test_item_cantidad_invalida(qty):
    with pytest.raises(InvalidOrderData):
        OrderItem("SKU001", qty, Money(Decimal("600.00")))


def test_item_sku_vacio():
    with pytest.raises(InvalidOrderData):
        OrderItem("  ", 1, Money(Decimal("600.00")))


def test_item_subtotal_se_calcula():
    item = OrderItem("SKU001", 2, Money(Decimal("600.00")))
    assert item.subtotal.amount == Decimal("1200.00")


# ---------- Datos cargados ----------
def test_16_pedidos_empiezan_en_draft(orders):
    assert len(orders) == 16
    assert all(o.status == OrderStatus.DRAFT for o in orders.values())


def test_o001_4_unidades_2100(orders):
    assert orders["O001"].units == 4
    assert orders["O001"].total.amount == Decimal("2100.00")


# ---------- Límite de 20 unidades ----------
def test_limite_cuenta_unidades_no_renglones(orders):
    # O008 tiene UN renglón con 20 unidades
    assert len(orders["O008"].items) == 1
    assert orders["O008"].units == 20


def test_21_unidades_se_rechaza_sin_modificar(orders):
    o = orders["O009"]                                   # 19 unidades
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
    assert o.units == 19 and len(o.items) == 1


def test_20_unidades_exactas_se_permite(orders):
    o = orders["O009"]
    o.add_item(OrderItem("SKU003", 1, Money(Decimal("120.00"))))
    assert o.units == 20


def test_no_se_agregan_articulos_fuera_de_draft(orders):
    o = orders["O013"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.add_item(OrderItem("SKU003", 1, Money(Decimal("120.00"))))


def test_solo_acepta_mxn(orders):
    with pytest.raises(InvalidOrderData):
        orders["O013"].add_item(OrderItem("SKU003", 1, Money(Decimal("5"), "USD")))


# ---------- confirm() ----------
def test_confirmar_pedido_vacio(orders):
    o = orders["O007"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert estado_y_eventos(o) == (OrderStatus.DRAFT, 0)


def test_confirmar_cliente_inactivo(orders):
    o = orders["O003"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert estado_y_eventos(o) == (OrderStatus.DRAFT, 0)


def test_confirmar_20_unidades(orders):
    o = orders["O008"]
    o.confirm()
    assert o.status == OrderStatus.CONFIRMED


def test_confirmacion_doble_no_agrega_evento(orders):
    o = orders["O013"]
    o.confirm()
    assert estado_y_eventos(o) == (OrderStatus.CONFIRMED, 1)
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert estado_y_eventos(o) == (OrderStatus.CONFIRMED, 1)


# ---------- ship() ----------
@pytest.mark.parametrize("guia", ["", "   ", None])
def test_envio_sin_guia(orders, guia):
    o = orders["O012"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.ship(guia)
    assert [e.name for e in o.events] == ["OrderConfirmed"]
    assert o.status == OrderStatus.CONFIRMED


def test_envio_desde_draft_no_permitido(orders):
    with pytest.raises(InvalidOrderTransition):
        orders["O012"].ship("GUIA-1")


# ---------- cancel() ----------
def test_cancelar_desde_shipped_no_permitido(orders):
    o = orders["O014"]
    o.confirm()
    o.ship("GUIA-1")
    with pytest.raises(InvalidOrderTransition):
        o.cancel("cambio de opinión")
    assert o.status == OrderStatus.SHIPPED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped"]


def test_cancelar_sin_motivo(orders):
    o = orders["O014"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.cancel("  ")
    assert o.status == OrderStatus.CONFIRMED


def test_cancelar_desde_confirmed(orders):
    o = orders["O014"]
    o.confirm()
    o.cancel("ya no lo quiero")
    assert o.status == OrderStatus.CANCELLED
    assert o.events[-1].name == "OrderCancelled"


# ---------- deliver() y return_order() ----------
def test_flujo_entrega(orders):
    o = orders["O016"]
    o.confirm(); o.ship("GUIA-1"); o.deliver()
    assert o.status == OrderStatus.DELIVERED
    assert [e.name for e in o.events] == [
        "OrderConfirmed", "OrderShipped", "OrderDelivered"]


def test_flujo_devolucion(orders):
    o = orders["O015"]
    o.confirm(); o.ship("GUIA-1"); o.return_order()
    assert o.status == OrderStatus.RETURNED
    assert o.events[-1].name == "OrderReturned"


@pytest.mark.parametrize("operacion", ["deliver", "return_order"])
def test_entregar_o_devolver_exigen_shipped(orders, operacion):
    o = orders["O016"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        getattr(o, operacion)()
    assert o.status == OrderStatus.CONFIRMED


def test_evento_tiene_id_de_pedido_y_fecha(orders):
    o = orders["O013"]
    o.confirm()
    ev = o.events[0]
    assert isinstance(ev, DomainEvent)
    assert ev.order_id == "O013" and ev.occurred_at is not None


# ---------- Specifications ----------
def test_specs_simples(orders):
    assert MinimumAmountSpec(500).is_satisfied_by(orders["O001"])
    assert VIPCustomerSpec().is_satisfied_by(orders["O001"])
    assert MinimumUnitsSpec(4).is_satisfied_by(orders["O001"])
    assert not ActivePromotionSpec().is_satisfied_by(orders["O001"])
    assert ActivePromotionSpec().is_satisfied_by(orders["O005"])


def test_umbral_estricto_500(orders):
    assert orders["O010"].total.amount == Decimal("500.00")
    assert not MinimumAmountSpec(500).is_satisfied_by(orders["O010"])


def test_composicion_and_or_not(orders):
    o001, o005 = orders["O001"], orders["O005"]
    vip, promo = VIPCustomerSpec(), ActivePromotionSpec()
    assert (vip & ~promo).is_satisfied_by(o001)        # AND + NOT
    assert not (vip & ~promo).is_satisfied_by(o005)
    assert (promo | vip).is_satisfied_by(o005)         # OR
    assert not (promo | MinimumUnitsSpec(99)).is_satisfied_by(o001)


def test_specification_no_modifica_el_pedido(orders):
    o = orders["O001"]
    antes = (o.status, len(o.items), len(o.events), o.total)
    discount_rate(o)
    assert (o.status, len(o.items), len(o.events), o.total) == antes


@pytest.mark.parametrize("pedido, esperado", [
    ("O001", "0.10"),   # E01: VIP, 2100, 4 u, sin promo
    ("O002", "0"),      # E02: no VIP, total < 5000
    ("O005", "0"),      # E04: promoción activa bloquea
    ("O006", "0.05"),   # E05: total 18000 > 5000, sin promo
    ("O010", "0"),      # E09: total exactamente 500
    ("O011", "0"),      # E10: solo 3 unidades
])
def test_descuentos_de_escenarios(orders, pedido, esperado):
    assert discount_rate(orders[pedido]) == Decimal(esperado)


def test_si_cumple_ambas_reglas_gana_el_10(orders):
    # VIP, sin promoción, 4 unidades y total > 5000 => aplica 10 %
    o = Order(customer=Customer("CX", is_vip=True), id="OX")
    o.add_item(OrderItem("SKU008", 4, Money(Decimal("18000.00"))))
    assert discount_rate(o) == Decimal("0.10")
