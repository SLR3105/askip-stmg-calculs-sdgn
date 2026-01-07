# Askip'en STMG Calculs

## Lancer en local
1. Installer Python 3.10+  
2. Dans un terminal :
   - `pip install -r requirements.txt`
   - `streamlit run app.py`

## Modifier / ajouter des exercices
Ouvre `exercises.json` et ajoute une entrée sur le modèle des autres.

## Mettre en ligne gratuitement (Streamlit Community Cloud)
1. Crée un compte GitHub
2. Mets ce dossier dans un repo GitHub
3. Va sur Streamlit Community Cloud > *Deploy* > choisis le repo > `app.py`


## V2 (ajouts)
- Questions QCM (choix unique) et questions à réponses multiples (cases à cocher).
- Feedback "il manque / à retirer" sur les questions à réponses multiples.
- Correction affichable par exercice.
