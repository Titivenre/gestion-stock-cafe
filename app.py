import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# Configuration
st.set_page_config(
    page_title="ERP Café & Clients", page_icon="☕", layout="wide"
)


# Connexion BDD
def get_connection():
  return sqlite3.connect("database.db")


# Initialisation des tables BDD avec mise à jour automatique
def init_db():
  conn = get_connection()
  cursor = conn.cursor()

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

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_entreprise TEXT NOT NULL,
        nom_contact TEXT,
        adresse TEXT,
        telephone TEXT,
        email TEXT,
        type_cafe TEXT,
        machine_installee INTEGER DEFAULT 0,
        frequence_jours INTEGER DEFAULT 30
    )
    """)

  # Vérification et ajout dynamique de la colonne type_cafe si manquante
  cursor.execute("PRAGMA table_info(clients)")
  columns = [column[1] for column in cursor.fetchall()]
  if "type_cafe" not in columns:
    cursor.execute("ALTER TABLE clients ADD COLUMN type_cafe TEXT")

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

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS lignes_commande (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        commande_id INTEGER NOT NULL,
        produit_id INTEGER NOT NULL,
        nom_produit TEXT NOT NULL,
        quantite REAL NOT NULL,
        prix_unitaire REAL NOT NULL
    )
    """)

  conn.commit()
  conn.close()


init_db()

# Titre
st.title("☕ ERP Café - Gestion globale & CRM")

# Chargement données
conn = get_connection()
df_stock = pd.read_sql_query("SELECT * FROM stock", conn)
df_clients = pd.read_sql_query("SELECT * FROM clients", conn)
df_commandes = pd.read_sql_query(
    "SELECT * FROM commandes ORDER BY id DESC", conn
)
conn.close()

# Relances
clients_a_relancer = []
if not df_clients.empty and not df_commandes.empty:
  actuel = datetime.now()
  for _, cli in df_clients.iterrows():
    cmds_cli = df_commandes[df_commandes["client_nom"] == cli["nom_entreprise"]]
    if not cmds_cli.empty:
      derniere_date_str = cmds_cli.iloc[0]["date_commande"]
      try:
        derniere_date = datetime.strptime(derniere_date_str, "%Y-%m-%d %H:%M")
      except ValueError:
        derniere_date = datetime.strptime(derniere_date_str, "%Y-%m-%d")

      prochaine_date = derniere_date + timedelta(
          days=int(cli["frequence_jours"])
      )
      if actuel > prochaine_date:
        retard = (actuel - prochaine_date).days
        clients_a_relancer.append({
            "Entreprise": cli["nom_entreprise"],
            "Contact": cli["nom_contact"] or "N/A",
            "Café habituel": cli.get("type_cafe", "Non précisé"),
            "Téléphone": cli["telephone"] or "N/A",
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
c1.metric("Valeur Stock", f"{valeur_stock:,.2f} €")
c2.metric("Clients", len(df_clients))
c3.metric(
    "🚨 Relances à Faire",
    len(clients_a_relancer),
    delta_color="inverse",
)
c4.metric("Commandes Total", len(df_commandes))

st.divider()

# Navigation
tab_stock, tab_commande, tab_relance, tab_clients, tab_historique = st.tabs([
    "📦 Gestion Stock",
    "🛒 Passer une Commande",
    "🔔 Rappels & Relances",
    "👥 Répertoire Clients",
    "📜 Historique Commandes",
])

# --- ONGLET 1 : STOCK ---
with tab_stock:
  st.subheader("➕ Ajouter un nouveau produit au stock")

  categories_de_base = [
      "Café",
      "Machines & Équipements",
      "Sucre",
      "Biscuits",
      "Alcools & Vins",
      "Gobelets",
      "Autre (créer une catégorie)",
  ]

  with st.form("add_stock_form"):
    col_s1, col_s2 = st.columns(2)
    with col_s1:
      nom_prod = st.text_input("Nom du produit *")
      cat_choix = st.selectbox("Catégorie *", categories_de_base)
      cat_custom = st.text_input(
          "Si 'Autre', tapez la nouvelle catégorie ici :"
      )
    with col_s2:
      qte_prod = st.number_input(
          "Quantité initiale", min_value=0.0, value=10.0, step=1.0
      )
      unite_prod = st.selectbox(
          "Unité", ["kg", "unités", "sachets", "cartons", "bouteilles", "paquets"]
      )
      prix_prod = st.number_input(
          "Prix unitaire HT (€)", min_value=0.0, value=5.0, step=0.5
      )
      seuil_prod = st.number_input(
          "Seuil d'alerte stock bas", min_value=0.0, value=5.0
      )

    if st.form_submit_button("➕ Ajouter au Stock"):
      cat_final = (
          cat_custom.strip()
          if cat_choix == "Autre (créer une catégorie)" and cat_custom.strip()
          else cat_choix
      )
      if nom_prod.strip():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
            (
                nom_prod.strip(),
                cat_final,
                qte_prod,
                unite_prod,
                seuil_prod,
                prix_prod,
            ),
        )
        conn.commit()
        conn.close()
        st.success(f"Produit '{nom_prod}' ajouté avec succès !")
        st.rerun()
      else:
        st.error("Veuillez saisir au moins un nom de produit.")

  st.divider()
  st.subheader("📋 État du Stock (Modifiable en direct)")
  if not df_stock.empty:
    edited_df = st.data_editor(
        df_stock,
        key="stock_editor",
        use_container_width=True,
        hide_index=True,
    )
    if st.button("💾 Sauvegarder les modifications du tableau stock"):
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
      st.success("Modifications du stock enregistrées !")
      st.rerun()
  else:
    st.info(
        "Le stock est vide. Utilisez le formulaire ci-dessus pour ajouter des"
        " articles."
    )

# --- ONGLET 2 : COMMANDE ---
with tab_commande:
  st.subheader("Créer une Commande")

  if df_clients.empty:
    st.warning("⚠️ Enregistrez d'abord un client dans le 'Répertoire Clients'.")
  elif df_stock.empty:
    st.warning(
        "⚠️ Aucun produit en stock. Ajoutez-en dans l'onglet 'Gestion Stock'."
    )
  else:
    if "panier" not in st.session_state:
      st.session_state.panier = []

    c_cmd1, c_cmd2 = st.columns([1, 1])

    with c_cmd1:
      st.write("### 1. Sélection du Client")
      client_choisi_nom = st.selectbox(
          "Client", df_clients["nom_entreprise"].tolist()
      )
      client_info = df_clients[
          df_clients["nom_entreprise"] == client_choisi_nom
      ].iloc[0]

      st.info(
          f"☕ **Café habituel :** {client_info.get('type_cafe', 'Non précisé')}  \n"
          f"⚙️ **Machine posée :** {'Oui' if client_info['machine_installee'] == 1 else 'Non'}"
      )

      st.write("### 2. Ajouter des produits")
      prod_options = {
          f"[{row['categorie']}] {row['nom']} (Stock: {row['quantite']}"
          f" {row['unite']})": row
          for _, row in df_stock.iterrows()
      }
      choix_prod_nom = st.selectbox("Produit", list(prod_options.keys()))
      prod_choisi = prod_options[choix_prod_nom]

      qte_souhaitee = st.number_input(
          f"Quantité ({prod_choisi['unite']})",
          min_value=0.1,
          max_value=max(float(prod_choisi["quantite"]), 0.1),
          value=1.0,
      )

      remise_pct = st.number_input(
          "Remise personnalisée sur cet article (%)",
          min_value=0.0,
          max_value=100.0,
          value=0.0,
      )
      prix_final = prod_choisi["prix_unitaire"] * (1 - (remise_pct / 100.0))

      if remise_pct > 0:
        st.write(f"Prix remisé : **{prix_final:,.2f} €**")

      if st.button("➕ Ajouter la ligne au panier"):
        st.session_state.panier.append({
            "produit_id": int(prod_choisi["id"]),
            "nom": str(prod_choisi["nom"]),
            "quantite": float(qte_souhaitee),
            "unite": str(prod_choisi["unite"]),
            "prix_unitaire": float(prix_final),
            "total": float(qte_souhaitee * prix_final),
        })
        st.success("Ajouté !")

    with c_cmd2:
      st.write("### 3. Récapitulatif du Panier")
      if st.session_state.panier:
        df_p = pd.DataFrame(st.session_state.panier)
        st.dataframe(
            df_p[["nom", "quantite", "unite", "prix_unitaire", "total"]],
            use_container_width=True,
            hide_index=True,
        )

        total_cmd = float(df_p["total"].sum())
        st.write(f"### Total HT : **{total_cmd:,.2f} €**")

        code_courrier_input = st.text_input("Code Suivi / Courrier (Optionnel)")

        if st.button("✅ Valider et Enregistrer la Commande", type="primary"):
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
                  str(client_choisi_nom),
                  date_str,
                  str(code_courrier_input),
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
                    int(cmd_id),
                    int(item["produit_id"]),
                    str(item["nom"]),
                    float(item["quantite"]),
                    float(item["prix_unitaire"]),
                ),
            )
            cursor.execute(
                "UPDATE stock SET quantite = quantite - ? WHERE id = ?",
                (float(item["quantite"]), int(item["produit_id"])),
            )

          conn.commit()
          conn.close()

          st.session_state.panier = []
          st.success(f"Commande N°{cmd_id} enregistrée !")
          st.rerun()

        if st.button("🗑️ Vider le panier"):
          st.session_state.panier = []
          st.rerun()

# --- ONGLET 3 : RELANCES ---
with tab_relance:
  st.subheader("🔔 Clients à relancer pour commander")
  if clients_a_relancer:
    st.error(
        f"⚠️ **{len(clients_a_relancer)} client(s) ont dépassé leur date"
        " habituelle de commande !**"
    )
    st.dataframe(
        pd.DataFrame(clients_a_relancer),
        use_container_width=True,
        hide_index=True,
    )
  else:
    st.info("Aucune relance à prévoir pour le moment.")

# --- ONGLET 4 : REPERTOIRE CLIENTS ---
with tab_clients:
  st.subheader("➕ Ajouter un Client")

  nom_entreprise = st.text_input("Nom du Client / Entreprise *")

  c1_cli, c2_cli = st.columns(2)
  with c1_cli:
    type_cafe = st.text_input(
        "Type de café habituel (ex: Arabica Grain, Grain Bio, Robusta Moulu)"
    )
    nom_contact = st.text_input("Nom du contact (Optionnel)")
    telephone = st.text_input("Téléphone (Optionnel)")
  with c2_cli:
    machine_inst = st.checkbox("Machine à café posée chez eux ?")
    email = st.text_input("Email (Optionnel)")
    adresse = st.text_input("Adresse (Optionnel)")
    frequence = st.number_input(
        "Rappel tous les combien de jours ?", min_value=1, value=30
    )

  if st.button("💾 Enregistrer le Client", type="primary"):
    if not nom_entreprise.strip():
      st.error("Veuillez remplir au moins le Nom du Client / Entreprise.")
    else:
      conn = get_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
            INSERT INTO clients (nom_entreprise, nom_contact, telephone, email, adresse, type_cafe, machine_installee, frequence_jours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              nom_entreprise.strip(),
              nom_contact.strip(),
              telephone.strip(),
              email.strip(),
              adresse.strip(),
              type_cafe.strip(),
              1 if machine_inst else 0,
              int(frequence),
          ),
      )
      conn.commit()
      conn.close()
      st.success(f"Client '{nom_entreprise}' enregistré !")
      st.rerun()

  st.divider()
  st.subheader("📋 Répertoire des Clients")
  if not df_clients.empty:
    st.dataframe(
        df_clients[[
            "id",
            "nom_entreprise",
            "type_cafe",
            "machine_installee",
            "frequence_jours",
            "nom_contact",
            "telephone",
            "email",
            "adresse",
        ]],
        use_container_width=True,
        hide_index=True,
    )
  else:
    st.info("Aucun client enregistré pour l'instant.")

# --- ONGLET 5 : HISTORIQUE ---
with tab_historique:
  st.subheader("Historique des Commandes")
  if not df_commandes.empty:
    conn = get_connection()
    for _, cmd in df_commandes.iterrows():
      with st.expander(
          f"Commande N°{cmd['id']} - {cmd['client_nom']}"
          f" ({cmd['prix_total']:,.2f} €)"
      ):
        st.write(f"**Date :** {cmd['date_commande']}")
        st.write(
            f"**Code Suivi/Courrier :** {cmd['code_courrier'] or 'Non'}"
            " renseigné"
        )

        df_l = pd.read_sql_query(
            "SELECT nom_produit, quantite, prix_unitaire FROM"
            f" lignes_commande WHERE commande_id = {cmd['id']}",
            conn,
        )
        st.dataframe(df_l, use_container_width=True, hide_index=True)
    conn.close()
  else:
    st.info("Aucune commande enregistrée.")
