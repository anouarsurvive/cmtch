# -*- coding: utf-8 -*-
"""Envoi d'emails (SMTP, confirmations)."""
from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

from core.config import (
    EMAIL_FROM,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USERNAME,
)


def send_email(to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """Envoie un email via SMTP.
    
    Args:
        to_email: Adresse email du destinataire
        subject: Sujet de l'email
        html_content: Contenu HTML de l'email
        text_content: Contenu texte alternatif (optionnel)
        
    Returns:
        True si l'email a Ã©tÃ© envoyÃ© avec succÃ¨s, False sinon
    """
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            print(f"âš ï¸ Configuration SMTP manquante - Email non envoyÃ© Ã  {to_email}")
            return False
            
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Ajouter le contenu texte et HTML
        if text_content:
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # Connexion au serveur SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        # Envoi de l'email
        text = msg.as_string()
        server.sendmail(EMAIL_FROM, to_email, text)
        server.quit()
        
        print(f"âœ… Email envoyÃ© avec succÃ¨s Ã  {to_email}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de l'envoi d'email Ã  {to_email}: {e}")
        return False


def generate_ics_content(event_title: str, event_description: str, start_datetime: datetime, 
                        end_datetime: datetime, location: str = "Club Municipal de Tennis Chihia") -> str:
    """GÃ©nÃ¨re le contenu d'un fichier ICS (iCalendar).
    
    Args:
        event_title: Titre de l'Ã©vÃ©nement
        event_description: Description de l'Ã©vÃ©nement
        start_datetime: Date et heure de dÃ©but
        end_datetime: Date et heure de fin
        location: Lieu de l'Ã©vÃ©nement
        
    Returns:
        Contenu du fichier ICS
    """
    # Format des dates pour ICS
    def format_datetime(dt):
        return dt.strftime("%Y%m%dT%H%M%SZ")
    
    # PrÃ©parer la description en Ã©chappant les caractÃ¨res spÃ©ciaux
    description = event_description.replace(chr(10), '\\n').replace(chr(13), '')
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CMTCH//Tennis Club//FR
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uuid.uuid4()}@cmtch.tn
DTSTAMP:{format_datetime(datetime.utcnow())}
DTSTART:{format_datetime(start_datetime)}
DTEND:{format_datetime(end_datetime)}
SUMMARY:{event_title}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
    
    return ics_content


def send_reservation_confirmation_email(user_email: str, user_name: str, reservation_data: Dict) -> bool:
    """Envoie un email de confirmation de rÃ©servation.
    
    Args:
        user_email: Email de l'utilisateur
        user_name: Nom de l'utilisateur
        reservation_data: DonnÃ©es de la rÃ©servation
        
    Returns:
        True si l'email a Ã©tÃ© envoyÃ© avec succÃ¨s
    """
    subject = f"Confirmation de rÃ©servation - Court {reservation_data['court_number']}"
    
    # Contenu texte
    text_content = f"""
Confirmation de rÃ©servation - Club Municipal de Tennis Chihia

Bonjour {user_name},

Votre rÃ©servation a Ã©tÃ© confirmÃ©e avec succÃ¨s.

DÃ©tails de la rÃ©servation :
- Date : {reservation_data['date']}
- Heure : {reservation_data['start_time']} - {reservation_data['end_time']}
- Court : {reservation_data['court_number']}
- ID rÃ©servation : #{reservation_data['id']}

Lieu : Club Municipal de Tennis Chihia

Merci de votre confiance !

L'Ã©quipe du Club Municipal de Tennis Chihia
"""
    
    # Contenu HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
        .reservation-details {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #667eea; }}
        .detail-item {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #667eea; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ðŸŽ¾ Confirmation de rÃ©servation</h1>
            <p>Club Municipal de Tennis Chihia</p>
        </div>
        <div class="content">
            <p>Bonjour <strong>{user_name}</strong>,</p>
            <p>Votre rÃ©servation a Ã©tÃ© confirmÃ©e avec succÃ¨s !</p>
            
            <div class="reservation-details">
                <h3>ðŸ“… DÃ©tails de votre rÃ©servation</h3>
                <div class="detail-item">
                    <span class="label">Date :</span> {reservation_data['date']}
                </div>
                <div class="detail-item">
                    <span class="label">Heure :</span> {reservation_data['start_time']} - {reservation_data['end_time']}
                </div>
                <div class="detail-item">
                    <span class="label">Court :</span> Court {reservation_data['court_number']}
                </div>
                <div class="detail-item">
                    <span class="label">ID rÃ©servation :</span> #{reservation_data['id']}
                </div>
            </div>
            
            <p><strong>Lieu :</strong> Club Municipal de Tennis Chihia</p>
            
            <p>Merci de votre confiance !</p>
            <p>Ã€ bientÃ´t sur les courts ! ðŸŽ¾</p>
        </div>
        <div class="footer">
            <p>Club Municipal de Tennis Chihia</p>
            <p>Cet email a Ã©tÃ© envoyÃ© automatiquement, merci de ne pas y rÃ©pondre.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return send_email(user_email, subject, html_content, text_content)


def send_member_validation_email(user_email: str, user_name: str, admin_name: str = "l'administrateur") -> bool:
    """Envoie un email de validation de membre.
    
    Args:
        user_email: Email de l'utilisateur
        user_name: Nom de l'utilisateur
        admin_name: Nom de l'administrateur qui a validÃ©
        
    Returns:
        True si l'email a Ã©tÃ© envoyÃ© avec succÃ¨s
    """
    subject = "Votre compte a Ã©tÃ© validÃ© - Club Municipal de Tennis Chihia"
    
    # Contenu texte
    text_content = f"""
Validation de compte - Club Municipal de Tennis Chihia

Bonjour {user_name},

Excellente nouvelle ! Votre compte a Ã©tÃ© validÃ© par {admin_name}.

Vous pouvez maintenant :
- Vous connecter Ã  votre espace personnel
- Effectuer des rÃ©servations de courts
- AccÃ©der Ã  toutes les fonctionnalitÃ©s du club

Connectez-vous dÃ¨s maintenant sur notre site web !

L'Ã©quipe du Club Municipal de Tennis Chihia
"""
    
    # Contenu HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
        .success-box {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #28a745; }}
        .cta-button {{ display: inline-block; background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>âœ… Compte validÃ© !</h1>
            <p>Club Municipal de Tennis Chihia</p>
        </div>
        <div class="content">
            <p>Bonjour <strong>{user_name}</strong>,</p>
            <p>Excellente nouvelle ! Votre compte a Ã©tÃ© validÃ© par <strong>{admin_name}</strong>.</p>
            
            <div class="success-box">
                <h3>ðŸŽ‰ Vous pouvez maintenant :</h3>
                <ul>
                    <li>Vous connecter Ã  votre espace personnel</li>
                    <li>Effectuer des rÃ©servations de courts</li>
                    <li>AccÃ©der Ã  toutes les fonctionnalitÃ©s du club</li>
                </ul>
            </div>
            
            <p style="text-align: center;">
                <a href="https://www.cmtch.online/connexion" class="cta-button">
                    ðŸŽ¾ Se connecter maintenant
                </a>
            </p>
            
            <p>Ã€ bientÃ´t sur les courts !</p>
        </div>
        <div class="footer">
            <p>Club Municipal de Tennis Chihia</p>
            <p>Cet email a Ã©tÃ© envoyÃ© automatiquement, merci de ne pas y rÃ©pondre.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return send_email(user_email, subject, html_content, text_content)


