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
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB hard limit to avoid abuse
ALLOWED_JOURNAL_EXTENSIONS = {"pdf"}
ALLOWED_ASSET_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "doc",
    "docx",
    "txt",
    "zip",
    "csv",
    "ppt",
    "pptx",
}


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
            flash("Entre com um usuário habilitado para continuar", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def require_permission(permission):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            user = session.get("user")
            if not user:
                flash("Sessão expirada", "warning")
                return redirect(url_for("login"))
            permissions = user.get("permissions", [])
            if permission not in permissions:
                flash("Você não tem permissão para essa ação", "danger")
                return redirect(url_for("dashboard"))
            return view(**kwargs)

        return wrapped_view

    return decorator


def allowed_file(filename, allowed_extensions):
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in allowed_extensions


config = load_config()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key")
app.config["UPLOAD_FOLDER_JOURNALS"] = os.path.join("uploads", "journals")
app.config["UPLOAD_FOLDER_ASSETS"] = os.path.join("uploads", "assets")
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

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
roles_path = os.path.join("data", "roles.json")
users_path = os.path.join("data", "users.json")
tickets_path = os.path.join("data", "tickets.json")

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
        "onboarding_done": False,
        "widgets": DEFAULT_WIDGETS,
    },
)
site_settings.setdefault("widgets", DEFAULT_WIDGETS)
site_settings.setdefault("onboarding_done", False)


def persist_site_settings_defaults():
    changed = False
    if "widgets" not in site_settings:
        site_settings["widgets"] = DEFAULT_WIDGETS
        changed = True
    if "onboarding_done" not in site_settings:
        site_settings["onboarding_done"] = False
        changed = True
    if changed:
        save_data(site_settings_path, site_settings)


persist_site_settings_defaults()


def normalized_widgets():
    stored_widgets = site_settings.get("widgets") or []
    default_map = {w["id"]: w for w in DEFAULT_WIDGETS}
    normalized = []
    seen_ids = set()
    for widget in stored_widgets:
        widget_id = widget.get("id")
        if not widget_id:
            continue
        merged = {**default_map.get(widget_id, {}), **widget}
        normalized.append(merged)
        seen_ids.add(widget_id)
    for widget in DEFAULT_WIDGETS:
        if widget["id"] not in seen_ids:
            normalized.append(widget)
    site_settings["widgets"] = normalized
    save_data(site_settings_path, site_settings)
    return normalized


def build_widget_cards():
    widgets = normalized_widgets()
    open_tickets = len([t for t in tickets if t.get("status") == "aberto"])
    pending_queue = sum(
        len([req for req in d.get("queue", []) if req.get("status") == "pendente"])
        for d in departments
    )
    active_students = len(students)
    next_event = None
    if calendar_events:
        try:
            next_event = sorted(
                calendar_events, key=lambda e: e.get("date") or "9999-12-31"
            )[0]
        except Exception:
            next_event = None

    widget_cards = []
    for widget in widgets:
        card = {**widget}
        if widget.get("type") == "metric" and widget.get("id") == "students":
            card["value"] = active_students
            card["helper"] = "Acesso ao portal em dia"
        elif widget.get("type") == "metric" and widget.get("id") == "tickets":
            card["value"] = open_tickets
            card["helper"] = "Inclui chamados com status aberto"
        elif widget.get("type") == "metric" and widget.get("id") == "departments":
            card["value"] = pending_queue
            card["helper"] = "Solicitações aguardando decisão"
        elif widget.get("type") == "event":
            if next_event:
                card["value"] = next_event.get("title")
                card["helper"] = f"{next_event.get('date', '')} · {next_event.get('description', '')}".strip()
            else:
                card["value"] = "Sem eventos"
                card["helper"] = "Adicione um evento no calendário"
        widget_cards.append(card)
    return [w for w in widget_cards if w.get("enabled")]
roles = ensure_data_file(
    roles_path,
    [
        {
            "name": "Administrador",
            "description": "Acesso total ao painel e configurações",
            "permissions": [
                "manage_students",
                "manage_journals",
                "manage_assets",
                "manage_rules",
                "manage_announcements",
                "manage_calendar",
                "manage_departments",
                "approve_departments",
                "manage_settings",
                "manage_roles",
                "manage_users",
                "manage_tickets",
            ],
        },
        {
            "name": "Gerente",
            "description": "Cuida de pessoas, calendários e arquivos",
            "permissions": [
                "manage_students",
                "manage_assets",
                "manage_calendar",
                "manage_announcements",
                "manage_departments",
                "manage_tickets",
            ],
        },
        {
            "name": "Diretor de Departamento",
            "description": "Aprova filas e acompanha entregas do time",
            "permissions": [
                "manage_assets",
                "manage_calendar",
                "approve_departments",
                "manage_tickets",
            ],
        },
        {
            "name": "Colaborador",
            "description": "Acesso apenas para consultar materiais",
            "permissions": [],
        },
    ],
)
users = ensure_data_file(users_path, [])
tickets = ensure_data_file(tickets_path, [])

REASONS = [
    "Problema técnico",
    "Solicitação de acesso",
    "Orientação de conteúdo",
    "Conflito de agenda",
    "Outro",
]

DEFAULT_WIDGETS = [
    {
        "id": "welcome",
        "title": "Boas-vindas",
        "enabled": True,
        "type": "text",
        "subtitle": "Orientação rápida",
        "content": "Use as guias para organizar o jornal e mantenha as permissões em dia.",
    },
    {
        "id": "students",
        "title": "Equipe ativa",
        "enabled": True,
        "type": "metric",
        "subtitle": "Fichas cadastradas",
    },
    {
        "id": "tickets",
        "title": "Tickets abertos",
        "enabled": True,
        "type": "metric",
        "subtitle": "Chamados aguardando resposta",
    },
    {
        "id": "agenda",
        "title": "Próximo evento",
        "enabled": True,
        "type": "event",
        "subtitle": "Calendário geral",
    },
    {
        "id": "departments",
        "title": "Filas de departamentos",
        "enabled": True,
        "type": "metric",
        "subtitle": "Pedidos para aprovar",
    },
]

for asset in assets:
    asset.setdefault("scope", "pessoal")
    asset.setdefault("owner", "")
    asset.setdefault("department_id", None)

for role in roles:
    permissions = role.setdefault("permissions", [])
    if role.get("name") in {"Administrador", "Gerente", "Diretor de Departamento"}:
        if "manage_tickets" not in permissions:
            permissions.append("manage_tickets")
save_data(roles_path, roles)

if not departments:
    departments.append(
        {
            "id": str(uuid.uuid4()),
            "name": "Redação",
            "description": "Produção de textos e pautas do jornal",
            "director": "Definir diretor",
            "join_token": str(uuid.uuid4()),
            "members": [],
            "queue": [],
        }
    )
    save_data(departments_path, departments)


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
            ("tickets", "Ajuda"),
            ("settings", "Configuração"),
            ("versions", "Versões"),
        ],
        "site_settings": site_settings,
        "roles": roles,
        "current_user": current_user(),
    }


def find_role(role_name):
    return next((role for role in roles if role.get("name") == role_name), None)


def permissions_for_role(role_name):
    role = find_role(role_name)
    return role.get("permissions", []) if role else []


def all_permissions():
    perm_set = set()
    for role in roles:
        perm_set.update(role.get("permissions", []))
    return sorted(list(perm_set))


def current_username():
    user = session.get("user")
    if isinstance(user, dict):
        return user.get("username")
    return user


def current_user():
    return session.get("user") or {}


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
                admin_perms = permissions_for_role("Administrador") or all_permissions()
                session["user"] = {
                    "username": username,
                    "role": "Administrador",
                    "permissions": admin_perms,
                }
                flash("Login realizado com sucesso", "success")
                return redirect(url_for("dashboard"))

        for user in users:
            if user.get("username") == username and user.get("portal_enabled", True):
                if check_password_hash(user.get("password_hash", ""), password):
                    perms = permissions_for_role(user.get("role"))
                    session["user"] = {
                        "username": username,
                        "role": user.get("role"),
                        "permissions": perms,
                    }
                    flash("Login realizado com sucesso", "success")
                    return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos ou acesso bloqueado", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Sessão encerrada", "info")
    return redirect(url_for("login"))


@app.route("/welcome")
@login_required
@require_permission("manage_settings")
def welcome():
    sorted_departments = sorted(departments, key=lambda d: d.get("name", "").lower())
    sorted_users = sorted(users, key=lambda u: u.get("name", "").lower())
    sorted_roles = sorted(roles, key=lambda r: r.get("name", "").lower())
    return render_template(
        "welcome.html",
        departments=sorted_departments,
        users=sorted_users,
        roles=sorted_roles,
        all_permissions=all_permissions(),
    )


@app.route("/welcome/complete", methods=["POST"])
@login_required
@require_permission("manage_settings")
def complete_onboarding():
    if not departments or not users:
        flash("Crie ao menos um departamento e um usuário para finalizar", "warning")
        return redirect(url_for("welcome"))
    site_settings["onboarding_done"] = True
    save_data(site_settings_path, site_settings)
    flash("Configuração inicial concluída!", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    if not site_settings.get("onboarding_done"):
        return redirect(url_for("welcome"))

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
    sorted_users = sorted(users, key=lambda u: u.get("name", "").lower())
    sorted_roles = sorted(roles, key=lambda r: r.get("name", "").lower())
    user = current_user()
    if "manage_tickets" in user.get("permissions", []):
        visible_tickets = sorted(
            tickets, key=lambda t: t.get("created_at", ""), reverse=True
        )
    else:
        visible_tickets = sorted(
            [t for t in tickets if t.get("created_by") == current_username()],
            key=lambda t: t.get("created_at", ""),
            reverse=True,
        )
    widget_cards = build_widget_cards()
    widget_config = normalized_widgets()
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
        users=sorted_users,
        roles=sorted_roles,
        all_permissions=all_permissions(),
        tickets=visible_tickets,
        reasons=REASONS,
        widget_cards=widget_cards,
        widget_config=widget_config,
    )


@app.route("/students", methods=["POST"])
@login_required
@require_permission("manage_students")
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
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="students")
    return redirect(destination)


@app.route("/students/<student_id>/toggle", methods=["POST"])
@login_required
@require_permission("manage_students")
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
@require_permission("manage_journals")
def create_journal():
    file = request.files.get("file")
    filename = None
    if file and file.filename:
        if not allowed_file(file.filename, ALLOWED_JOURNAL_EXTENSIONS):
            flash("Formato não permitido. Envie apenas PDF.", "danger")
            return redirect(url_for("dashboard", tab="journals"))
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
@require_permission("manage_assets")
def upload_asset():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Selecione um arquivo para enviar", "warning")
        return redirect(url_for("dashboard", tab="assets"))

    if not allowed_file(file.filename, ALLOWED_ASSET_EXTENSIONS):
        flash("Formato de arquivo não permitido", "danger")
        return redirect(url_for("dashboard", tab="assets"))

    filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
    destination = os.path.join(app.config["UPLOAD_FOLDER_ASSETS"], filename)
    file.save(destination)

    asset = {
        "id": str(uuid.uuid4()),
        "original_name": file.filename,
        "stored_name": filename,
        "notes": request.form.get("notes"),
        "owner": request.form.get("owner") or current_username(),
        "department_id": request.form.get("department_id") or None,
        "scope": "departamento" if request.form.get("department_id") else "pessoal",
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    assets.append(asset)
    save_data(assets_path, assets)
    flash("Arquivo arquivado com sucesso", "success")
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="assets")
    return redirect(destination)


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
@require_permission("manage_rules")
def update_rules():
    rules["content"] = request.form.get("content", "")
    rules["updated_at"] = datetime.utcnow().isoformat()
    save_data(rules_path, rules)
    flash("Manual de regras atualizado", "success")
    return redirect(url_for("dashboard", tab="rules"))


@app.route("/announcements", methods=["POST"])
@login_required
@require_permission("manage_announcements")
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
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="announcements")
    return redirect(destination)


@app.route("/announcements/<announcement_id>/remove", methods=["POST"])
@login_required
@require_permission("manage_announcements")
def remove_announcement(announcement_id):
    global announcements
    announcements = [a for a in announcements if a.get("id") != announcement_id]
    save_data(announcements_path, announcements)
    flash("Mensagem removida", "info")
    return redirect(url_for("dashboard", tab="announcements"))


@app.route("/calendar", methods=["POST"])
@login_required
@require_permission("manage_calendar")
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
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="calendar")
    return redirect(destination)


@app.route("/tickets", methods=["POST"])
@login_required
def create_ticket():
    reason = request.form.get("reason") or "Outro"
    custom_reason = request.form.get("custom_reason")
    ticket = {
        "id": str(uuid.uuid4()),
        "title": request.form.get("title"),
        "reason": custom_reason if reason == "Outro" else reason,
        "urgency": request.form.get("urgency", "normal"),
        "status": "aberto",
        "created_by": current_username(),
        "created_role": current_user().get("role"),
        "messages": [
            {
                "author": current_username(),
                "role": current_user().get("role"),
                "body": request.form.get("message"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
        "created_at": datetime.utcnow().isoformat(),
    }
    tickets.append(ticket)
    save_data(tickets_path, tickets)
    flash("Ticket criado e enviado para a diretoria", "success")
    return redirect(url_for("dashboard", tab="tickets"))


@app.route("/tickets/<ticket_id>/reply", methods=["POST"])
@login_required
def reply_ticket(ticket_id):
    ticket = next((t for t in tickets if t.get("id") == ticket_id), None)
    if not ticket:
        flash("Ticket não encontrado", "danger")
        return redirect(url_for("dashboard", tab="tickets"))

    user = current_user()
    permissions = user.get("permissions", [])
    if ticket.get("created_by") != current_username() and "manage_tickets" not in permissions:
        flash("Você não pode interagir com este ticket", "danger")
        return redirect(url_for("dashboard", tab="tickets"))

    ticket.setdefault("messages", []).append(
        {
            "author": current_username(),
            "role": user.get("role"),
            "body": request.form.get("message"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    if ticket.get("status") == "fechado" and "manage_tickets" in permissions:
        ticket["status"] = "aberto"
    save_data(tickets_path, tickets)
    flash("Resposta enviada", "success")
    return redirect(url_for("dashboard", tab="tickets"))


@app.route("/tickets/<ticket_id>/close", methods=["POST"])
@login_required
@require_permission("manage_tickets")
def close_ticket(ticket_id):
    ticket = next((t for t in tickets if t.get("id") == ticket_id), None)
    if not ticket:
        flash("Ticket não encontrado", "danger")
        return redirect(url_for("dashboard", tab="tickets"))
    ticket["status"] = "fechado"
    ticket.setdefault("messages", []).append(
        {
            "author": current_username(),
            "role": current_user().get("role"),
            "body": request.form.get("message") or "Ticket fechado",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    save_data(tickets_path, tickets)
    flash("Ticket encerrado", "info")
    return redirect(url_for("dashboard", tab="tickets"))


@app.route("/tickets/<ticket_id>/delete", methods=["POST"])
@login_required
@require_permission("manage_tickets")
def delete_ticket(ticket_id):
    global tickets
    tickets = [t for t in tickets if t.get("id") != ticket_id]
    save_data(tickets_path, tickets)
    flash("Ticket removido", "info")
    return redirect(url_for("dashboard", tab="tickets"))


@app.route("/departments", methods=["POST"])
@login_required
@require_permission("manage_departments")
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
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="departments")
    return redirect(destination)


@app.route("/departments/<department_id>/queue/<queue_id>/<action>", methods=["POST"])
@login_required
@require_permission("approve_departments")
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
                request_entry["decided_by"] = current_username()
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
                request_entry["decided_by"] = current_username()
            break

    save_data(departments_path, departments)
    flash("Fila atualizada", "info")
    return redirect(url_for("dashboard", tab="departments"))


@app.route("/departments/<department_id>/members", methods=["POST"])
@login_required
@require_permission("manage_departments")
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


@app.route("/roles", methods=["POST"])
@login_required
@require_permission("manage_roles")
def create_role():
    role = {
        "name": request.form.get("name"),
        "description": request.form.get("description"),
        "permissions": request.form.getlist("permissions"),
    }
    existing = find_role(role.get("name"))
    if existing:
        flash("Já existe um cargo com esse nome", "warning")
        return redirect(url_for("dashboard", tab="settings"))
    roles.append(role)
    save_data(roles_path, roles)
    flash("Cargo criado", "success")
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="settings")
    return redirect(destination)


@app.route("/users", methods=["POST"])
@login_required
@require_permission("manage_users")
def create_user():
    username = request.form.get("username")
    if any(u.get("username") == username for u in users):
        flash("Usuário já existe", "warning")
        return redirect(url_for("dashboard", tab="settings"))
    password = request.form.get("password")
    user = {
        "id": str(uuid.uuid4()),
        "name": request.form.get("name"),
        "username": username,
        "role": request.form.get("role"),
        "password_hash": generate_password_hash(password),
        "portal_enabled": request.form.get("portal_enabled") == "on",
        "created_at": datetime.utcnow().isoformat(),
    }
    users.append(user)
    save_data(users_path, users)
    flash("Usuário criado com sucesso", "success")
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="settings")
    return redirect(destination)


@app.route("/users/<user_id>/role", methods=["POST"])
@login_required
@require_permission("manage_roles")
def update_user_role(user_id):
    target_role = request.form.get("role")
    user = next((u for u in users if u.get("id") == user_id), None)
    if not user:
        flash("Usuário não encontrado", "danger")
        return redirect(url_for("dashboard", tab="settings"))
    if not find_role(target_role):
        flash("Cargo inválido", "danger")
        return redirect(url_for("dashboard", tab="settings"))
    user["role"] = target_role
    save_data(users_path, users)
    flash("Permissões atualizadas", "success")
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="settings")
    return redirect(destination)


@app.route("/users/<user_id>/toggle", methods=["POST"])
@login_required
@require_permission("manage_users")
def toggle_user_access(user_id):
    user = next((u for u in users if u.get("id") == user_id), None)
    if not user:
        flash("Usuário não encontrado", "danger")
        return redirect(url_for("dashboard", tab="settings"))
    user["portal_enabled"] = not user.get("portal_enabled", True)
    save_data(users_path, users)
    flash("Acesso atualizado", "info")
    destination = request.form.get("redirect_to") or url_for("dashboard", tab="settings")
    return redirect(destination)


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
@require_permission("manage_settings")
def update_settings():
    site_settings["logo_url"] = request.form.get("logo_url", "")
    site_settings["primary_color"] = request.form.get("primary_color", "#0d6efd")
    site_settings["accent_color"] = request.form.get("accent_color", "#6610f2")
    site_settings["tagline"] = request.form.get("tagline", site_settings.get("tagline"))
    save_data(site_settings_path, site_settings)
    flash("Configurações visuais atualizadas", "success")
    return redirect(url_for("dashboard", tab="settings"))


@app.route("/settings/widgets", methods=["POST"])
@login_required
@require_permission("manage_settings")
def update_dashboard_widgets():
    widgets = normalized_widgets()
    updated = []
    for widget in widgets:
        widget_id = widget.get("id")
        widget["enabled"] = request.form.get(f"enabled_{widget_id}") == "on"
        widget["title"] = request.form.get(f"title_{widget_id}") or widget.get("title")
        widget["subtitle"] = request.form.get(f"subtitle_{widget_id}") or widget.get(
            "subtitle"
        )
        updated.append(widget)
    site_settings["widgets"] = updated
    save_data(site_settings_path, site_settings)
    flash("Widgets atualizados com sucesso", "success")
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
    app.run(
        host="0.0.0.0",
        port=config.get("port", 5000),
        debug=bool(config.get("debug", False)),
    )
