import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURATION & STYLE ENTERPRISE
# ==========================================
st.set_page_config(
    page_title="ERP Café Pro — Enterprise Edition",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS pour une interface sobre et moderne (paramètre corrigé : unsafe_allow_html)
st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
    }
    .stSelectbox, .stTextInput, .stNumberInput {
        margin-bottom: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_FILE = "database.db"


# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES SÉCURISÉE
# ==========================================
def get_connection():
  """Connexion sécurisée avec timeout pour éviter les verrous de BDD."""
  conn = sqlite3.connect(DB_FILE, timeout=20)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  """Initialisation et auto-migration du schéma sans risque de perte de données."""
  conn = get_connection()
  cursor = conn.cursor()

  try:
    cursor.execute("PRAGMA journal_mode=WAL;")
  except Exception:
    pass

  # Table Stock
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

  # Table Clients
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

  # Table Commandes
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS commandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_nom TEXT NOT NULL,
        date_commande TEXT NOT NULL,
        code_courrier TEXT,
        prix_total REAL NOT NULL,
        statut TEXT NOT NULL DEFAULT 'En préparation',
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )
    """)

  # Table Lignes de commande
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

  # Migration dynamique pour ajouter TOUTES les colonnes pouvant manquer
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
  safe_add_column("commandes", "code_courrier TEXT")
  safe_add_column("commandes", "statut TEXT DEFAULT 'En préparation'")
  safe_add_column("stock", "prix_achat REAL DEFAULT 0")

  conn.commit()
  conn.close()


init_db()


# ==========================================
# 3. CHARGEMENT ET TRAITEMENT DES DONNÉES
# ==========================================
def load_data():
  conn = get_connection()
  df_s = pd.read_sql_query("SELECT * FROM stock", conn)
  df_c = pd.read_sql_query("SELECT * FROM clients", conn)
  df_cmd = pd.read_sql_query("SELECT * FROM commandes ORDER BY id DESC", conn)
  conn.close()
  return df_s, df_c, df_cmd


df_stock, df_clients, df_commandes = load_data()

# Calcul des relances
clients_a_relancer = []
if not df_clients.empty and not df_commandes.empty:
  now = datetime.now()
  for _, cli in df_clients.iterrows():
    cmds = df_commandes[df_commandes["client_nom"] == cli["nom_entreprise"]]
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
            "ID": cli["id"],
            "Entreprise": cli["nom_entreprise"],
            "Contact": cli["nom_contact"] or "N/A",
            "Café habituel": (
                cli["type_cafe"]
                if pd.notna(cli["type_cafe"])
                else "Non renseigné"
            ),
            "Téléphone": cli["telephone"] or "N/A",
            "Dernière Commande": last_date_str,
            "Retard (Jours)": retard,
        })


# ==========================================
# 4. EN-TÊTE & DASHBOARD EXECUTIVE
# ==========================================
st.title("☕ ERP Café Pro — Solution de Gestion")
st.caption(
    "Système intégré de gestion de stock, CRM client, commandes et logistique"
)

col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)

valeur_stock_ht = (
    (df_stock["quantite"] * df_stock["prix_unitaire"]).sum()
    if not df_stock.empty
    else 0.0
)
alertes_stock = (
    len(df_stock[df_stock["quantite"] <= df_stock["seuil_alerte"]])
    if not df_stock.empty
    else 0
)
ca_total = (
    df_commandes["prix_total"].sum() if not df_commandes.empty else 0.0
)

col_kpi1.metric("📦 Valeur Stock (HT)", f"{valeur_stock_ht:,.2f} €")
col_kpi2.metric("👥 Répertoire Clients", len(df_clients))
col_kpi3.metric("🛒 CA Total Généré", f"{ca_total:,.2f} €")
col_kpi4.metric("🚨 Alertes Stock Bas", alertes_stock)
col_kpi5.metric(
    "🔔 Relances à Faire", len(clients_a_relancer), delta_color="inverse"
)

st.divider()

# Navigation principale par Onglets
tab_pos, tab_cmd_hist, tab_stock, tab_crm, tab_relances = st.tabs([
    "🛒 Prise de Commande (POS)",
    "📜 Commandes & Logistique",
    "📦 Gestion des Stocks",
    "👥 CRM & Fiches Clients",
    "🔔 Rappels & Relances",
])

# ==========================================
# ONGLET 1 : PRISE DE COMMANDE (POS)
# ==========================================
with tab_pos:
  st.subheader("Créer une nouvelle commande")

  if df_clients.empty:
    st.info("💡 Ajoutez votre premier client dans l'onglet **'CRM'**.")
  elif df_stock.empty:
    st.info(
        "💡 Ajoutez vos premiers articles dans l'onglet **'Gestion des"
        " Stocks'**."
    )
  else:
    if "panier" not in st.session_state:
      st.session_state.panier = []

    c_left, c_right = st.columns([1, 1], gap="medium")

    with c_left:
      st.markdown("##### 1. Sélection du Client")
      selected_client_name = st.selectbox(
          "Choisir le client *",
          options=df_clients["nom_entreprise"].tolist(),
          key="pos_client_select",
      )

      client_row = df_clients[
          df_clients["nom_entreprise"] == selected_client_name
      ].iloc[0]

      cafe_habituel = (
          client_row["type_cafe"]
          if pd.notna(client_row["type_cafe"]) and str(client_row["type_cafe"]).strip()
          else "Non renseigné"
      )
      machine = "Oui" if client_row["machine_installee"] == 1 else "Non"

      st.info(
          f"🏢 **Client :** {selected_client_name}  \n"
          f"☕ **Café habituel :** {cafe_habituel} | ⚙️ **Machine en prêt :** {machine}  \n"
          f"📞 **Contact :** {client_row['nom_contact'] or 'N/A'} ({client_row['telephone'] or 'N/A'})"
      )

      st.markdown("##### 2. Sélection des produits")
      p_options = {}
      for _, r in df_stock.iterrows():
        label = f"[{r['categorie']}] {r['nom']} — Stock: {r['quantite']} {r['unite']} ({r['prix_unitaire']:.2f} €/u)"
        p_options[label] = r

      selected_prod_label = st.selectbox(
          "Rechercher un produit *", list(p_options.keys()), key="pos_prod_select"
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
            f"Quantité ({selected_prod['unite']})",
            min_value=0.1,
            max_value=max_qte,
            value=min(1.0, max_qte),
            step=1.0,
        )
      with col_q2:
        remise_input = st.number_input(
            "Remise article (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=5.0,
        )

      prix_base = float(selected_prod["prix_unitaire"])
      prix_effectif = prix_base * (1.0 - (remise_input / 100.0))

      if remise_input > 0:
        st.caption(
            f"Prix unitaire remisé : **{prix_effectif:.2f} € HT** (au lieu de"
            f" {prix_base:.2f} €)"
        )

      if st.button("➕ Ajouter la ligne au panier", use_container_width=True):
        if selected_prod["quantite"] < qte_input:
          st.error("Stock insuffisant pour ce produit !")
        else:
          st.session_state.panier.append({
              "produit_id": int(selected_prod["id"]),
              "nom": str(selected_prod["nom"]),
              "quantite": float(qte_input),
              "unite": str(selected_prod["unite"]),
              "prix_unitaire": float(prix_effectif),
              "total": float(qte_input * prix_effectif),
          })
          st.success(f"'{selected_prod['nom']}' ajouté au panier.")
          st.rerun()

    with c_right:
      st.markdown("##### 3. Récapitulatif de la Commande")
      if st.session_state.panier:
        df_cart = pd.DataFrame(st.session_state.panier)

        st.dataframe(
            df_cart[["nom", "quantite", "unite", "prix_unitaire", "total"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nom": "Produit",
                "quantite": "Qté",
                "unite": "Unité",
                "prix_unitaire": st.column_config.NumberColumn(
                    "Prix U. HT", format="%.2f €"
                ),
                "total": st.column_config.NumberColumn(
                    "Total HT", format="%.2f €"
                ),
            },
        )

        total_ht = float(df_cart["total"].sum())
        tva = total_ht * 0.20
        total_ttc = total_ht + tva

        col_tot1, col_tot2 = st.columns(2)
        col_tot1.metric("Total HT", f"{total_ht:,.2f} €")
        col_tot2.metric("Total TTC (20%)", f"{total_ttc:,.2f} €")

        code_suivi = st.text_input(
            "Code Suivi / N° de Courrier (Optionnel)",
            placeholder="Ex: FR-849302-X",
        )

        col_act1, col_act2 = st.columns(2)
        with col_act1:
         if st.button(
    "✅ Valider & Enregistrer", type="primary", use_container_width=True
):
  try:
    conn = get_connection()
    cursor = conn.cursor()
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Vérification des colonnes réelles de la table 'commandes'
    cursor.execute("PRAGMA table_info(commandes)")
    cmd_cols = [r[1] for r in cursor.fetchall()]

    if "client_id" in cmd_cols:
      cursor.execute(
          """
                INSERT INTO commandes (client_id, client_nom, date_commande, code_courrier, prix_total, statut)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
          (
              int(client_row["id"]),
              str(selected_client_name),
              date_now,
              str(code_suivi).strip(),
              float(total_ht),
              "En préparation",
          ),
      )
    else:
      cursor.execute(
          """
                INSERT INTO commandes (client_nom, date_commande, code_courrier, prix_total, statut)
                VALUES (?, ?, ?, ?, ?)
                """,
          (
              str(selected_client_name),
              date_now,
              str(code_suivi).strip(),
              float(total_ht),
              "En préparation",
          ),
      )

    cmd_id = cursor.lastrowid

    for item in st.session_state.panier:
      cursor.execute(
          """
                INSERT INTO lignes_commande (commande_id, produit_id, nom_produit, quantite, prix_unitaire, total_ligne)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
          (
              int(cmd_id),
              int(item["produit_id"]),
              str(item["nom"]),
              float(item["quantite"]),
              float(item["prix_unitaire"]),
              float(item["total"]),
          ),
      )
      cursor.execute(
          """
                UPDATE stock 
                SET quantite = MAX(0, quantite - ?) 
                WHERE id = ?
                """,
          (float(item["quantite"]), int(item["produit_id"])),
      )

    conn.commit()
    conn.close()

    st.session_state.panier = []
    st.balloons()
    st.success(f"🎉 Commande N°{cmd_id} enregistrée avec succès !")
    st.rerun()

  except Exception as e:
    st.error(f"Erreur lors de l'enregistrement : {e}")

# ==========================================
# ONGLET 2 : LOGISTIQUE & HISTORIQUE
# ==========================================
with tab_cmd_hist:
  st.subheader("Historique des Commandes & Suivi Logistique")

  if not df_commandes.empty:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
      filter_client = st.selectbox(
          "Filtrer par Client",
          ["Tous"] + df_commandes["client_nom"].unique().tolist(),
      )
    with col_f2:
      filter_statut = st.selectbox(
          "Filtrer par Statut",
          ["Tous", "En préparation", "Expédiée", "Livrée", "Annulée"],
      )

    df_filtered = df_commandes.copy()
    if filter_client != "Tous":
      df_filtered = df_filtered[df_filtered["client_nom"] == filter_client]
    if filter_statut != "Tous":
      df_filtered = df_filtered[df_filtered["statut"] == filter_statut]

    conn = get_connection()
    for _, cmd in df_filtered.iterrows():
      status_color = (
          "🟡"
          if cmd["statut"] == "En préparation"
          else ("🔵" if cmd["statut"] == "Expédiée" else "🟢")
      )

      header_text = f"{status_color} Commande N°{cmd['id']} — {cmd['client_nom']} — {cmd['prix_total']:,.2f} € HT ({cmd['date_commande']})"

      with st.expander(header_text):
        c_info1, c_info2 = st.columns(2)

        with c_info1:
          st.write(f"**Client :** {cmd['client_nom']}")
          st.write(f"**Date :** {cmd['date_commande']}")
          st.write(f"**Code Suivi/Courrier :** {cmd['code_courrier'] or 'N/A'}")

        with c_info2:
          new_statut = st.selectbox(
              "Changer le statut :",
              ["En préparation", "Expédiée", "Livrée", "Annulée"],
              index=["En préparation", "Expédiée", "Livrée", "Annulée"].index(
                  cmd["statut"]
                  if cmd["statut"]
                  in ["En préparation", "Expédiée", "Livrée", "Annulée"]
                  else "En préparation"
              ),
              key=f"status_select_{cmd['id']}",
          )
          if new_statut != cmd["statut"]:
            c_up = get_connection()
            c_up.execute(
                "UPDATE commandes SET statut = ? WHERE id = ?",
                (new_statut, cmd["id"]),
            )
            c_up.commit()
            c_up.close()
            st.success("Statut mis à jour !")
            st.rerun()

        df_lines = pd.read_sql_query(
            "SELECT nom_produit as Produit, quantite as Quantité, prix_unitaire"
            " as 'Prix U. HT', total_ligne as 'Total HT' FROM lignes_commande"
            f" WHERE commande_id = {cmd['id']}",
            conn,
        )
        st.dataframe(df_lines, use_container_width=True, hide_index=True)

    conn.close()
  else:
    st.info("Aucune commande dans l'historique pour le moment.")

# ==========================================
# ONGLET 3 : GESTION DU STOCK
# ==========================================
with tab_stock:
  st.subheader("Gestion & Entrées en Stock")

  with st.expander("➕ Ajouter un nouveau produit au catalogue", expanded=False):
    with st.form("form_add_stock"):
      cols1, cols2 = st.columns(2)
      with cols1:
        new_nom = st.text_input("Nom du produit *")
        new_cat = st.selectbox(
            "Catégorie *",
            [
                "Café en Grain",
                "Café Moulu",
                "Gélules / Capsules",
                "Machines & Équipements",
                "Sucre & Encas",
                "Accessoires & Gobelets",
                "Autre",
            ],
        )
        new_unite = st.selectbox(
            "Unité de mesure",
            ["kg", "unités", "sachets", "cartons", "bouteilles"],
        )
      with cols2:
        new_qte = st.number_input("Quantité initiale", min_value=0.0, value=10.0)
        new_prix_unitaire = st.number_input(
            "Prix de vente HT (€)", min_value=0.0, value=12.0
        )
        new_seuil = st.number_input(
            "Seuil d'alerte stock", min_value=0.0, value=5.0
        )

      if st.form_submit_button(
          "💾 Enregistrer le Produit", use_container_width=True
      ):
        if new_nom.strip():
          conn = get_connection()
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
              (
                  new_nom.strip(),
                  new_cat,
                  float(new_qte),
                  new_unite,
                  float(new_seuil),
                  float(new_prix_unitaire),
              ),
          )
          conn.commit()
          conn.close()
          st.success(f"Produit '{new_nom}' ajouté !")
          st.rerun()
        else:
          st.error("Nom du produit obligatoire.")

  st.divider()
  st.subheader("📋 État et Édition du Stock")

  if not df_stock.empty:
    edited_stock = st.data_editor(
        df_stock,
        key="editor_stock",
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": "ID",
            "nom": "Produit",
            "categorie": "Catégorie",
            "quantite": st.column_config.NumberColumn(
                "Quantité en Stock", min_value=0.0
            ),
            "unite": "Unité",
            "seuil_alerte": "Seuil d'Alerte",
            "prix_unitaire": st.column_config.NumberColumn(
                "Prix Vente HT (€)", format="%.2f €"
            ),
        },
    )

    if st.button("💾 Sauvegarder les modifications du Stock"):
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
      st.success("Mise à jour du stock effectuée avec succès !")
      st.rerun()
  else:
    st.info("Le catalogue de stock est vide.")

# ==========================================
# ONGLET 4 : CRM & CLIENTS
# ==========================================
with tab_crm:
  st.subheader("Répertoire & Fiches Clients")

  with st.expander("➕ Créer une nouvelle fiche client", expanded=False):
    with st.form("form_add_client"):
      cc1, cc2 = st.columns(2)
      with cc1:
        c_entreprise = st.text_input("Nom de l'Entreprise / Client *")
        c_contact = st.text_input("Nom du Contact")
        c_telephone = st.text_input("Téléphone")
        c_email = st.text_input("Adresse Email")
      with cc2:
        c_cafe = st.text_input(
            "Type de café habituel (ex: Grain Bio Arabica 1kg)"
        )
        c_machine = st.checkbox("Machine à café installée en entreprise")
        c_freq = st.number_input(
            "Fréquence de réapprovisionnement (en jours)",
            min_value=1,
            value=30,
        )
        c_adresse = st.text_input("Adresse de livraison")

      if st.form_submit_button(
          "💾 Enregistrer le Client", use_container_width=True
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
            st.success(f"Client '{c_entreprise}' ajouté au répertoire !")
            st.rerun()
          except sqlite3.IntegrityError:
            st.error("Un client avec ce nom existe déjà.")
        else:
          st.error("Le nom de l'entreprise est obligatoire.")

  st.divider()
  st.subheader("📋 Liste des Clients Enregistrés")

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
            "nom_entreprise": "Entreprise",
            "nom_contact": "Contact",
            "telephone": "Téléphone",
            "email": "Email",
            "type_cafe": "Café Habituel",
            "machine_installee": "Machine Posée",
            "frequence_jours": "Cycle (Jours)",
            "adresse": "Adresse",
        },
    )
  else:
    st.info("Aucun client dans le répertoire.")

# ==========================================
# ONGLET 5 : RELANCES & RAPPELS
# ==========================================
with tab_relances:
  st.subheader("🔔 Suivi des Relances Commerciales")

  if clients_a_relancer:
    st.warning(
        f"⚠️ **{len(clients_a_relancer)} client(s)** ont dépassé leur cycle"
        " habituel de réapprovisionnement !"
    )

    df_rel = pd.DataFrame(clients_a_relancer)
    st.dataframe(
        df_rel[[
            "Entreprise",
            "Contact",
            "Téléphone",
            "Café habituel",
            "Dernière Commande",
            "Retard (Jours)",
        ]],
        use_container_width=True,
        hide_index=True,
    )
  else:
    st.success(
        "✅ Aucun client en retard de réapprovisionnement pour le moment !"
    )
