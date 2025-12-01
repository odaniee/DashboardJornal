import json
import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def ensure_data_file(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(default, file, ensure_ascii=False, indent=2)
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_data(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("user"):
            flash("Entre com um usuário administrador para continuar", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


config = load_config()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key")
app.config["UPLOAD_FOLDER_JOURNALS"] = os.path.join("uploads", "journals")
app.config["UPLOAD_FOLDER_ASSETS"] = os.path.join("uploads", "assets")

os.makedirs(app.config["UPLOAD_FOLDER_JOURNALS"], exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER_ASSETS"], exist_ok=True)

students_path = os.path.join("data", "students.json")
journals_path = os.path.join("data", "journals.json")
assets_path = os.path.join("data", "assets.json")
rules_path = os.path.join("data", "rules.json")
announcements_path = os.path.join("data", "announcements.json")
calendar_path = os.path.join("data", "calendar.json")
departments_path = os.path.join("data", "departments.json")
site_settings_path = os.path.join("data", "site_settings.json")

students = ensure_data_file(students_path, [])
journals = ensure_data_file(journals_path, [])
assets = ensure_data_file(assets_path, [])
rules = ensure_data_file(
    rules_path, {"content": "Defina aqui as regras de convivência do jornal.", "updated_at": None}
)
announcements = ensure_data_file(announcements_path, [])
calendar_events = ensure_data_file(calendar_path, [])
departments = ensure_data_file(departments_path, [])
site_settings = ensure_data_file(
    site_settings_path,
    {
        "logo_url": "",
        "primary_color": "#0d6efd",
        "accent_color": "#6610f2",
        "tagline": "Painel interno do jornal escolar",
    },
)

for asset in assets:
    asset.setdefault("scope", "pessoal")
    asset.setdefault("owner", "")
    asset.setdefault("department_id", None)


@app.context_processor
def inject_globals():
    base_url = f"{config.get('protocol', 'http')}://{config.get('host', 'localhost')}:{config.get('port', 5000)}"
    return {
        "base_url": base_url,
        "dashboard_tabs": [
            ("students", "Funcionários"),
            ("journals", "Jornais"),
            ("assets", "Arquivos"),
            ("rules", "Manual de Regras"),
            ("announcements", "Administração"),
            ("calendar", "Calendário"),
            ("departments", "Departamentos"),
            ("settings", "Configuração"),
            ("versions", "Versões"),
        ],
        "site_settings": site_settings,
    }


@app.route("/")
def index():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        for admin in config.get("admin_users", []):
            if admin.get("username") == username and admin.get("password") == password:
                session["user"] = username
                flash("Login realizado com sucesso", "success")
                return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Sessão encerrada", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    tab = request.args.get("tab", "students")
    sorted_students = sorted(students, key=lambda s: s.get("name", "").lower())
    sorted_journals = sorted(
        journals, key=lambda j: j.get("release_date", ""), reverse=True
    )
    sorted_assets = sorted(assets, key=lambda a: a.get("uploaded_at", ""), reverse=True)
    sorted_announcements = sorted(
        announcements, key=lambda a: a.get("created_at", ""), reverse=True
    )
    sorted_events = sorted(calendar_events, key=lambda e: e.get("date", ""))
    sorted_departments = sorted(departments, key=lambda d: d.get("name", "").lower())
    return render_template(
        "dashboard.html",
        current_tab=tab,
        students=sorted_students,
        journals=sorted_journals,
        assets=sorted_assets,
        rules=rules,
        announcements=sorted_announcements,
        calendar_events=sorted_events,
        departments=sorted_departments,
    )


@app.route("/students", methods=["POST"])
@login_required
def create_student():
    student = {
        "id": str(uuid.uuid4()),
        "name": request.form.get("name"),
        "role": request.form.get("role"),
        "contact": request.form.get("contact"),
        "notes": request.form.get("notes"),
        "portal_enabled": request.form.get("portal_enabled") == "on",
        "created_at": datetime.utcnow().isoformat(),
    }
    students.append(student)
    save_data(students_path, students)
    flash("Ficha de participante criada", "success")
    return redirect(url_for("dashboard", tab="students"))


@app.route("/students/<student_id>/toggle", methods=["POST"])
@login_required
def toggle_student(student_id):
    for student in students:
        if student.get("id") == student_id:
            student["portal_enabled"] = not student.get("portal_enabled", False)
            save_data(students_path, students)
            flash("Permissão de portal atualizada", "info")
            break
    return redirect(url_for("dashboard", tab="students"))


@app.route("/journals", methods=["POST"])
@login_required
def create_journal():
    file = request.files.get("file")
    filename = None
    if file and file.filename:
        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        destination = os.path.join(app.config["UPLOAD_FOLDER_JOURNALS"], filename)
        file.save(destination)

    journal = {
        "id": str(uuid.uuid4()),
        "title": request.form.get("title"),
        "edition": request.form.get("edition"),
        "release_date": request.form.get("release_date"),
        "description": request.form.get("description"),
        "file": filename,
        "status": "pendente",
        "approval_reason": None,
        "approval_token": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
    }
    journals.append(journal)
    save_data(journals_path, journals)
    flash("Jornal enviado para aprovação", "success")
    return redirect(url_for("dashboard", tab="journals"))


@app.route("/assets", methods=["POST"])
@login_required
def upload_asset():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Selecione um arquivo para enviar", "warning")
        return redirect(url_for("dashboard", tab="assets"))

    filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
    destination = os.path.join(app.config["UPLOAD_FOLDER_ASSETS"], filename)
    file.save(destination)

    asset = {
        "id": str(uuid.uuid4()),
        "original_name": file.filename,
        "stored_name": filename,
        "notes": request.form.get("notes"),
        "owner": request.form.get("owner") or session.get("user"),
        "department_id": request.form.get("department_id") or None,
        "scope": "departamento" if request.form.get("department_id") else "pessoal",
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    assets.append(asset)
    save_data(assets_path, assets)
    flash("Arquivo arquivado com sucesso", "success")
    return redirect(url_for("dashboard", tab="assets"))


@app.route("/uploads/journals/<filename>")
@login_required
def download_journal(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER_JOURNALS"], filename)


@app.route("/uploads/assets/<filename>")
@login_required
def download_asset(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER_ASSETS"], filename)


@app.route("/rules", methods=["POST"])
@login_required
def update_rules():
    rules["content"] = request.form.get("content", "")
    rules["updated_at"] = datetime.utcnow().isoformat()
    save_data(rules_path, rules)
    flash("Manual de regras atualizado", "success")
    return redirect(url_for("dashboard", tab="rules"))


@app.route("/announcements", methods=["POST"])
@login_required
def create_announcement():
    announcement = {
        "id": str(uuid.uuid4()),
        "title": request.form.get("title"),
        "body": request.form.get("body"),
        "audience": request.form.get("audience", "todos"),
        "pinned": request.form.get("pinned") == "on",
        "created_at": datetime.utcnow().isoformat(),
    }
    announcements.append(announcement)
    save_data(announcements_path, announcements)
    flash("Mensagem publicada", "success")
    return redirect(url_for("dashboard", tab="announcements"))


@app.route("/announcements/<announcement_id>/remove", methods=["POST"])
@login_required
def remove_announcement(announcement_id):
    global announcements
    announcements = [a for a in announcements if a.get("id") != announcement_id]
    save_data(announcements_path, announcements)
    flash("Mensagem removida", "info")
    return redirect(url_for("dashboard", tab="announcements"))


@app.route("/calendar", methods=["POST"])
@login_required
def add_calendar_event():
    event = {
        "id": str(uuid.uuid4()),
        "title": request.form.get("title"),
        "date": request.form.get("date"),
        "category": request.form.get("category", "geral"),
        "department_id": request.form.get("department_id") or None,
        "description": request.form.get("description"),
    }
    calendar_events.append(event)
    save_data(calendar_path, calendar_events)
    flash("Evento adicionado", "success")
    return redirect(url_for("dashboard", tab="calendar"))


@app.route("/departments", methods=["POST"])
@login_required
def create_department():
    department = {
        "id": str(uuid.uuid4()),
        "name": request.form.get("name"),
        "description": request.form.get("description"),
        "director": request.form.get("director"),
        "join_token": str(uuid.uuid4()),
        "members": [],
        "queue": [],
    }
    departments.append(department)
    save_data(departments_path, departments)
    flash("Departamento criado", "success")
    return redirect(url_for("dashboard", tab="departments"))


@app.route("/departments/<department_id>/queue/<queue_id>/<action>", methods=["POST"])
@login_required
def decide_queue(department_id, queue_id, action):
    department = next((d for d in departments if d.get("id") == department_id), None)
    if not department:
        flash("Departamento não encontrado", "danger")
        return redirect(url_for("dashboard", tab="departments"))

    for request_entry in department.get("queue", []):
        if request_entry.get("id") == queue_id and request_entry.get("status") == "pendente":
            if action == "approve":
                request_entry["status"] = "aprovado"
                request_entry["decided_at"] = datetime.utcnow().isoformat()
                request_entry["decided_by"] = session.get("user")
                department.setdefault("members", []).append(
                    {
                        "name": request_entry.get("name"),
                        "role": request_entry.get("desired_role"),
                        "joined_at": datetime.utcnow().isoformat(),
                    }
                )
            elif action == "reject":
                request_entry["status"] = "rejeitado"
                request_entry["decided_at"] = datetime.utcnow().isoformat()
                request_entry["decided_by"] = session.get("user")
            break

    save_data(departments_path, departments)
    flash("Fila atualizada", "info")
    return redirect(url_for("dashboard", tab="departments"))


@app.route("/departments/<department_id>/members", methods=["POST"])
@login_required
def add_member(department_id):
    department = next((d for d in departments if d.get("id") == department_id), None)
    if not department:
        flash("Departamento não encontrado", "danger")
        return redirect(url_for("dashboard", tab="departments"))

    department.setdefault("members", []).append(
        {
            "name": request.form.get("name"),
            "role": request.form.get("role"),
            "joined_at": datetime.utcnow().isoformat(),
        }
    )
    save_data(departments_path, departments)
    flash("Membro adicionado", "success")
    return redirect(url_for("dashboard", tab="departments"))


@app.route("/departments/apply/<token>", methods=["GET", "POST"])
def apply_department(token):
    department = next((d for d in departments if d.get("join_token") == token), None)
    if not department:
        flash("Link de inscrição inválido", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        request_entry = {
            "id": str(uuid.uuid4()),
            "name": request.form.get("name"),
            "contact": request.form.get("contact"),
            "desired_role": request.form.get("desired_role"),
            "motivation": request.form.get("motivation"),
            "status": "pendente",
            "created_at": datetime.utcnow().isoformat(),
        }
        department.setdefault("queue", []).append(request_entry)
        save_data(departments_path, departments)
        flash("Solicitação registrada! Aguarde o retorno do diretor.", "success")
        return redirect(url_for("apply_department", token=token))

    return render_template("apply_department.html", department=department)


@app.route("/settings", methods=["POST"])
@login_required
def update_settings():
    site_settings["logo_url"] = request.form.get("logo_url", "")
    site_settings["primary_color"] = request.form.get("primary_color", "#0d6efd")
    site_settings["accent_color"] = request.form.get("accent_color", "#6610f2")
    site_settings["tagline"] = request.form.get("tagline", site_settings.get("tagline"))
    save_data(site_settings_path, site_settings)
    flash("Configurações visuais atualizadas", "success")
    return redirect(url_for("dashboard", tab="settings"))


@app.route("/approve/<token>", methods=["GET", "POST"])
def approve_journal(token):
    journal = next((j for j in journals if j.get("approval_token") == token), None)
    if not journal:
        flash("Solicitação não encontrada", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action")
        reason = request.form.get("reason")
        if action == "approve":
            journal["status"] = "aprovado"
            journal["approval_reason"] = None
        elif action == "reject":
            journal["status"] = "rejeitado"
            journal["approval_reason"] = reason or "Sem justificativa"
        save_data(journals_path, journals)
        flash("Avaliação registrada", "success")
        return redirect(url_for("approve_journal", token=token))

    return render_template("approval.html", journal=journal)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.get("port", 5000), debug=True)
