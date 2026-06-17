import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)
app.secret_key = "pigmi_secure_production_key_2026"
DB_FILE = "pigmi_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS system_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        theme TEXT DEFAULT 'light'
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
            margin: 0;
            background-color: var(--bg-secondary);
            color: var(--text-main);
            transition: background 0.2s, color 0.2s;
            -webkit-tap-highlight-color: transparent;
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
        button {
            background-color: var(--text-main); color: var(--bg-primary);
            border: none; font-weight: 600; cursor: pointer; transition: opacity 0.2s;
        }
        button:active { opacity: 0.8; }

        #auth-container { max-width: 420px; margin: 10% auto; padding: 30px; }
        .card { background-color: var(--bg-primary); border-radius: 14px; box-shadow: var(--card-shadow); padding: 24px; }

        header {
            position: sticky; top: 0; z-index: 100;
            background-color: var(--bg-primary); padding: 12px 24px;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border-color);
        }
        .profile-btn { background: none; border: none; cursor: pointer; width: auto; min-height: auto; padding: 0; }
        .mini-p { font-size: 32px; font-weight: 900; color: var(--text-main); margin: 0; line-height: 1; }
        .mini-dot { width: 8px; height: 8px; background-color: var(--accent-red); border-radius: 50%; margin: -2px auto 0 auto; }

        .dashboard-grid {
            max-width: 1200px; margin: 24px auto;
            display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px; padding: 0 16px;
        }
        .flex-box { cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; border: 1px solid transparent; }
        .flex-box:hover { transform: translateY(-3px); box-shadow: 0 6px 16px rgba(0,0,0,0.1); border-color: var(--border-color); }

        .modal {
            position: fixed; top:0; left:0; width:100vw; height:100vh;
            background: rgba(0,0,0,0.45); backdrop-filter: blur(4px);
            display: flex; justify-content: center; align-items: flex-end; z-index: 1000;
        }
        @media (min-width: 768px) { .modal { align-items: center; } }

        .modal-content {
            background: var(--bg-primary); padding: 24px;
            border-top-left-radius: 20px; border-top-right-radius: 20px;
            width: 100%; max-height: 85vh; overflow-y: auto; position: relative;
        }
        @media (min-width: 768px) {
            .modal-content { border-radius: 16px; max-width: 750px; width: 95%; max-height: 80vh; }
        }

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

        document.getElementById('update-auth-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const res = await fetch('/api/setup-auth', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    u: document.getElementById('new-username').value,
                    p: document.getElementById('new-password').value
                })
            });
            const data = await res.json();
            if(data.success) alert("Credentials successfully reconfigured.");
        });

        // FLEX 1: SYSTEM COLLECTION MATRIX VIEW
        async function openFlex1() {
            const res = await fetch('/api/get-customers');
            const users = await res.json();
            const todayDate = new Date().toISOString().split('T')[0];
            
            let html = '<span class="close-modal" onclick="closeElement(\\'action-modal\\')">&times;</span>' +
                '<h2 style="margin-top:0;">📅 Daily Input Matrix</h2>' +
                '<h4 style="color:var(--accent-blue); margin-top:0;">Collection Date: ' + todayDate + '</h4>' +
                '<div class="table-responsive">' +
                '<table><tr><th>Customer Profile</th><th>Action Route</th></tr>';
            
            users.forEach(u => {
                let phoneDisplay = u.phone ? u.phone : 'No Phone Link';
                html += '<tr>' +
                    '<td><strong>' + u.name + '</strong><br><span style="font-size:12px; opacity:0.6;">' + phoneDisplay + '</span></td>' +
                    '<td><button style="width:auto; min-height:36px; padding:6px 12px; font-size:14px; margin:0; background-color:var(--accent-blue); color:white;" onclick="launchPaymentPopup(' + u.customer_id + ', \\'' + u.name + '\\')">Collect</button></td>' +
                '</tr>';
            });
            html += '</table></div>';
            document.getElementById('action-modal-body').innerHTML = html;
            document.getElementById('action-modal').classList.remove('hidden');
        }

        function launchPaymentPopup(id, name) {
            const amt = prompt("Enter modern ledger payment amount for " + name + ":", "100");
            if (amt === null || amt.trim() === "") return;
            const mode = prompt("Specify Processing Channel (Cash / UPI / Bank):", "Cash");
            if (mode === null || mode.trim() === "") return;

            fetch('/api/post-collection', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: id, amount: amt, mode: mode })
            })
            .then(r => r.json())
            .then(data => {
                if(data.success) {
                    alert("Collection baseline array posted successfully.");
                    openFlex1();
                } else if(data.require_bio) {
                    if(confirm("An entry already exists for today! Scan fingerprint simulation to override?")) {
                        fetch('/api/post-collection-override', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ id: id, amount: amt, mode: mode })
                        })
                        .then(r => r.json())
                        .then(d => { alert(d.msg); openFlex1(); });
                    }
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
            if(!name.trim()) return alert("Valid name metadata payload required.");
            await fetch('/api/add-customer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name, phone })
            });
            openFlex2();
        }

        async function editCustomer(id, oldName, oldPhone) {
            const n = prompt("Edit structural profile name mapping:", oldName);
            const p = prompt("Edit processing system mobile channel mapping:", oldPhone);
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

        // FLEX 3: BALANCE MATRIX RENDERING ENGINE
        async function openFlex3() {
            const res = await fetch('/api/get-matrix');
            const data = await res.json();
            const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
            const currentMonthName = monthNames[new Date().getMonth()];
            const currentYear = new Date().getFullYear();
            
            let html = '<span class="close-modal" onclick="closeElement(\\'action-modal\\')">&times;</span>' +
                '<h2 style="margin-top:0;">📊 Balance Matrix Overview (' + currentMonthName + ' ' + currentYear + ')</h2>' +
                '<div class="table-responsive">' +
                '<table id="matrix-table"><thead><tr>';
            
            if(data.columns.length === 0) {
                html += "<th>No active data profiles registered to the framework.</th></tr></thead></table></div>";
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
                    '<button onclick="window.location.href=\\'/api/export-excel\\'" style="background-color:var(--accent-green); color:white; margin:0;">Excel Spreadsheet</button>' +
                    '<button onclick="exportToPDF(\\'' + currentMonthName + '\\', ' + currentYear + ')" style="background-color:var(--accent-red); color:white; margin:0;">Print PDF Report</button>' +
                '</div>';
            
            document.getElementById('action-modal-body').innerHTML = html;
            document.getElementById('action-modal').classList.remove('hidden');
        }

        function exportToPDF(month, year) {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF('l', 'pt', 'a4');
            doc.text("Pigmi Ledger Analytics - " + month + " " + year, 40, 30);
            doc.autoTable({ html: '#matrix-table', styles: { fontSize: 10 }, marginTop: 50 });
            doc.save("Pigmi_Ledger_" + month + "_" + year + ".pdf");
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
    c.execute("DELETE FROM system_config")
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
    return jsonify({"success": False, "msg": "Invalid structural credential data input."})

@app.route('/api/save-theme', methods=['POST'])
def save_theme():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE system_config SET theme=?", (data['theme'],))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/api/get-customers')
def get_customers():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; c = conn.cursor()
    c.execute("SELECT * FROM customers ORDER BY name ASC")
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    return jsonify(rows)

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
    return jsonify({"success": True})

@app.route('/api/post-collection-override', methods=['POST'])
def post_collection_override():
    data = request.get_json(); today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE collections SET amount=?, mode=? WHERE customer_id=? AND date=?",
              (float(data['amount']), data['mode'], data['id'], today))
    conn.commit(); conn.close()
    return jsonify({"success": True, "msg": "Biometric simulation validated. Record updated."})

def build_pandas_matrix():
    import pandas as pd
    conn = sqlite3.connect(DB_FILE)
    df_cust = pd.read_sql_query("SELECT customer_id, name FROM customers", conn)
    df_coll = pd.read_sql_query("SELECT customer_id, date, amount FROM collections", conn)
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
    matrix = matrix.drop(columns=['customer_id']).sort_values(by='name')
    
    total_row = {col: matrix[col].sum() if col != 'name' else 'Daily Total Sum' for col in matrix.columns}
    matrix = pd.concat([matrix, pd.DataFrame([total_row])], ignore_index=True)
    return matrix

@app.route('/api/export-excel')
def export_excel():
    import io; from flask import send_file
    df = build_pandas_matrix()
    current_month_str = datetime.now().strftime("%B_%Y")
    output = io.BytesIO()
    with io.BytesIO() as output:
        if not df.empty: df.to_excel(output, index=False, sheet_name='Pigmi Ledger')
        output.seek(0)
        return send_file(
            io.BytesIO(output.read()), 
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            as_attachment=True, 
            download_name=f"Pigmi_Ledger_{current_month_str}.xlsx"
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
