import os
import json
import sqlite3
import pandas as pd
import io
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file

app = Flask(__name__)
app.secret_key = "pigmi_secure_production_key_2026"

# Absolute data path configuration ensures durability over application container shifts
DATA_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(DATA_DIR, "pigmi_data.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS system_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        theme TEXT DEFAULT 'light',
                        biometric_credential_id TEXT,
                        biometric_public_key TEXT
                     )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
                        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        phone TEXT
                     )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        date TEXT,
                        amount REAL,
                        mode TEXT,
                        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                     )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trash_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        name TEXT,
                        phone TEXT,
                        deleted_at TEXT,
                        payment_history_json TEXT
                     )''')
    conn.commit()
    conn.close()

init_db()

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pigmi Microfinance Ledger</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.28/jspdf.plugin.autotable.min.js"></script>
    <style>
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --text-main: #212529;
            --accent-red: #dc3545;
            --accent-blue: #0d6efd;
            --accent-green: #198754;
            --border-color: #dee2e6;
            --card-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        [data-theme="dark"] {
            --bg-primary: #121212;
            --bg-secondary: #1e1e1e;
            --text-main: #f8f9fa;
            --border-color: #333333;
            --card-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body {
            margin: 0; background-color: var(--bg-secondary); color: var(--text-main);
            transition: background 0.2s, color 0.2s; -webkit-tap-highlight-color: transparent;
        }
        #splash-screen {
            position: fixed; top:0; left:0; width:100vw; height:100vh;
            background: #ffffff; display: flex; flex-direction: column;
            justify-content: center; align-items: center; z-index: 9999;
        }
        .brand-p { font-size: 140px; font-weight: 900; color: #000000; margin: 0; line-height: 1; }
        .red-dot { width: 24px; height: 24px; background-color: var(--accent-red); border-radius: 50%; margin-top: -10px; }
        .hidden { display: none !important; }
        input, select, button {
            width: 100%; min-height: 48px; padding: 12px; margin: 8px 0;
            border-radius: 8px; border: 1px solid var(--border-color);
            background: var(--bg-primary); color: var(--text-main); font-size: 16px;
        }
        button { background-color: var(--text-main); color: var(--bg-primary); border: none; font-weight: 600; cursor: pointer; }
        #auth-container { max-width: 420px; margin: 10% auto; padding: 30px; }
        .card { background-color: var(--bg-primary); border-radius: 14px; box-shadow: var(--card-shadow); padding: 24px; }
        header {
            position: sticky; top: 0; z-index: 100; background-color: var(--bg-primary); padding: 12px 24px;
            display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color);
        }
        .profile-btn { background: none; border: none; cursor: pointer; width: auto; min-height: auto; padding: 0; }
        .mini-p { font-size: 32px; font-weight: 900; color: var(--text-main); margin: 0; line-height: 1; }
        .mini-dot { width: 8px; height: 8px; background-color: var(--accent-red); border-radius: 50%; margin: -2px auto 0 auto; }
        .dashboard-grid {
            max-width: 1200px; margin: 24px auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; padding: 0 16px;
        }
        .flex-box { cursor: pointer; transition: transform 0.2s; border: 1px solid transparent; }
        .flex-box:hover { transform: translateY(-3px); border-color: var(--border-color); }
        .modal {
            position: fixed; top:0; left:0; width:100vw; height:100vh; background: rgba(0,0,0,0.45);
            backdrop-filter: blur(4px); display: flex; justify-content: center; align-items: flex-end; z-index: 1000;
        }
        @media (min-width: 768px) { .modal { align-items: center; } }
        .modal-content {
            background: var(--bg-primary); padding: 24px; border-top-left-radius: 20px; border-top-right-radius: 20px;
            width: 100%; max-height: 85vh; overflow-y: auto; position: relative;
        }
        @media (min-width: 768px) { .modal-content { border-radius: 16px; max-width: 750px; width: 95%; max-height: 80vh; } }
        .close-modal { position: absolute; top: 16px; right: 20px; font-size: 28px; cursor: pointer; opacity: 0.6; }
        .table-responsive { width: 100%; overflow-x: auto; margin-top: 16px; border-radius: 8px; border: 1px solid var(--border-color); }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }
        th, td { padding: 14px; border-bottom: 1px solid var(--border-color); min-width: 110px; }
        th { background-color: var(--bg-secondary); font-weight: 600; position: sticky; top: 0; }
        .action-group { display: flex; gap: 8px; flex-wrap: wrap; }
        .action-group button { width: auto; min-height: 38px; padding: 6px 14px; font-size: 14px; margin: 0; }
    </style>
</head>
<body data-theme="light">

    <div id="splash-screen">
        <h1 class="brand-p">P</h1>
        <div class="red-dot"></div>
    </div>

    <div id="auth-container" class="card hidden">
        <h2 id="auth-title" style="margin-top:0;">Account Access</h2>
        <form id="auth-form">
            <input type="text" id="username" placeholder="Username" required>
            <input type="password" id="password" placeholder="Password" required>
            <button type="submit" style="margin-top:16px;">Log In</button>
        </form>
    </div>

    <div id="main-app" class="hidden">
        <header>
            <button class="profile-btn" onclick="openSettings()">
                <div class="mini-p">P</div>
                <div class="mini-dot"></div>
            </button>
            <div style="text-align: center;">
                <h3 style="margin:0; font-weight:800; letter-spacing:0.5px;">PIGMI</h3>
                <span style="font-size:11px; opacity:0.6; font-weight:500;">Microfinance Management</span>
            </div>
            <div style="width:32px;"></div>
        </header>

        <main class="dashboard-grid">
            <div class="card flex-box" onclick="openFlex1()">
                <h3 style="margin-top:0; color:var(--accent-blue);">📅 Daily Collection Update</h3>
                <p style="margin-bottom:0; opacity:0.8; font-size:14px;">Log today's cash or digital deposits directly into the customer lists.</p>
            </div>
            <div class="card flex-box" onclick="openFlex2()">
                <h3 style="margin-top:0; color:var(--accent-green);">👥 Customer Registry</h3>
                <p style="margin-bottom:0; opacity:0.8; font-size:14px;">Provision new microfinance targets, alter metadata, or perform safe deletions.</p>
            </div>
            <div class="card flex-box" onclick="openFlex3()">
                <h3 style="margin-top:0; color:var(--text-main);">📊 Balance Matrix & Reports</h3>
                <p style="margin-bottom:0; opacity:0.8; font-size:14px;">Instantly compile dynamic monthly spreadsheets and download verified PDF outputs.</p>
            </div>
        </main>
    </div>

    <div id="settings-modal" class="modal hidden">
        <div class="modal-content">
            <span class="close-modal" onclick="closeElement('settings-modal')">&times;</span>
            <h2 style="margin-top:0;">Control Console</h2>
            <hr style="border:0; border-top:1px solid var(--border-color); margin:16px 0;">
            
            <h4 style="margin:12px 0 4px 0;">Visual Mode Configuration</h4>
            <button onclick="toggleThemeSkin()">Toggle Light / Dark Mode</button>
            
            <h4 style="margin:20px 0 4px 0;">Biometric Access Authorization</h4>
            <button onclick="registerBiometrics()" style="background-color: var(--accent-green); color: white;">Link Native Fingerprint Scanner</button>
            <p id="bio-status" style="font-size:12px; margin-top:4px; opacity:0.7; font-style:italic;"></p>

            <h4 style="margin:20px 0 4px 0;">Modify Management Credentials</h4>
            <form id="update-auth-form">
                <input type="text" id="new-username" placeholder="New Username" required>
                <input type="password" id="new-password" placeholder="New Password" required>
                <button type="submit" style="background-color:var(--accent-blue); color:white;">Save Security Data</button>
            </form>
            
            <h3 style="color:var(--accent-red); margin:24px 0 8px 0;">🗑️ Archive Storage Recovery Trash</h3>
            <div id="trash-list-container"></div>
        </div>
    </div>

    <div id="action-modal" class="modal hidden">
        <div class="modal-content" id="action-modal-body"></div>
    </div>

    <script>
        let IS_FIRST_TIME = false;

        window.addEventListener('DOMContentLoaded', () => {
            setTimeout(async () => {
                const res = await fetch('/api/check-auth-state');
                const data = await res.json();
                document.getElementById('splash-screen').classList.add('hidden');
                document.getElementById('auth-container').classList.remove('hidden');
                if (data.status === 'setup') {
                    IS_FIRST_TIME = true;
                    document.getElementById('auth-title').innerText = "Initial Master Configuration";
                }
            }, 1200);
        });

        document.getElementById('auth-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = IS_FIRST_TIME ? '/api/setup-auth' : '/api/login-auth';
            const res = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    u: document.getElementById('username').value,
                    p: document.getElementById('password').value
                })
            });
            const data = await res.json();
            if(data.success) {
                document.getElementById('auth-container').classList.add('hidden');
                document.getElementById('main-app').classList.remove('hidden');
                if(data.theme) document.body.setAttribute('data-theme', data.theme);
            } else {
                alert(data.msg || "Access validation failure.");
            }
        });

        function closeElement(id) { document.getElementById(id).classList.add('hidden'); }

        async function openSettings() {
            document.getElementById('settings-modal').classList.remove('hidden');
            const bioCheck = await fetch('/api/check-bio-registered');
            const bioData = await bioCheck.json();
            document.getElementById('bio-status').innerText = bioData.registered ? "🔒 Fingerprint scanner profile actively linked to system configuration." : "⚠️ Biometrics unlinked. Set scanner up before attempt to modify collection data.";
            
            const res = await fetch('/api/get-trash');
            const records = await res.json();
            const container = document.getElementById('trash-list-container');
            if(records.length === 0) {
                container.innerHTML = "<p style='font-style:italic; opacity:0.5; font-size:14px;'>Archive empty.</p>";
                return;
            }
            let html = "<div class='table-responsive'><table><tr><th>Profile Name</th><th>Deletion Timestamp</th></tr>";
            records.forEach(r => { html += "<tr><td>" + r.name + "</td><td>" + r.deleted_at + "</td></tr>"; });
            html += "</table></div>";
            container.innerHTML = html;
        }

        async function registerBiometrics() {
            if (!window.PublicKeyCredential) {
                return alert("Biometric protocols (WebAuthn) are not supported or active on this runtime environment.");
            }
            const challenge = new Uint8Array(32);
            window.crypto.getRandomValues(challenge);
            const userId = new Uint8Array(16);
            window.crypto.getRandomValues(userId);

            const options = {
                publicKey: {
                    challenge: challenge,
                    rp: { name: "Pigmi Framework" },
                    user: { id: userId, name: "manager", displayName: "System Manager" },
                    pubKeyCredParams: [{ type: "public-key", alg: -7 }],
                    timeout: 60000,
                    authenticatorSelection: { authenticatorAttachment: "platform", userVerification: "required" }
                }
            };

            try {
                const cred = await navigator.credentials.create(options);
                const rawId = btoa(String.fromCharCode.apply(null, new Uint8Array(cred.rawId)));
                await fetch('/api/register-bio', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ credential_id: rawId })
                });
                alert("Native fingerprint hardware verified and successfully coupled.");
                openSettings();
            } catch (err) {
                alert("Biometric enrollment interrupted: " + err.message);
            }
        }

        async function verifyBiometrics() {
            if (!window.PublicKeyCredential) return false;
            const res = await fetch('/api/check-bio-registered');
            const status = await res.json();
            if (!status.registered) {
                alert("Verification stopped: Please attach fingerprints first inside configuration profile.");
                return false;
            }
            const challenge = new Uint8Array(32);
            window.crypto.getRandomValues(challenge);
            const options = {
                publicKey: {
                    challenge: challenge,
                    timeout: 60000,
                    userVerification: "required"
                }
            };
            try {
                await navigator.credentials.get(options);
                return true;
            } catch (e) {
                alert("Biometric match failure: " + e.message);
                return false;
            }
        }

        async function toggleThemeSkin() {
            const current = document.body.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', target);
            await fetch('/api/save-theme', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ theme: target })
            });
        }

        // FLEX 1: SYSTEM COLLECTION MATRIX VIEW
        async function openFlex1() {
            const res = await fetch('/api/get-customers');
            const users = await res.json();
            const logsRes = await fetch('/api/get-todays-logs');
            const loggedIds = await logsRes.json();
            const todayDate = new Date().toISOString().split('T')[0];
            
            let html = '<span class="close-modal" onclick="closeElement(\\'action-modal\\')">&times;</span>' +
                '<h2 style="margin-top:0;">📅 Daily Input Matrix</h2>' +
                '<h4 style="color:var(--accent-blue); margin-top:0;">Collection Date: ' + todayDate + '</h4>' +
                '<div class="table-responsive">' +
                '<table><tr><th>Customer Profile</th><th>Action Route</th></tr>';
            
            users.forEach(u => {
                let phoneDisplay = u.phone ? u.phone : 'No Phone Link';
                let isCollected = loggedIds.includes(u.customer_id);
                let btnStyle = isCollected ? 'background-color:#ffc107; color:black;' : 'background-color:var(--accent-blue); color:white;';
                let btnText = isCollected ? 'Modify (🔒 Biometric)' : 'Collect';
                
                html += '<tr>' +
                    '<td><strong>' + u.name + '</strong><br><span style="font-size:12px; opacity:0.6;">' + phoneDisplay + '</span></td>' +
                    '<td><button style="width:auto; min-height:36px; padding:6px 12px; font-size:14px; margin:0; ' + btnStyle + '" onclick="launchPaymentPopup(' + u.customer_id + ', \\'' + u.name + '\\', ' + isCollected + ')">' + btnText + '</button></td>' +
                '</tr>';
            });
            html += '</table></div>';
            document.getElementById('action-modal-body').innerHTML = html;
            document.getElementById('action-modal').classList.remove('hidden');
        }

        async function launchPaymentPopup(id, name, isCollected) {
            if (isCollected) {
                const authorized = await verifyBiometrics();
                if (!authorized) return;
            }
            const amt = prompt("Enter payment amount for " + name + ":", "100");
            if (amt === null || amt.trim() === "") return;
            const mode = prompt("Specify Processing Channel (Cash / UPI / Bank):", "Cash");
            if (mode === null || mode.trim() === "") return;

            const url = isCollected ? '/api/post-collection-override' : '/api/post-collection';
            fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: id, amount: amt, mode: mode })
            })
            .then(r => r.json())
            .then(data => {
                if(data.success) {
                    alert(data.msg || "Collection array posted successfully.");
                    openFlex1();
                }
            });
        }

        // FLEX 2: PROFILE DIRECTORY EDITOR
        async function openFlex2() {
            const res = await fetch('/api/get-customers');
            const users = await res.json();
            let html = '<span class="close-modal" onclick="closeElement(\\'action-modal\\')">&times;</span>' +
                '<h2 style="margin-top:0;">👥 Customer Registry Engine</h2>' +
                '<div class="card" style="box-shadow:none; border:1px solid var(--border-color); margin-bottom:16px; padding:16px;">' +
                    '<h4 style="margin-top:0; margin-bottom:8px;">Provision New Active Account</h4>' +
                    '<input type="text" id="c-name" placeholder="Full Name Identifier">' +
                    '<input type="tel" id="c-phone" placeholder="Phone Data String">' +
                    '<button style="background-color:var(--accent-green); color:white;" onclick="submitNewCustomer()">Provision Profile</button>' +
                '</div>' +
                '<div class="table-responsive">' +
                '<table><tr><th>Active Core Listings</th><th>Management Options</th></tr>';
            
            users.forEach(u => {
                html += '<tr>' +
                    '<td><strong>' + u.name + '</strong><br><span style="font-size:12px; opacity:0.6;">' + u.phone + '</span></td>' +
                    '<td>' +
                        '<div class="action-group">' +
                            '<button style="background-color:var(--bg-secondary); color:var(--text-main); border:1px solid var(--border-color);" onclick="editCustomer(' + u.customer_id + ', \\'' + u.name + '\\', \\'' + u.phone + '\\')">Modify</button>' +
                            '<button style="background-color:var(--accent-red); color:white;" onclick="deleteCustomer(' + u.customer_id + ', \\'' + u.name + '\\')">Delete</button>' +
                        '</div>' +
                    '</td>' +
                '</tr>';
            });
            html += '</table></div>';
            document.getElementById('action-modal-body').innerHTML = html;
            document.getElementById('action-modal').classList.remove('hidden');
        }

        async function submitNewCustomer() {
            const name = document.getElementById('c-name').value;
            const phone = document.getElementById('c-phone').value;
            if(!name.trim()) return alert("Valid name payload required.");
            await fetch('/api/add-customer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name, phone })
            });
            openFlex2();
        }

        async function editCustomer(id, oldName, oldPhone) {
            const n = prompt("Edit structural profile name mapping:", oldName);
            const p = prompt("Edit mobile channel mapping:", oldPhone);
            if(!n || !n.trim()) return;
            await fetch('/api/edit-customer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id, name: n, phone: p })
            });
            openFlex2();
        }

        async function deleteCustomer(id, name) {
            if(confirm("Completely isolate and archive data arrays for " + name + "?")) {
                await fetch('/api/delete-customer', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                openFlex2();
            }
        }

        // FLEX 3: BALANCE MATRIX RENDERING ENGINE WITH HISTORICAL MONTH PICKER
        async function openFlex3(selectedTargetMonth = null) {
            if(!selectedTargetMonth) {
                const now = new Date();
                selectedTargetMonth = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, '0');
            }
            const res = await fetch('/api/get-matrix?month=' + selectedTargetMonth);
            const data = await res.json();
            
            let html = '<span class="close-modal" onclick="closeElement(\\'action-modal\\')">&times;</span>' +
                '<h2 style="margin-top:0;">📊 Balance Matrix Overview</h2>' +
                '<div style="margin-bottom:16px;">' +
                    '<label style="font-size:14px; font-weight:600;">Choose Target Accounting Ledger Period: </label>' +
                    '<input type="month" id="matrix-month-picker" value="' + selectedTargetMonth + '" onchange="openFlex3(this.value)" style="width:auto; display:inline-block; min-height:38px; margin-left:8px; padding:6px;">' +
                '</div>' +
                '<div class="table-responsive">' +
                '<table id="matrix-table"><thead><tr>';
            
            if(!data.columns || data.columns.length === 0) {
                html += "<th>No active data profiles match filter selection.</th></tr></thead></table></div>";
                document.getElementById('action-modal-body').innerHTML = html;
                return;
            }

            data.columns.forEach(col => { html += "<th>" + col + "</th>"; });
            html += "</tr></thead><tbody>";

            data.data.forEach((row, index) => {
                let isLast = (index === data.data.length - 1);
                html += isLast ? "<tr style='font-weight:bold; background-color:var(--bg-secondary);'>" : "<tr>";
                row.forEach(val => { html += "<td>" + (val !== null ? val : 0) + "</td>"; });
                html += "</tr>";
            });

            html += '</tbody></table></div>' +
                '<div style="margin-top:20px; display:grid; grid-template-columns: 1fr 1fr; gap:12px;">' +
                    '<button onclick="triggerExcelExport(\\''+selectedTargetMonth+'\\')" style="background-color:var(--accent-green); color:white; margin:0;">Excel Spreadsheet</button>' +
                    '<button onclick="exportToPDF(\\'' + selectedTargetMonth + '\\')" style="background-color:var(--accent-red); color:white; margin:0;">Print PDF Report</button>' +
                '</div>';
            
            document.getElementById('action-modal-body').innerHTML = html;
            document.getElementById('action-modal').classList.remove('hidden');
        }

        function triggerExcelExport(monthStr) {
            window.location.href = '/api/export-excel?month=' + monthStr;
        }

        function exportToPDF(monthStr) {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF('l', 'pt', 'a4');
            doc.text("Pigmi Ledger Analytics Ledger - " + monthStr, 40, 30);
            doc.autoTable({ html: '#matrix-table', styles: { fontSize: 10 }, marginTop: 50 });
            doc.save("Pigmi_Ledger_" + monthStr + ".pdf");
        }
    </script>
</body>
</html>
"""

@app.route('/')
def render_app_surface(): return render_template_string(INDEX_TEMPLATE)

@app.route('/api/check-auth-state')
def check_auth_state():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM system_config")
    count = c.fetchone()[0]; conn.close()
    return jsonify({"status": "login" if count > 0 else "setup"})

@app.route('/api/setup-auth', methods=['POST'])
def setup_auth():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT biometric_credential_id, biometric_public_key FROM system_config LIMIT 1")
    existing_bio = c.fetchone()
    c.execute("DELETE FROM system_config")
    if existing_bio:
        c.execute("INSERT INTO system_config (username, password, biometric_credential_id, biometric_public_key) VALUES (?, ?, ?, ?)",
                  (data['u'], data['p'], existing_bio[0], existing_bio[1]))
    else:
        c.execute("INSERT INTO system_config (username, password) VALUES (?, ?)", (data['u'], data['p']))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/login-auth', methods=['POST'])
def login_auth():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT theme FROM system_config WHERE username=? AND password=?", (data['u'], data['p']))
    row = c.fetchone(); conn.close()
    if row: return jsonify({"success": True, "theme": row[0]})
    return jsonify({"success": False, "msg": "Invalid credential data input."})

@app.route('/api/save-theme', methods=['POST'])
def save_theme():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE system_config SET theme=?", (data['theme'],))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/check-bio-registered')
def check_bio_registered():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT biometric_credential_id FROM system_config WHERE biometric_credential_id IS NOT NULL")
    row = c.fetchone(); conn.close()
    return jsonify({"registered": True if row else False})

@app.route('/api/register-bio', methods=['POST'])
def register_bio():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE system_config SET biometric_credential_id=?", (data['credential_id'],))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/get-customers')
def get_customers():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; c = conn.cursor()
    c.execute("SELECT * FROM customers ORDER BY customer_id ASC")
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    return jsonify(rows)

@app.route('/api/get-todays-logs')
def get_todays_logs():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT customer_id FROM collections WHERE date=?", (today,))
    ids = [row[0] for row in c.fetchall()]; conn.close()
    return jsonify(ids)

@app.route('/api/add-customer', methods=['POST'])
def add_customer():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (data['name'], data['phone']))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/edit-customer', methods=['POST'])
def edit_customer():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE customers SET name=?, phone=? WHERE customer_id=?", (data['name'], data['phone'], data['id']))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/delete-customer', methods=['POST'])
def delete_customer():
    data = request.get_json(); cid = data['id']
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT name, phone FROM customers WHERE customer_id=?", (cid,))
    cust = c.fetchone()
    if not cust: conn.close(); return jsonify({"success": False})
    
    c.execute("SELECT date, amount, mode FROM collections WHERE customer_id=?", (cid,))
    history_list = [{"date": h[0], "amount": h[1], "mode": h[2]} for h in c.fetchall()]
    
    c.execute("INSERT INTO trash_records (customer_id, name, phone, deleted_at, payment_history_json) VALUES (?, ?, ?, ?, ?)",
              (cid, cust[0], cust[1], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(history_list)))
    c.execute("DELETE FROM customers WHERE customer_id=?", (cid,))
    c.execute("DELETE FROM collections WHERE customer_id=?", (cid,))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/get-trash')
def get_trash():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; c = conn.cursor()
    c.execute("SELECT name, phone, deleted_at FROM trash_records ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    return jsonify(rows)

@app.route('/api/post-collection', methods=['POST'])
def post_collection():
    data = request.get_json(); today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT id FROM collections WHERE customer_id=? AND date=?", (data['id'], today))
    exists = c.fetchone(); conn.close()
    if exists: return jsonify({"success": False, "require_bio": True})
        
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO collections (customer_id, date, amount, mode) VALUES (?, ?, ?, ?)",
              (data['id'], today, float(data['amount']), data['mode']))
    conn.commit(); conn.close()
    return jsonify({"success": True, "msg": "Collection posted successfully."})

@app.route('/api/post-collection-override', methods=['POST'])
def post_collection_override():
    data = request.get_json(); today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE collections SET amount=?, mode=? WHERE customer_id=? AND date=?",
              (float(data['amount']), data['mode'], data['id'], today))
    conn.commit(); conn.close()
    return jsonify({"success": True, "msg": "Biometric validation passed. Entry safely amended."})

def build_pandas_matrix(target_month=None):
    if not target_month:
        target_month = datetime.now().strftime("%Y-%m")
    
    conn = sqlite3.connect(DB_FILE)
    df_cust = pd.read_sql_query("SELECT customer_id, name FROM customers ORDER BY customer_id ASC", conn)
    # Filter transactional logs to fit the targeted month format match (YYYY-MM-DD starts with YYYY-MM)
    df_coll = pd.read_sql_query(f"SELECT customer_id, date, amount FROM collections WHERE date LIKE '{target_month}%'", conn)
    conn.close()
    
    if df_cust.empty: return pd.DataFrame()
    if df_coll.empty:
        matrix = df_cust.copy()
        matrix['Monthly Total'] = 0.0
        return matrix.drop(columns=['customer_id'])

    pivot = df_coll.pivot_table(index='customer_id', columns='date', values='amount', aggfunc='sum').fillna(0)
    matrix = pd.merge(df_cust, pivot, on='customer_id', how='left').fillna(0)
    
    date_cols = [c for c in matrix.columns if c not in ['customer_id', 'name']]
    matrix['Monthly Total'] = matrix[date_cols].sum(axis=1)
    matrix = matrix.drop(columns=['customer_id'])
    
    total_row = {col: matrix[col].sum() if col != 'name' else 'Daily Total Sum' for col in matrix.columns}
    matrix = pd.concat([matrix, pd.DataFrame([total_row])], ignore_index=True)
    return matrix

@app.route('/api/get-matrix')
def get_matrix_json():
    target_month = request.args.get('month')
    df = build_pandas_matrix(target_month)
    if df.empty: return jsonify({"columns": [], "data": []})
    return jsonify({"columns": list(df.columns), "data": df.values.tolist()})

@app.route('/api/export-excel')
def export_excel():
    target_month = request.args.get('month')
    df = build_pandas_matrix(target_month)
    output = io.BytesIO()
    if not df.empty:
        df.to_excel(output, index=False, sheet_name='Pigmi Monthly Ledger')
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"Pigmi_Ledger_{target_month}.xlsx")
    return jsonify({"error": "Empty set"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
