import pyodbc
import configparser
import os
import sys
from decimal import Decimal
import urllib.parse

try:
    from .models import Orcamento, ItemOrcamento
except ImportError:
    from models import Orcamento, ItemOrcamento

def get_config_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        config_path = os.path.join(base_path, 'config.ini')
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_path, 'config', 'config.ini')
    return config_path

def get_terminal_config():
    config = configparser.ConfigParser()
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return '01'
    
    config.read(config_path, encoding='utf-8')
    return config.get('Application', 'terminal', fallback='01')

def get_deposito_config():
    config = configparser.ConfigParser()
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return '01'
    
    config.read(config_path, encoding='utf-8')
    return config.get('Application', 'deposito', fallback='01')

def get_empresa_config():
    config = configparser.ConfigParser()
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return '01'
    
    config.read(config_path, encoding='utf-8')
    return config.get('Application', 'empresa', fallback='01')

def calcular_senha_dinamica(formula_senha):
    from datetime import datetime
    hoje = datetime.now()
    
    try:
        if not formula_senha:
            return str(hoje.day)
        
        formula = formula_senha.strip()
        
        import re
        formula_calculada = formula
        formula_calculada = re.sub(r'\bAno\b', str(hoje.year), formula_calculada, flags=re.IGNORECASE)
        formula_calculada = re.sub(r'\bMes\b', str(hoje.month), formula_calculada, flags=re.IGNORECASE)
        formula_calculada = re.sub(r'\bDia\b', str(hoje.day), formula_calculada, flags=re.IGNORECASE)
        formula_calculada = re.sub(r'\bHora\b', str(hoje.hour), formula_calculada, flags=re.IGNORECASE)
        formula_calculada = re.sub(r'\bMinuto\b', str(hoje.minute), formula_calculada, flags=re.IGNORECASE)
        
        formula_calculada = formula_calculada.replace(' ', '')
        
        if re.match(r'^[\d\+\-\*/\(\)]+$', formula_calculada):
            resultado = eval(formula_calculada)
            return str(int(resultado))
        else:
            senha = re.sub(r'[^\d]', '', formula_calculada)
            return senha if senha else str(hoje.day)
        
    except Exception as e:
        print(f" Erro ao calcular senha dinâmica: {str(e)}")
        return str(hoje.day) 

def get_desconto_vendedor(codigo_usuario, codigo_vendedor=None):
    conn = get_db_connection()
    if not conn:
        return {'desconto_max': 0.0, 'vendedor_encontrado': False}
    
    try:
        cursor = conn.cursor()
        
        vendedor_codigo = codigo_vendedor or codigo_usuario
        
        cursor.execute("""
            SELECT PERCENTMAX_GUD, CODUSUARIO_GUD, CODVENDEDOR_GUD
            FROM GE_USUARIOS_DESCONTOVENDEDOR 
            WHERE CODUSUARIO_GUD = ? OR CODVENDEDOR_GUD = ?
        """, (codigo_usuario, vendedor_codigo))
        
        resultado = cursor.fetchone()
        
        if resultado:
            desconto_max, cod_usuario, cod_vendedor = resultado
            
            cursor.close()
            return {
                'desconto_max': float(desconto_max or 0),
                'vendedor_encontrado': True,
                'codigo_usuario': cod_usuario,
                'codigo_vendedor': cod_vendedor
            }
        else:
            cursor.close()
            return {'desconto_max': 0.0, 'vendedor_encontrado': False}
            
    except Exception as e:
        return {'desconto_max': 0.0, 'vendedor_encontrado': False}
    finally:
        if conn:
            conn.close()

def get_usuarios_sistema():
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COD_USR,
                LOGIN_USR,
                NOME_USR,
                STATUS_USR
            FROM USUARIOS 
            WHERE STATUS_USR = 'S'
            AND LOGIN_USR IS NOT NULL
            ORDER BY NOME_USR
        """)
        
        usuarios = []
        for linha in cursor.fetchall():
            cod_usr, login_usr, nome_usr, status = linha
            usuarios.append({
                'codigo': cod_usr,
                'login': login_usr,
                'nome': nome_usr,
                'status': status
            })
        
        cursor.close()
        return usuarios
        
    except Exception as e:
        return []
    finally:
        if conn:
            conn.close()

def get_desconto_config():
    from datetime import datetime
    
    conn = get_db_connection()
    if not conn: 
        senha_hoje = str(datetime.now().day)
        return {'limite_sem_senha': 5.0, 'senha_liberacao': senha_hoje, 'habilitar_desconto': True, 'formula_senha': 'Dia'}
    
    try:
        cursor = conn.cursor()
        
        formula_senha = 'Dia'
        senha_calculada = str(datetime.now().day)
        
        try:
            cursor.execute("SELECT BI_PGE FROM APARAMGE WHERE BI_PGE IS NOT NULL")
            resultado = cursor.fetchone()
            
            if resultado and resultado[0]:
                formula_senha = resultado[0].strip()
                senha_calculada = calcular_senha_dinamica(formula_senha)
                print(f"✓ Fórmula de senha encontrada em APARAMGE.BI_PGE: '{formula_senha}'")
            else:
                print(f"⚠ Nenhuma fórmula encontrada em APARAMGE.BI_PGE, usando padrão: 'Dia'")
                        
        except Exception as e:
            print(f"⚠ Erro ao buscar fórmula de senha em APARAMGE.BI_PGE: {str(e)}")
            print(f"  Usando fórmula padrão: 'Dia'")
        
        desconto_habilitado = True
        limite_desconto = 5.0
        
        try:
            cursor.execute("SELECT DescontoArquivo_PGE FROM APARAMGE")
            resultado = cursor.fetchone()
            if resultado:
                desconto_habilitado = resultado[0] == 'S'
        except:
            pass
        
        try:
            cursor.execute("""
                SELECT AVG(CAST(DescontoMaximo AS FLOAT))
                FROM CE_PRODUTOS_ADICIONAIS 
                WHERE DescontoMaximo IS NOT NULL AND DescontoMaximo > 0
            """)
            resultado = cursor.fetchone()
            if resultado and resultado[0]:
                limite_desconto = min(float(resultado[0]), 15.0)
        except:
            pass
        
        try:
            cursor.execute("SELECT COUNT(*) FROM GE_USUARIOS_DESCONTOVENDEDOR")
            resultado = cursor.fetchone()
            count_vendedores = resultado[0] if resultado else 0
        except:
            count_vendedores = 0
        
        config = {
            'limite_sem_senha': limite_desconto,
            'senha_liberacao': senha_calculada,
            'habilitar_desconto': desconto_habilitado,
            'formula_senha': formula_senha,
            'tem_desconto_vendedor': count_vendedores > 0,
            'total_vendedores_especiais': count_vendedores
        }
        
        print(f"═══════════════════════════════════════════════════════")
        print(f"📋 Configurações de desconto carregadas do sistema legado:")
        print(f"   • Fórmula da senha: '{config['formula_senha']}'")
        print(f"   • Senha calculada para hoje: '{config['senha_liberacao']}'")
        print(f"   • Limite sem senha: {config['limite_sem_senha']}%")
        print(f"   • Desconto habilitado: {config['habilitar_desconto']}")
        print(f"   • Vendedores especiais: {config['total_vendedores_especiais']}")
        print(f"   • Fonte: Tabela APARAMGE (campo BI_PGE)")
        print(f"═══════════════════════════════════════════════════════")
        
        cursor.close()
        return config
        
    except Exception as e:
        print(f"❌ Erro ao buscar configurações de desconto: {str(e)}")
    finally:
        if conn: 
            conn.close()
    
    print("⚠ Usando configurações padrão de desconto")
    senha_padrao = str(datetime.now().day)
    return {'limite_sem_senha': 5.0, 'senha_liberacao': senha_padrao, 'habilitar_desconto': True, 'formula_senha': 'dia'}

def get_db_connection():
    config = configparser.ConfigParser()
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        print(f"Erro: Arquivo de configuração não encontrado em: {config_path}")
        return None
    
    config.read(config_path, encoding='utf-8')

    if 'Database' not in config:
        print("Erro: Seção [Database] não encontrada no arquivo config.ini")
        return None

    db_config = config['Database']
    server = db_config.get('server')
    database = db_config.get('database')
    username = db_config.get('username')
    password = db_config.get('password')
    driver = db_config.get('driver')

    caracteres_especiais = ['ç', '*', '&', '%', '=', ';', '+', '<', '>', '|', '"', "'"]
    tem_caracteres_especiais = password and any(char in password for char in caracteres_especiais)
    
    try:
        if tem_caracteres_especiais:
            conn_str = (
                f'DRIVER={driver};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'TrustServerCertificate=yes;'
            )
            conn = pyodbc.connect(conn_str, password=password, autocommit=False)
        else:
            conn_str = (
                f'DRIVER={driver};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password};'
                f'TrustServerCertificate=yes;'
            )
            conn = pyodbc.connect(conn_str, autocommit=False)
        
        return conn
        
    except pyodbc.Error as ex:
        print(f"Erro de conexão com o banco de dados: {ex}")
        return None
def get_proximo_numero_orcamento():
    conn = get_db_connection()
    if not conn: return "Erro"
    
    terminal = get_terminal_config()
    
    try:
        cursor = conn.cursor()
        query = f"SELECT MAX(AA_NFA) FROM ANOTASNO WHERE AO_NFA='{terminal}'"
        cursor.execute(query)
        result = cursor.fetchone()
        if result and result[0]:
            ultimo_numero_str = result[0]
            proximo_numero = int(ultimo_numero_str) + 1
        else:
            proximo_numero = 1
        return f"{proximo_numero:06d}"
    except pyodbc.Error as ex:
        print(f"Erro ao buscar próximo número do orçamento: {ex}")
        return "Erro"
    finally:
        if conn: conn.close()

def get_vendedores():
    conn = get_db_connection()
    if not conn: return []
    vendedores = []
    try:
        cursor = conn.cursor()
        query = "SELECT CODIGO_VEN, NOME_VEN FROM AVENDEGE ORDER BY CODIGO_VEN"
        cursor.execute(query)
        for row in cursor.fetchall():
            vendedores.append({
                'codigo': row.CODIGO_VEN.strip() if row.CODIGO_VEN else '', 
                'nome': row.NOME_VEN.strip() if row.NOME_VEN else ''
            })
        return vendedores
    except pyodbc.Error as ex:
        print(f"Erro ao buscar vendedores: {ex}")
        return []
    finally:
        if conn: conn.close()

def buscar_clientes(codigo=None, nome=None, termo_inteligente=None):
    conn = get_db_connection()
    if not conn: return []
    clientes = []
    try:
        cursor = conn.cursor()
        query = "SELECT CODIGO_CLI, NOME_CLI, CGCCPF_CLI, ENDER_CLI, NUMER_CLI, DDD_CLI, TELEF_CLI FROM ACLIENGE"
        params = []
        
        if termo_inteligente:
            query += " WHERE (CODIGO_CLI LIKE ? OR UPPER(NOME_CLI) LIKE ?)"
            termo_upper = f"%{termo_inteligente.upper()}%"
            params.extend([f"%{termo_inteligente}%", termo_upper])
        elif codigo:
            query += " WHERE CODIGO_CLI = ?"
            params.append(codigo)
        elif nome:
            query += " WHERE UPPER(NOME_CLI) LIKE ?"
            params.append(f"%{nome.upper()}%")
            
        query += " ORDER BY NOME_CLI"
        
        cursor.execute(query, *params)
        for row in cursor.fetchall():
            endereco = f"{row.ENDER_CLI.strip() if row.ENDER_CLI else ''}, {row.NUMER_CLI.strip() if row.NUMER_CLI else ''}"
            telefone = f"({row.DDD_CLI.strip() if row.DDD_CLI else ''}) {row.TELEF_CLI.strip() if row.TELEF_CLI else ''}"
            clientes.append({
                'codigo': row.CODIGO_CLI.strip() if row.CODIGO_CLI else '', 
                'nome': row.NOME_CLI.strip() if row.NOME_CLI else '',
                'cpf_cnpj': row.CGCCPF_CLI.strip() if row.CGCCPF_CLI else '',
                'endereco': endereco,
                'telefone': telefone
            })
        
        if termo_inteligente and clientes:
            clientes = sorted(clientes, key=lambda c: _get_search_priority(c, termo_inteligente))
            
        return clientes
    except pyodbc.Error as ex:
        print(f"Erro ao buscar clientes: {ex}")
        return []
    finally:
        if conn: conn.close()

def get_cliente_por_codigo(codigo):
    codigo_formatado = codigo.zfill(5)
    clientes = buscar_clientes(codigo=codigo_formatado)
    return clientes[0] if clientes else None

def get_condicoes_pagamento():
    conn = get_db_connection()
    if not conn: return []
    condicoes = []
    try:
        cursor = conn.cursor()
        query = "SELECT CODIGO_CPG, DESCRI_CPG FROM ACONPGFA WHERE (COND_CPG <> 'S' OR COND_CPG IS NULL) ORDER BY CODIGO_CPG"
        cursor.execute(query)
        for row in cursor.fetchall():
            condicoes.append({
                'codigo': row.CODIGO_CPG.strip() if row.CODIGO_CPG else '', 
                'descricao': row.DESCRI_CPG.strip() if row.DESCRI_CPG else ''
            })
        return condicoes
    except pyodbc.Error as ex:
        print(f"Erro ao buscar condições de pagamento: {ex}")
        return []
    finally:
        if conn: conn.close()

def get_condicoes_pagamento_detalhadas():
    conn = get_db_connection()
    if not conn: return []
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            CODIGO_CPG AS codigo,
            DESCRI_CPG AS descricao,
            PEDECLI_CPG AS exige_cliente,
            VISPRA_CPG AS tipo_pagamento,
            CASE VISPRA_CPG 
                WHEN 1 THEN 'A VISTA'
                WHEN 2 THEN 'A PRAZO'
                WHEN 3 THEN 'CHEQUE'
                WHEN 4 THEN 'CHEQUE PRE'
                WHEN 5 THEN 'CARTAO CREDITO'
                WHEN 6 THEN 'OUTROS'
                WHEN 7 THEN 'CARTAO DEBITO'
                WHEN 8 THEN 'TRANSFERENCIA'
                WHEN 9 THEN 'PAGAMENTO DIGITAL'
            END AS tipo_descricao
        FROM ACONPGFA 
        WHERE CODIGO_CPG <> ''
        ORDER BY CODIGO_CPG
        """
        
        cursor.execute(query)
        condicoes = []
        
        for row in cursor.fetchall():
            condicoes.append({
                'codigo': row.codigo.strip() if row.codigo else '',
                'descricao': row.descricao.strip() if row.descricao else '',
                'exige_cliente': row.exige_cliente.strip() if row.exige_cliente else 'S',
                'tipo_pagamento': row.tipo_pagamento,
                'tipo_descricao': row.tipo_descricao,
                'permite_sem_cliente': row.exige_cliente.strip() == 'N' if row.exige_cliente else False
            })
        return condicoes
        
    except pyodbc.Error as ex:
        print(f"Erro ao buscar condições de pagamento detalhadas: {ex}")
        return []
    finally:
        if conn: conn.close()

def condicao_permite_sem_cliente(codigo_condicao):
    conn = get_db_connection()
    if not conn: return False
    
    try:
        cursor = conn.cursor()
        query = "SELECT PEDECLI_CPG FROM ACONPGFA WHERE CODIGO_CPG = ?"
        cursor.execute(query, codigo_condicao)
        row = cursor.fetchone()
        
        if row and row.PEDECLI_CPG:
            return row.PEDECLI_CPG.strip() == 'N'
        
        return False
        
    except pyodbc.Error as ex:
        print(f"Erro ao verificar condição de pagamento {codigo_condicao}: {ex}")
        return False
    finally:
        if conn: conn.close()

def _get_search_priority(item, termo_busca):
    termo_lower = termo_busca.lower()
    
    if 'codigo' in item and 'descricao' in item:
        codigo = item['codigo'].lower()
        descricao = item['descricao'].lower()
        
        if codigo == termo_lower:
            return (1, codigo)
        
        if codigo.startswith(termo_lower):
            return (2, codigo)
        
        if descricao == termo_lower:
            return (3, descricao)
        
        if descricao.startswith(termo_lower):
            return (4, descricao)
        
        if termo_lower in codigo:
            return (5, codigo)
        
        if termo_lower in descricao:
            return (6, descricao)
    
    elif 'codigo' in item and 'nome' in item:
        codigo = item['codigo'].lower()
        nome = item['nome'].lower()
        
        if codigo == termo_lower:
            return (1, codigo)
        
        if codigo.startswith(termo_lower):
            return (2, codigo)
        
        if nome == termo_lower:
            return (3, nome)
        
        if nome.startswith(termo_lower):
            return (4, nome)
        
        if termo_lower in codigo:
            return (5, codigo)
        
        if termo_lower in nome:
            return (6, nome)
    
    return (7, item.get('codigo', '').lower() or item.get('nome', '').lower())

def buscar_produtos(codigo=None, nome=None, termo_inteligente=None):
    conn = get_db_connection()
    if not conn: return []
    produtos = []
    try:
        cursor = conn.cursor()
        query = """
            SELECT p.AU_ITE, p.AB_ITE, u.AB_UNI, pa.PrecoVendaMax, pa.CustoMedio
            FROM CE_PRODUTO p
            LEFT JOIN AUNIDACE u ON p.AH_ITE = u.AA_UNI
            LEFT JOIN CE_PRODUTOS_ADICIONAIS pa ON p.AU_ITE = pa.CodReduzido
        """
        params = []

        if termo_inteligente:
            query += " WHERE (p.AU_ITE LIKE ? OR UPPER(p.AB_ITE) LIKE ?)"
            termo_upper = f"%{termo_inteligente.upper()}%"
            params.extend([f"%{termo_inteligente}%", termo_upper])
        elif codigo:
            query += " WHERE p.AU_ITE = ?"
            params.append(codigo)
        elif nome:
            query += " WHERE UPPER(p.AB_ITE) LIKE ?"
            params.append(f"%{nome.upper()}%")

        query += " ORDER BY p.AB_ITE"
        cursor.execute(query, *params)

        for row in cursor.fetchall():
            produtos.append({
                'codigo': row.AU_ITE.strip() if row.AU_ITE else '',
                'descricao': row.AB_ITE.strip() if row.AB_ITE else '',
                'unidade': row.AB_UNI.strip() if row.AB_UNI else 'UN',
                'preco': Decimal(row.PrecoVendaMax or '0.0'),
                'custo': Decimal(row.CustoMedio or '0.0')
            })
        
        if termo_inteligente and produtos:
            produtos = sorted(produtos, key=lambda p: _get_search_priority(p, termo_inteligente))
            
        return produtos
    except pyodbc.Error as ex:
        print(f"Erro ao buscar produtos: {ex}")
        return []
    finally:
        if conn: conn.close()

def get_produto_por_codigo(codigo):
    produtos = buscar_produtos(codigo=codigo)
    return produtos[0] if produtos else None

def salvar_orcamento(orcamento: Orcamento, itens: list[ItemOrcamento]):
    conn = get_db_connection()
    if not conn:
        return False, "Não foi possível conectar ao banco de dados."
    
    terminal = get_terminal_config()
    
    try:
        cursor = conn.cursor()
        
        sql_anotasno = """
            INSERT INTO ANOTASNO (
                AA_NFA, AB_NFA, AC_NFA, AD_NFA, AE_NFA, AF_NFA, AG_NFA, AH_NFA, 
                AI_NFA, AK_NFA, AL_NFA, AN_NFA, AP_NFA, AO_NFA, AZ_NFA, BC_NFA, 
                BD_NFA, BG_NFA, BH_NFA, PROMOTOR_NFA, BI_NFA, BJ_NFA, ENTRADADUP_NFA, 
                OBSENTREGA_NFA, NotaEmLancto_NFA, ORIGEM_NFA, LEITURA_NFA
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_anotasno = (
            orcamento.numero_nota, orcamento.codigo_cliente, orcamento.data_emissao,
            orcamento.codigo_cond_pag, orcamento.codigo_vendedor, '8', orcamento.data_emissao,
            orcamento.data_emissao, orcamento.valor_total, '1', orcamento.hora_emissao,
            orcamento.data_emissao, Decimal('0.0'), terminal, '', None, '', None, 'N', '',
            Decimal('0.0'), Decimal('0.0'), 'N', None, 'S', 'N', 'N'
        )
        cursor.execute(sql_anotasno, params_anotasno)

        sql_aproduno = """
            INSERT INTO APRODUNO (
                AA_PCA, AL_PCA, AB_PCA, AC_PCA, AD_PCA, AE_PCA, AF_PCA, AG_PCA, AI_PCA, AK_PCA, 
                AN_PCA, AO_PCA, AP_PCA, AQ_PCA, QTDE_PCA, AR_PCA, AS_PCA, AT_PCA, AU_PCA, 
                AV_PCA, AX_PCA, AY_PCA, AZ_PCA, BB_PCA
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for item in itens:
            params_aproduno = (
                item.numero_nota, terminal, item.codigo_produto, item.deposito,
                item.quantidade, item.valor_unitario, item.valor_desconto,
                item.total_bruto_item, item.sequencia, item.custo, item.total_bruto_item,
                Decimal('0.0'), Decimal('0.0'), Decimal('0.0'), Decimal('0.0'),
                Decimal('0.0'), '', 'N', Decimal('0.0'), Decimal('0.0'),
                Decimal('0.0'), '', Decimal('0.0'), 'N'
            )
            cursor.execute(sql_aproduno, params_aproduno)

        sql_finalizar = f"UPDATE ANOTASNO SET NotaEmLancto_NFA = 'N' WHERE AA_NFA = ? AND AO_NFA = '{terminal}'"
        cursor.execute(sql_finalizar, orcamento.numero_nota)

        conn.commit()
        return True, "Orçamento salvo com sucesso!"
    except pyodbc.Error as ex:
        conn.rollback()
        print(f"Erro ao salvar orçamento: {ex}")
        return False, f"Erro ao salvar no banco de dados: {ex}"
    finally:
        if conn: conn.close()

def get_orcamento_cabecalho(numero_nota):
    conn = get_db_connection()
    if not conn: return None
    
    terminal = get_terminal_config()
    
    try:
        cursor = conn.cursor()
        query = "SELECT AB_NFA, AE_NFA, AD_NFA, AF_NFA FROM ANOTASNO WHERE AA_NFA = ? AND AO_NFA = ?"
        cursor.execute(query, numero_nota, terminal)
        row = cursor.fetchone()
        if row:
            return {
                'codigo_cliente': row.AB_NFA.strip() if row.AB_NFA else '',
                'codigo_vendedor': row.AE_NFA.strip() if row.AE_NFA else '',
                'codigo_cond_pag': row.AD_NFA.strip() if row.AD_NFA else '',
                'status': row.AF_NFA.strip() if row.AF_NFA else ''
            }
        return None
    except pyodbc.Error as ex:
        print(f"Erro ao buscar cabeçalho do orçamento {numero_nota}: {ex}")
        return None
    finally:
        if conn: conn.close()

def get_orcamento_itens(numero_nota):
    conn = get_db_connection()
    if not conn: return []
    
    terminal = get_terminal_config()
    
    itens = []
    try:
        cursor = conn.cursor()
        query = """
            SELECT p.AB_PCA, p.AD_PCA, p.AE_PCA, p.AF_PCA, pr.AB_ITE, u.AB_UNI, pa.CustoMedio
            FROM APRODUNO p
            LEFT JOIN CE_PRODUTO pr ON p.AB_PCA = pr.AU_ITE
            LEFT JOIN AUNIDACE u ON pr.AH_ITE = u.AA_UNI
            LEFT JOIN CE_PRODUTOS_ADICIONAIS pa ON p.AB_PCA = pa.CodReduzido
            WHERE p.AA_PCA = ? AND p.AL_PCA = ?
        """
        cursor.execute(query, numero_nota, terminal)
        for row in cursor.fetchall():
            quantidade = Decimal(row.AD_PCA or '0.0')
            preco = Decimal(row.AE_PCA or '0.0')
            desconto = Decimal(row.AF_PCA or '0.0')
            itens.append({
                'codigo': row.AB_PCA.strip() if row.AB_PCA else '',
                'descricao': row.AB_ITE.strip() if row.AB_ITE else '',
                'quantidade': quantidade,
                'unidade': row.AB_UNI.strip() if row.AB_UNI else 'UN',
                'preco': preco,
                'custo': Decimal(row.CustoMedio or '0.0'),
                'subtotal': quantidade * preco,
                'desconto': desconto
            })
        return itens
    except pyodbc.Error as ex:
        print(f"Erro ao buscar itens do orçamento {numero_nota}: {ex}")
        return []
    finally:
        if conn: conn.close()

def atualizar_orcamento(orcamento: Orcamento, itens: list[ItemOrcamento]):
    conn = get_db_connection()
    if not conn:
        return False, "Não foi possível conectar ao banco de dados."
    
    terminal = get_terminal_config()
    
    try:
        cursor = conn.cursor()

        query_status = f"SELECT AF_NFA FROM ANOTASNO WHERE AA_NFA = ? AND AO_NFA = '{terminal}'"
        cursor.execute(query_status, orcamento.numero_nota)
        status_row = cursor.fetchone()

        if status_row and status_row[0] != '8':
            return False, "Este orçamento já foi convertido em venda e não pode ser alterado."

        sql_delete_itens = f"DELETE FROM APRODUNO WHERE AA_PCA = ? AND AL_PCA = '{terminal}'"
        cursor.execute(sql_delete_itens, orcamento.numero_nota)

        sql_update_anotasno = f"""
            UPDATE ANOTASNO SET
                AB_NFA = ?, AE_NFA = ?, AD_NFA = ?, AI_NFA = ?, NotaEmLancto_NFA = 'S'
            WHERE AA_NFA = ? AND AO_NFA = '{terminal}'
        """
        params_update = (
            orcamento.codigo_cliente, orcamento.codigo_vendedor,
            orcamento.codigo_cond_pag, orcamento.valor_total, orcamento.numero_nota
        )
        cursor.execute(sql_update_anotasno, params_update)

        sql_aproduno = """
            INSERT INTO APRODUNO (
                AA_PCA, AL_PCA, AB_PCA, AC_PCA, AD_PCA, AE_PCA, AF_PCA, AG_PCA, AI_PCA, AK_PCA, 
                AN_PCA, AO_PCA, AP_PCA, AQ_PCA, QTDE_PCA, AR_PCA, AS_PCA, AT_PCA, AU_PCA, 
                AV_PCA, AX_PCA, AY_PCA, AZ_PCA, BB_PCA
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for item in itens:
            params_aproduno = (
                item.numero_nota, terminal, item.codigo_produto, item.deposito,
                item.quantidade, item.valor_unitario, item.valor_desconto,
                item.total_bruto_item, item.sequencia, item.custo, item.total_bruto_item,
                Decimal('0.0'), Decimal('0.0'), Decimal('0.0'), Decimal('0.0'),
                Decimal('0.0'), '', 'N', Decimal('0.0'), Decimal('0.0'),
                Decimal('0.0'), '', Decimal('0.0'), 'N'
            )
            cursor.execute(sql_aproduno, params_aproduno)

        sql_finalizar = f"UPDATE ANOTASNO SET NotaEmLancto_NFA = 'N' WHERE AA_NFA = ? AND AO_NFA = '{terminal}'"
        cursor.execute(sql_finalizar, orcamento.numero_nota)

        conn.commit()
        return True, "Orçamento atualizado com sucesso!"
    except pyodbc.Error as ex:
        conn.rollback()
        print(f"Erro ao atualizar orçamento: {ex}")
        return False, f"Erro ao atualizar no banco de dados: {ex}"
    finally:
        if conn: conn.close()

def get_dados_empresa():
    conn = get_db_connection()
    if not conn: return None
    
    try:
        cursor = conn.cursor()
        query = "SELECT TOP 1 NOME_EMP, CGC_EMP, ENDER_EMP, NUMER_EMP, BAIRR_EMP, CIDADE_EMP, ESTADO_EMP, DDD_EMP, TELEF_EMP FROM AEMPREGE"
        cursor.execute(query)
        row = cursor.fetchone()
        if row:
            endereco = f"{row.ENDER_EMP.strip() if row.ENDER_EMP else ''}, {row.NUMER_EMP.strip() if row.NUMER_EMP else ''} - {row.BAIRR_EMP.strip() if row.BAIRR_EMP else ''}, {row.CIDADE_EMP.strip() if row.CIDADE_EMP else ''}/{row.ESTADO_EMP.strip() if row.ESTADO_EMP else ''}"
            telefone = f"({row.DDD_EMP.strip() if row.DDD_EMP else ''}) {row.TELEF_EMP.strip() if row.TELEF_EMP else ''}"
            return {
                'nome': row.NOME_EMP.strip() if row.NOME_EMP else '',
                'cnpj': row.CGC_EMP.strip() if row.CGC_EMP else '',
                'endereco': endereco,
                'telefone': telefone
            }
        return None
    except pyodbc.Error as ex:
        print(f"Erro ao buscar dados da empresa: {ex}")
        return None
    finally:
        if conn: conn.close()

def inserir_desconto_vendedor(codigo_usuario, codigo_vendedor, percentual_max):
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM GE_USUARIOS_DESCONTOVENDEDOR 
            WHERE CODUSUARIO_GUD = ? AND CODVENDEDOR_GUD = ?
        """, (codigo_usuario, codigo_vendedor))
        
        resultado = cursor.fetchone()
        existe = resultado and resultado[0] > 0
        
        if existe:
            cursor.execute("""
                UPDATE GE_USUARIOS_DESCONTOVENDEDOR 
                SET PERCENTMAX_GUD = ?
                WHERE CODUSUARIO_GUD = ? AND CODVENDEDOR_GUD = ?
            """, (percentual_max, codigo_usuario, codigo_vendedor))
            print(f"Desconto atualizado para usuário {codigo_usuario}, vendedor {codigo_vendedor}: {percentual_max}%")
        else:
            cursor.execute("""
                INSERT INTO GE_USUARIOS_DESCONTOVENDEDOR (CODUSUARIO_GUD, CODVENDEDOR_GUD, PERCENTMAX_GUD)
                VALUES (?, ?, ?)
            """, (codigo_usuario, codigo_vendedor, percentual_max))
            print(f"Desconto cadastrado para usuário {codigo_usuario}, vendedor {codigo_vendedor}: {percentual_max}%")
        
        conn.commit()
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Erro ao inserir/atualizar desconto do vendedor: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()
