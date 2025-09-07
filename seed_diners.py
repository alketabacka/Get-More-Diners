import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv

# Load env
load_dotenv(".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Load Excel
df = pd.read_excel("DinerDataTest.xlsx")

# Insert into Supabase
for _, row in df.iterrows():
    diner = {
        "first_name": row["First Name"],
        "last_name": row["Last Name"],
        "seniority": row["Seniority"],
        "city": row["City"],
        "state": row["State"],
        "address": row["Address"],
        "dining_interests": row["Dining Interests"],
        "email": row["Email"],
        "phone": row["Phone"]
    }
    supabase.table("diners").insert(diner).execute()


print("✅ Diners seeded successfully!")
