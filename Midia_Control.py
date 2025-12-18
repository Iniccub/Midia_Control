import streamlit as st

st.set_page_config(page_title="Midia Control", page_icon="icon.PNG", layout="wide")
st.markdown("<h1 style='color:#4D268C;'>Midia Control - Rede Lius Agostinianos</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='color:#F29829;'>Bem-vindo ao Midia Control! Sua plataforma para controle do consumo dos adiantamentos para mídias sociais</h1>", unsafe_allow_html=True)
st.write("Navegue pelo menu lateral para acessar as diferentes funcionalidades do Midia Control.")

st.write("---")

# ==== MongoDB (conexão e utilitários) ====
from pymongo import MongoClient
import uuid
from datetime import date, datetime
import os

try:
    import certifi
    _TLS_CA_FILE = certifi.where()
except Exception:
    _TLS_CA_FILE = None

SOLICITANTES = [
    "Erika Gonçalves Sousa de Jesus",
    "Nathalia Duarte Ballesteros",
    "Francisco Angellys Vanderlei da Silva",
]

RESPONSAVEL = [
    "Gisele Bragheto de Souza Nogueira",
    "Luciana da Paixão Felix Mendes"
]

UNIDADES = [
    "CSA BH",
    "CSA CTG",
    "CSA NL",
    "CSA GZ",
    "CSA DV I",
    "CSA DV II",
    "REDE LIUS",
    "EPSA",
    "ESA",
    "AIACOM",
    "ADEODATO",
    "PROVINCIA",
]

@st.cache_resource
def get_collection():
    try:
        cfg = st.secrets["mongodb"]
    except Exception:
        cfg = {}
    username = cfg.get("MONGODB_USERNAME") or os.environ.get("MONGODB_USERNAME")
    password = cfg.get("MONGODB_PASSWORD") or os.environ.get("MONGODB_PASSWORD")
    cluster = cfg.get("MONGODB_CLUSTER") or os.environ.get("MONGODB_CLUSTER")
    db_name = cfg.get("MONGODB_DB_NAME") or os.environ.get("MONGODB_DB_NAME") or "Midia_Control"
    if not all([username, password, cluster, db_name]):
        raise RuntimeError("Configuração de MongoDB ausente")
    conn_str = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority"
    client = MongoClient(conn_str, tls=True, tlsCAFile=_TLS_CA_FILE) if _TLS_CA_FILE else MongoClient(conn_str, tls=True)
    db = client[db_name]
    return db["registros"]

def load_all_registros():
    col = get_collection()
    docs = list(col.find({}))
    st.session_state['registros'] = {}
    for d in docs:
        rid = d.get('_id') or d.get('registro_id')
        st.session_state['registros'][rid] = {
            'solicitacao': d.get('solicitacao', {}),
            'adiantamento': d.get('adiantamento', None),
            'faturamentos': d.get('faturamentos', [])
        }

def init_state():
    if 'registros' not in st.session_state:
        st.session_state['registros'] = {}  # {registro_id: {'solicitacao': {...}, 'adiantamento': {... or None}, 'faturamentos': []}}
    # Carrega dados do MongoDB apenas uma vez
    if 'db_loaded' not in st.session_state:
        try:
            load_all_registros()
            st.session_state['db_loaded'] = True
        except Exception as e:
            st.session_state['db_loaded'] = False
            st.warning(f"Não foi possível carregar dados do MongoDB. Usando sessão local. Detalhe: {e}")

def novo_registro(descricao, solicitante, valor_estimado, data_solicitacao, observacoes, unidade=None):
    registro_id = uuid.uuid4().hex[:8].upper()
    doc = {
        '_id': registro_id,
        'solicitacao': {
            'descricao': descricao,
            'solicitante': solicitante,
            'valor_estimado': float(valor_estimado) if valor_estimado is not None else 0.0,
            'data_solicitacao': str(data_solicitacao),
            'observacoes': observacoes or '',
            'unidade': unidade or ''
        },
        'adiantamento': None,
        'faturamentos': [],
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    # Persistir no MongoDB
    try:
        col = get_collection()
        col.insert_one(doc)
    except Exception as e:
        st.error(f"Falha ao salvar no MongoDB: {e}")
    # Atualizar sessão
    st.session_state['registros'][registro_id] = {
        'solicitacao': doc['solicitacao'],
        'adiantamento': None,
        'faturamentos': []
    }
    return registro_id

def registrar_adiantamento(registro_id, valor, data_adiantamento, responsavel, observacao, unidade=None):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return False
    ad = {
        'valor': float(valor),
        'data_adiantamento': str(data_adiantamento),
        'responsavel': responsavel or '',
        'observacao': observacao or '',
        'unidade': unidade or reg['solicitacao'].get('unidade', '')
    }
    # Atualizar sessão
    st.session_state['registros'][registro_id]['adiantamento'] = ad
    # Persistir no MongoDB
    try:
        col = get_collection()
        col.update_one({'_id': registro_id}, {'$set': {'adiantamento': ad, 'updated_at': datetime.utcnow()}})
    except Exception as e:
        st.error(f"Falha ao atualizar adiantamento no MongoDB: {e}")
    return True

def adicionar_faturamento(registro_id, numero_fatura, valor, data_fatura, descricao, unidade=None):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return False
    fat = {
        'id': uuid.uuid4().hex[:8].upper(),
        'numero_fatura': numero_fatura or '',
        'valor': float(valor),
        'data_fatura': str(data_fatura),
        'descricao': descricao or '',
        'unidade': unidade or reg['adiantamento'].get('unidade') or reg['solicitacao'].get('unidade', '')
    }
    # Atualizar sessão
    st.session_state['registros'][registro_id]['faturamentos'].append(fat)
    # Persistir no MongoDB (push na lista de faturamentos e atualizar updated_at)
    try:
        col = get_collection()
        col.update_one({'_id': registro_id}, {'$push': {'faturamentos': fat}, '$set': {'updated_at': datetime.utcnow()}})
    except Exception as e:
        st.error(f"Falha ao adicionar faturamento no MongoDB: {e}")
    return True

def atualizar_registro(registro_id, descricao, solicitante, valor_estimado, data_solicitacao, observacoes, unidade=None):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return False
    solicitacao = {
        'descricao': descricao,
        'solicitante': solicitante,
        'valor_estimado': float(valor_estimado) if valor_estimado is not None else 0.0,
        'data_solicitacao': str(data_solicitacao),
        'observacoes': observacoes or '',
        'unidade': unidade or reg['solicitacao'].get('unidade', '')
    }
    st.session_state['registros'][registro_id]['solicitacao'] = solicitacao
    try:
        col = get_collection()
        col.update_one({'_id': registro_id}, {'$set': {'solicitacao': solicitacao, 'updated_at': datetime.utcnow()}})
    except Exception as e:
        st.error(f"Falha ao atualizar solicitação no MongoDB: {e}")
    return True

def editar_adiantamento(registro_id, valor, data_adiantamento, responsavel, observacao):
    return registrar_adiantamento(registro_id, valor, data_adiantamento, responsavel, observacao)

def editar_faturamento(registro_id, fat_id, numero_fatura, valor, data_fatura, descricao, unidade=None):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return False
    idx = None
    for i, f in enumerate(reg['faturamentos']):
        if f.get('id') == fat_id:
            idx = i
            break
    if idx is None:
        return False
    novo = {
        'id': fat_id,
        'numero_fatura': numero_fatura or '',
        'valor': float(valor),
        'data_fatura': str(data_fatura),
        'descricao': descricao or '',
        'unidade': unidade or reg['faturamentos'][idx].get('unidade') or reg['adiantamento'].get('unidade') or reg['solicitacao'].get('unidade', '')
    }
    st.session_state['registros'][registro_id]['faturamentos'][idx] = novo
    try:
        col = get_collection()
        col.update_one(
            {'_id': registro_id},
            {'$set': {
                'faturamentos.$[elem].numero_fatura': novo['numero_fatura'],
                'faturamentos.$[elem].valor': novo['valor'],
                'faturamentos.$[elem].data_fatura': novo['data_fatura'],
                'faturamentos.$[elem].descricao': novo['descricao'],
                'faturamentos.$[elem].unidade': novo['unidade'],
                'updated_at': datetime.utcnow()
            }},
            array_filters=[{'elem.id': fat_id}]
        )
    except Exception as e:
        st.error(f"Falha ao editar faturamento no MongoDB: {e}")
    return True

def excluir_registro(registro_id):
    st.session_state['registros'].pop(registro_id, None)
    try:
        col = get_collection()
        col.delete_one({'_id': registro_id})
    except Exception as e:
        st.error(f"Falha ao excluir registro no MongoDB: {e}")
    return True

def excluir_faturamento(registro_id, fat_id):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return False
    st.session_state['registros'][registro_id]['faturamentos'] = [f for f in reg['faturamentos'] if f.get('id') != fat_id]
    try:
        col = get_collection()
        col.update_one({'_id': registro_id}, {'$pull': {'faturamentos': {'id': fat_id}}, '$set': {'updated_at': datetime.utcnow()}})
    except Exception as e:
        st.error(f"Falha ao excluir faturamento no MongoDB: {e}")
    return True

def excluir_adiantamento(registro_id):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return False
    st.session_state['registros'][registro_id]['adiantamento'] = None
    try:
        col = get_collection()
        col.update_one({'_id': registro_id}, {'$set': {'adiantamento': None, 'updated_at': datetime.utcnow()}})
    except Exception as e:
        st.error(f"Falha ao excluir adiantamento no MongoDB: {e}")
    return True

# Novo: processo de faturamento em lote integrado
def processar_faturamentos_em_lote(registro_id, linhas, permitir_exceder=False):
    # Normaliza e filtra linhas válidas
    novos = []
    for l in linhas:
        try:
            valor = float(l.get('valor', 0) or 0)
        except (TypeError, ValueError):
            valor = 0.0
        numero = (l.get('numero_fatura') or '').strip()
        desc = (l.get('descricao') or '').strip()
        data = l.get('data_fatura')
        # Aceita data como date/datetime/str, converte para str
        if hasattr(data, 'isoformat'):
            data_str = data.isoformat()
        else:
            data_str = str(data) if data else ''
        if valor > 0 and (numero or desc):
            novos.append({
                'id': uuid.uuid4().hex[:8].upper(),
                'numero_fatura': numero,
                'valor': valor,
                'data_fatura': data_str,
                'descricao': desc
            })

    if not novos:
        return {'inseridos': 0, 'total_novo': 0.0, 'excedeu': False, 'mensagem': 'Nenhuma linha válida para inserir.'}

    # Validação contra limite de adiantamento
    total_novo = sum(n['valor'] for n in novos)
    validar = validar_limite_adiantamento(registro_id, total_novo)
    if validar['exceder'] and not permitir_exceder:
        return {
            'inseridos': 0,
            'total_novo': total_novo,
            'excedeu': True,
            'mensagem': f"Total novo (R$ {total_novo:,.2f}) excede saldo (R$ {validar['saldo']:,.2f}). Habilite 'Permitir exceder' para lançar mesmo assim."
        }

    # Atualiza sessão
    st.session_state['registros'][registro_id]['faturamentos'].extend(novos)

    # Persiste no MongoDB com $push $each
    try:
        col = get_collection()
        col.update_one(
            {'_id': registro_id},
            {'$push': {'faturamentos': {'$each': novos}}, '$set': {'updated_at': datetime.utcnow()}}
        )
    except Exception as e:
        return {'inseridos': 0, 'total_novo': total_novo, 'excedeu': False, 'mensagem': f'Falha ao salvar no MongoDB: {e}'}

    return {'inseridos': len(novos), 'total_novo': total_novo, 'excedeu': validar['exceder'], 'mensagem': 'Faturamentos lançados com sucesso.'}

def validar_limite_adiantamento(registro_id, novos_total):
    adiantado, faturado_atual, saldo_atual = calcular_consumo(registro_id)
    exceder = novos_total > saldo_atual if adiantado > 0 else False
    return {
        'adiantado': adiantado,
        'faturado_atual': faturado_atual,
        'saldo': saldo_atual,
        'exceder': exceder
    }
def calcular_consumo(registro_id):
    reg = st.session_state['registros'].get(registro_id)
    if not reg:
        return 0.0, 0.0, 0.0
    adiantado = float(reg['adiantamento']['valor']) if reg['adiantamento'] else 0.0
    total_faturado = sum(float(f['valor']) for f in reg['faturamentos'])
    saldo = adiantado - total_faturado
    return adiantado, total_faturado, saldo

def render_resumo_financeiro(registros=None):
    linhas = []
    regs_src = registros if registros is not None else st.session_state['registros']
    for rid, reg in regs_src.items():
        adiantado, faturado, saldo = calcular_consumo(rid)
        status = 'Encerrado' if adiantado > 0 and saldo <= 0 else ('Em aberto' if adiantado > 0 else 'Aguardando adiantamento')
        linhas.append({
            'Registro': rid,
            'Solicitante': reg['solicitacao']['solicitante'],
            'Descrição': reg['solicitacao']['descricao'],
            'Unidade': reg['solicitacao'].get('unidade',''),
            'Valor adiantado': adiantado,
            'Total faturado': faturado,
            'Saldo': saldo,
            'Status': status
        })
    st.dataframe(linhas, use_container_width=True)

init_state()

def render_dashboard():
    with st.expander("Filtros"):
        unidades_disp = list({reg['solicitacao'].get('unidade','') for reg in st.session_state['registros'].values() if reg['solicitacao'].get('unidade','')}) or UNIDADES
        unidades_disp = UNIDADES if set(UNIDADES) >= set(unidades_disp) else list(dict.fromkeys(unidades_disp + UNIDADES))
        solicitantes_disp = list({reg['solicitacao'].get('solicitante','') for reg in st.session_state['registros'].values()})
        solicitantes_disp = SOLICITANTES if set(SOLICITANTES) >= set(solicitantes_disp) else list(dict.fromkeys(solicitantes_disp + SOLICITANTES))
        status_opts = ["Encerrado", "Em aberto", "Aguardando adiantamento"]
        sel_unidades = st.multiselect("Unidades", options=unidades_disp, default=[])
        sel_solicitantes = st.multiselect("Solicitantes", options=solicitantes_disp, default=[])
        sel_status = st.multiselect("Status", options=status_opts, default=[])
        usar_periodo = st.checkbox("Filtrar por período da solicitação", value=False)
        if usar_periodo:
            ini = st.date_input("Início", value=date.today().replace(day=1), key="f_ini")
            fim = st.date_input("Fim", value=date.today(), key="f_fim")
        else:
            ini = None
            fim = None
    filtrados = {}
    for rid, reg in st.session_state['registros'].items():
        u = reg['solicitacao'].get('unidade','')
        s = reg['solicitacao'].get('solicitante','')
        adiantado, faturado, saldo = calcular_consumo(rid)
        stt = 'Encerrado' if adiantado > 0 and saldo <= 0 else ('Em aberto' if adiantado > 0 else 'Aguardando adiantamento')
        if sel_unidades and u not in sel_unidades:
            continue
        if sel_solicitantes and s not in sel_solicitantes:
            continue
        if sel_status and stt not in sel_status:
            continue
        if ini and fim:
            ds = reg['solicitacao'].get('data_solicitacao')
            try:
                dsv = date.fromisoformat(ds) if ds else None
            except Exception:
                dsv = None
            if dsv and not (ini <= dsv <= fim):
                continue
        filtrados[rid] = reg
    total_registros = len(filtrados)
    total_adiantado = sum(float(r['adiantamento']['valor']) for r in filtrados.values() if r['adiantamento'])
    total_faturado = sum(sum(float(f['valor']) for f in r['faturamentos']) for r in filtrados.values())
    total_saldo = total_adiantado - total_faturado
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{total_registros}")
    c2.metric("Total adiantado (R$)", f"{total_adiantado:,.2f}")
    c3.metric("Total faturado (R$)", f"{total_faturado:,.2f}")
    c4.metric("Saldo (R$)", f"{total_saldo:,.2f}")
    st.divider()
    st.subheader("Resumo por registro")
    render_resumo_financeiro(filtrados)

def render_solicitacoes():
    col_a, col_b = st.columns([1, 3])
    novo = col_a.button("Novo registro")
    if novo or st.session_state.get('abrir_novo'):
        st.session_state['abrir_novo'] = True
        with st.form("form_novo_registro"):
            descricao = st.text_input("Descrição da campanha")
            solicitante = st.selectbox("Solicitante", options=SOLICITANTES)
            data_solicitacao = st.date_input("Data da solicitação", value=date.today())
            valor_estimado = st.number_input("Valor estimado (R$)", min_value=0.0, step=100.0, format="%.2f")
            observacoes = st.text_area("Observações")
            unidade = st.selectbox("Unidade", options=UNIDADES)
            submitted = st.form_submit_button("Salvar")
            if submitted:
                if not descricao or not solicitante:
                    st.warning("Preencha pelo menos descrição e solicitante.")
                else:
                    rid = novo_registro(descricao, solicitante, valor_estimado, data_solicitacao, observacoes, unidade)
                    st.session_state['abrir_novo'] = False
                    st.success(f"Registro criado: {rid}")
                    st.rerun()
    st.divider()
    rids = list(st.session_state['registros'].keys())
    if rids:
        rid_edit = st.selectbox("Editar registro", options=rids)
        reg = st.session_state['registros'][rid_edit]
        with st.form("form_editar_registro"):
            descricao = st.text_input("Descrição da campanha", value=reg['solicitacao'].get('descricao', ''))
            _curr_sol = reg['solicitacao'].get('solicitante', '')
            _opts = SOLICITANTES if _curr_sol in SOLICITANTES else [_curr_sol] + SOLICITANTES
            solicitante = st.selectbox("Solicitante", options=_opts, index=_opts.index(_curr_sol) if _curr_sol in _opts else 0)
            data_solicitacao = st.date_input("Data da solicitação", value=date.fromisoformat(reg['solicitacao'].get('data_solicitacao')) if reg['solicitacao'].get('data_solicitacao') else date.today())
            valor_estimado = st.number_input("Valor estimado (R$)", value=float(reg['solicitacao'].get('valor_estimado', 0.0)), min_value=0.0, step=100.0, format="%.2f")
            observacoes = st.text_area("Observações", value=reg['solicitacao'].get('observacoes', ''))
            _curr_uni = reg['solicitacao'].get('unidade', '')
            _uni_opts = UNIDADES if _curr_uni in UNIDADES else [_curr_uni] + UNIDADES
            unidade = st.selectbox("Unidade", options=_uni_opts, index=_uni_opts.index(_curr_uni) if _curr_uni in _uni_opts else 0)
            submitted_e = st.form_submit_button("Salvar alterações")
            if submitted_e:
                atualizar_registro(rid_edit, descricao, solicitante, valor_estimado, data_solicitacao, observacoes, unidade)
                st.success("Registro atualizado")
        col_del1, col_del2 = st.columns([1, 3])
        confirm_del = col_del1.checkbox("Confirmar exclusão do registro", key=f"confirm_del_{rid_edit}")
        if col_del2.button("Excluir registro", key=f"btn_del_{rid_edit}"):
            if confirm_del:
                excluir_registro(rid_edit)
                st.success("Registro excluído")
                st.rerun()
            else:
                st.warning("Marque a confirmação para excluir.")

def render_faturamentos():
    registros_com_adiantamento = [rid for rid, r in st.session_state['registros'].items() if r['adiantamento']]
    if not registros_com_adiantamento:
        st.info("Nenhum adiantamento encontrado.")
        return
    rid_sel = st.selectbox("Registro", options=registros_com_adiantamento)
    reg = st.session_state['registros'][rid_sel]
    c1, c2, c3 = st.columns(3)
    c1.metric("Adiantado (R$)", f"{float(reg['adiantamento']['valor']):,.2f}")
    adiantado, faturado, saldo = calcular_consumo(rid_sel)
    c2.metric("Faturado (R$)", f"{faturado:,.2f}")
    c3.metric("Saldo (R$)", f"{saldo:,.2f}")
    st.divider()
    st.subheader("Novo faturamento")
    with st.form("form_faturamento_novo"):
        numero_fatura = st.text_input("Número da fatura/nota")
        valor_fatura = st.number_input("Valor faturado (R$)", min_value=0.0, step=100.0, format="%.2f")
        data_fatura = st.date_input("Data do faturamento", value=date.today())
        desc_fatura = st.text_input("Descrição/Observação")
        _curr_uni_nf = reg['adiantamento'].get('unidade') if reg.get('adiantamento') else reg['solicitacao'].get('unidade','')
        _uni_opts_nf = UNIDADES if _curr_uni_nf in UNIDADES else ([_curr_uni_nf] + UNIDADES if _curr_uni_nf else UNIDADES)
        unidade_nf = st.selectbox("Unidade", options=_uni_opts_nf, index=_uni_opts_nf.index(_curr_uni_nf) if _curr_uni_nf in _uni_opts_nf else 0)
        submitted_f = st.form_submit_button("Lançar")
        if submitted_f:
            if valor_fatura <= 0:
                st.warning("Informe um valor maior que zero.")
            else:
                adicionar_faturamento(rid_sel, numero_fatura, valor_fatura, data_fatura, desc_fatura, unidade_nf)
                st.success("Faturamento lançado")
    st.divider()
    st.subheader("Editar faturamento")
    fats = reg['faturamentos']
    if fats:
        fat_ids = [f.get('id', f"{i}") for i, f in enumerate(fats)]
        fat_sel_id = st.selectbox("Selecionar", options=fat_ids, format_func=lambda x: next((f['numero_fatura'] or x for f in fats if f.get('id', str(fats.index(f))) == x), x))
        fat = next((f for f in fats if f.get('id') == fat_sel_id), None)
        if fat is None:
            idx = fat_ids.index(fat_sel_id)
            fat = fats[idx]
            fat_sel_id = fat.get('id') or uuid.uuid4().hex[:8].upper()
            fat['id'] = fat_sel_id
        with st.form("form_editar_faturamento"):
            numero_fatura_e = st.text_input("Número da fatura/nota", value=fat.get('numero_fatura',''))
            valor_e = st.number_input("Valor faturado (R$)", value=float(fat.get('valor',0.0)), min_value=0.0, step=100.0, format="%.2f")
            data_e = st.date_input("Data do faturamento", value=date.fromisoformat(fat.get('data_fatura')) if fat.get('data_fatura') else date.today())
            desc_e = st.text_input("Descrição/Observação", value=fat.get('descricao',''))
            _curr_uni_fe = fat.get('unidade') or reg['adiantamento'].get('unidade') or reg['solicitacao'].get('unidade','')
            _uni_opts_fe = UNIDADES if _curr_uni_fe in UNIDADES else ([_curr_uni_fe] + UNIDADES if _curr_uni_fe else UNIDADES)
            unidade_fe = st.selectbox("Unidade", options=_uni_opts_fe, index=_uni_opts_fe.index(_curr_uni_fe) if _curr_uni_fe in _uni_opts_fe else 0)
            submitted_ef = st.form_submit_button("Salvar alterações")
            if submitted_ef:
                editar_faturamento(rid_sel, fat_sel_id, numero_fatura_e, valor_e, data_e, desc_e, unidade_fe)
                st.success("Faturamento atualizado")
        col_delf1, col_delf2 = st.columns([1, 3])
        confirm_del_f = col_delf1.checkbox("Confirmar exclusão do faturamento", key=f"confirm_del_f_{fat_sel_id}")
        if col_delf2.button("Excluir faturamento", key=f"btn_del_f_{fat_sel_id}"):
            if confirm_del_f:
                excluir_faturamento(rid_sel, fat_sel_id)
                st.success("Faturamento excluído")
                st.rerun()
            else:
                st.warning("Marque a confirmação para excluir.")
    else:
        st.info("Sem faturamentos lançados")

def render_financeiro():
    registros_sem_adiantamento = [rid for rid, r in st.session_state['registros'].items() if r['adiantamento'] is None]
    st.subheader("Gerar adiantamento")
    if registros_sem_adiantamento:
        with st.form("form_adiantamento"):
            rid_fin = st.selectbox("Registro", options=registros_sem_adiantamento)
            valor_adiantamento = st.number_input("Valor do adiantamento (R$)", min_value=0.0, step=100.0, format="%.2f")
            data_adiantamento = st.date_input("Data do adiantamento", value=date.today())
            responsavel = st.selectbox("Responsável", options=RESPONSAVEL)
            _curr_uni_ad = st.session_state['registros'][rid_fin]['solicitacao'].get('unidade','')
            _uni_opts_ad = UNIDADES if _curr_uni_ad in UNIDADES else ([_curr_uni_ad] + UNIDADES if _curr_uni_ad else UNIDADES)
            unidade_ad = st.selectbox("Unidade", options=_uni_opts_ad, index=_uni_opts_ad.index(_curr_uni_ad) if _curr_uni_ad in _uni_opts_ad else 0)
            observacao_fin = st.text_area("Observação")
            submitted_a = st.form_submit_button("Registrar")
            if submitted_a:
                if valor_adiantamento <= 0:
                    st.warning("Informe um valor maior que zero.")
                else:
                    registrar_adiantamento(rid_fin, valor_adiantamento, data_adiantamento, responsavel, observacao_fin, unidade_ad)
                    st.success("Adiantamento registrado")
    else:
        st.info("Não há solicitações pendentes de adiantamento")
    st.divider()
    st.subheader("Editar adiantamento")
    registros_com_adiantamento = [rid for rid, r in st.session_state['registros'].items() if r['adiantamento']]
    if registros_com_adiantamento:
        rid_e = st.selectbox("Registro", options=registros_com_adiantamento, key="rid_edit_ad")
        ad = st.session_state['registros'][rid_e]['adiantamento']
        with st.form("form_editar_adiantamento"):
            valor_e = st.number_input("Valor do adiantamento (R$)", value=float(ad.get('valor',0.0)), min_value=0.0, step=100.0, format="%.2f")
            data_e = st.date_input("Data do adiantamento", value=date.fromisoformat(ad.get('data_adiantamento')) if ad.get('data_adiantamento') else date.today())
            _curr_resp = ad.get('responsavel','')
            _resp_opts = RESPONSAVEL if _curr_resp in RESPONSAVEL else [_curr_resp] + RESPONSAVEL
            responsavel_e = st.selectbox("Responsável", options=_resp_opts, index=_resp_opts.index(_curr_resp) if _curr_resp in _resp_opts else 0)
            _curr_uni_ae = ad.get('unidade') or st.session_state['registros'][rid_e]['solicitacao'].get('unidade','')
            _uni_opts_ae = UNIDADES if _curr_uni_ae in UNIDADES else ([_curr_uni_ae] + UNIDADES if _curr_uni_ae else UNIDADES)
            unidade_e = st.selectbox("Unidade", options=_uni_opts_ae, index=_uni_opts_ae.index(_curr_uni_ae) if _curr_uni_ae in _uni_opts_ae else 0)
            observacao_e = st.text_area("Observação", value=ad.get('observacao',''))
            submitted_ea = st.form_submit_button("Salvar alterações")
            if submitted_ea:
                editar_adiantamento(rid_e, valor_e, data_e, responsavel_e, observacao_e, unidade_e)
                st.success("Adiantamento atualizado")
        col_dela1, col_dela2 = st.columns([1, 3])
        confirm_del_a = col_dela1.checkbox("Confirmar exclusão do adiantamento", key=f"confirm_del_a_{rid_e}")
        if col_dela2.button("Excluir adiantamento", key=f"btn_del_a_{rid_e}"):
            if confirm_del_a:
                excluir_adiantamento(rid_e)
                st.success("Adiantamento excluído")
                st.rerun()
            else:
                st.warning("Marque a confirmação para excluir.")
    else:
        st.info("Nenhum adiantamento para editar")

def render_relatorios():
    tab_adi, tab_fat, tab_saldo = st.tabs(["Adiantamentos", "Faturamentos", "Saldos"])
    with tab_adi:
        linhas = []
        for rid, reg in st.session_state['registros'].items():
            if reg['adiantamento']:
                linhas.append({
                    'Registro': rid,
                    'Solicitante': reg['solicitacao']['solicitante'],
                    'Descrição': reg['solicitacao']['descricao'],
                    'Unidade': reg['solicitacao'].get('unidade',''),
                    'Valor adiantado': float(reg['adiantamento']['valor']),
                    'Data adiantamento': reg['adiantamento'].get('data_adiantamento',''),
                    'Responsável': reg['adiantamento'].get('responsavel','')
                })
        st.dataframe(linhas, use_container_width=True)
    with tab_fat:
        linhas = []
        for rid, reg in st.session_state['registros'].items():
            for f in reg['faturamentos']:
                linhas.append({
                    'Registro': rid,
                    'Unidade': f.get('unidade') or reg['adiantamento'].get('unidade') or reg['solicitacao'].get('unidade',''),
                    'Número fatura': f.get('numero_fatura',''),
                    'Descrição': f.get('descricao',''),
                    'Valor': float(f.get('valor',0.0)),
                    'Data': f.get('data_fatura','')
                })
        st.dataframe(linhas, use_container_width=True)
    with tab_saldo:
        render_resumo_financeiro()

if 'view' not in st.session_state:
    st.session_state['view'] = 'Dashboard'

with st.sidebar:
    st.image("rede lius.png", width=300)
    view = st.radio("Ir para", ["Solicitações", "Financeiro", "Faturamentos",  "Relatórios", "Dashboard"], index=["Solicitações", "Financeiro", "Faturamentos", "Relatórios", "Dashboard"].index(st.session_state['view']))
    if view != st.session_state['view']:
        st.session_state['view'] = view
        st.rerun()

if st.session_state['view'] == 'Solicitações':
    render_solicitacoes()
elif st.session_state['view'] == 'Financeiro':
    render_financeiro()
elif st.session_state['view'] == 'Faturamentos':
    render_faturamentos()
elif st.session_state['view'] == 'Dashboard':
    render_dashboard()
else:
    render_relatorios()
