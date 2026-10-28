from decimal import Decimal


class Specification:
    """Regla de negocio evaluable y combinable. No modifica el pedido."""

    def is_satisfied_by(self, order):
        raise NotImplementedError

    def __and__(self, other):
        return AndSpec(self, other)

    def __or__(self, other):
        return OrSpec(self, other)

    def __invert__(self):
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, left, right):
        self.left, self.right = left, right

    def is_satisfied_by(self, order):
        return (self.left.is_satisfied_by(order)
                and self.right.is_satisfied_by(order))


class OrSpec(Specification):
    def __init__(self, left, right):
        self.left, self.right = left, right

    def is_satisfied_by(self, order):
        return (self.left.is_satisfied_by(order)
                or self.right.is_satisfied_by(order))


class NotSpec(Specification):
    def __init__(self, spec):
        self.spec = spec

    def is_satisfied_by(self, order):
        return not self.spec.is_satisfied_by(order)


# --- Reglas simples ---
class MinimumAmountSpec(Specification):
    """Total ESTRICTAMENTE mayor que el mínimo (>, no >=)."""

    def __init__(self, minimum):
        self.minimum = Decimal(minimum)

    def is_satisfied_by(self, order):
        return order.total.amount > self.minimum


class VIPCustomerSpec(Specification):
    def is_satisfied_by(self, order):
        return order.customer.is_vip


class MinimumUnitsSpec(Specification):
    """Al menos N unidades (>=). Cuenta unidades, no renglones."""

    def __init__(self, minimum):
        self.minimum = minimum

    def is_satisfied_by(self, order):
        return order.units >= self.minimum


class ActivePromotionSpec(Specification):
    def is_satisfied_by(self, order):
        return order.has_promotion


# --- Reglas compuestas de descuento ---
# 10 %: VIP, total > 500, al menos 4 unidades y SIN promoción activa.
TEN_PERCENT_RULE = (
    MinimumAmountSpec(500)
    & VIPCustomerSpec()
    & MinimumUnitsSpec(4)
    & ~ActivePromotionSpec()
)

# 5 %: total > 5000 y SIN promoción activa.
FIVE_PERCENT_RULE = MinimumAmountSpec(5000) & ~ActivePromotionSpec()

# Cualquiera de las dos reglas (composición OR).
ANY_DISCOUNT_RULE = TEN_PERCENT_RULE | FIVE_PERCENT_RULE


def discount_rate(order):
    """Devuelve 0.10, 0.05 o 0. Si ambas reglas aplican, gana el 10 %."""
    if not ANY_DISCOUNT_RULE.is_satisfied_by(order):
        return Decimal("0")
    if TEN_PERCENT_RULE.is_satisfied_by(order):
        return Decimal("0.10")
    return Decimal("0.05")
