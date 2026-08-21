import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="Gestion Stock & Commandes - Café",
    page_icon="☕",
    layout="wide"
)

# Style CSS personnalisé
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Connexion à la base de données SQLite
def get_connection():
    conn = sqlite3.connect("database.db")
    return conn

# Initialisation des tables
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
        produit_id INTEGER NOT NULL,
        nom_produit TEXT NOT NULL,
        quantite REAL NOT NULL,
        prix_total REAL NOT NULL,
        statut TEXT NOT NULL,
        FOREIGN KEY (produit_id) REFERENCES stock (id)
    )
    """)
    
    # Données d'exemple si la table est vide
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

# Chargement initial
init_db()

# En-tête de l'application
st.title("☕ ERP Café - Gestion des Stocks & Commandes")
st.caption("Système centralisé de gestion des ressources et du flux de ventes")

# Chargement des données
conn = get_connection()
df_stock = pd.read_sql_query("SELECT * FROM stock", conn)
df_commandes = pd.read_sql_query("SELECT * FROM commandes ORDER BY id DESC", conn)
conn.close()

# Statistiques globales (KPIs)
valeur_totale_stock = (df_stock["quantite"] * df_stock["prix_unitaire"]).sum()
articles_alerte = df_stock[df_stock["quantite"] <= df_stock["seuil_alerte"]]
nb_commandes = len(df_commandes)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Valeur du Stock", f"{valeur_totale_stock:,.2f} €")
col2.metric("Références en Stock", len(df_stock))
col3.metric("Alertes Stock Bas", len(articles_alerte), delta_color="inverse")
col4.metric("Total Commandes", nb_commandes)

st.divider()

# Navigation par onglets
tab_stock, tab_commande, tab_ajout, tab_historique = st.tabs([
    "📦 Stock & Emplacements", 
    "🛒 Passer une Commande", 
    "➕ Ajouter une Référence", 
    "📜 Historique des Commandes"
])

# --- OANGET 1 : GESTION DU STOCK ---
with tab_stock:
    st.subheader("État Général des Stocks")
    
    if not articles_alerte.empty:
        st.error(f"⚠️ **{len(articles_alerte)} article(s) sous le seuil critique de réapprovisionnement !**")
    
    # Filtres
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        recherche = st.text_input("🔍 Rechercher un produit...", "")
    with col_f2:
        categories = ["Toutes"] + list(df_stock["categorie"].unique())
        cat_filtre = st.selectbox("Filtrer par catégorie", categories)
    
    df_affiche = df_stock.copy()
    if recherche:
        df_affiche = df_affiche[df_affiche["nom"].str.contains(recherche, case=False)]
    if cat_filtre != "Toutes":
        df_affiche = df_affiche[df_affiche["categorie"] == cat_filtre]
    
    # Affichage du tableau de stock
    st.dataframe(
        df_affiche.rename(columns={
            "id": "ID",
            "nom": "Produit",
            "categorie": "Catégorie",
            "quantite": "Quantité en Stock",
            "unite": "Unité",
            "seuil_alerte": "Seuil Alerte",
            "prix_unitaire": "Prix Unitaire (€)"
        }),
        use_container_width=True,
        hide_index=True
    )

# --- ONGLET 2 : NOUVELLE COMMANDE ---
with tab_commande:
    st.subheader("Enregistrer une nouvelle commande client")
    
    if df_stock.empty:
        st.warning("Aucun produit en stock.")
    else:
        with st.form("form_commande"):
            client = st.text_input("Nom de l'entreprise / Client")
            
            produits_list = df_stock.apply(lambda x: f"{x['id']} - {x['nom']} (Dispo: {x['quantite']} {x['unite']})", axis=1).tolist()
            produit_sel = st.selectbox("Sélectionner le produit", produits_list)
            
            quantite_cmd = st.number_input("Quantité commandée", min_value=0.1, value=1.0, step=1.0)
            
            valider_cmd = st.form_submit_button("Valider et déduire du stock")
            
            if valider_cmd:
                if not client.strip():
                    st.error("Veuillez saisir le nom du client.")
                else:
                    prod_id = int(produit_sel.split(" - ")[0])
                    prod_info = df_stock[df_stock["id"] == prod_id].iloc[0]
                    
                    if quantite_cmd > prod_info["quantite"]:
                        st.error(f"Stock insuffisant ! Disponible : {prod_info['quantite']} {prod_info['unite']}")
                    else:
                        nouvelle_qte = prod_info["quantite"] - quantite_cmd
                        prix_total = quantite_cmd * prod_info["prix_unitaire"]
                        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        cursor.execute("UPDATE stock SET quantite = ? WHERE id = ?", (nouvelle_qte, prod_id))
                        cursor.execute("""
                        INSERT INTO commandes (client, date_commande, produit_id, nom_produit, quantite, prix_total, statut)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (client, date_str, prod_id, prod_info["nom"], quantite_cmd, prix_total, "Validée"))
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"Commande validée ! Total : {prix_total:,.2f} €")
                        st.rerun()

# --- ONGLET 3 : AJOUTER UN PRODUIT ---
with tab_ajout:
    st.subheader("Ajouter un nouvel article au catalogue")
    
    with st.form("form_ajout_produit"):
        col_a, col_b = st.columns(2)
        with col_a:
            nom_p = st.text_input("Nom du produit (ex: Café Moka Éthiopie)")
            cat_p = st.selectbox("Catégorie", ["Café", "Conditionnement", "Équipement", "Consommable", "Autre"])
            qte_p = st.number_input("Quantité initiale", min_value=0.0, value=100.0)
        with col_b:
            unite_p = st.selectbox("Unité de mesure", ["kg", "unités", "sacs", "cartons", "litres"])
            seuil_p = st.number_input("Seuil d'alerte critique", min_value=0.0, value=10.0)
            prix_p = st.number_input("Prix unitaire HT (€)", min_value=0.0, value=15.0, step=0.5)
            
        valider_ajout = st.form_submit_button("Ajouter la référence")
        
        if valider_ajout:
            if not nom_p.strip():
                st.error("Le nom du produit est obligatoire.")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO stock (nom, categorie, quantite, unite, seuil_alerte, prix_unitaire)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (nom_p, cat_p, qte_p, unite_p, seuil_p, prix_p))
                conn.commit()
                conn.close()
                
                st.success(f"Référence '{nom_p}' ajoutée avec succès.")
                st.rerun()

# --- ONGLET 4 : HISTORIQUE DES COMMANDES ---
with tab_historique:
    st.subheader("Historique des Transactions")
    
    if df_commandes.empty:
        st.info("Aucune commande enregistrée pour le moment.")
    else:
        st.dataframe(
            df_commandes.rename(columns={
                "id": "N° Commande",
                "client": "Client",
                "date_commande": "Date / Heure",
                "nom_produit": "Produit",
                "quantite": "Quantité",
                "prix_total": "Total (€)",
                "statut": "Statut"
            }),
            use_container_width=True,
            hide_index=True
        )
