#!/usr/bin/env python3
"""
Script pour créer des articles de test multilingues (arabe et français)
"""

import os
import sqlite3
from datetime import datetime

def create_test_multilingual_articles():
    """Crée des articles de test en arabe et en français"""
    print("🔄 Création d'articles de test multilingues...")
    
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "database.db")
        
        if not os.path.exists(DB_PATH):
            print("❌ Base de données n'existe pas")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Articles de test
        test_articles = [
            {
                "title": "مرحباً بكم في نادي التنس البلدي بشيحية",
                "content": "نحن سعداء لترحيبكم في نادي التنس البلدي بشيحية. نادينا يقدم أفضل المرافق والخدمات لمحبي التنس من جميع الأعمار. نحن نؤمن بأن التنس ليس مجرد رياضة، بل أسلوب حياة يعزز الصحة والرفاهية.\n\nنادي التنس البلدي بشيحية مجهز بأحدث المعدات والملاعب، ويوفر بيئة آمنة ومريحة للتدريب واللعب. فريقنا من المدربين المحترفين جاهز لمساعدتكم في تطوير مهاراتكم وتحقيق أهدافكم الرياضية.\n\nانضموا إلينا واكتشفوا متعة التنس في أجواء ودية ومحفزة!",
                "image_path": "https://www.cmtch.online/photos/d5918ec87dd84e6b9135003161cd7253.jpg?v=20250901"
            },
            {
                "title": "Bienvenue au Club Municipal de Tennis Chihia",
                "content": "Nous sommes ravis de vous accueillir au Club Municipal de Tennis Chihia. Notre club offre les meilleures installations et services pour les amateurs de tennis de tous âges. Nous croyons que le tennis n'est pas seulement un sport, mais un mode de vie qui favorise la santé et le bien-être.\n\nLe Club Municipal de Tennis Chihia est équipé des dernières technologies et courts, offrant un environnement sûr et confortable pour l'entraînement et le jeu. Notre équipe d'entraîneurs professionnels est prête à vous aider à développer vos compétences et atteindre vos objectifs sportifs.\n\nRejoignez-nous et découvrez le plaisir du tennis dans une atmosphère amicale et motivante!",
                "image_path": "https://www.cmtch.online/photos/d5918ec87dd84e6b9135003161cd7253.jpg?v=20250901"
            },
            {
                "title": "دورة تدريبية جديدة للمبتدئين",
                "content": "يسرنا أن نعلن عن بدء دورة تدريبية جديدة للمبتدئين في التنس. هذه الدورة مصممة خصيصاً للأشخاص الذين يرغبون في تعلم أساسيات التنس بطريقة ممتعة وفعالة.\n\nستشمل الدورة:\n- تعلم القواعد الأساسية للتنس\n- تطوير المهارات الأساسية\n- تمارين اللياقة البدنية\n- مباريات ودية\n\nالدورة ستبدأ في الأسبوع القادم وستستمر لمدة 8 أسابيع. الرسوم معقولة والمواعيد مرنة.\n\nللتسجيل، يرجى الاتصال بنا أو زيارة النادي.",
                "image_path": "https://www.cmtch.online/photos/d5918ec87dd84e6b9135003161cd7253.jpg?v=20250901"
            },
            {
                "title": "Nouveau Tournoi de Tennis - Inscriptions Ouvertes",
                "content": "Nous avons le plaisir d'annoncer l'ouverture des inscriptions pour notre nouveau tournoi de tennis. Ce tournoi est ouvert à tous les membres du club, quel que soit leur niveau.\n\nCatégories disponibles:\n- Seniors (18 ans et plus)\n- Juniors (moins de 18 ans)\n- Doubles mixtes\n- Doubles hommes\n- Doubles femmes\n\nLe tournoi se déroulera sur deux week-ends avec des prix attractifs pour les gagnants. C'est une excellente occasion de rencontrer d'autres joueurs et de mettre vos compétences à l'épreuve.\n\nLes inscriptions sont limitées, alors n'hésitez pas à vous inscrire rapidement!",
                "image_path": "https://www.cmtch.online/photos/d5918ec87dd84e6b9135003161cd7253.jpg?v=20250901"
            }
        ]
        
        created_count = 0
        
        for article in test_articles:
            print(f"\n🔄 Création de l'article: {article['title'][:50]}...")
            
            # Insérer l'article
            cur.execute("""
                INSERT INTO articles (title, content, image_path, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                article['title'],
                article['content'],
                article['image_path'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            print(f"   ✅ Article créé avec succès")
            created_count += 1
        
        # Sauvegarder les changements
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Articles créés: {created_count}/{len(test_articles)}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur création: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Création d'articles de test multilingues")
    print("=" * 60)
    
    if create_test_multilingual_articles():
        print("✅ Articles multilingues créés avec succès")
        print("\n📋 Articles créés:")
        print("   - 2 articles en arabe")
        print("   - 2 articles en français")
        print("\n🌐 Testez maintenant le support RTL/LTR sur le site!")
    else:
        print("❌ Échec de la création des articles")

if __name__ == "__main__":
    main()
