import streamlit as st
import pandas as pd
import os

# Titre de l'application
st.title("☕ Gestion du Stock & Commandes - Café")

# Fichiers pour sauvegarder les données
STOCK_FILE = "stock.csv"
ORDERS_FILE = "commandes.csv"

# Initialisation des fichiers si inexistants
if not os.path.exists(STOCK_FILE):
    df_init = pd.DataFrame([
        {"ID": 1, "Produit": "Café Arabica Grain", "Catégorie": "Café", "Quantité (kg)": 100, "Prix unitaire (€)": 15.0},
        {"ID": 2, "Produit": "Café Robusta Moulu", "Catégorie": "Café", "Quantité (kg)": 50, "Prix unitaire (€)": 12.0},
        {"ID": 3, "Produit": "Sacs d'emballage 1kg", "Catégorie": "Accessoire", "Quantité (unités)": 500, "Prix unitaire (€)": 0.5}
    ])
    df_init.to_csv(STOCK_FILE, index=False)

if not os.path.exists(ORDERS_FILE):
    df_orders_init = pd.DataFrame(columns=["Client", "Produit", "Quantité", "Total (€)", "Statut"])
    df_orders_init.to_csv(ORDERS_FILE, index=False)

# Chargement des données
df_stock = pd.read_csv(STOCK_FILE)
df_orders = pd.read_csv(ORDERS_FILE)

# Onglets de l'application
tab1, tab2, tab3 = st.tabs(["📦 Stock actuel", "➕ Ajouter un produit", "🛒 Nouvelle Commande"])

# --- TAB 1 : VOIR LE STOCK ---
with tab1:
    st.subheader("État des stocks")
    st.dataframe(df_stock, use_container_width=True)
    
    st.subheader("Historique des commandes")
    st.dataframe(df_orders, use_container_width=True)

# --- TAB 2 : AJOUTER UN PRODUIT ---
with tab2:
    st.subheader("Ajouter un nouvel article")
    with st.form("add_product_form"):
        nom = st.text_input("Nom du produit (ex: Café Brésil Grain)")
        categorie = st.selectbox("Catégorie", ["Café", "Accessoire", "Machine", "Autre"])
        quantite = st.number_input("Quantité", min_value=1, value=10)
        prix = st.number_input("Prix unitaire (€)", min_value=0.0, value=10.0, step=0.5)
        
        submitted = st.form_submit_button("Ajouter au stock")
        if submitted and nom:
            new_id = len(df_stock) + 1
            new_row = {"ID": new_id, "Produit": nom, "Catégorie": categorie, "Quantité (kg/unités)": quantite, "Prix unitaire (€)": prix}
            df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
            df_stock.to_csv(STOCK_FILE, index=False)
            st.success(f"Produit '{nom}' ajouté avec succès !")
            st.rerun()

# --- TAB 3 : PASSER UNE COMMANDE ---
with tab3:
    st.subheader("Enregistrer une commande")
    if not df_stock.empty:
        with st.form("order_form"):
            client = st.text_input("Nom du Client")
            produit_choisi = st.selectbox("Produit", df_stock["Produit"].tolist())
            quantite_cmd = st.number_input("Quantité commandée", min_value=1, value=1)
            
            submitted_order = st.form_submit_button("Valider la commande")
            if submitted_order and client:
                idx = df_stock[df_stock["Produit"] == produit_choisi].index[0]
                stock_dispo = df_stock.loc[idx, "Quantité (kg)"] if "Quantité (kg)" in df_stock.columns else df_stock.loc[idx, "Quantité (unités)"]
                
                if quantite_cmd > stock_dispo:
                    st.error("Stock insuffisant pour cette commande !")
                else:
                    # Mise à jour du stock
                    if "Quantité (kg)" in df_stock.columns:
                        df_stock.loc[idx, "Quantité (kg)"] -= quantite_cmd
                    else:
                        df_stock.loc[idx, "Quantité (unités)"] -= quantite_cmd
                    df_stock.to_csv(STOCK_FILE, index=False)
                    
                    # Enregistrement de la commande
                    prix_unit = df_stock.loc[idx, "Prix unitaire (€)"]
                    total = prix_unit * quantite_cmd
                    new_order = {"Client": client, "Produit": produit_choisi, "Quantité": quantite_cmd, "Total (€)": total, "Statut": "Validée"}
                    df_orders = pd.concat([df_orders, pd.DataFrame([new_order])], ignore_index=True)
                    df_orders.to_csv(ORDERS_FILE, index=False)
                    
                    st.success(f"Commande enregistrée pour {client} ! Total : {total} €")
                    st.rerun()