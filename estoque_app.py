import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
import io

# ===============================
# LOGIN SIMPLES
# ===============================
def autenticar(usuario, senha):
    return usuario == "admin" and senha == "1234"

with st.sidebar:
    st.markdown("## 🔐 Login")
    user = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    if not autenticar(user, password):
        st.warning("Acesso restrito. Informe usuário e senha.")
        st.stop()

# ===============================
# BANCO DE DADOS
# ===============================
def conectar():
    return sqlite3.connect("estoque.db")

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT,
            preco REAL,
            estoque INTEGER,
            estoque_minimo INTEGER,
            validade TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            tipo TEXT,
            quantidade INTEGER,
            data TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)
    conn.commit()
    conn.close()

# ===============================
# FUNÇÕES DE OPERAÇÃO
# ===============================
def inserir_produto(nome, categoria, preco, estoque, estoque_minimo, validade):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO produtos (nome, categoria, preco, estoque, estoque_minimo, validade)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nome, categoria, preco, estoque, estoque_minimo, validade))
    conn.commit()
    conn.close()

def buscar_produtos():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM produtos", conn)
    conn.close()
    return df

def movimentar_estoque(produto_id, tipo, quantidade):
    conn = conectar()
    cursor = conn.cursor()

    # Verifica estoque atual
    cursor.execute("SELECT estoque FROM produtos WHERE id = ?", (produto_id,))
    estoque_atual = cursor.fetchone()[0]

    if tipo == 'saida' and quantidade > estoque_atual:
        conn.close()
        raise ValueError("❌ Quantidade maior que o estoque disponível.")

    if tipo == 'entrada':
        cursor.execute("UPDATE produtos SET estoque = estoque + ? WHERE id = ?", (quantidade, produto_id))
    elif tipo == 'saida':
        cursor.execute("UPDATE produtos SET estoque = estoque - ? WHERE id = ?", (quantidade, produto_id))

    cursor.execute("""
        INSERT INTO movimentacoes (produto_id, tipo, quantidade)
        VALUES (?, ?, ?)
    """, (produto_id, tipo, quantidade))

    conn.commit()
    conn.close()

# ===============================
# INTERFACE STREAMLIT
# ===============================
st.set_page_config(page_title="Mini Estoque Guanabara", layout="centered")
st.title("📦 Controle de Estoque – Mini Guanabara")

# Cria tabelas se necessário
criar_tabelas()

# Menu lateral
aba = st.sidebar.radio("📋 Menu", [
    "Cadastrar produto",
    "Visualizar estoque",
    "Movimentar estoque",
    "Histórico de movimentações"
])

# ===============================
# ABA 1 – Cadastro de Produtos
# ===============================
if aba == "Cadastrar produto":
    st.header("➕ Cadastrar novo produto")
    with st.form("formulario_produto"):
        nome = st.text_input("Nome do produto")
        categoria = st.text_input("Categoria")
        preco = st.number_input("Preço (R$)", min_value=0.01, step=0.01)
        estoque = st.number_input("Quantidade em estoque", min_value=0, step=1)
        estoque_minimo = st.number_input("Estoque mínimo", min_value=0, step=1)
        validade = st.date_input("Validade", value=date.today())
        enviar = st.form_submit_button("Cadastrar produto")

        if enviar:
            if nome and preco and estoque is not None:
                inserir_produto(nome, categoria, preco, estoque, estoque_minimo, str(validade))
                st.success(f"✅ Produto '{nome}' cadastrado com sucesso!")
            else:
                st.error("❌ Preencha todos os campos obrigatórios.")

# ===============================
# ABA 2 – Visualizar Estoque
# ===============================
elif aba == "Visualizar estoque":
    st.header("📋 Produtos cadastrados")
    df_produtos = buscar_produtos()

    if df_produtos.empty:
        st.info("Nenhum produto cadastrado.")
    else:
        # Destacar estoque abaixo do mínimo
        def destacar_linha(row):
            if row["estoque"] <= row["estoque_minimo"]:
                return ['background-color: #ffcccc'] * len(row)
            else:
                return [''] * len(row)

        st.dataframe(df_produtos.style.apply(destacar_linha, axis=1))

        # Botão para exportar para Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_produtos.to_excel(writer, index=False, sheet_name='Estoque')

        st.download_button(
            label="📥 Baixar tabela como Excel",
            data=buffer,
            file_name="estoque.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ===============================
# ABA 3 – Movimentar Estoque
# ===============================
elif aba == "Movimentar estoque":
    st.header("🔁 Entrada / Saída de estoque")

    df = buscar_produtos()
    nomes = df["nome"].tolist()

    if not nomes:
        st.warning("⚠️ Nenhum produto cadastrado ainda.")
    else:
        with st.form("movimentacao_form"):
            produto_nome = st.selectbox("Escolha o produto", nomes)
            tipo = st.selectbox("Tipo de movimentação", ["entrada", "saida"])
            quantidade = st.number_input("Quantidade", min_value=1, step=1)
            enviar = st.form_submit_button("Registrar movimentação")

            if enviar:
                try:
                    linha = df[df["nome"].str.strip() == produto_nome.strip()]
                    if linha.empty:
                        raise ValueError("❌ Produto não encontrado.")
                    produto_id = int(linha["id"].values[0])
                    movimentar_estoque(produto_id, tipo, quantidade)
                    st.success(f"✅ {tipo.capitalize()} de {quantidade} unidades registrada para '{produto_nome}'")
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Erro inesperado: {e}")

# ===============================
# ABA 4 – Histórico de movimentações
# ===============================
elif aba == "Histórico de movimentações":
    st.header("📊 Histórico de entradas e saídas")

    conn = conectar()
    df_mov = pd.read_sql_query("""
        SELECT m.data, p.nome AS produto, m.tipo, m.quantidade
        FROM movimentacoes m
        JOIN produtos p ON m.produto_id = p.id
        ORDER BY m.data DESC
    """, conn)
    conn.close()

    if df_mov.empty:
        st.info("Nenhuma movimentação registrada.")
    else:
        st.dataframe(df_mov)
