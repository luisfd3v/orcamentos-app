from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List

@dataclass
class ItemOrcamento:
    numero_nota: str
    codigo_produto: str
    deposito: str
    quantidade: Decimal
    valor_unitario: Decimal
    sequencia: int
    valor_desconto: Decimal = Decimal('0.0')
    total_bruto_item: Decimal = Decimal('0.0')
    custo: Decimal = Decimal('0.0')

@dataclass
class Orcamento:
    numero_nota: str
    codigo_cliente: str
    codigo_vendedor: str
    codigo_cond_pag: str
    data_emissao: datetime
    valor_total: Decimal
    hora_emissao: str = field(default_factory=lambda: datetime.now().strftime('%H:%M:%S'))
    itens: List[ItemOrcamento] = field(default_factory=list)
