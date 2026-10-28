"""Ejecuta los 15 escenarios de datos/escenarios.csv y genera bitacora_escenarios.csv.
Uso (desde la raíz del proyecto):  python escenarios_run.py
"""
import csv
from decimal import Decimal

from cargar_csv import load_fixture, rows
from app.domain import DomainException, Money, OrderItem
from app.specifications import discount_rate


def precio(sku):
    for fila in rows("productos.csv"):
        if fila["sku"] == sku:
            return Decimal(fila["precio_mxn"])
    raise ValueError(f"SKU no encontrado: {sku}")


# --- Acciones: una función por cada texto de la columna "accion" ---
def evaluar_descuento(o):
    return f"descuento {discount_rate(o) * 100:.0f}%"

def confirmar(o):
    o.confirm()
    return "confirmado"

def agregar_sku003_x2(o):
    o.add_item(OrderItem("SKU003", 2, Money(precio("SKU003"))))
    return "artículo agregado"

def confirmar_y_enviar_sin_guia(o):
    o.confirm()
    o.ship("")
    return "enviado"

def confirmar_dos_veces(o):
    o.confirm()
    o.confirm()
    return "confirmado dos veces"

def confirmar_enviar_cancelar(o):
    o.confirm()
    o.ship("GUIA-001")
    o.cancel("cambio de opinión")
    return "cancelado"

def confirmar_enviar_devolver(o):
    o.confirm()
    o.ship("GUIA-001")
    o.return_order()
    return "devuelto"

def confirmar_enviar_entregar(o):
    o.confirm()
    o.ship("GUIA-001")
    o.deliver()
    return "entregado"


ACCIONES = {
    "evaluar_descuento":            evaluar_descuento,
    "confirmar":                    confirmar,
    "agregar SKU003 x2":            agregar_sku003_x2,
    "confirmar y enviar sin guia":  confirmar_y_enviar_sin_guia,
    "confirmar dos veces":          confirmar_dos_veces,
    "confirmar, enviar y cancelar": confirmar_enviar_cancelar,
    "confirmar, enviar y devolver": confirmar_enviar_devolver,
    "confirmar, enviar y entregar": confirmar_enviar_entregar,
}


def cumple(objetivo, resultado):
    if objetivo.endswith("%"):
        return resultado == f"descuento {objetivo}"
    if objetivo.startswith("rechazo"):
        return resultado.startswith("RECHAZADO")
    if objetivo == "exito":
        return not resultado.startswith("RECHAZADO")
    return False


def main():
    filas = []
    for c in rows("escenarios.csv"):
        accion = c["accion"]
        if accion not in ACCIONES:
            raise KeyError(f"{c['caso_id']}: acción sin implementar -> {accion!r}")

        order = load_fixture()[c["pedido_id"]]            # datos limpios en cada caso
        pre = (f"estado={order.status.value}; VIP={'sí' if order.customer.is_vip else 'no'}; "
               f"activo={'sí' if order.customer.active else 'no'}; "
               f"promo={'sí' if order.has_promotion else 'no'}; "
               f"{order.units} u / {order.total.amount} MXN")
        try:
            resultado = ACCIONES[accion](order)
        except DomainException as e:
            resultado = f"RECHAZADO ({type(e).__name__}): {e}"

        eventos = ", ".join(ev.name for ev in order.events) or "sin evento"
        veredicto = "OK" if cumple(c["objetivo"], resultado) else "FALLA"
        # La última columna (explicación) la escribes tú con tus palabras.
        filas.append([c["caso_id"], c["pedido_id"], pre, accion, resultado,
                      order.status.value, eventos, c["objetivo"], veredicto, ""])
        print(" | ".join(filas[-1][:-1]))

    with open("bitacora_escenarios.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["caso", "pedido", "precondiciones", "operacion",
                    "resultado_real", "estado_final", "eventos",
                    "objetivo", "veredicto", "explicacion"])
        w.writerows(filas)

    fallas = [fila[0] for fila in filas if fila[8] == "FALLA"]
    print(f"\n{len(filas) - len(fallas)}/{len(filas)} casos cumplen el objetivo.")
    if fallas:
        print("Revisar:", ", ".join(fallas))


if __name__ == "__main__":
    main()
