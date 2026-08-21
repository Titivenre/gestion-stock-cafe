import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="ERP Café & Ventes",
    page_icon="☕",
    layout="wide"
)

# Connexion à la base de données
def get_connection():
    return sqlite3.connect("database.db")

# Initialisation de la base de données
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
    
    # Table Commandes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS commandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT NOT NULL,
        date_commande TEXT NOT NULL,
        code_courrier TEXT,
        prix_total REAL NOT NULL,
        statut TEXT NOT NULL
    )
    """)
    
    # Table Lignes de commande (pour le multi-produits)
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
    
    # Migration de la table si necessaire (pour ajouter la colonne code_courrier si elle manquait)
    try:
        cursor.execute("ALTER TABLE commandes ADD COLUMN code_courrier TEXT")
    except sqlite3.OperationalError:
        pass  # La colonne existe deja
        
    # Exemples initiaux
    cursor.execute("SELECT COUNT(*) FROM stock")
    if cursor.fetchone()[0] == 0:
        exemples = [
            ("Café Arabica Grain Colombie", "Café", 120.0, "kg", 20.0, 18.50),
            ("Café Robusta Moulu Viêt Nam", "Café", 15.0, "kg", 25.0, 14.00),
            ("Sacs d'emballage 1kg", "Conditionnement", 450.0, "unités", 100.0, 0.40),
            ("Machine Expresso Pro V2", "Équipement", 3.0, "unités", 2.0, 1200.00)
        ]
        cursor.executemany("""
        INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
        VALUES (?, ?, ?, ?, ?, ?)
        """, exemples)
    
    conn.commit()
    conn.close()

init_db()

# Titre
st.title("☕ ERP Café - Gestion des Stocks & Commandes")
st.caption("Plateforme de gestion globale : multi-produits, suivi courrier et mise à jour de stock")

# Données actuelles
conn = get_connection()
df_stock = pd.read_sql_query("SELECT * FROM stock", conn)
df_commandes = pd.read_sql_query("SELECT * FROM commandes ORDER BY id DESC", conn)
conn.close()

# KPIs
valeur_stock = (df_stock["quantite"] * df_stock["prix_unitaire"]).sum() if not df_stock.empty else 0
articles_alerte = df_stock[df_stock["quantite"] <= df_stock["seuil_alerte"]] if not df_stock.empty else []

c1, c2, c3, c4 = st.columns(4)
c1.metric("Valeur du Stock", f"{valeur_stock:,.2f} €")
c2.metric("Total Références", len(df_stock))
c3.metric("Alertes Stock Bas", len(articles_alerte))
c4.metric("Commandes Passées", len(df_commandes))

st.divider()

# Navigation
tab_stock, tab_commande, tab_historique, tab_ajout = st.tabs([
    "📦 Gestion du Stock", 
    "🛒 Passer une Commande (Multi-produits)", 
    "📜 Commandes & Codes Courrier",
    "➕ Ajouter un Produit"
])

# --- ONGLET 1 : GESTION ET MODIFICATION DU STOCK ---
with tab_stock:
    st.subheader("État des Stocks (Modifiable)")
    st.info("💡 Vous pouvez modifier directement les quantités et informations dans le tableau ci-dessous, puis cliquer sur **Sauvegarder les modifications**.")
    
    if not df_stock.empty:
        # Tableau éditable
        edited_df = st.data_editor(
            df_stock,
            key="stock_editor",
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "nom": "Nom du produit",
                "categorie": "Catégorie",
                "quantite": st.column_config.NumberColumn("Quantité en stock", min_value=0.0, step=1.0),
                "unite": "Unité",
                "seuil_alerte": "Seuil Alerte",
                "prix_unitaire": st.column_config.NumberColumn("Prix HT (€)", format="%.2f €")
            }
        )
        
        if st.button("💾 Sauvegarder les modifications du stock", type="primary"):
            conn = get_connection()
            cursor = conn.cursor()
            for _, row in edited_df.iterrows():
                cursor.execute("""
                UPDATE stock 
                SET nom = ?, categorie = ?, quantite = ?, unite = ?, seuil_alerte = ?, prix_unitaire = ?
                WHERE id = ?
                """, (row["nom"], row["categorie"], row["quantite"], row["unite"], row["seuil_alerte"], row["prix_unitaire"], row["id"]))
            conn.commit()
            conn.close()
            st.success("Stock mis à jour avec succès !")
            st.rerun()

# --- ONGLET 2 : COMMANDE MULTI-PRODUITS ---
with tab_commande:
    st.subheader("Créer une Commande Multi-Produits")
    
    if "panier" not in st.session_state:
        st.session_state.panier = []

    col_cmd1, col_cmd2 = st.columns([1, 1])
    
    with col_cmd1:
        st.write("### 1. Sélectionner les produits")
        if not df_stock.empty:
            prod_options = {f"{row['nom']} (Stock: {row['quantite']} {row['unite']})": row for _, row in df_stock.iterrows()}
            choix_prod_nom = st.selectbox("Produit à ajouter", list(prod_options.keys()))
            prod_choisi = prod_options[choix_prod_nom]
            
            qte_souhaitee = st.number_input(
                f"Quantité ({prod_choisi['unite']})", 
                min_value=0.1, 
                max_value=float(prod_choisi["quantite"]), 
                value=1.0, 
                step=1.0
            )
            
            if st.button("➕ Ajouter au panier"):
                st.session_state.panier.append({
                    "produit_id": prod_choisi["id"],
                    "nom": prod_choisi["nom"],
                    "quantite": qte_souhaitee,
                    "unite": prod_choisi["unite"],
                    "prix_unitaire": prod_choisi["prix_unitaire"],
                    "total": qte_souhaitee * prod_choisi["prix_unitaire"]
                })
                st.success(f"{prod_choisi['nom']} ajouté au panier !")

    with col_cmd2:
        st.write("### 2. Récapitulatif & Finalisation")
        if st.session_state.panier:
            df_panier = pd.DataFrame(st.session_state.panier)
            st.dataframe(df_panier[["nom", "quantite", "unite", "total"]], use_container_width=True, hide_index=True)
            
            total_general = df_panier["total"].sum()
            st.write(f"### Total HT : **{total_general:,.2f} €**")
            
            client_nom = st.text_input("Nom du Client / Entreprise")
            code_courrier_input = st.text_input("Code de suivi / Courrier (Optionnel)", placeholder="Ex: FR-884920-LAPOST")
            
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("✅ Valider la Commande", type="primary"):
                    if not client_nom.strip():
                        st.error("Veuillez remplir le nom du client.")
                    else:
                        conn = get_connection()
                        cursor = conn.cursor()
                        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        # Création de la commande
                        cursor.execute("""
                        INSERT INTO commandes (client, date_commande, code_courrier, prix_total, statut)
                        VALUES (?, ?, ?, ?, ?)
                        """, (client_nom, date_str, code_courrier_input, total_general, "En préparation"))
                        cmd_id = cursor.lastrowid
                        
                        # Ajout des lignes et déduction du stock
                        for item in st.session_state.panier:
                            cursor.execute("""
                            INSERT INTO lignes_commande (commande_id, produit_id, nom_produit, quantite, prix_unitaire)
                            VALUES (?, ?, ?, ?, ?)
                            """, (cmd_id, item["produit_id"], item["nom"], item["quantite"], item["prix_unitaire"]))
                            
                            cursor.execute("UPDATE stock SET quantite = quantite - ? WHERE id = ?", (item["quantite"], item["produit_id"]))
                            
                        conn.commit()
                        conn.close()
                        
                        st.session_state.panier = []
                        st.success(f"Commande N°{cmd_id} validée avec succès !")
                        st.rerun()
            
            with c_btn2:
                if st.button("🗑️ Vider le panier"):
                    st.session_state.panier = []
                    st.rerun()
        else:
            st.info("Le panier est actuellement vide.")

# --- ONGLET 3 : HISTORIQUE ET CODES COURRIER ---
with tab_historique:
    st.subheader("Suivi des Commandes & Codes Courrier")
    
    if df_commandes.empty:
        st.info("Aucune commande enregistrée.")
    else:
        conn = get_connection()
        for _, cmd in df_commandes.iterrows():
            with st.expander(f"Commande N°{cmd['id']} - {cmd['client']} ({cmd['prix_total']:,.2f} €) - Statut: {cmd['statut']}"):
                col_h1, col_h2 = st.columns(2)
                
                with col_h1:
                    st.write(f"**Date :** {cmd['date_commande']}")
                    st.write(f"**Code de suivi / Courrier :** {cmd['code_courrier'] if cmd['code_courrier'] else 'Non renseigné'}")
                    
                    # Formulaire pour ajouter ou modifier le code courrier
                    nouveau_code = st.text_input(f"Modifier le code courrier pour N°{cmd['id']}", value=cmd['code_courrier'] or "", key=f"code_{cmd['id']}")
                    if st.button(f"Mettre à jour le code courrier N°{cmd['id']}", key=f"btn_code_{cmd['id']}"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE commandes SET code_courrier = ? WHERE id = ?", (nouveau_code, cmd['id']))
                        conn.commit()
                        st.success("Code courrier mis à jour !")
                        st.rerun()

                with col_h2:
                    st.write("**Contenu de la commande :**")
                    df_lignes = pd.read_sql_query(f"SELECT nom_produit as Produit, quantite as Quantité, prix_unitaire as 'Prix Unit.' FROM lignes_commande WHERE commande_id = {cmd['id']}", conn)
                    st.dataframe(df_lignes, use_container_width=True, hide_index=True)
        conn.close()

# --- ONGLET 4 : AJOUTER UN PRODUIT ---
with tab_ajout:
    st.subheader("Ajouter un nouveau produit")
    with st.form("form_ajout"):
        ca, cb = st.columns(2)
        with ca:
            nom_p = st.text_input("Nom de l'article")
            cat_p = st.selectbox("Catégorie", ["Café", "Conditionnement", "Équipement", "Autre"])
            qte_p = st.number_input("Quantité initiale", min_value=0.0, value=50.0)
        with cb:
            unite_p = st.selectbox("Unité", ["kg", "unités", "sacs", "cartons"])
            seuil_p = st.number_input("Seuil d'alerte", min_value=0.0, value=10.0)
            prix_p = st.number_input("Prix Unitaire HT (€)", min_value=0.0, value=12.0)
            
        if st.form_submit_button("Ajouter la référence"):
            if nom_p:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (nom_p, cat_p, qte_p, unite_p, seuil_p, prix_p))
                conn.commit()
                conn.close()
                st.success(f"Produit '{nom_p}' ajouté !")
                st.rerun()
