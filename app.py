import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv
import streamlit as st

# ------------------------------------------------
# Inicializace
# ------------------------------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("Chybí DATABASE_URL v .env souboru")
    st.stop()


def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def load_table(table_name: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(f"SELECT * FROM {table_name}", conn)


def load_view(view_name: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(f"SELECT * FROM {view_name}", conn)


def upsert_customer(name: str, email: str):
    if not name or not email:
        raise ValueError("Jméno i e-mail musí být vyplněné")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customers (name, email)
                VALUES (%s, %s)
                ON CONFLICT (email)
                DO UPDATE SET name = EXCLUDED.name
                """,
                (name, email),
            )
            conn.commit()


def delete_customer(customer_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
            conn.commit()


def execute_sql(query: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            if cur.description:  # SELECT, vrací data
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                return pd.DataFrame(rows, columns=cols)
            else:
                conn.commit()
                return None


# ------------------------------------------------
# Streamlit UI
# ------------------------------------------------
st.set_page_config(page_title="Supabase demo", layout="wide")

st.title("Supabase demo – zákazníci, faktury, sklad")

# Sidebar navigace
st.sidebar.header("Navigace")
page = st.sidebar.radio(
    "Vyber sekci:",
    [
        "Customers",
        "Invoices",
        "Stock items",
        "Customer invoices summary",
        "SQL terminál",
    ],
)

# ------------------------------------------------
# 1) Customers – CRUD
# ------------------------------------------------
if page == "Customers":
    st.subheader("Zákazníci (customers)")

    df_customers = load_table("customers")
    st.dataframe(df_customers, use_container_width=True)

    st.divider()
    st.subheader("Přidat / upravit zákazníka (UPsert podle e-mailu)")

    with st.form("customer_form"):
        name = st.text_input("Jméno / název")
        email = st.text_input("E-mail")
        submitted = st.form_submit_button("Uložit (vložit / přepsat)")

        if submitted:
            try:
                upsert_customer(name, email)
                st.success(f"Zákazník '{name}' byl uložen (vložen/aktualizován).")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Něco se posralo při ukládání: {e}")

    st.divider()
    st.subheader("Smazat zákazníka")

    if df_customers.empty:
        st.info("Žádní zákazníci v tabulce.")
    else:
        options = [
            f"{row['name']} ({row['email']}) [{row['id']}]"
            for _, row in df_customers.iterrows()
        ]
        selected = st.selectbox("Vyber zákazníka k odstranění", options)

        if st.button("Smazat vybraného zákazníka"):
            customer_id = selected.split("[")[-1].rstrip("]")
            try:
                delete_customer(customer_id)
                st.success("Zákazník byl smazán.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Něco se posralo při mazání: {e}")


# ------------------------------------------------
# 2) Invoices – přehled faktur
# ------------------------------------------------
elif page == "Invoices":
    st.subheader("Faktury (invoices)")

    try:
        df_invoices = load_table("invoices")
        st.dataframe(df_invoices, use_container_width=True)
    except Exception as e:
        st.error(f"Nešlo načíst tabulku invoices: {e}")


# ------------------------------------------------
# 3) Stock items – skladové zásoby
# ------------------------------------------------
elif page == "Stock items":
    st.subheader("Skladové zásoby (stock_items)")

    try:
        df_stock = load_table("stock_items")
        st.dataframe(df_stock, use_container_width=True)
    except Exception as e:
        st.error(f"Nešlo načíst tabulku stock_items: {e}")


# ------------------------------------------------
# 4) Customer invoices summary – VIEW s JOINem
# ------------------------------------------------
elif page == "Customer invoices summary":
    st.subheader("Souhrn faktur podle zákazníků (view: customer_invoices_summary)")

    try:
        df_view = load_view("customer_invoices_summary")
        st.dataframe(df_view, use_container_width=True)
    except Exception as e:
        st.error(f"Nešlo načíst view customer_invoices_summary: {e}")


# ------------------------------------------------
# 5) SQL terminál
# ------------------------------------------------
elif page == "SQL terminál":
    st.subheader("SQL terminál")

    default_query = "SELECT * FROM customers LIMIT 10;"

    query = st.text_area(
        "Zadej SQL dotaz (ideálně SELECT):",
        default_query,
        height=200,
    )

    if st.button("Spustit SQL"):
        # Pokud chceš být hodně hodný na svoje data, odkomentuj:
        # if not query.strip().lower().startswith("select"):
        #     st.warning("Tahle verze povoluje jen SELECT dotazy, šéfe.")
        #     st.stop()

        try:
            result = execute_sql(query)
            if result is not None:
                st.dataframe(result, use_container_width=True)
            else:
                st.success("Dotaz proveden (bez návratových dat).")
        except Exception as e:
            st.error(f"Chyba při provedení dotazu: {e}")