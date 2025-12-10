from reportlab.lib import pagesizes, colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import os
import sys
import subprocess
import platform
from decimal import Decimal
from typing import Any, List

try:
    from .database import get_dados_empresa
except ImportError:
    from database import get_dados_empresa

UNIDADES_ABREVIADAS = {
    'UNIDADE': 'UN',
    'METRO': 'MT',
    'KILOGRAMA': 'KG',
    'LITRO': 'LT',
    'PECA': 'PÇ',
    'CAIXA': 'CX',
}

def _get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _abbreviate_unit(unit_name):
    return UNIDADES_ABREVIADAS.get(unit_name.upper(), unit_name[:3].upper())

def gerar_pdf_orcamento(orcamento, itens, cliente_info, vendedor_info, condicao_pagamento=None, desconto_aplicado=0.0, valor_final=None):
    base_path = _get_base_path()
    output_dir = os.path.join(base_path, 'Impressao')
    os.makedirs(output_dir, exist_ok=True)
    
    file_name = f"orcamento_{orcamento.numero_nota}.pdf"
    file_path = os.path.join(output_dir, file_name)
    
    doc = SimpleDocTemplate(file_path, pagesize=pagesizes.A4, 
                            leftMargin=1.5*cm, rightMargin=1.5*cm, 
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"Orçamento {orcamento.numero_nota}")
    
    story = []
    styles = getSampleStyleSheet()
    
    empresa_info = get_dados_empresa()
    if not empresa_info:
        return False

    header_data = [
        [
            Paragraph(f"<b>{empresa_info['nome']}</b>", styles['Normal']),
            Paragraph("<b>ORÇAMENTO</b>", ParagraphStyle('h1_right', parent=styles['h1'], alignment=TA_RIGHT))
        ],
        [
            Paragraph(empresa_info['endereco'], styles['Normal']),
            Paragraph(f"<b>Número:</b> {orcamento.numero_nota}", ParagraphStyle('p_right', parent=styles['Normal'], alignment=TA_RIGHT))
        ],
        [
            Paragraph(empresa_info['telefone'], styles['Normal']),
            Paragraph(f"<b>Data de Emissão:</b> {orcamento.data_emissao.strftime('%d/%m/%Y')}", ParagraphStyle('p_right', parent=styles['Normal'], alignment=TA_RIGHT))
        ]
    ]
    header_table = Table(header_data, colWidths=['70%', '30%'])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (0, 0), (0, 0)), 
        ('SPAN', (0, 1), (0, 1)),
        ('SPAN', (0, 2), (0, 2)),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.5*cm))

    dest_style = ParagraphStyle('dest_title', parent=styles['h3'], alignment=TA_CENTER, spaceAfter=6)
    story.append(Paragraph("DESTINATÁRIO", dest_style))
    
    if cliente_info and cliente_info.get('nome'):
        dest_data = [
            [Paragraph(f"<b>CLIENTE:</b> {cliente_info['nome']}", styles['Normal']), Paragraph(f"<b>CPF/CNPJ:</b> {cliente_info['cpf_cnpj']}", styles['Normal'])],
            [Paragraph(f"<b>ENDEREÇO:</b> {cliente_info['endereco']}", styles['Normal']), Paragraph(f"<b>TELEFONE:</b> {cliente_info['telefone']}", styles['Normal'])]
        ]
    else:
        dest_data = [
            [Paragraph("<b>CLIENTE:</b> <i>Não informado</i>", styles['Normal']), Paragraph("<b>CPF/CNPJ:</b> <i>Não informado</i>", styles['Normal'])],
            [Paragraph("<b>ENDEREÇO:</b> <i>Não informado</i>", styles['Normal']), Paragraph("<b>TELEFONE:</b> <i>Não informado</i>", styles['Normal'])]
        ]
    
    dest_table = Table(dest_data, colWidths=['50%', '50%'])
    dest_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(dest_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("PRODUTOS / SERVIÇOS", dest_style))
    
    table_header = ['ITEM', 'DESCRIÇÃO', 'QUANTIDADE', 'UNITÁRIO (R$)', 'TOTAL (R$)']
    table_data: List[List[Any]] = [table_header]
    
    for i, item in enumerate(itens, 1):
        qty_str = f"{item['quantidade']:.2f}".replace('.', ',')
        unit_str = _abbreviate_unit(item['unidade'])
        
        table_data.append([
            str(i),
            Paragraph(item['descricao'], styles['Normal']),
            f"{qty_str} {unit_str}",
            _format_currency(item['valor_unitario']),
            _format_currency(item['subtotal'])
        ])

    subtotal = sum(item['subtotal'] for item in itens)
    
    if valor_final is None:
        valor_final = orcamento.valor_total
    
    if desconto_aplicado > 0:
        subtotal_row = [
            '', '', '', Paragraph('<b>SUBTOTAL:</b>', ParagraphStyle('subtotal_label', parent=styles['Normal'], alignment=TA_RIGHT)),
            Paragraph(f"<b>{_format_currency(subtotal)}</b>", ParagraphStyle('subtotal_value', parent=styles['Normal'], alignment=TA_RIGHT))
        ]
        table_data.append(subtotal_row)
        
        desconto_row = [
            '', '', '', Paragraph('<b>DESCONTO:</b>', ParagraphStyle('desconto_label', parent=styles['Normal'], alignment=TA_RIGHT)),
            Paragraph(f"<b>- {_format_currency(desconto_aplicado)}</b>", ParagraphStyle('desconto_value', parent=styles['Normal'], alignment=TA_RIGHT, textColor=colors.red))
        ]
        table_data.append(desconto_row)
        
        total_row = [
            '', '', '', Paragraph('<b>TOTAL:</b>', ParagraphStyle('total_label', parent=styles['Normal'], alignment=TA_RIGHT)),
            Paragraph(f"<b>{_format_currency(valor_final)}</b>", ParagraphStyle('total_value', parent=styles['Normal'], alignment=TA_RIGHT))
        ]
        table_data.append(total_row)
    else:
        total_row = [
            '', '', '', Paragraph('<b>TOTAL:</b>', ParagraphStyle('total_label', parent=styles['Normal'], alignment=TA_RIGHT)),
            Paragraph(f"<b>{_format_currency(orcamento.valor_total)}</b>", ParagraphStyle('total_value', parent=styles['Normal'], alignment=TA_RIGHT))
        ]
        table_data.append(total_row)

    products_table = Table(table_data, colWidths=[1.5*cm, 8*cm, 2.5*cm, 3*cm, 3*cm])
    products_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        ('ALIGN', (0, 1), (0, -1), 'CENTER'), 
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        
        ('FONTNAME', (3, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(products_table)
    story.append(Spacer(1, 0.8*cm))

    info_adicional = [
        [Paragraph(f"<b>VENDEDOR:</b> {vendedor_info['nome']}", styles['Normal'])],
    ]
    
    if condicao_pagamento:
        info_adicional.append([Paragraph(f"<b>FORMA DE PAGAMENTO:</b> {condicao_pagamento}", styles['Normal'])])
    
    info_adicional.append([Paragraph("<b>VALIDADE DA PROPOSTA:</b> ___________________", styles['Normal'])])
    
    info_table = Table(info_adicional, colWidths=[18*cm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)

    story.append(Spacer(1, 0.5*cm))
    
    obs_style = ParagraphStyle('obs_style', parent=styles['Normal'], fontSize=10)
    story.append(Paragraph("<b>OBSERVAÇÕES:</b>", obs_style))
    story.append(Spacer(1, 0.2*cm))
    
    line_drawing = Table([['_' * 95], ['_' * 95], ['_' * 95]], colWidths=[18*cm])
    line_drawing.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
    ]))
    story.append(line_drawing)

    story.append(Spacer(1, 1.5*cm))
    
    disclaimer_style = ParagraphStyle('disclaimer', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, textColor=colors.grey)
    story.append(Paragraph("<b>ESTE DOCUMENTO NÃO TEM VALIDADE FISCAL</b>", disclaimer_style))

    try:
        doc.build(story)
        abrir_pdf(file_path)
        return True
    except Exception as e:
        return False

def abrir_pdf(file_path):
    try:
        sistema = platform.system()
        if sistema == "Windows":
            os.startfile(file_path)
        elif sistema == "Darwin":
            subprocess.run(['open', file_path], check=True)
        else:
            subprocess.run(['xdg-open', file_path], check=True)
    except Exception as e:
        pass
