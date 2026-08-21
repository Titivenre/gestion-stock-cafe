import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="ERP Café & Clients", page_icon="☕", layout="wide"
)


# Connexion à la base de données
def get_connection():
  return sqlite3.connect("database.db")


# Initialisation et migration de la base de données
def init_db():
  conn = get_connection()
  cursor = conn.cursor()

  # Table Stock
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        categorie TEXT NOT NULL,
        quantite REAL NOT NULL,
        unite TEXT NOT NULL,
        seuil_alerte REAL NOT NULL,
        prix_unitaire REAL NOT NULL
    )
    """)

  # Table Clients
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_contact TEXT,
        nom_entreprise TEXT NOT NULL,
        adresse TEXT,
        telephone TEXT,
        email TEXT,
        machine_installee INTEGER DEFAULT 0,
        frequence_jours INTEGER DEFAULT 30
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
        statut TEXT NOT NULL
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
        FOREIGN KEY (commande_id) REFERENCES commandes (id),
        FOREIGN KEY (produit_id) REFERENCES stock (id)
    )
    """)

  # Exemples initiaux
  cursor.execute("SELECT COUNT(*) FROM stock")
  if cursor.fetchone()[0] == 0:
    exemples_stock = [
        ("Café Arabica Grain Colombie", "Café", 120.0, "kg", 20.0, 18.50),
        ("Café Robusta Moulu Viêt Nam", "Café", 15.0, "kg", 25.0, 14.00),
        (
            "Sacs d'emballage 1kg",
            "Conditionnement",
            450.0,
            "unités",
            100.0,
            0.40,
        ),
    ]
    cursor.executemany("""
        INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
        VALUES (?, ?, ?, ?, ?, ?)
        """, exemples_stock)

  conn.commit()
  conn.close()


init_db()

# Titre
st.title("☕ ERP Café - Gestion globale & CRM")

# Données actuelles
conn = get_connection()
df_stock = pd.read_sql_query("SELECT * FROM stock", conn)
df_clients = pd.read_sql_query("SELECT * FROM clients", conn)
df_commandes = pd.read_sql_query(
    "SELECT * FROM commandes ORDER BY id DESC", conn
)
conn.close()

# CALCUL DES RAPPELS (Clients à relancer)
clients_a_relancer = []
if not df_clients.empty and not df_commandes.empty:
  actuel = datetime.now()
  for _, cli in df_clients.iterrows():
    cmds_cli = df_commandes[df_commandes["client_nom"] == cli["nom_entreprise"]]
    if not cmds_cli.empty:
      derniere_date_str = cmds_cli.iloc[0]["date_commande"]
      try:
        derniere_date = datetime.strptime(
            derniere_date_str, "%Y-%m-%d %H:%M"
        )
      except ValueError:
        derniere_date = datetime.strptime(derniere_date_str, "%Y-%m-%d")

      prochaine_date = derniere_date + timedelta(
          days=int(cli["frequence_jours"])
      )
      if actuel > prochaine_date:
        retard = (actuel - prochaine_date).days
        clients_a_relancer.append({
            "Entreprise": cli["nom_entreprise"],
            "Contact": cli["nom_contact"],
            "Téléphone": cli["telephone"],
            "Dernière Commande": derniere_date_str,
            "Retard (Jours)": retard,
        })

# KPIs
c1, c2, c3, c4 = st.columns(4)
valeur_stock = (
    (df_stock["quantite"] * df_stock["prix_unitaire"]).sum()
    if not df_stock.empty
    else 0
)
c1.metric("Valeur du Stock", f"{valeur_stock:,.2f} €")
c2.metric("Clients Enregistrés", len(df_clients))
c3.metric(
    "🚨 Relances à Faire",
    len(clients_a_relancer),
    delta_color="inverse",
)
c4.metric("Commandes Totales", len(df_commandes))

st.divider()

# Navigation
tab_stock, tab_commande, tab_relance, tab_clients, tab_historique = st.tabs([
    "📦 Gestion Stock",
    "🛒 Passer une Commande",
    "🔔 Rappels & Relances",
    "👥 Repertoire Clients",
    "📜 Historique Commandes",
])

# --- ONGLET 1 : STOCK ---
with tab_stock:
  st.subheader("État du Stock (Modifiable)")
  if not df_stock.empty:
    edited_df = st.data_editor(
        df_stock,
        key="stock_editor",
        use_container_width=True,
        hide_index=True,
    )
    if st.button("💾 Sauvegarder les modifications du stock"):
      conn = get_connection()
      cursor = conn.cursor()
      for _, row in edited_df.iterrows():
        cursor.execute(
            """
                UPDATE stock 
                SET nom = ?, categorie = ?, quantite = ?, unite = ?, seuil_alerte = ?, prix_unitaire = ?
                WHERE id = ?
                """,
            (
                row["nom"],
                row["categorie"],
                row["quantite"],
                row["unite"],
                row["seuil_alerte"],
                row["prix_unitaire"],
                row["id"],
            ),
        )
      conn.commit()
      conn.close()
      st.success("Stock mis à jour !")
      st.rerun()

# --- ONGLET 2 : NOUVELLE COMMANDE ---
with tab_commande:
  st.subheader("Créer une Commande Multi-Produits")

  if df_clients.empty:
    st.warning("⚠️ Veillez d'abord ajouter au moins un client dans l'onglet 'Répertoire Clients'.")
  else:
    if "panier" not in st.session_state:
      st.session_state.panier = []

    c_cmd1, c_cmd2 = st.columns([1, 1])

    with c_cmd1:
      st.write("### 1. Client & Tarif")
      client_choisi_nom = st.selectbox(
          "Sélectionner le Client", df_clients["nom_entreprise"].tolist()
      )
      client_info = df_clients[
          df_clients["nom_entreprise"] == client_choisi_nom
      ].iloc[0]

      a_machine = client_info["machine_installee"] == 1
      if a_machine:
        st.success(
            "💡 **Machine installée chez ce client : Remise de 15 % appliquée sur le café !**"
        )
      else:
        st.info("Client standard (Tarif normal)")

      st.write("### 2. Sélection des produits")
      if not df_stock.empty:
        prod_options = {
            f"{row['nom']} (Stock: {row['quantite']} {row['unite']})": row
            for _, row in df_stock.iterrows()
        }
        choix_prod_nom = st.selectbox(
            "Produit à ajouter", list(prod_options.keys())
        )
        prod_choisi = prod_options[choix_prod_nom]

        qte_souhaitee = st.number_input(
            f"Quantité ({prod_choisi['unite']})",
            min_value=0.1,
            max_value=float(prod_choisi["quantite"]),
            value=1.0,
        )

        prix_appl = prod_choisi["prix_unitaire"]
        if a_machine and prod_choisi["categorie"] == "Café":
          prix_appl = prix_appl * 0.85  # 15% de réduction

        if st.button("➕ Ajouter au panier"):
          st.session_state.panier.append({
              "produit_id": prod_choisi["id"],
              "nom": prod_choisi["nom"],
              "quantite": qte_souhaitee,
              "unite": prod_choisi["unite"],
              "prix_unitaire": prix_appl,
              "total": qte_souhaitee * prix_appl,
          })
          st.success("Produit ajouté !")

    with c_cmd2:
      st.write("### 3. Panier & Validation")
      if st.session_state.panier:
        df_p = pd.DataFrame(st.session_state.panier)
        st.dataframe(
            df_p[["nom", "quantite", "unite", "prix_unitaire", "total"]],
            use_container_width=True,
            hide_index=True,
        )

        total_cmd = df_p["total"].sum()
        st.write(f"### Total HT : **{total_cmd:,.2f} €**")

        code_courrier_input = st.text_input("Code Suivi / Courrier (Optionnel)")

        if st.button("✅ Valider la Commande", type="primary"):
          conn = get_connection()
          cursor = conn.cursor()
          date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

          cursor.execute(
              """
                    INSERT INTO commandes (client_id, client_nom, date_commande, code_courrier, prix_total, statut)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
              (
                  int(client_info["id"]),
                  client_choisi_nom,
                  date_str,
                  code_courrier_input,
                  total_cmd,
                  "En préparation",
              ),
          )
          cmd_id = cursor.lastrowid

          for item in st.session_state.panier:
            cursor.execute(
                """
                        INSERT INTO lignes_commande (commande_id, produit_id, nom_produit, quantite, prix_unitaire)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                (
                    cmd_id,
                    item["produit_id"],
                    item["nom"],
                    item["quantite"],
                    item["prix_unitaire"],
                ),
            )
            cursor.execute(
                "UPDATE stock SET quantite = quantite - ? WHERE id = ?",
                (item["quantite"], item["produit_id"]),
            )

          conn.commit()
          conn.close()

          st.session_state.panier = []
          st.success(f"Commande N°{cmd_id} enregistrée sans erreur !")
          st.rerun()

        if st.button("🗑️ Vider le panier"):
          st.session_state.panier = []
          st.rerun()

# --- ONGLET 3 : RELANCES CLIENTS ---
with tab_relance:
  st.subheader("🔔 Clients ayant dépassé leur fréquence de commande")
  if clients_a_relancer:
    st.error(
        f"⚠️ **{len(clients_a_relancer)} client(s) devrai(ent) déjà avoir recommandé du café !**"
    )
    st.dataframe(
        pd.DataFrame(clients_a_relancer),
        use_container_width=True,
        hide_index=True,
    )
  else:
    st.success("✅ Aucun retard de commande détecté pour le moment.")

# --- ONGLET 4 : REPERTOIRE CLIENTS ---
with tab_clients:
  st.subheader("Gestion de la Base Clients")

  with st.expander("➕ Ajouter un nouveau client"):
    with st.form("form_add_client"):
      f1, f2 = st.columns(2)
      with f1:
        nom_ent = st.text_input("Nom de l'Entreprise *")
        nom_cont = st.text_input("Nom du Contact")
        tel = st.text_input("Téléphone")
      with f2:
        email = st.text_input("Email")
        adr = st.text_area("Adresse complète", height=68)

      f3, f4 = st.columns(2)
      with f3:
        machine = st.checkbox("Machine à café mise à disposition chez eux ?")
      with f4:
        freq = st.number_input(
            "Fréquence de commande habituelle (en jours)",
            min_value=1,
            value=30,
        )

      if st.form_submit_button("Enregistrer le client"):
        if nom_ent:
          conn = get_connection()
          cursor = conn.cursor()
          cursor.execute(
              """
                    INSERT INTO clients (nom_entreprise, nom_contact, telephone, email, adresse, machine_installee, frequence_jours)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
              (
                  nom_ent,
                  nom_cont,
                  tel,
                  email,
                  adr,
                  1 if machine else 0,
                  int(freq),
              ),
          )
          conn.commit()
          conn.close()
          st.success("Client ajouté !")
          st.rerun()

  if not df_clients.empty:
    st.dataframe(df_clients, use_container_width=True, hide_index=True)

# --- ONGLET 5 : HISTORIQUE ---
with tab_historique:
  st.subheader("Historique des Commandes & Suivis")
  if not df_commandes.empty:
    conn = get_connection()
    for _, cmd in df_commandes.iterrows():
      with st.expander(
          f"Commande N°{cmd['id']} - {cmd['client_nom']} ({cmd['prix_total']:,.2f} €)"
      ):
        st.write(f"**Date :** {cmd['date_commande']}")
        st.write(
            f"**Code Suivi/Courrier :** {cmd['code_courrier'] or 'Non renseigné'}"
        )

        df_l = pd.read_sql_query(
            f"SELECT nom_produit, quantite, prix_unitaire FROM lignes_commande WHERE commande_id = {cmd['id']}",
            conn,
        )
        st.dataframe(df_l, use_container_width=True, hide_index=True)
    conn.close()
