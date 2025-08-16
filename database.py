import os
import sqlite3

# Tentative d'import de psycopg2 avec gestion d'erreur
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
    print("✅ psycopg2 importé avec succès")
except ImportError as e:
    print(f"⚠️ psycopg2 non disponible: {e}")
    print("🔄 Utilisation de SQLite en fallback")
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    RealDictCursor = None

from typing import Union

def get_db_connection():
    """Retourne une connexion à la base de données (SQLite en local, PostgreSQL sur Render)"""
    
    # Vérifier si on est sur Render (base de données PostgreSQL)
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        # Connexion PostgreSQL sur Render
        try:
            conn = psycopg2.connect(database_url)
            conn.cursor_factory = RealDictCursor
            return conn
        except Exception as e:
            print(f"❌ Erreur de connexion PostgreSQL: {e}")
            print("🔄 Fallback vers SQLite")
            # Fallback vers SQLite si PostgreSQL échoue
            pass
    
    # Connexion SQLite en local ou en fallback
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "database.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données (SQLite ou PostgreSQL)"""
    
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Initialisation PostgreSQL
        init_postgresql_db()
    else:
        # Initialisation SQLite
        init_sqlite_db()

def init_sqlite_db():
    """Initialise la base de données SQLite"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "database.db")
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Table des utilisateurs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            ijin_number TEXT,
            birth_date TEXT,
            photo_path TEXT,
            is_admin INTEGER DEFAULT 0,
            validated INTEGER DEFAULT 0,
            is_trainer INTEGER DEFAULT 0
        )
    """)
    
    # Table des réservations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            court_number INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # Table des articles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    
    # Créer l'utilisateur admin par défaut
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        from app import hash_password
        admin_pwd = hash_password("admin")
        cur.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, is_admin, validated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("admin", admin_pwd, "Administrateur", "admin@example.com", "", 1, 1))
        conn.commit()
    
    conn.close()

def init_postgresql_db():
    """Initialise la base de données PostgreSQL"""
    if not PSYCOPG2_AVAILABLE:
        print("⚠️ psycopg2 non disponible, initialisation PostgreSQL ignorée")
        return
        
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        return
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Table des utilisateurs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(50),
                ijin_number VARCHAR(100),
                birth_date VARCHAR(20),
                photo_path TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                validated BOOLEAN DEFAULT FALSE,
                is_trainer BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Table des réservations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                court_number INTEGER NOT NULL,
                date VARCHAR(20) NOT NULL,
                start_time VARCHAR(10) NOT NULL,
                end_time VARCHAR(10) NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        
        # Table des articles
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                image_path TEXT,
                created_at VARCHAR(50) NOT NULL
            )
        """)
        
        conn.commit()
        
        # Créer l'utilisateur admin par défaut
        cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if not cur.fetchone():
            from app import hash_password
            admin_pwd = hash_password("admin")
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, is_admin, validated)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, ("admin", admin_pwd, "Administrateur", "admin@example.com", "", True, True))
            conn.commit()
        
        conn.close()
        print("✅ Base de données PostgreSQL initialisée avec succès")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation PostgreSQL: {e}")

def migrate_data_from_sqlite():
    """Migre les données de SQLite vers PostgreSQL (si nécessaire)"""
    if not PSYCOPG2_AVAILABLE:
        print("⚠️ psycopg2 non disponible, migration ignorée")
        return
        
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        return
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "database.db")
    
    if not os.path.exists(DB_PATH):
        return
    
    try:
        # Connexion SQLite
        sqlite_conn = sqlite3.connect(DB_PATH)
        sqlite_cur = sqlite_conn.cursor()
        
        # Connexion PostgreSQL
        pg_conn = psycopg2.connect(database_url)
        pg_cur = pg_conn.cursor()
        
        # Vérifier si PostgreSQL a déjà des données
        pg_cur.execute("SELECT COUNT(*) FROM users")
        pg_count = pg_cur.fetchone()[0]
        
        if pg_count > 0:
            print("⚠️ PostgreSQL contient déjà des données, migration ignorée")
            sqlite_conn.close()
            pg_conn.close()
            return
        
        # Migrer les utilisateurs
        sqlite_cur.execute("SELECT * FROM users")
        users = sqlite_cur.fetchall()
        
        for user in users:
            pg_cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, 
                                 ijin_number, birth_date, photo_path, is_admin, validated, is_trainer)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, user[1:])  # Exclure l'ID auto-incrémenté
        
        # Migrer les réservations
        sqlite_cur.execute("SELECT * FROM reservations")
        reservations = sqlite_cur.fetchall()
        
        for reservation in reservations:
            pg_cur.execute("""
                INSERT INTO reservations (user_id, court_number, date, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s)
            """, reservation[1:])
        
        # Migrer les articles
        sqlite_cur.execute("SELECT * FROM articles")
        articles = sqlite_cur.fetchall()
        
        for article in articles:
            pg_cur.execute("""
                INSERT INTO articles (title, content, image_path, created_at)
                VALUES (%s, %s, %s, %s)
            """, article[1:])
        
        pg_conn.commit()
        sqlite_conn.close()
        pg_conn.close()
        
        print(f"✅ Migration terminée : {len(users)} utilisateurs, {len(reservations)} réservations, {len(articles)} articles")
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'pg_conn' in locals():
            pg_conn.close()
