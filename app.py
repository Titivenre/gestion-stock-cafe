import streamlit as st
import pandas as pd
import sqlite3
import datetime

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(
    page_title="CoffeeStock Pro - Gestion d'Entreprise",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- NOM DE LA BASE DE DONNÉES PERSISTANTE ---
DB_FILE = "database.db"

# --- CONNEXION & INITIALISATION DE LA BASE DE DONNÉES (SQLITE) ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table des produits (Stock)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_sku TEXT UNIQUE,
            nom TEXT NOT NULL,
            categorie TEXT NOT NULL,
            quantite REAL NOT NULL,
            seuil_alerte REAL DEFAULT 10,
            unite TEXT DEFAULT 'kg',
            prix_unitaire REAL NOT NULL,
            emplacement TEXT DEFAULT 'Entrepôt A'
        )
    ''')
    
    # Table des commandes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_commande TEXT NOT NULL,
            client TEXT NOT NULL,
            produit_id INTEGER NOT NULL,
            produit_nom TEXT NOT NULL,
            quantite REAL NOT NULL,
            prix_total REAL NOT NULL,
            statut TEXT DEFAULT 'En attente',
            FOREIGN KEY (produit_id) REFERENCES stock (id)
        )
    ''')
    
    # Remplir avec des données de démonstration si la base est vide
    cursor.execute("SELECT COUNT(*) FROM stock")
    if cursor.fetchone()[0] == 0:
        demo_stock = [
            ("CAF-COL-01", "Café Arabica Colombie (Grains)", "Café Grain", 150.0, 30.0, "kg", 18.50, "Zone A - Allée 1"),
            ("CAF-ETH-02", "Café Éthiopie Moka (Grains)", "Café Grain", 85.0, 20.0, "kg", 22.00, "Zone A - Allée 1"),
            ("CAF-BRA-03", "Café Brésil Santos (Moulu)", "Café Moulu", 25.0, 40.0, "kg", 15.00, "Zone A - Allée 2"),
            ("CAP-INT-04", "Capsules Espresso Intense (x100)", "Capsules", 300.0, 50.0, "boîtes", 28.00, "Zone B - Étagère 4"),
            ("ACC-SAC-05", "Sacs Kraft Hermétiques 1kg", "Conditionnement", 1200.0, 200.0, "unités", 0.45, "Zone C - Stock Emballage"),
            ("MAC-EXP-06", "Machine Espresso Pro 2 Groupes", "Equipement", 4.0, 2.0, "unités", 2450.00, "Zone D - Showroom")
        ]
        cursor.executemany('''
            INSERT INTO stock (code_sku, nom, categorie, quantite, seuil_alerte, unite, prix_unitaire, emplacement)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', demo_stock)
        conn.commit()
        
    conn.close()

init_db()

# --- DESIGN & STYLE CUSTOMIZÉ (CSS PRO) ---
st.markdown("""
    <style>
    /* Style général */
    .stApp {
        background-color: #F8FAFC;
    }
    
    /* Cartes KPI Header */
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
    }
    .kpi-title {
        color: #64748B;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: #1E293B;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .kpi-alert {
        color: #E11D48;
    }
    
    /* Titre d'en-tête */
    .main-header {
        background: linear-gradient(90deg, #3B2314 0%, #5C3A21 100%);
        color: white;
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 25px;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 5px 0 0 0;
        opacity: 0.85;
    }
    
    /* Boutons */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
    </style>
""", unsafe_unsafe_html=True if hasattr(st, "unsafe_html") else True)

# --- FONCTIONS UTILITAIRES BASE DE DONNÉES ---
def load_stock_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM stock ORDER BY id DESC", conn)
    conn.close()
    return df

def load_orders_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM commandes ORDER BY id DESC", conn)
    conn.close()
    return df

# --- ENTÊTE DE L'APPLICATION ---
st.markdown("""
    <div class="main-header">
        <h1>☕ CoffeeStock Pro — Système ERP & Logistique</h1>
        <p>Plateforme centralisée de gestion des stocks, approvisionnements et commandes clients</p>
    </div>
""", unsafe_allow_html=True)

# --- CHARGEMENT DES DONNÉES EN TEMPS RÉEL ---
df_stock = load_stock_df()
df_orders = load_orders_df()

# Calcul des KPIs principaux
valeur_totale_stock = (df_stock["quantite"] * df_stock["prix_unitaire"]).sum()
nb_articles_critiques = len(df_stock[df_stock["quantite"] <= df_stock["seuil_alerte"]])
nb_commandes_encours = len(df_orders[df_orders["statut"].isin(["En attente", "En préparation"])])

# --- TABLEAU DE BORD (KPIS HAUT DE PAGE) ---
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Valeur Totale du Stock</div>
            <div class="kpi-value">{valeur_totale_stock:,.2f} €</div>
        </div>
    """, unsafe_allow_html=True)

with col_kpi2:
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Références en Stock</div>
            <div class="kpi-value">{len(df_stock)}</div>
        </div>
    """, unsafe_allow_html=True)

with col_kpi3:
    color_class = "kpi-alert" if nb_articles_critiques > 0 else ""
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Alertes Stock Bas</div>
            <div class="kpi-value {color_class}">{nb_articles_critiques}</div>
        </div>
    """, unsafe_allow_html=True)

with col_kpi4:
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Commandes en cours</div>
            <div class="kpi-value">{nb_commandes_encours}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- NAVIGATION PAR ONGLETS ---
tab_dashboard, tab_stock, tab_commandes, tab_admin = st.tabs([
    "📊 Tableau de Bord",
    "📦 Gestion du Stock",
    "🛒 Prise & Suivi de Commande",
    "⚙️ Sauvegarde & Exportation"
])

# ==========================================
# TAB 1 : TABLEAU DE BORD
# ==========================================
with tab_dashboard:
    st.subheader("Aperçu Général des Activités")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**Répartition du Stock par Catégorie (Valeur €)**")
        df_stock["valeur_totale"] = df_stock["quantite"] * df_stock["prix_unitaire"]
        cat_chart = df_stock.groupby("categorie")["valeur_totale"].sum()
        st.bar_chart(cat_chart)
        
    with col_chart2:
        st.markdown("**Produits sous le seuil de Réapprovisionnement**")
        df_low_stock = df_stock[df_stock["quantite"] <= df_stock["seuil_alerte"]]
        if not df_low_stock.empty:
            st.error(f"⚠️ {len(df_low_stock)} produit(s) nécessitent un réapprovisionnement immédiat !")
            st.dataframe(
                df_low_stock[["code_sku", "nom", "quantite", "seuil_alerte", "unite", "emplacement"]],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.success("✅ Tous les niveaux de stock sont optimaux.")

# ==========================================
# TAB 2 : GESTION DU STOCK
# ==========================================
with tab_stock:
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Inventaire Actuel")
        
        # Filtres de recherche
        search_term = st.text_input("🔍 Rechercher un produit ou SKU :", "")
        cat_filter = st.selectbox("Filtrer par catégorie :", ["Toutes"] + list(df_stock["categorie"].unique()))
        
        filtered_df = df_stock.copy()
        if search_term:
            filtered_df = filtered_df[
                filtered_df["nom"].str.contains(search_term, case=False, na=False) |
                filtered_df["code_sku"].str.contains(search_term, case=False, na=False)
            ]
        if cat_filter != "Toutes":
            filtered_df = filtered_df[filtered_df["categorie"] == cat_filter]
            
        st.dataframe(
            filtered_df[["code_sku", "nom", "categorie", "quantite", "unite", "prix_unitaire", "seuil_alerte", "emplacement"]],
            hide_index=True,
            use_container_width=True
        )

    with col_right:
        st.subheader("➕ Ajouter / Ajuster Stock")
        
        mode = st.radio("Action :", ["Nouveau produit", "Ajuster quantité existante"])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if mode == "Nouveau produit":
            with st.form("form_add_product"):
                new_sku = st.text_input("Code SKU", value=f"CAF-{len(df_stock)+1:03d}")
                new_nom = st.text_input("Nom du produit *")
                new_cat = st.selectbox("Catégorie", ["Café Grain", "Café Moulu", "Capsules", "Conditionnement", "Equipement", "Autre"])
                new_qty = st.number_input("Quantité initiale", min_value=0.0, value=50.0)
                new_unite = st.selectbox("Unité", ["kg", "unités", "boîtes", "palettes", "sacs"])
                new_prix = st.number_input("Prix unitaire HT (€)", min_value=0.0, value=15.0, step=0.5)
                new_seuil = st.number_input("Seuil d'alerte", min_value=0.0, value=10.0)
                new_emp = st.text_input("Emplacement entrepôt", value="Zone A")
                
                btn_submit = st.form_submit_button("Enregistrer en Base")
                if btn_submit:
                    if not new_nom:
                        st.error("Le nom du produit est obligatoire.")
                    else:
                        try:
                            cursor.execute('''
                                INSERT INTO stock (code_sku, nom, categorie, quantite, seuil_alerte, unite, prix_unitaire, emplacement)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (new_sku, new_nom, new_cat, new_qty, new_seuil, new_unite, new_prix, new_emp))
                            conn.commit()
                            st.success(f"Article '{new_nom}' ajouté avec succès et sauvegardé !")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Ce code SKU existe déjà. Utilisez un code unique.")
                            
        else:
            with st.form("form_update_qty"):
                product_to_update = st.selectbox("Choisir l'article :", df_stock["nom"].tolist())
                qty_change = st.number_input("Ajouter/Retirer quantité (+ ou -) :", value=10.0)
                
                btn_update = st.form_submit_button("Mettre à jour la quantité")
                if btn_update:
                    cursor.execute("UPDATE stock SET quantite = quantite + ? WHERE nom = ?", (qty_change, product_to_update))
                    conn.commit()
                    st.success(f"Stock mis à jour pour {product_to_update} !")
                    st.rerun()
                    
        conn.close()

# ==========================================
# TAB 3 : COMMANDES & LIVRAISONS
# ==========================================
with tab_commandes:
    col_cmd1, col_cmd2 = st.columns([1, 1])
    
    with col_cmd1:
        st.subheader("📝 Nouvelle Commande Client")
        
        with st.form("form_new_order"):
            client_nom = st.text_input("Nom du Client / Entreprise *")
            
            # Sélection de l'article dans le stock disponible
            options_produits = {row["nom"]: row for _, row in df_stock.iterrows()}
            selected_prod_name = st.selectbox("Sélectionner l'article :", list(options_produits.keys()))
            selected_prod = options_produits[selected_prod_name]
            
            st.info(f"Stock disponible : **{selected_prod['quantite']} {selected_prod['unite']}** | Prix unitaire : **{selected_prod['prix_unitaire']} €**")
            
            cmd_qty = st.number_input("Quantité demandée :", min_value=0.1, value=1.0)
            prix_total_calc = cmd_qty * selected_prod['prix_unitaire']
            
            st.write(f"### Total HT : **{prix_total_calc:,.2f} €**")
            
            btn_order = st.form_submit_button("Valider la Commande")
            
            if btn_order and client_nom:
                if cmd_qty > selected_prod['quantite']:
                    st.error("❌ Stock insuffisant pour valider cette commande !")
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # 1. Déduire du stock
                    cursor.execute("UPDATE stock SET quantite = quantite - ? WHERE id = ?", (cmd_qty, selected_prod['id']))
                    
                    # 2. Créer la commande
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    cursor.execute('''
                        INSERT INTO commandes (date_commande, client, produit_id, produit_nom, quantite, prix_total, statut)
                        VALUES (?, ?, ?, ?, ?, ?, 'En attente')
                    ''', (today_str, client_nom, selected_prod['id'], selected_prod_name, cmd_qty, prix_total_calc))
                    
                    conn.commit()
                    conn.close()
                    
                    st.success(f"Commande validée pour {client_nom} ! Le stock a été mis à jour.")
                    st.rerun()

    with col_right:
        st.subheader("📋 Historique des Commandes")
        if not df_orders.empty:
            st.dataframe(
                df_orders[["id", "date_commande", "client", "produit_nom", "quantite", "prix_total", "statut"]],
                hide_index=True,
                use_container_width=True
            )
            
            # Modifier le statut d'une commande
            st.markdown("---")
            st.markdown("**Modifier le Statut d'une Commande**")
            conn = get_db_connection()
            cursor = conn.cursor()
            
            order_id_to_edit = st.selectbox("N° Commande :", df_orders["id"].tolist())
            new_status = st.selectbox("Nouveau Statut :", ["En attente", "En préparation", "Expédiée", "Livrée", "Annulée"])
            
            if st.button("Mettre à jour le statut"):
                cursor.execute("UPDATE commandes SET statut = ? WHERE id = ?", (new_status, order_id_to_edit))
                conn.commit()
                st.success("Statut mis à jour !")
                st.rerun()
            conn.close()
        else:
            st.write("Aucune commande enregistrée.")

# ==========================================
# TAB 4 : ADMIN & SAUVEGARDE
# ==========================================
with tab_admin:
    st.subheader("⚙️ Gestion de la Base de Données & Exportation")
    st.write("Toutes vos données sont automatiquement enregistrées dans le fichier **`database.db`**.")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.markdown("### 📥 Exporter en Excel / CSV")
        csv_stock = df_stock.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Télécharger le Stock (CSV)",
            data=csv_stock,
            file_name=f"stock_export_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        
        csv_orders = df_orders.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Télécharger les Commandes (CSV)",
            data=csv_orders,
            file_name=f"commandes_export_{datetime.date.today()}.csv",
            mime="text/csv"
        )

    with col_exp2:
        st.markdown("### 🔒 Statut de la Persistance")
        st.success(" Base de données SQLite active (`database.db`). Vos modifications restent conservées entre vos connexions.")
`
