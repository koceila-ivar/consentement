from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from io import BytesIO
import base64
from PIL import Image
import io as pyio
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL = "EMAIL"
PASSWORD = "PASSWORD"

class ConsentementData(BaseModel):
    nom: str
    date: str
    items: list[str]
    signature: str

def generer_pdf(data: ConsentementData):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 25 * mm
    y = height - 35 * mm

    # Titre
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "Consentement éclairé à l'anesthésie")
    y -= 20

    # Préambule espacé
    c.setFont("Helvetica", 11)
    c.drawString(margin_x, y, "Aucun acte médical ne peut être pratiqué sans le consentement libre et éclairé de la personne")
    y -= 15
    c.drawString(margin_x, y, "(Article L. 1111-4 du Code de la santé publique).")
    y -= 20
    c.drawString(margin_x, y, "Votre intervention ne pourra avoir lieu en l'absence de signature de ce document.")
    y -= 15
    c.drawString(margin_x, y, "Le consentement ne constitue pas une décharge de responsabilité.")
    y -= 30

    # Nom & naissance
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, f"Nom et prénom : {data.nom}")
    y -= 25

    # Corps des phrases avec tirets et interlignes
    c.setFont("Helvetica", 11)
    for item in data.items:
        wrapped = c.beginText(margin_x, y)
        wrapped.setFont("Helvetica", 11)
        wrapped.textLines(f"– {item}")
        c.drawText(wrapped)
        y -= 30 * len(item.splitlines())

    y -= 20

    # Signature
    if data.signature:
        try:
            signature_data = base64.b64decode(data.signature.split(",")[1])
            image = Image.open(pyio.BytesIO(signature_data)).convert("RGBA")
            bg = Image.new("RGB", image.size, (255, 255, 255))
            bg.paste(image, mask=image.split()[3])
            image_path = "/tmp/signature.jpg"
            bg.save(image_path, "JPEG")
            c.drawImage(image_path, margin_x, y - 80, width=200, height=60)
            y -= 90
            c.setFont("Helvetica", 10)
            c.drawString(margin_x, y, "Signature")
            y -= 20
            try:
                european_date = datetime.strptime(data.date, "%Y-%m-%d").strftime("%d-%m-%Y")
            except:
                european_date = data.date
            c.drawString(margin_x, y, f"Date : {european_date}")
        except Exception as e:
            c.drawString(margin_x, y, "[Erreur signature]")

    c.showPage()
    c.save()
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
        return {"message": "PDF généré et email envoyé avec succès."}
    except Exception as e:
        return {"error": str(e)}
from fastapi.responses import HTMLResponse

@app.get("/formulaire", response_class=HTMLResponse)
def afficher_formulaire():
    with open("formulaire_consentement.html", "r", encoding="utf-8") as f:
        return f.read()
    from fastapi.responses import RedirectResponse

@app.get("/")
def rediriger_vers_formulaire():
    return RedirectResponse(url="/formulaire")
