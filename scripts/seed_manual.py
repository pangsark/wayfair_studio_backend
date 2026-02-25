# scripts/seed_manual.py
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def seed_database():
    conn = psycopg2.connect(DATABASE_URL)
    
    with conn:
        with conn.cursor() as cur:
            # Create tables if they don't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS manuals (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    description TEXT,
                    product_image_url TEXT
                )
            """)
            print("✓ Created/verified manuals table")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    id SERIAL PRIMARY KEY,
                    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
                    step_number INTEGER NOT NULL,
                    description TEXT,
                    tools TEXT[],
                    image_url TEXT NOT NULL,
                    UNIQUE(manual_id, step_number)
                )
            """)
            print("✓ Created/verified steps table")
            
            # Insert the manual with product reference image
            cur.execute("""
                INSERT INTO manuals (name, slug, description, product_image_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE 
                SET product_image_url = EXCLUDED.product_image_url
                RETURNING id
            """, (
                '3-Drawer Nightstand',
                '3-drawer-nightstand',
                'Assembly manual for 3-drawer nightstand',
                'http://localhost:4000/static/images/colored_drawer.png'
            ))
            manual_id = cur.fetchone()[0]
            print(f"✓ Created/updated manual with id: {manual_id}")
            
            # Insert the diagram as step 1 (image served from public/manuals/<id>/step1.png)
            base_url = os.getenv("APP_URL", "http://localhost:4000").rstrip("/")
            step1_image_url = f"{base_url}/manuals/{manual_id}/step1.png"
            cur.execute("""
                INSERT INTO steps (manual_id, step_number, description, image_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (manual_id, step_number) DO UPDATE
                SET image_url = EXCLUDED.image_url
            """, (
                manual_id,
                1,
                'Dimensions diagram',
                step1_image_url
            ))
            print(f"✓ Added step 1 (dimensions diagram) to manual {manual_id}")
    
    conn.close()
    print("\n🎉 Database seeded successfully!")

if __name__ == "__main__":
    seed_database()