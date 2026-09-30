# 🚀 Render Deployment Guide - Hostel Maintenance Predictor

Aapka project **Render.com** par deploy hone ke liye **100% ready** kar diya gaya hai. Saari zaroori configuration files add ho chuki hain:

- ✅ `render.yaml` (Render Blueprint 1-click config)
- ✅ `Procfile` (`web: gunicorn app:app`)
- ✅ `requirements.txt` (`Flask`, `gunicorn`, `pandas`, `matplotlib`, `numpy`, `Werkzeug`)
- ✅ `runtime.txt` (`python-3.11.9`)
- ✅ `.gitignore` (Clean upload)
- ✅ `app.py` (Dynamic cloud `PORT` & `0.0.0.0` binding support)

---

## 📋 Steps to Deploy on Render (Free Tier):

### Step 1: Project ko GitHub par Upload karein
1. [GitHub.com](https://github.com/) par jayein aur ek **New Repository** banayein (e.g., `hostel-maintenance-predictor`).
2. GitHub page par **"uploading an existing file"** par click karein.
3. Apne project folder (`c:\Users\JOHN\Desktop\hostel_management_predictor`) ke saare files aur folders (`templates`, `static`, `app.py`, `models.py`, `analysis.py`, `Procfile`, `requirements.txt`, `render.yaml`) ko drag & drop karke **Commit changes** kar dein.

---

### Step 2: Render par Deploy karein
1. [Render.com](https://render.com/) par jayein aur **Sign In / Sign Up with GitHub** karein.
2. Render Dashboard me **"New +"** button par click karein aur **"Web Service"** chunein.
3. Apni GitHub repository (`hostel-maintenance-predictor`) ko select karke **Connect** karein.
4. Render settings me check karein:
   - **Name:** `hostel-maintenance-predictor`
   - **Region:** Singapore ya Frankfurt (koi bhi)
   - **Branch:** `main` (ya `master`)
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** `Free`
5. Neeche **"Deploy Web Service"** button par click karein!

---

### Step 3: Done! 🎉
- 2-3 minute me Render dependencies install karega aur app live ho jayegi.
- Render aapko ek live URL dega, jaise:
  `https://hostel-maintenance-predictor.onrender.com`
- Is URL ko aap kisi bhi mobile, laptop ya seminar projector par direct open kar sakte hain!
