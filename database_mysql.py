import os
import sqlite3

# Tentative d'import de mysql-connector avec gestion d'erreur
try:
    import mysql.connector
    from mysql.connector import Error
    MYSQL_AVAILABLE = True
    print("✅ mysql-connector importé avec succès")
except ImportError as e:
    print(f"⚠️ mysql-connector non disponible: {e}")
    print("🔄 Utilisation de SQLite en fallback")
    MYSQL_AVAILABLE = False
    mysql = None

from typing import Union

def get_db_connection():
    """Retourne une connexion à la base de données (SQLite en local, MySQL sur HostGator)"""
    
    # Vérifier si on est sur Render avec MySQL
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and MYSQL_AVAILABLE and 'mysql://' in database_url:
        # Connexion MySQL sur HostGator
        try:
            # Parser l'URL MySQL
            # Format: mysql://user:password@host:port/database
            url_parts = database_url.replace('mysql://', '').split('@')
            user_pass = url_parts[0].split(':')
            host_db = url_parts[1].split('/')
            host_port = host_db[0].split(':')
            
            user = user_pass[0]
            password = user_pass[1]
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 3306
            database = host_db[1]
            
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            return conn
        except Exception as e:
            print(f"❌ Erreur de connexion MySQL: {e}")
            print("🔄 Fallback vers SQLite")
            # Fallback vers SQLite si MySQL échoue
            pass
    
    # Connexion SQLite en local ou en fallback
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "database.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données (SQLite ou MySQL)"""
    
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and 'mysql://' in database_url:
        # Initialisation MySQL
        init_mysql_db()
    else:
        # Initialisation SQLite
        init_sqlite_db()

def init_mysql_db():
    """Initialise la base de données MySQL"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Table des utilisateurs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            email VARCHAR(255),
            phone VARCHAR(50),
            ijin_number VARCHAR(100),
            birth_date VARCHAR(20),
            photo_path VARCHAR(500),
            is_admin TINYINT DEFAULT 0,
            validated TINYINT DEFAULT 0,
            is_trainer TINYINT DEFAULT 0,
            email_verification_token VARCHAR(255) NULL,
            email_verified TINYINT DEFAULT 0
        )
    """)
    
    # Table des réservations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            court_number INT NOT NULL,
            date VARCHAR(20) NOT NULL,
            start_time VARCHAR(10) NOT NULL,
            end_time VARCHAR(10) NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # Table des articles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            image_path VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    
    # Vérifier si la base de données est vide
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    
    if users_count == 0:
        # Créer l'utilisateur admin seulement si la base est vide
        print("🔄 Base de données vide - Création de l'utilisateur admin...")
        from app import hash_password
        admin_pwd = hash_password("admin")
        cur.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, is_admin, validated)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("admin", admin_pwd, "Administrateur", "admin@example.com", "", 1, 1))
        conn.commit()
        print("✅ Utilisateur admin créé avec succès (MySQL)")
    else:
        print("✅ Base de données MySQL non vide - Utilisateur admin non créé automatiquement.")
    
    conn.close()

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
            is_trainer INTEGER DEFAULT 0,
            email_verification_token TEXT NULL,
            email_verified INTEGER DEFAULT 0
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    
    # Vérifier si la base de données est vide
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    
    if users_count == 0:
        # Créer l'utilisateur admin seulement si la base est vide
        print("🔄 Base de données vide - Création de l'utilisateur admin...")
        from app import hash_password
        admin_pwd = hash_password("admin")
        cur.execute("""
            INSERT INTO users (username, password_hash, full_name, email, phone, is_admin, validated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("admin", admin_pwd, "Administrateur", "admin@example.com", "", 1, 1))
        conn.commit()
        print("✅ Utilisateur admin créé avec succès (SQLite)")
    else:
        print("✅ Base de données SQLite non vide - Utilisateur admin non créé automatiquement.")
    
    conn.close()
