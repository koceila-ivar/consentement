
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import smtplib
from email.message import EmailMessage
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.units import mm
import os
import sys
import base64
from PIL import Image as PILImage
import io as pyio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

class ConsentementData(BaseModel):
    nom: str
    date: str
    items: list[str]
    signature: str  # base64 PNG

def generer_pdf(data: ConsentementData):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=25*mm, leftMargin=25*mm,
                            topMargin=25*mm, bottomMargin=25*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY, fontName="Helvetica", fontSize=11, leading=15))
    styles.add(ParagraphStyle(name="JustifyItalic", alignment=TA_JUSTIFY, fontName="Helvetica-Oblique", fontSize=11, leading=15))
    styles.add(ParagraphStyle(name="TitleCenter", alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=16, spaceAfter=12))
    styles.add(ParagraphStyle(name="Bold", fontName="Helvetica-Bold", fontSize=12, leading=14))

    story = []
    story.append(Paragraph("Consentement éclairé à l'anesthésie", styles["TitleCenter"]))
    story.append(Spacer(1, 12))

    preambule = (
        "Aucun acte médical ne peut être pratiqué sans le consentement libre et éclairé de la personne "
        "(Article L. 1111-4 du Code de la santé publique). "
        "Votre intervention ne pourra avoir lieu en l'absence de signature de ce document. "
        "Le consentement ne constitue pas une décharge de responsabilité."
    )
    story.append(Paragraph(preambule, styles["JustifyItalic"]))
    story.append(Spacer(1, 18))

    story.append(Paragraph(f"Nom et prénom : {data.nom}", styles["Bold"]))
    story.append(Spacer(1, 12))

    for p in data.items:
        story.append(Paragraph(f"– {p}", styles["Justify"]))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 30))
    story.append(Paragraph("Signature", styles["Justify"]))
    story.append(Spacer(1, 8))

    # 🔽 Ajout de l'image de signature à partir du base64
    try:
        header, encoded = data.signature.split(",", 1)
        signature_data = base64.b64decode(encoded)
        image_io = pyio.BytesIO(signature_data)
        pil_image = PILImage.open(image_io)
        pil_image_rgb = pil_image.convert("RGB")
        signature_buffer = BytesIO()
        pil_image_rgb.save(signature_buffer, format="PNG")
        signature_buffer.seek(0)
        img = Image(signature_buffer, width=100, height=50)
        story.append(img)
        story.append(Spacer(1, 8))
    except Exception as e:
        story.append(Paragraph("⚠️ Erreur de signature : non insérée", styles["Justify"]))
        print(f"[PDF] Erreur d'insertion de la signature : {e}", file=sys.stderr)

    try:
        european_date = datetime.strptime(data.date, "%Y-%m-%d").strftime("%d-%m-%Y")
    except:
        european_date = data.date
    story.append(Paragraph(f"Date : {european_date}", styles["Justify"]))

    doc.build(story)
    buffer.seek(0)
    return buffer

@app.post("/envoyer-consentement/")
async def envoyer_consentement(data: ConsentementData):
    pdf_buffer = generer_pdf(data)

    msg = EmailMessage()
    msg["Subject"] = f"Consentement anesthésie - {data.nom}"
    msg["From"] = EMAIL
    msg["To"] = EMAIL
    msg.set_content("Veuillez trouver ci-joint le consentement signé.")

    filename = f"{data.nom.replace(' ', '_')}_consentement.pdf"
    msg.add_attachment(pdf_buffer.read(), maintype="application", subtype="pdf", filename=filename)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL, PASSWORD)
            smtp.send_message(msg)
        print("✅ Email envoyé avec succès", file=sys.stderr)
        return {"message": "PDF généré et email envoyé avec succès."}
    except Exception as e:
        print("❌ Erreur SMTP :", file=sys.stderr)
        print(e, file=sys.stderr)
        return {"error": f"Échec de l'envoi : {e}"}

@app.get("/formulaire", response_class=HTMLResponse)
def afficher_formulaire():
    with open("formulaire_consentement.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/")
def rediriger_vers_formulaire():
    return RedirectResponse(url="/formulaire")
