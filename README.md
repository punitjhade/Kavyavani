# SukhanSarai — Setup Guide 🌙

## Your Folder Structure
```
SukhanSarai/
│
├── app.py                    ← Main Flask application
├── requirements.txt          ← Python packages needed
├── sukhan.db                 ← SQLite database (auto-created)
│
├── static/
│   └── css/
│       └── style.css         ← All styling
│
└── templates/
    ├── user/
    │   ├── base.html
    │   ├── index.html
    │   ├── login.html
    │   ├── signup.html
    │   ├── poem.html
    │   ├── write.html
    │   ├── profile.html
    │   ├── edit_profile.html
    │   ├── category.html
    │   └── search.html
    └── admin/
        ├── base.html
        ├── login.html
        ├── dashboard.html
        ├── users.html
        ├── poems.html
        └── comments.html
```

---

## ✅ STEP 1 — Install Python
- Download from: https://python.org
- During install: ✅ Check "Add Python to PATH"
- Verify: open Terminal and type `python --version`

---

## ✅ STEP 2 — Open in VS Code
1. Open VS Code
2. File → Open Folder → Select `SukhanSarai` folder
3. Open the Terminal inside VS Code: View → Terminal (or Ctrl+`)

---

## ✅ STEP 3 — Install Flask
In the VS Code terminal, type:
```
pip install flask werkzeug
```
Wait for it to finish.

---

## ✅ STEP 4 — Run the Website
In the terminal:
```
python app.py
```
You'll see:
```
✅ Database ready.
 * Running on http://127.0.0.1:5000
```

---

## ✅ STEP 5 — Open in Browser
- **User site:** http://127.0.0.1:5000
- **Admin panel:** http://127.0.0.1:5000/admin-login

---

## 🔐 Admin Login Credentials
```
Username: admin
Password: admin123
```
**Change this password after first login!**

---

## 🌐 MAKING IT ACCESSIBLE TO OTHERS (on same WiFi)
1. Find your computer's local IP:
   - Windows: open cmd → type `ipconfig` → look for IPv4 Address (e.g. 192.168.1.5)
   - Mac/Linux: open terminal → type `ifconfig`
2. In app.py, change the last line to:
   ```python
   app.run(debug=False, host='0.0.0.0', port=5000)
   ```
3. Other people on the same WiFi can visit:
   `http://192.168.1.5:5000`  (use YOUR IP address)

---

## 🌍 MAKING IT PUBLIC (for anyone on the internet)
Use **ngrok** (free):
1. Download from: https://ngrok.com
2. Run your Flask app: `python app.py`
3. In a NEW terminal: `ngrok http 5000`
4. ngrok gives you a public URL like: `https://abc123.ngrok.io`
5. Share that URL with anyone in the world!

---

## 📋 All Website Pages

| URL | Description |
|-----|-------------|
| / | Homepage with poem feed |
| /signup | Create account |
| /login | Login |
| /write | Write a poem |
| /poem/1 | View a poem |
| /profile/username | Poet profile |
| /category/Love | Browse by category |
| /search?q=... | Search poems |
| /admin-login | Admin portal |
| /admin/dashboard | Admin dashboard |
| /admin/users | Manage users |
| /admin/poems | Manage poems |
| /admin/comments | Moderate comments |

---

## 🛑 Stopping the Server
Press `Ctrl + C` in the terminal.

---

## ❓ Common Issues

**"ModuleNotFoundError: No module named flask"**
→ Run: `pip install flask werkzeug`

**"Address already in use"**
→ Change port in app.py: `port=5001`

**Page not loading**
→ Make sure `python app.py` is running in terminal
