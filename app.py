import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURATION & DESIGN SIMPLIFIÉ
# ==========================================
st.set_page_config(
    page_title="ERP Café Pro (咖啡管理系统)",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Style visuel simplifié pour faciliter la lecture
st.markdown(
    """
    <style>
    .main { background-color: #f4f6f9; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e0e6ed;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
        font-size: 16px;
        padding: 10px 20px;
    }
    .stAlert {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_FILE = "database.db"


# ==========================================
# 2. BASE DE DONNÉES & MIGRATIONS AUTOMATIQUES
# ==========================================
def get_connection():
  conn = sqlite3.connect(DB_FILE, timeout=20)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  conn = get_connection()
  cursor = conn.cursor()

  try:
    cursor.execute("PRAGMA journal_mode=WAL;")
  except Exception:
    pass

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        categorie TEXT NOT NULL,
        quantite REAL NOT NULL DEFAULT 0,
        unite TEXT NOT NULL DEFAULT 'kg',
        seuil_alerte REAL NOT NULL DEFAULT 5,
        prix_achat REAL NOT NULL DEFAULT 0,
        prix_unitaire REAL NOT NULL DEFAULT 0
    )
    """)

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_entreprise TEXT NOT NULL UNIQUE,
        nom_contact TEXT,
        adresse TEXT,
        telephone TEXT,
        email TEXT,
        type_cafe TEXT,
        machine_installee INTEGER DEFAULT 0,
        frequence_jours INTEGER DEFAULT 30,
        date_creation TEXT
    )
    """)

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS commandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_nom TEXT NOT NULL DEFAULT '',
        date_commande TEXT NOT NULL,
        code_courrier TEXT,
        prix_total REAL NOT NULL,
        statut TEXT NOT NULL DEFAULT 'En préparation',
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )
    """)

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS lignes_commande (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        commande_id INTEGER NOT NULL,
        produit_id INTEGER NOT NULL,
        nom_produit TEXT NOT NULL,
        quantite REAL NOT NULL,
        prix_unitaire REAL NOT NULL,
        total_ligne REAL NOT NULL,
        FOREIGN KEY(commande_id) REFERENCES commandes(id),
        FOREIGN KEY(produit_id) REFERENCES stock(id)
    )
    """)

  def safe_add_column(table, column_def):
    col_name = column_def.split()[0]
    cursor.execute(f"PRAGMA table_info({table})")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if col_name not in existing_cols:
      cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")

  safe_add_column("clients", "type_cafe TEXT")
  safe_add_column("clients", "machine_installee INTEGER DEFAULT 0")
  safe_add_column("clients", "frequence_jours INTEGER DEFAULT 30")
  safe_add_column("clients", "date_creation TEXT")

  safe_add_column("commandes", "client_id INTEGER")
  safe_add_column("commandes", "client_nom TEXT DEFAULT ''")
  safe_add_column("commandes", "code_courrier TEXT")
  safe_add_column("commandes", "statut TEXT DEFAULT 'En préparation'")

  safe_add_column("lignes_commande", "total_ligne REAL DEFAULT 0")
  safe_add_column("lignes_commande", "prix_unitaire REAL DEFAULT 0")

  safe_add_column("stock", "prix_achat REAL DEFAULT 0")

  conn.commit()
  conn.close()


init_db()


# ==========================================
# 3. CHARGEMENT & CALCULS
# ==========================================
def load_data():
  conn = get_connection()
  df_s = pd.read_sql_query("SELECT * FROM stock", conn)
  df_c = pd.read_sql_query("SELECT * FROM clients", conn)
  df_cmd = pd.read_sql_query("SELECT * FROM commandes ORDER BY id DESC", conn)
  conn.close()
  return df_s, df_c, df_cmd


df_stock, df_clients, df_commandes = load_data()

clients_a_relancer = []
if not df_clients.empty and not df_commandes.empty:
  now = datetime.now()
  col_cli = (
      "client_nom"
      if "client_nom" in df_commandes.columns
      else ("client" if "client" in df_commandes.columns else None)
  )

  if col_cli:
    for _, cli in df_clients.iterrows():
      cmds = df_commandes[df_commandes[col_cli] == cli["nom_entreprise"]]
      if not cmds.empty:
        last_date_str = cmds.iloc[0]["date_commande"]
        try:
          last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M")
        except ValueError:
          try:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
          except ValueError:
            continue

        freq = int(cli["frequence_jours"]) if cli["frequence_jours"] else 30
        next_date = last_date + timedelta(days=freq)
        if now > next_date:
          retard = (now - next_date).days
          clients_a_relancer.append({
              "Client (客户)": cli["nom_entreprise"],
              "Contact (联系人)": cli["nom_contact"] or "N/A",
              "Téléphone (电话)": cli["telephone"] or "N/A",
              "Café habituel (常用咖啡)": (
                  cli["type_cafe"]
                  if pd.notna(cli["type_cafe"])
                  else "Non renseigné (未填写)"
              ),
              "Dernière Commande (上次订单)": last_date_str,
              "Retard (Jours) (延迟天数)": f"{retard} jours (天)",
          })


# ==========================================
# 4. TABLEAU DE BORD (DASHBOARD)
# ==========================================
st.title("☕ ERP Café Pro (咖啡管理系统)")
st.caption("Gestion simple et rapide (简单快速的管理工具)")

# Indicateurs clés en haut de page
col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)

valeur_stock = (
    (df_stock["quantite"] * df_stock["prix_unitaire"]).sum()
    if not df_stock.empty
    else 0.0
)
alertes = (
    len(df_stock[df_stock["quantite"] <= df_stock["seuil_alerte"]])
    if not df_stock.empty
    else 0
)
ca_total = (
    df_commandes["prix_total"].sum() if not df_commandes.empty else 0.0
)

col_k1.metric("📦 Valeur Stock (库存总值)", f"{valeur_stock:,.2f} €")
col_k2.metric("👥 Clients (客户数量)", len(df_clients))
col_k3.metric("🛒 Ventes (总销售额)", f"{ca_total:,.2f} €")
col_k4.metric("🚨 Alertes Stock (库存警告)", alertes)
col_k5.metric(
    "🔔 Relances (需要催单)", len(clients_a_relancer), delta_color="inverse"
)

st.divider()

# Navigation par onglets bilingues
tab_pos, tab_cmd, tab_stock, tab_crm, tab_relances = st.tabs([
    "🛒 1. Vendre ( Take Order / 下订单 )",
    "📜 2. Commandes ( Order History / 历史订单 )",
    "📦 3. Stocks ( Inventory / 库存管理 )",
    "👥 4. Clients ( Customers / 客户管理 )",
    "🔔 5. Relances ( Reminders / 催单提醒 )",
])


# ==========================================
# ONGLET 1 : NOUVELLE COMMANDE (POS)
# ==========================================
with tab_pos:
  st.subheader("🛒 Prise de Commande ( Taking an Order / 下订单 )")

  if df_clients.empty:
    st.warning(
        "⚠️ Aucun client enregistré. Allez dans l'onglet **'4. Clients"
        " (客户)'** pour en ajouter un."
    )
  elif df_stock.empty:
    st.warning(
        "⚠️ Aucun produit en stock. Allez dans l'onglet **'3. Stocks"
        " (库存)'** pour ajouter des produits."
    )
  else:
    if "panier" not in st.session_state:
      st.session_state.panier = []

    c_left, c_right = st.columns([1, 1], gap="large")

    # SECTION GAUCHE : CHOIX DU CLIENT ET PRODUITS
    with c_left:
      st.markdown("### Étape 1 : Choisir le Client (步骤 1：选择客户)")
      selected_client_name = st.selectbox(
          "Sélectionner un client dans la liste (选择客户) :",
          options=df_clients["nom_entreprise"].tolist(),
          key="pos_client_select",
      )

      client_row = df_clients[
          df_clients["nom_entreprise"] == selected_client_name
      ].iloc[0]
      cafe_habituel = (
          client_row["type_cafe"]
          if pd.notna(client_row["type_cafe"])
          and str(client_row["type_cafe"]).strip()
          else "Non renseigné (未填写)"
      )
      machine = (
          "Oui (有)" if client_row["machine_installee"] == 1 else "Non (无)"
      )

      st.info(
          f"👤 **Client (客户) :** {selected_client_name}  \n"
          f"☕ **Café habituel (常用咖啡) :** {cafe_habituel}  \n"
          f"⚙️ **Machine prêtée (借用咖啡机) :** {machine} | 📞 **Tél (电话) :**"
          f" {client_row['telephone'] or 'N/A'}"
      )

      st.markdown(
          "--- \n### Étape 2 : Ajouter des Produits (步骤 2：添加商品)"
      )

      p_options = {}
      for _, r in df_stock.iterrows():
        label = (
            f"[{r['categorie']}] {r['nom']} — Restant (库存): {r['quantite']}"
            f" {r['unite']} | {r['prix_unitaire']:.2f} €/u"
        )
        p_options[label] = r

      selected_prod_label = st.selectbox(
          "Choisir un produit (选择商品) :",
          list(p_options.keys()),
          key="pos_prod_select",
      )
      selected_prod = p_options[selected_prod_label]

      col_q1, col_q2 = st.columns(2)
      with col_q1:
        max_qte = (
            float(selected_prod["quantite"])
            if selected_prod["quantite"] > 0
            else 0.1
        )
        qte_input = st.number_input(
            f"Quantité (数量) en {selected_prod['unite']} :",
            min_value=0.1,
            max_value=max_qte,
            value=min(1.0, max_qte),
            step=1.0,
        )

      with col_q2:
        remise_input = st.number_input(
            "Remise / Reduction (折扣) % :",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=5.0,
        )

      prix_base = float(selected_prod["prix_unitaire"])
      prix_effectif = prix_base * (1.0 - (remise_input / 100.0))

      if st.button(
          "➕ Ajouter au panier (放入购物车)", use_container_width=True
      ):
        if selected_prod["quantite"] < qte_input:
          st.error("❌ Stock insuffisant (库存不足) !")
        else:
          st.session_state.panier.append({
              "produit_id": int(selected_prod["id"]),
              "nom": str(selected_prod["nom"]),
              "quantite": float(qte_input),
              "unite": str(selected_prod["unite"]),
              "prix_unitaire": float(prix_effectif),
              "total": float(qte_input * prix_effectif),
          })
          st.success(
              f"✅ '{selected_prod['nom']}' ajouté au panier (已加入购物车) !"
          )
          st.rerun()

    # SECTION DROITE : RECAPITULATIF ET VALIDATION
    with c_right:
      st.markdown("### Étape 3 : Valider le Panier (步骤 3：确认并提交)")

      if st.session_state.panier:
        df_cart = pd.DataFrame(st.session_state.panier)

        st.dataframe(
            df_cart[["nom", "quantite", "unite", "prix_unitaire", "total"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nom": "Produit (商品)",
                "quantite": "Qté (数量)",
                "unite": "Unité (单位)",
                "prix_unitaire": st.column_config.NumberColumn(
                    "Prix U. HT (单价)", format="%.2f €"
                ),
                "total": st.column_config.NumberColumn(
                    "Total HT (小计)", format="%.2f €"
                ),
            },
        )

        total_ht = float(df_cart["total"].sum())
        tva = total_ht * 0.20
        total_ttc = total_ht + tva

        col_tot1, col_tot2 = st.columns(2)
        col_tot1.metric("Total HT (不含税总价)", f"{total_ht:,.2f} €")
        col_tot2.metric("Total TTC (含税总价 20%)", f"{total_ttc:,.2f} €")

        code_suivi = st.text_input(
            "N° de suivi / Courrier (快递单号 / 追踪号 - 可选) :",
            placeholder="Ex: FR-849302-X",
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
          if st.button(
              "✅ VALIDER LA COMMANDE (确认订单)",
              type="primary",
              use_container_width=True,
          ):
            try:
              conn = get_connection()
              cursor = conn.cursor()
              date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

              cursor.execute("PRAGMA table_info(commandes)")
              cols_cmd = [r[1] for r in cursor.fetchall()]

              fields_cmd = []
              vals_cmd = []

              if "client_id" in cols_cmd:
                fields_cmd.append("client_id")
                vals_cmd.append(int(client_row["id"]))

              if "client_nom" in cols_cmd:
                fields_cmd.append("client_nom")
                vals_cmd.append(str(selected_client_name))

              if "client" in cols_cmd:
                fields_cmd.append("client")
                vals_cmd.append(str(selected_client_name))

              first_nom = (
                  st.session_state.panier[0]["nom"]
                  if st.session_state.panier
                  else "Produit"
              )
              first_pid = (
                  st.session_state.panier[0]["produit_id"]
                  if st.session_state.panier
                  else 1
              )

              if "nom_produit" in cols_cmd:
                fields_cmd.append("nom_produit")
                vals_cmd.append(first_nom)

              if "produit" in cols_cmd:
                fields_cmd.append("produit")
                vals_cmd.append(first_nom)

              if "produit_id" in cols_cmd:
                fields_cmd.append("produit_id")
                vals_cmd.append(first_pid)

              if "quantite" in cols_cmd:
                fields_cmd.append("quantite")
                vals_cmd.append(st.session_state.panier[0]["quantite"])

              fields_cmd.extend(
                  ["date_commande", "code_courrier", "prix_total", "statut"]
              )
              vals_cmd.extend([
                  date_now,
                  str(code_suivi).strip(),
                  float(total_ht),
                  "En préparation",
              ])

              q_cmd = f"INSERT INTO commandes ({', '.join(fields_cmd)}) VALUES ({', '.join(['?']*len(fields_cmd))})"
              cursor.execute(q_cmd, vals_cmd)
              cmd_id = cursor.lastrowid

              cursor.execute("PRAGMA table_info(lignes_commande)")
              cols_lc = [r[1] for r in cursor.fetchall()]

              for item in st.session_state.panier:
                fields_lc = ["commande_id", "produit_id", "quantite"]
                vals_lc = [
                    int(cmd_id),
                    int(item["produit_id"]),
                    float(item["quantite"]),
                ]

                if "nom_produit" in cols_lc:
                  fields_lc.append("nom_produit")
                  vals_lc.append(str(item["nom"]))

                if "prix_unitaire" in cols_lc:
                  fields_lc.append("prix_unitaire")
                  vals_lc.append(float(item["prix_unitaire"]))

                if "total_ligne" in cols_lc:
                  fields_lc.append("total_ligne")
                  vals_lc.append(float(item["total"]))

                q_lc = f"INSERT INTO lignes_commande ({', '.join(fields_lc)}) VALUES ({', '.join(['?']*len(fields_lc))})"
                cursor.execute(q_lc, vals_lc)

                cursor.execute(
                    "UPDATE stock SET quantite = MAX(0, quantite - ?) WHERE id"
                    " = ?",
                    (float(item["quantite"]), int(item["produit_id"])),
                )

              conn.commit()
              conn.close()

              st.session_state.panier = []
              st.balloons()
              st.success(
                  f"🎉 Commande N°{cmd_id} enregistrée avec succès ! (订单已成功保存)"
              )
              st.rerun()

            except Exception as e:
              st.error(f"Erreur (错误) : {e}")

        with col_b2:
          if st.button("🗑️ Vider le panier (清空购物车)", use_container_width=True):
            st.session_state.panier = []
            st.rerun()

      else:
        st.info("💡 Votre panier est vide. (购物车是空的)")


# ==========================================
# ONGLET 2 : HISTORIQUE DES COMMANDES
# ==========================================
with tab_cmd:
  st.subheader("📜 Historique des Commandes ( Order History / 订单历史与追踪 )")

  if not df_commandes.empty:
    col_client_name = (
        "client_nom"
        if "client_nom" in df_commandes.columns
        else ("client" if "client" in df_commandes.columns else None)
    )

    client_options = (
        ["Tous (全部)"]
        + df_commandes[col_client_name].dropna().unique().tolist()
        if col_client_name
        else ["Tous (全部)"]
    )

    col_f1, col_f2 = st.columns(2)
    with col_f1:
      filter_client = st.selectbox(
          "Filtrer par Client (按客户筛选) :", client_options
      )
    with col_f2:
      filter_statut = st.selectbox(
          "Filtrer par Statut (按状态筛选) :",
          [
              "Tous (全部)",
              "En préparation (准备中)",
              "Expédiée (已发货)",
              "Livrée (已送达)",
              "Annulée (已取消)",
          ],
      )

    df_filtered = df_commandes.copy()
    if col_client_name and filter_client != "Tous (全部)":
      df_filtered = df_filtered[df_filtered[col_client_name] == filter_client]

    if filter_statut != "Tous (全部)":
      clean_statut = filter_statut.split(" (")[0]
      df_filtered = df_filtered[df_filtered["statut"] == clean_statut]

    conn = get_connection()
    for _, cmd in df_filtered.iterrows():
      status_icon = (
          "🟡"
          if cmd["statut"] == "En préparation"
          else ("🔵" if cmd["statut"] == "Expédiée" else "🟢")
      )

      c_name = cmd[col_client_name] if col_client_name else "Client"
      header_text = (
          f"{status_icon} Commande (订单) N°{cmd['id']} — {c_name} —"
          f" {cmd['prix_total']:,.2f} € ({cmd['date_commande']})"
      )

      with st.expander(header_text):
        c_i1, c_i2 = st.columns(2)

        with c_i1:
          st.write(f"**Client (客户) :** {c_name}")
          st.write(f"**Date (日期) :** {cmd['date_commande']}")
          st.write(
              f"**Code Suivi (快递单号) :** {cmd['code_courrier'] or 'Aucun (无)'}"
          )

        with c_i2:
          statut_mapping = {
              "En préparation": "En préparation (准备中)",
              "Expédiée": "Expédiée (已发货)",
              "Livrée": "Livrée (已送达)",
              "Annulée": "Annulée (已取消)",
          }
          current_s_display = statut_mapping.get(
              cmd["statut"], "En préparation (准备中)"
          )

          new_statut_display = st.selectbox(
              "Changer le statut (修改状态) :",
              [
                  "En préparation (准备中)",
                  "Expédiée (已发货)",
                  "Livrée (已送达)",
                  "Annulée (已取消)",
              ],
              index=[
                  "En préparation (准备中)",
                  "Expédiée (已发货)",
                  "Livrée (已送达)",
                  "Annulée (已取消)",
              ].index(current_s_display),
              key=f"status_select_{cmd['id']}",
          )

          new_statut_clean = new_statut_display.split(" (")[0]

          if new_statut_clean != cmd["statut"]:
            c_up = get_connection()
            c_up.execute(
                "UPDATE commandes SET statut = ? WHERE id = ?",
                (new_statut_clean, cmd["id"]),
            )
            c_up.commit()
            c_up.close()
            st.success("Statut mis à jour (状态已更新) !")
            st.rerun()

        df_lines = pd.read_sql_query(
            "SELECT nom_produit, quantite, prix_unitaire, total_ligne FROM"
            f" lignes_commande WHERE commande_id = {cmd['id']}",
            conn,
        )
        st.dataframe(
            df_lines,
            use_container_width=True,
            hide_index=True,
            column_config={
                "nom_produit": "Produit (商品)",
                "quantite": "Quantité (数量)",
                "prix_unitaire": st.column_config.NumberColumn(
                    "Prix U. HT (单价)", format="%.2f €"
                ),
                "total_ligne": st.column_config.NumberColumn(
                    "Total HT (小计)", format="%.2f €"
                ),
            },
        )

    conn.close()
  else:
    st.info("Aucune commande enregistrée pour l'instant. (暂无订单记录)")


# ==========================================
# ONGLET 3 : GESTION DES STOCKS
# ==========================================
with tab_stock:
  st.subheader("📦 Gestion des Stocks ( Inventory / 库存管理 )")

  with st.expander(
      "➕ Ajouter un nouveau produit au catalogue (添加新商品)", expanded=False
  ):
    with st.form("form_add_stock"):
      cols1, cols2 = st.columns(2)
      with cols1:
        new_nom = st.text_input("Nom du produit (商品名称) *")
        new_cat = st.selectbox(
            "Catégorie (商品类别) *",
            [
                "Café en Grain (咖啡豆)",
                "Café Moulu (咖啡粉)",
                "Gélules / Capsules (胶囊咖啡)",
                "Machines & Équipements (咖啡机/设备)",
                "Sucre & Encas (糖与零食)",
                "Accessoires & Gobelets (配件与杯子)",
                "Autre (其他)",
            ],
        )
        new_unite = st.selectbox(
            "Unité de mesure (计量单位)",
            ["kg (公斤)", "unités (个/件)", "sachets (包)", "cartons (箱)"],
        )
      with cols2:
        new_qte = st.number_input(
            "Quantité initiale en stock (初始库存数量)",
            min_value=0.0,
            value=10.0,
        )
        new_prix_unitaire = st.number_input(
            "Prix de vente HT (€) (售价/不含税)", min_value=0.0, value=12.0
        )
        new_seuil = st.number_input(
            "Seuil d'alerte stock (预警预留库存)", min_value=0.0, value=5.0
        )

      if st.form_submit_button(
          "💾 Enregistrer le Produit (保存商品)", use_container_width=True
      ):
        if new_nom.strip():
          clean_cat = new_cat.split(" (")[0]
          clean_unite = new_unite.split(" (")[0]

          conn = get_connection()
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
              (
                  new_nom.strip(),
                  clean_cat,
                  float(new_qte),
                  clean_unite,
                  float(new_seuil),
                  float(new_prix_unitaire),
              ),
          )
          conn.commit()
          conn.close()
          st.success(
              f"✅ Produit '{new_nom}' ajouté avec succès (商品添加成功) !"
          )
          st.rerun()
        else:
          st.error("⚠️ Nom du produit obligatoire (商品名称不能为空).")

  st.divider()
  st.markdown("### Modifiez directement dans le tableau (在表格中直接修改库存) :")

  if not df_stock.empty:
    edited_stock = st.data_editor(
        df_stock[
            [
                "id",
                "nom",
                "categorie",
                "quantite",
                "unite",
                "seuil_alerte",
                "prix_unitaire",
            ]
        ],
        key="editor_stock",
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": "ID",
            "nom": "Produit (商品)",
            "categorie": "Catégorie (类别)",
            "quantite": st.column_config.NumberColumn(
                "Stock (库存数量)", min_value=0.0
            ),
            "unite": "Unité (单位)",
            "seuil_alerte": "Alerte (预警线)",
            "prix_unitaire": st.column_config.NumberColumn(
                "Prix HT (€) (单价)", format="%.2f €"
            ),
        },
    )

    if st.button(
        "💾 Sauvegarder les modifications du Stock (保存修改)",
        type="primary",
    ):
      conn = get_connection()
      cursor = conn.cursor()
      for _, row in edited_stock.iterrows():
        cursor.execute(
            """
                    UPDATE stock 
                    SET nom=?, categorie=?, quantite=?, unite=?, seuil_alerte=?, prix_unitaire=?
                    WHERE id=?
                    """,
            (
                str(row["nom"]),
                str(row["categorie"]),
                float(row["quantite"]),
                str(row["unite"]),
                float(row["seuil_alerte"]),
                float(row["prix_unitaire"]),
                int(row["id"]),
            ),
        )
      conn.commit()
      conn.close()
      st.success("✅ Stocks mis à jour (库存已保存更新) !")
      st.rerun()
  else:
    st.info("Le catalogue est vide. (库存为空)")


# ==========================================
# ONGLET 4 : CRM & CLIENTS
# ==========================================
with tab_crm:
  st.subheader("👥 Répertoire Clients ( Customer Directory / 客户管理 )")

  with st.expander(
      "➕ Ajouter un nouveau client (添加新客户)", expanded=False
  ):
    with st.form("form_add_client"):
      cc1, cc2 = st.columns(2)
      with cc1:
        c_entreprise = st.text_input("Nom de l'Entreprise / Client (公司/客户名) *")
        c_contact = st.text_input("Nom du Contact (联系人姓名)")
        c_telephone = st.text_input("Téléphone (电话号码)")
        c_email = st.text_input("Email (电子邮箱)")
      with cc2:
        c_cafe = st.text_input("Café habituel (常用咖啡 - 例: Grain Bio 1kg)")
        c_machine = st.checkbox("Machine à café installée (是否有借用咖啡机)")
        c_freq = st.number_input(
            "Cycle de commande habituel en jours (补货周期/天数)",
            min_value=1,
            value=30,
        )
        c_adresse = st.text_input("Adresse de livraison (送货地址)")

      if st.form_submit_button(
          "💾 Enregistrer le Client (保存客户)", use_container_width=True
      ):
        if c_entreprise.strip():
          try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                            INSERT INTO clients (nom_entreprise, nom_contact, telephone, email, adresse, type_cafe, machine_installee, frequence_jours, date_creation)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                (
                    c_entreprise.strip(),
                    c_contact.strip(),
                    c_telephone.strip(),
                    c_email.strip(),
                    c_adresse.strip(),
                    c_cafe.strip(),
                    1 if c_machine else 0,
                    int(c_freq),
                    datetime.now().strftime("%Y-%m-%d"),
                ),
            )
            conn.commit()
            conn.close()
            st.success(
                f"✅ Client '{c_entreprise}' enregistré (客户已保存) !"
            )
            st.rerun()
          except sqlite3.IntegrityError:
            st.error("⚠️ Un client avec ce nom existe déjà (该客户已存在).")
        else:
          st.error("⚠️ Le nom est obligatoire (客户名称不能为空).")

  st.divider()
  st.markdown("### Liste des Clients (客户列表) :")

  if not df_clients.empty:
    cols_display = [
        col
        for col in [
            "id",
            "nom_entreprise",
            "nom_contact",
            "telephone",
            "email",
            "type_cafe",
            "machine_installee",
            "frequence_jours",
            "adresse",
        ]
        if col in df_clients.columns
    ]

    st.dataframe(
        df_clients[cols_display],
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": "ID",
            "nom_entreprise": "Client (公司/客户)",
            "nom_contact": "Contact (联系人)",
            "telephone": "Tél (电话)",
            "email": "Email (邮箱)",
            "type_cafe": "Café Habituel (常用咖啡)",
            "machine_installee": "Machine (咖啡机)",
            "frequence_jours": "Cycle (周期/天)",
            "adresse": "Adresse (地址)",
        },
    )
  else:
    st.info("Aucun client enregistré. (暂无客户记录)")


# ==========================================
# ONGLET 5 : RELANCES COMMERCIALES
# ==========================================
with tab_relances:
  st.subheader(
      "🔔 Clients à recontacter ( Order Reminders / 客户补货/催单提醒 )"
  )

  if clients_a_relancer:
    st.warning(
        f"⚠️ **{len(clients_a_relancer)} client(s)** n'ont pas commandé depuis"
        " longtemps ! (有客户超过预定周期未下单，建议联系！)"
    )

    df_rel = pd.DataFrame(clients_a_relancer)
    st.dataframe(df_rel, use_container_width=True, hide_index=True)
  else:
    st.success(
        "✅ Tous vos clients sont à jour ! Aucun retard détecté. (所有客户订单正常，无延迟！)"
    )
