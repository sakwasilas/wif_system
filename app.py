# ==================== STANDARD LIBRARY ====================
import os
import io
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.exc import IntegrityError

from sqlalchemy import func, case  

# ==================== FLASK ====================
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_apscheduler import APScheduler
# ==================== MIKROTIK HELPER ====================
from mikrotik_helper import block_ip, unblock_ip, get_mikrotik_connection


# ==================== THIRD-PARTY ====================
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from sqlalchemy.orm import joinedload

# ==================== LOCAL MODULES ====================
from connections import SessionLocal
from models import User, Customer, CustomerNetwork, Branch, Router

# ==================== FLASK APP ====================
app = Flask(__name__)
app.secret_key = "123456123456silas123456"

@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()

scheduler = APScheduler()

# APScheduler config (safe defaults)
app.config["SCHEDULER_API_ENABLED"] = False
app.config["SCHEDULER_TIMEZONE"] = "Africa/Nairobi"

scheduler.init_app(app)

# ==================== LOGIN / LOGOUT ====================
from functools import wraps
#======          ==============   =====================

#=================run app sheduler======================

#===========login decorator==========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

#==================role based decorator===============
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))

            if session.get("role") not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("admin_dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
#================get db context manager=========================
from contextlib import contextmanager

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def popup_due(last_shown, today):
    return (last_shown is None) or (last_shown != today)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as db:
            user = db.query(User).filter_by(username=username).first()

            # Super admin hardcoded
            if username == "admin" and password == "admin123":
                session['user_id'] = "super_admin"
                session['username'] = "admin"
                session['role'] = "super_admin"
                flash("Welcome Super Admin", "success")
                return redirect(url_for("admin_dashboard"))

            # Regular admin
            if user and check_password_hash(user.password, password):
                if user.role != "super_admin" and not user.is_active:
                    flash("Your account is pending approval. Please contact the admin.", "warning")
                    return redirect(url_for("login"))

                if user.role not in ["admin", "super_admin"]:
                    flash("Access denied. You are not an admin.", "danger")
                    return redirect(url_for("login"))

                # Explicit session assignments
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                flash("Welcome", "success")
                return redirect(url_for("admin_dashboard"))

            flash("Invalid username or password", "danger")

    return render_template("login.html")


@app.route("/logout")

def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

# ==================== ADMIN DASHBOARD ====================
@app.route("/admin_dashboard")
@login_required
@roles_required("admin", "super_admin")
def admin_dashboard():
    db = SessionLocal()
    try:
        # Customer stats
        total_users = db.query(Customer).count()
        active_users = db.query(Customer).filter_by(status="active").count()
        grace_users = db.query(Customer).filter_by(status="grace").count()
        suspended_users = db.query(Customer).filter_by(status="suspended").count()
        pending_router_users = db.query(Customer).filter_by(status="pending_router").count()  # ✅ NEW

        # Get all branches and routers for dropdowns
        branches = db.query(Branch).all()
        routers = db.query(Router).all()

        return render_template(
            "admin/admin_dashboard.html",
            username=session.get("username"),
            role=session.get("role"),
            total_users=total_users,
            active_users=active_users,
            grace_users=grace_users,
            suspended_users=suspended_users,
            pending_router_users=pending_router_users,  # ✅ NEW
            branches=branches,
            routers=routers,
            datetime=datetime
        )
    finally:
        db.close()



# ==================== USER MANAGEMENT ====================
@app.route("/manage_users")
@login_required
@roles_required("admin", "super_admin")
def manage_users():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        users = db.query(User).all()
    finally:
        db.close()
    return render_template("admin/manage_user.html", users=users)

@app.route("/pending_users")
@login_required
@roles_required("admin", "super_admin")
def pending_users():

    db = SessionLocal()
    try:
        users = db.query(User).filter_by(is_active=False, role="admin").all()
    finally:
        db.close()
    return render_template("admin/pending_users.html", users=users)

@app.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def delete_user(user_id):
    db = SessionLocal()
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("pending_users"))
    db.delete(user)
    db.commit()
    flash(f"User '{user.username}' has been rejected and removed.", "success")
    return redirect(url_for("pending_users"))

@app.route("/toggle_user/<int:user_id>", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def toggle_user(user_id):
    
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.is_active = not user.is_active
            db.commit()
            flash(f"User '{user.username}' status updated.", "success")
        else:
            flash("User not found.", "danger")
    finally:
        db.close()
    return redirect(url_for("manage_users"))

@app.route("/register", methods=["GET", "POST"])

def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required", "warning")
            return redirect(url_for("register"))

        db = SessionLocal()
        try:
            existing = db.query(User).filter_by(username=username).first()
            if existing:
                flash("Username already taken", "danger")
                return redirect(url_for("register"))

            new_user = User(
                username=username,
                password=generate_password_hash(password),
                role="admin",
                is_active=False
            )
            db.add(new_user)
            db.commit()
            flash("Registration submitted. Wait for super admin approval.", "info")
            return redirect(url_for("login"))
        finally:
            db.close()
    return render_template("register.html")

# ==================== ADD BRANCH ====================
@app.route("/add_branch", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def add_branch():
    with get_db() as db:
        if request.method == "POST":
            branch_name = request.form.get("name", "").strip()
            if not branch_name:
                flash("Branch name cannot be empty", "warning")
                return redirect(url_for("add_branch"))

            # Check for duplicate
            existing = db.query(Branch).filter_by(name=branch_name).first()
            if existing:
                flash("Branch already exists", "danger")
                return redirect(url_for("add_branch"))

            new_branch = Branch(name=branch_name)
            db.add(new_branch)
            db.commit()
            flash(f"Branch '{branch_name}' added successfully!", "success")
            return redirect(url_for("list_branches"))

        return render_template("admin/add_branch.html")



#---------------------------------------------------------------------------
@app.route("/edit_branch/<int:branch_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def edit_branch(branch_id):
    with get_db() as db:
        branch = db.query(Branch).filter_by(id=branch_id).first()
        if not branch:
            flash("Branch not found", "danger")
            return redirect(url_for("list_branches"))

        if request.method == "POST":
            branch.name = request.form.get("name", "").strip()
            db.commit()
            flash("Branch updated successfully", "success")
            return redirect(url_for("list_branches"))

        return render_template("admin/edit_branch.html", branch=branch)

#-------------------------------------------------------------------------------------
@app.route("/delete_branch/<int:branch_id>", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def delete_branch(branch_id):
    with get_db() as db:
        branch = db.query(Branch).filter_by(id=branch_id).first()
        if branch:
            db.delete(branch)
            db.commit()
            flash("Branch deleted successfully", "success")
        else:
            flash("Branch not found", "danger")
    return redirect(url_for("list_branches"))

@app.route('/branches')
@login_required
def list_branches():
    # Use a session to query the database
    with get_db() as db:  # assuming get_db() returns a SQLAlchemy session
        branches = db.query(Branch).all()
    return render_template('admin/list_branches.html', branches=branches)




#=======================router management==========================
@app.route("/add_router", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def add_router():
    with get_db() as db:
        branches = db.query(Branch).all()

        if request.method == "POST":
            ip_address = request.form.get("ip_address", "").strip()
            description = request.form.get("description", "").strip()
            branch_id = request.form.get("branch_id")
            username = request.form.get("username", "").strip() or "admin"
            password = request.form.get("password", "").strip()
            port = int(request.form.get("port") or 8728)

            if db.query(Router).filter_by(ip_address=ip_address).first():
                flash("Router IP already exists!", "danger")
                return redirect(url_for("add_router"))

            router = Router(
                ip_address=ip_address,
                description=description,
                branch_id=branch_id,
                username=username,
                password=password,
                port=port
            )
            db.add(router)
            db.commit()
            flash("Router added successfully!", "success")
            return redirect(url_for("add_router"))

        return render_template("admin/add_router.html", branches=branches)

#==================list router===============================
@app.route("/routers")
@login_required
@roles_required("admin", "super_admin")
def list_routers():
    with get_db() as db:
        routers = db.query(Router).options(joinedload(Router.branch)).all()
    return render_template("admin/list_routers.html", routers=routers)

#---------------------list branch 
@app.route("/branch/<int:branch_id>/customers")
@login_required
@roles_required("admin", "super_admin")
def customers_by_branch(branch_id):
    with get_db() as db:
        branch = db.query(Branch).filter_by(id=branch_id).first()
        if not branch:
            flash("Branch not found", "danger")
            return redirect(url_for("list_branches"))

        customers = (
            db.query(Customer)
            .join(Customer.router)
            .filter(Router.branch_id == branch_id)
            .options(
                joinedload(Customer.network),
                joinedload(Customer.router).joinedload(Router.branch)
            )
            .all()
        )

    return render_template(
        "admin/customer_table.html",
        branch=branch,
        customers=customers
    )


# ------------------ EDIT ROUTER ------------------
@app.route("/edit_router/<int:router_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def edit_router(router_id):
    with get_db() as db:
        router = db.query(Router).filter_by(id=router_id).first()
        branches = db.query(Branch).all()

        if not router:
            flash("Router not found", "danger")
            return redirect(url_for("list_routers"))

        if request.method == "POST":
            router.ip_address = request.form.get("ip_address", "").strip()
            router.description = request.form.get("description", "").strip()
            router.branch_id = request.form.get("branch_id")
            router.username = request.form.get("username", "").strip()
            router.password = request.form.get("password", "").strip()
            router.port = int(request.form.get("port") or 8728)
            db.commit()
            flash("Router updated successfully", "success")
            return redirect(url_for("list_routers"))

        return render_template("admin/edit_router.html", router=router, branches=branches)


# ------------------ DELETE ROUTER ------------------
@app.route("/delete_router/<int:router_id>", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def delete_router(router_id):
    with get_db() as db:
        router = db.query(Router).filter_by(id=router_id).first()
        if router:
            db.delete(router)
            db.commit()
            flash("Router deleted successfully", "success")
        else:
            flash("Router not found", "danger")
    return redirect(url_for("list_routers"))

# ================== FETCH ROUTER IP BY BRANCH ==================
from flask import jsonify

@app.route("/get_router_ip/<int:branch_id>")
@login_required
@roles_required("admin", "super_admin")
def get_router_ip(branch_id):
    """
    Returns all routers for a given branch as JSON.
    Format: [{id: router_id, ip_address: 'IP', description: 'desc'}, ...]
    """
    with get_db() as db:
        routers = db.query(Router).filter(Router.branch_id == branch_id).all()
        router_list = [
            {
                "id": r.id,
                "ip_address": r.ip_address,
                "description": r.description or ""
            }
            for r in routers
        ]
        return jsonify(router_list)


# ==================== TEST ROUTER CONNECTION ====================
@app.route("/test_router/<int:router_id>", methods=["GET"])
@login_required
@roles_required("admin", "super_admin")
def test_router(router_id):
    """Test if a router connection works and basic commands run."""
    db = SessionLocal()
    try:
        router = db.query(Router).filter_by(id=router_id).first()
        if not router:
            flash("Router not found.", "danger")
            return redirect(url_for("list_routers"))

        api = get_mikrotik_connection(router.ip_address, router.username, router.password, router.port)
        if not api:
            flash(f"❌ Failed to connect to router {router.ip_address}. Check credentials or API service.", "danger")
            return redirect(url_for("list_routers"))

        # ✅ Try a simple MikroTik command
        interfaces = list(api(cmd="/interface/print"))
        if interfaces:
            flash(f"✅ Connected successfully to router {router.ip_address}. Found {len(interfaces)} interfaces.", "success")
        else:
            flash(f"✅ Connected to router {router.ip_address}, but no interfaces found.", "warning")

    except Exception as e:
        flash(f"❌ Error testing router: {e}", "danger")
    finally:
        db.close()

    return redirect(url_for("list_routers"))


def to_str(val):
    """Convert value to string or None if empty."""
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return None
    return str(val).strip()

def to_float(val):
    """Convert value to float or None if empty."""
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None

@app.route("/import_customers", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def import_customers():
    file = request.files.get("excel_file")
    if not file:
        flash("No Excel file uploaded", "danger")
        return redirect(url_for("admin_dashboard"))

    df = pd.read_excel(file)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    required_columns = [
        "account_no", "customer_name", "phone", "ip_address",
        "billing_amount", "start_date", "branch_name", "router_ip"
    ]

    missing_cols = [c for c in required_columns if c not in df.columns]
    if missing_cols:
        flash(f"Missing columns: {', '.join(missing_cols)}", "danger")
        return redirect(url_for("admin_dashboard"))

    db = SessionLocal()
    success = 0
    errors = []

    try:
        for index, row in df.iterrows():
            row_no = index + 2  # Excel row number

            if row.isnull().all():
                continue

            # ----------------- Branch -----------------
            branch_name = to_str(row.get("branch_name"))
            if not branch_name:
                errors.append(f"Row {row_no}: Missing branch_name")
                continue

            branch = db.query(Branch).filter(Branch.name.ilike(branch_name)).first()
            if not branch:
                branch = Branch(name=branch_name)
                db.add(branch)
                db.flush()

            # ----------------- Router (OPTIONAL) -----------------
            router_ip = to_str(row.get("router_ip"))
            router = None

            if router_ip:
                router = db.query(Router).filter_by(ip_address=router_ip).first()
                if not router:
                    # Do NOT create router here
                    errors.append(
                        f"Row {row_no}: Router '{router_ip}' not found. Customer imported WITHOUT router (assign later)."
                    )
                    router = None
                else:
                    # Optional: if router exists but belongs to different branch, warn and ignore router
                    if router.branch_id != branch.id:
                        errors.append(
                            f"Row {row_no}: Router '{router_ip}' is not under branch '{branch_name}'. "
                            f"Customer imported WITHOUT router (fix router branch or Excel)."
                        )
                        router = None

            # ----------------- Customer IP (recommended required) -----------------
            customer_ip = to_str(row.get("ip_address"))
            if not customer_ip:
                errors.append(f"Row {row_no}: Missing customer ip_address")
                continue

            # ----------------- Create Customer -----------------
            customer = Customer(
                account_no=to_str(row.get("account_no")),
                name=to_str(row.get("customer_name")),
                phone=to_str(row.get("phone")),
                fat_id=to_str(row.get("fat_id")),
                ip_address=customer_ip,
                location=to_str(row.get("location")),
                billing_amount=to_float(row.get("billing_amount")),
                start_date=to_datetime(row.get("start_date")),
                contract_date=to_datetime(row.get("contract_date")),
                # If router is missing, mark as pending_router (you can rename if you want)
                status="active" if router else "pending_router",
                router_id=router.id if router else None
            )

            db.add(customer)
            db.flush()

            # ----------------- Customer Network (optional) -----------------
            network = CustomerNetwork(
                customer_id=customer.id,
                cable_no=to_str(row.get("cable_no")),
                cable_type=to_str(row.get("cable_type")),
                splitter=to_str(row.get("splitter")),
                tube_no=to_str(row.get("tube_no")),
                core_used=to_str(row.get("core_used")),
                loop_no=to_str(row.get("loop_no")),
                power_level=to_str(row.get("power_level")),
                final_coordinates=to_str(row.get("final_coordinates")),
                coordinates=to_str(row.get("coordinates"))
            )
            db.add(network)

            success += 1

        db.commit()
        flash(f"{success} customers imported successfully", "success")

        if errors:
            # Avoid too long flash; but keep it for now
            flash("Some rows had issues: " + " | ".join(errors), "warning")

    except IntegrityError:
        db.rollback()
        flash("Database error: possible duplicate Account No", "danger")

    except Exception as e:
        db.rollback()
        flash(f"Error importing Excel: {str(e)}", "danger")

    finally:
        db.close()

    return redirect(url_for("admin_dashboard"))



def to_datetime(val, fmt="%Y-%m-%d"):
    """Convert a string or pandas datetime to Python datetime or None if empty."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str == "":
        return None
    if isinstance(val, datetime):
        return val
    # Try to parse string to datetime
    try:
        return datetime.strptime(val_str, fmt)
    except ValueError:
        return None






# ==================== CUSTOMER MANAGEMENT ====================
@app.route("/add_customer", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def add_customer():
    with get_db() as db:
        branches = db.query(Branch).all()
        routers = []

        if branches:
            routers = db.query(Router).filter(
                Router.branch_id == branches[0].id
            ).all()

        if request.method == "POST":
            router_id = request.form.get("router_id")
            router_id = int(router_id) if router_id else None

            customer = Customer(
                account_no=to_str(request.form.get("account_no")),
                name=to_str(request.form.get("name")),
                phone=to_str(request.form.get("phone")),
                fat_id=to_str(request.form.get("fat_id")),
                location=to_str(request.form.get("location")),
                ip_address=to_str(request.form.get("ip_address")),
                billing_amount=to_float(request.form.get("billing_amount")),
                start_date=to_datetime(request.form.get("start_date")),
                contract_date=to_datetime(request.form.get("contract_date")),
                status="active",
                router_id=router_id
            )

            db.add(customer)
            db.commit()
            db.refresh(customer)

            network = CustomerNetwork(
                customer_id=customer.id,
                cable_no=to_str(request.form.get("cable_no")),
                cable_type=to_str(request.form.get("cable_type")),
                splitter=to_str(request.form.get("splitter")),
                tube_no=to_str(request.form.get("tube_no")),
                core_used=to_str(request.form.get("core_used")),
                final_coordinates=to_str(request.form.get("final_coordinates")),
                loop_no=to_str(request.form.get("loop_no")),
                power_level=to_str(request.form.get("power_level")),
                coordinates=to_str(request.form.get("coordinates")),
            )

            db.add(network)
            db.commit()

            flash("✅ Customer added successfully", "success")
            return redirect(url_for("list_customers"))

        return render_template(
            "admin/add_new_customer.html",
            branches=branches,
            routers=routers
        )


# ==================== LIST / EDIT / DELETE CUSTOMERS ====================
# @app.route("/customers")
# @login_required
# @roles_required("admin", "super_admin")
# def list_customers():
#     search_term = request.args.get("search", "").strip()
#     status_filter = request.args.get("status", "").strip()  # ✅ NEW
#     page = int(request.args.get("page", 1))
#     per_page = 2000

#     with get_db() as db:
#         query = db.query(Customer).options(
#             joinedload(Customer.network),
#             joinedload(Customer.router).joinedload(Router.branch)
#         )

#         # ✅ Search filter
#         if search_term:
#             query = query.filter(
#                 (Customer.account_no.ilike(f"%{search_term}%")) |
#                 (Customer.name.ilike(f"%{search_term}%")) |
#                 (Customer.ip_address.ilike(f"%{search_term}%"))
#             )

#         # ✅ Status filter (pending_router, active, grace, suspended, etc.)
#         if status_filter:
#             query = query.filter(Customer.status == status_filter)

#         total = query.count()
#         customers = query.offset((page - 1) * per_page).limit(per_page).all()
#         has_next = total > page * per_page

#     return render_template(
#         "admin/list_customer.html",
#         customers=customers,
#         page=page,
#         per_page=per_page,
#         total=total,
#         has_next=has_next,
#         search_term=search_term,
#         status_filter=status_filter  # ✅ optional for UI highlighting
#     )

@app.route("/customers")
@login_required
@roles_required("admin", "super_admin")
def list_customers():
    search_term = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 2000

    with get_db() as db:
        # ✅ needed by the template
        branches = db.query(Branch).order_by(Branch.name.asc()).all()
        routers = db.query(Router).options(joinedload(Router.branch)).order_by(Router.ip_address.asc()).all()

        query = db.query(Customer).options(
            joinedload(Customer.network),
            joinedload(Customer.router).joinedload(Router.branch)
        )

        if search_term:
            query = query.filter(
                (Customer.account_no.ilike(f"%{search_term}%")) |
                (Customer.name.ilike(f"%{search_term}%")) |
                (Customer.ip_address.ilike(f"%{search_term}%"))
            )

        if status_filter:
            query = query.filter(Customer.status == status_filter)

        total = query.count()
        customers = query.offset((page - 1) * per_page).limit(per_page).all()
        has_next = total > page * per_page

    return render_template(
        "admin/list_customer.html",
        customers=customers,
        branches=branches,   # ✅ NEW
        routers=routers,     # ✅ NEW
        page=page,
        per_page=per_page,
        total=total,
        has_next=has_next,
        search_term=search_term,
        status_filter=status_filter
    )

@app.route("/customers/quick_add_branch", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def quick_add_branch():
    name = (request.form.get("name") or "").strip()

    if not name:
        flash("Branch name cannot be empty", "warning")
        return redirect(url_for("list_customers"))

    with get_db() as db:
        existing = db.query(Branch).filter(Branch.name.ilike(name)).first()
        if existing:
            flash("Branch already exists", "warning")
            return redirect(url_for("list_customers"))

        db.add(Branch(name=name))
        db.commit()

    flash(f"✅ Branch '{name}' added", "success")
    return redirect(url_for("list_customers"))


@app.route("/customers/quick_add_router", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def quick_add_router():
    ip = (request.form.get("ip_address") or "").strip()
    branch_id = request.form.get("branch_id")
    description = (request.form.get("description") or "").strip()
    username = (request.form.get("username") or "admin").strip()
    password = (request.form.get("password") or "").strip()
    port = int(request.form.get("port") or 8728)

    if not ip or not branch_id or not password:
        flash("Router IP, Branch and Password are required", "warning")
        return redirect(url_for("list_customers"))

    with get_db() as db:
        if db.query(Router).filter_by(ip_address=ip).first():
            flash("Router IP already exists!", "danger")
            return redirect(url_for("list_customers"))

        branch = db.query(Branch).filter_by(id=int(branch_id)).first()
        if not branch:
            flash("Selected branch not found", "danger")
            return redirect(url_for("list_customers"))

        db.add(Router(
            ip_address=ip,
            description=description,
            branch_id=int(branch_id),
            username=username,
            password=password,
            port=port
        ))
        db.commit()

    flash(f"✅ Router '{ip}' added", "success")
    return redirect(url_for("list_customers"))


@app.route("/customers/<int:customer_id>/assign_router", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def assign_router(customer_id):
    router_id = request.form.get("router_id")
    router_id = int(router_id) if router_id else None

    with get_db() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            flash("Customer not found", "danger")
            return redirect(url_for("list_customers"))

        customer.router_id = router_id

        # ✅ optional: if was pending_router, activate once router assigned
        if router_id and customer.status == "pending_router":
            customer.status = "active"

        db.commit()

    flash("✅ Router assigned", "success")
    return redirect(url_for("list_customers"))




@app.route("/edit_customer/<int:customer_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def edit_customer(customer_id):
    with get_db() as db:
        customer = db.query(Customer).options(
            joinedload(Customer.router).joinedload(Router.branch),
            joinedload(Customer.network)
        ).filter(Customer.id == customer_id).first()

        if not customer:
            flash("Customer not found", "danger")
            return redirect(url_for("list_customers"))

        branches = db.query(Branch).all()

        # ✅ Selected branch is determined by customer's router -> branch
        selected_branch_id = (
            customer.router.branch.id
            if customer.router and customer.router.branch
            else None
        )

        # ✅ Load routers ONLY for that branch
        routers = []
        if selected_branch_id:
            routers = db.query(Router).filter(Router.branch_id == selected_branch_id).all()

        if request.method == "POST":
            # Keep old router id for comparison
            old_router_id = customer.router_id

            # ----------------- Customer fields -----------------
            customer.account_no = to_str(request.form.get("account_no"))
            customer.name = request.form.get("name")
            customer.phone = request.form.get("phone")
            customer.fat_id = request.form.get("fat_id")
            customer.location = request.form.get("location")
            customer.ip_address = request.form.get("ip_address")
            customer.billing_amount = to_float(request.form.get("billing_amount"))
            customer.start_date = to_datetime(request.form.get("start_date"))
            customer.contract_date = to_datetime(request.form.get("contract_date"))

            

            # ✅ Assign router (router determines branch)
            selected_router_id = request.form.get("router_id")
            customer.router_id = int(selected_router_id) if selected_router_id else None

            # ----------------- Network fields -----------------
            network = customer.network or CustomerNetwork(customer_id=customer.id)
            network.cable_no = request.form.get("cable_no")
            network.cable_type = request.form.get("cable_type")
            network.splitter = request.form.get("splitter")
            network.tube_no = request.form.get("tube_no")
            network.core_used = request.form.get("core_used")
            network.final_coordinates = request.form.get("final_coordinates")
            network.loop_no = request.form.get("loop_no")
            network.power_level = request.form.get("power_level")
            network.coordinates = request.form.get("coordinates")
            customer.network = network

            db.add(customer)
            db.commit()

            # ✅ Apply MikroTik immediately (only if router exists + IP exists)
            # IMPORTANT: Don't rely on customer.router after changing router_id; query it fresh
            router = db.query(Router).filter_by(id=customer.router_id).first() if customer.router_id else None

            if router and customer.ip_address:
                try:
                    # If customer is in any blocked-like state -> block
                    if customer.status in ["suspended", "manually_suspended", "on_hold"]:
                        block_ip(customer.ip_address, router)
                    else:
                        # active/grace/pending_router/anything else -> unblock to ensure access
                        unblock_ip(customer.ip_address, router)

                except Exception as e:
                    flash(f"⚠️ Customer saved but MikroTik action failed: {e}", "warning")

            # Optional info message if router not assigned
            if customer.router_id is None:
                flash("ℹ️ Customer updated. Router not assigned yet, so WiFi control is disabled.", "info")
            else:
                flash("✅ Customer updated successfully!", "success")

            return redirect(url_for("list_customers"))

        return render_template(
            "admin/edit_customer.html",
            customer=customer,
            branches=branches,
            routers=routers,
            selected_branch_id=selected_branch_id,
            selected_router_id=customer.router_id,
            network=customer.network
        )



@app.route("/delete_customer/<int:customer_id>", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def delete_customer(customer_id):
    with get_db() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if customer:
            db.delete(customer)
            db.commit()
            flash("✅ Customer deleted successfully!", "success")
        else:
            flash("❌ Customer not found", "danger")
    return redirect(url_for("list_customers"))



@app.route('/admin/monthly_report')
def monthly_report():
    session = SessionLocal()

    try:
        # Query monthly stats
        monthly_data = session.query(
            func.date_format(Customer.start_date, '%Y-%m').label('month'),
            func.sum(case([(Customer.status=='active', 1)], else_=0)).label('active_clients'),
            func.sum(case([(Customer.status=='grace', 1)], else_=0)).label('grace_clients'),
            func.sum(case([(Customer.status=='suspended', 1)], else_=0)).label('suspended_clients'),
            func.sum(Customer.billing_amount).label('total_collection')
        ).filter(Customer.start_date != None).group_by('month').order_by('month').all()

        # Convert result to list of dicts for easier rendering
        report = []
        for row in monthly_data:
            report.append({
                'month': row.month,
                'active_clients': row.active_clients,
                'grace_clients': row.grace_clients,
                'suspended_clients': row.suspended_clients,
                'total_collection': row.total_collection
            })

        return render_template('admin/monthly_report.html', report=report)

    finally:
        session.close()

#==================== GRACE / WIFI ACCESS ====================
@app.route("/grace_popup/<ip_address>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def grace_popup(ip_address):
    with get_db() as db:
        customer = db.query(Customer).options(
            joinedload(Customer.router).joinedload(Router.branch),
            joinedload(Customer.network)
        ).filter_by(ip_address=ip_address).first()

        if not customer:
            return "Customer not found", 404

        router = customer.router
        today = datetime.utcnow().date()
        start_date = customer.start_date.date() if customer.start_date else today
        subscription_end = start_date + timedelta(days=30)
        if not customer.grace_days or customer.grace_days < 1:
            customer.grace_days = 1
        grace_end = subscription_end + timedelta(days=customer.grace_days)

        if request.method == "POST":
            selected_days = request.form.get("grace_days")
            try:
                selected_days = int(selected_days) if selected_days else 1
                selected_days = min(selected_days, 5)
                customer.grace_days = selected_days
                customer.popup_shown = True
                customer.status = "grace"
                db.commit()

                # ✅ Unblock IP if router exists
                if router:
                    unblock_ip(customer.ip_address, router)

                flash(f"Grace period of {selected_days} day(s) activated.", "success")
                return redirect(url_for("wifi_access", ip_address=ip_address))
            except Exception as e:
                db.rollback()
                flash(f"Error: {e}", "danger")
                return redirect(url_for("grace_popup", ip_address=ip_address))

        # Auto-increment grace days if popup not shown
        if not customer.popup_shown:
            customer.grace_days = min((customer.grace_days or 1) + 1, 5)
            db.commit()

        return render_template("customer/grace_popup.html", customer=customer)

from flask import Response

@app.route("/activate_grace/<ip_address>", methods=["GET", "POST"])
def activate_grace(ip_address):
    next_url = request.args.get("next") or "https://google.com"

    with get_db() as db:
        customer = (
            db.query(Customer)
            .options(joinedload(Customer.router))
            .filter_by(ip_address=ip_address)
            .first()
        )
        if not customer:
            return "Customer not found", 404

        today = datetime.utcnow().date()
        start_date = customer.start_date.date() if customer.start_date else today
        days_used = (today - start_date).days + 1

        # ✅ Only allow grace Day 31–33
        if not (31 <= days_used <= 33):
            customer.status = "suspended"
            db.commit()
        else:
            customer.grace_pass_date = today
            customer.status = "grace"
            db.commit()

            # ✅ Unblock on MikroTik (optional)
            router = customer.router
            if router:
                try:
                    unblock_ip(customer.ip_address, router)
                except Exception as e:
                    print(f"⚠️ MikroTik unblock failed: {e}")

    # ✅ IMPORTANT: captive portals sometimes ignore 302 redirects
    # So we return a small HTML page that forces redirect.
    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta http-equiv="refresh" content="0;url={next_url}">
      <script>window.location.replace("{next_url}");</script>
    </head>
    <body>
      Redirecting...
      <a href="{next_url}">Continue</a>
    </body>
    </html>
    """
    return Response(html, mimetype="text/html")


@app.route("/wifi_access/<ip_address>")
def wifi_access(ip_address):
    # ✅ must be INSIDE the route
    next_url = request.args.get("next") or "https://google.com"

    with get_db() as db:
        customer = (
            db.query(Customer)
            .options(joinedload(Customer.router))
            .filter_by(ip_address=ip_address)
            .first()
        )
        if not customer:
            return "Customer not found", 404

        router = customer.router
        today = datetime.utcnow().date()

        start_date = customer.start_date.date() if customer.start_date else today
        subscription_end = start_date + timedelta(days=30)

        days_used = (today - start_date).days + 1
        days_left = max((subscription_end - today).days, 0)

        old_status = customer.status

        # popup vars
        show_popup = False
        popup_type = None
        popup_message = None

        # ✅ show active card once per billing cycle
        show_active_card = False

        short_message = ""
        detailed_message = None

        # ==================== DAY 1–30 (ACTIVE) ====================
        if days_used <= 30:
            customer.status = "active"
            short_message = f"Your subscription runs from {start_date} to {subscription_end}."

            # ✅ show ACTIVE card only once per cycle
            if customer.active_card_cycle_start != start_date:
                show_active_card = True
                customer.active_card_cycle_start = start_date

            # ✅ day 25–30 popup once per day
            if 25 <= days_used <= 30 and popup_due(customer.pre_expiry_popup_last_shown, today):
                show_popup = True
                popup_type = "pre_expiry"
                popup_message = (
                    f"Your subscription will expire on <strong>{subscription_end}</strong> "
                    f"({days_left} day(s) left). Please make payment to continue uninterrupted service."
                )
                customer.pre_expiry_popup_last_shown = today

        # ==================== DAY 31–33 (GRACE OFFER) ====================
        elif 31 <= days_used <= 33:
            if customer.grace_pass_date == today:
                customer.status = "grace"
                short_message = "Grace activated for today. Please make payment to restore monthly service."
            else:
                customer.status = "suspended"
                short_message = "Your subscription has expired."

                # ✅ show grace button popup once per day
                if popup_due(customer.grace_offer_popup_last_shown, today):
                    show_popup = True
                    popup_type = "grace_offer"
                    popup_message = (
                        "Your subscription has expired.<br>"
                        "Click <strong>GRACE</strong> to continue browsing for today."
                    )
                    customer.grace_offer_popup_last_shown = today

        # ==================== DAY 34+ (SUSPENDED) ====================
        else:
            customer.status = "suspended"
            short_message = "You have utilised all your grace for the month. Please pay to continue enjoying the internet."
            detailed_message = f"Hi {customer.name}, your account is suspended. Contact support for help."

        db.commit()

        # ✅ MikroTik only when status changes
        if router and customer.status != old_status:
            try:
                if customer.status == "suspended":
                    block_ip(customer.ip_address, router)
                else:
                    unblock_ip(customer.ip_address, router)
            except Exception as e:
                print(f"⚠️ MikroTik action failed: {e}")

        # ✅ IMPORTANT CHANGE:
        # If ACTIVE/GRACE and NO popup and NO active-card -> redirect to next_url (google)
        if customer.status in ("active", "grace") and (not show_popup) and (not show_active_card):
            # ✅ avoid loop if next_url mistakenly points back to wifi_access
            if next_url and "wifi_access" not in next_url:
                return redirect(next_url)
            return "", 204

        return render_template(
            "customer/wifi_home.html",
            customer=customer,
            status=customer.status,
            short_message=short_message,
            detailed_message=detailed_message,
            show_popup=show_popup,
            popup_type=popup_type,
            popup_message=popup_message,
            show_active_card=show_active_card,
            start_date=start_date,
            subscription_end=subscription_end,
            days_left=days_left,
            next_url=next_url,
            current_year=datetime.utcnow().year,
        )

@app.route("/suspended_customers")
@login_required
@roles_required("admin", "super_admin")
def suspended_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        suspended_list = db.query(Customer).filter_by(status="suspended").all()
    finally:
        db.close()
    return render_template("admin/suspended_customers.html", customers=suspended_list)

# ==================== MARK PAID ====================
@app.route("/mark_paid/<int:customer_id>", methods=["POST"])
@login_required
@roles_required("admin", "super_admin")
def mark_paid(customer_id):
    with get_db() as db:
        customer = (
            db.query(Customer)
            .options(joinedload(Customer.router))
            .filter_by(id=customer_id)
            .first()
        )
        if not customer:
            flash("Customer not found.", "danger")
            return redirect(url_for("list_customers"))

        router = customer.router

        # ✅ restart new 30-day cycle
        customer.start_date = datetime.utcnow()
        customer.status = "active"
        customer.active_card_cycle_start = None

        # ✅ reset manual restrictions (ONLY keep fields that exist in your model)
        if hasattr(customer, "manually_suspended"):
            customer.manually_suspended = False
        if hasattr(customer, "hold_status"):
            customer.hold_status = False
        if hasattr(customer, "hold_until"):
            customer.hold_until = None

        # ✅ reset legacy fields (keep if still used anywhere)
        if hasattr(customer, "grace_days"):
            customer.grace_days = 0
        if hasattr(customer, "popup_shown"):
            customer.popup_shown = False
        if hasattr(customer, "pre_expiry_popup_shown"):
            customer.pre_expiry_popup_shown = False

        # ✅ reset NEW FLOW fields
        if hasattr(customer, "grace_pass_date"):
            customer.grace_pass_date = None
        if hasattr(customer, "pre_expiry_popup_last_shown"):
            customer.pre_expiry_popup_last_shown = None
        if hasattr(customer, "grace_offer_popup_last_shown"):
            customer.grace_offer_popup_last_shown = None
        if hasattr(customer, "suspended_popup_last_shown"):
            customer.suspended_popup_last_shown = None

        db.commit()

        # ✅ unblock on MikroTik
        if router and customer.ip_address:
            try:
                unblock_ip(customer.ip_address, router)
                flash(f"{customer.name} is marked paid and WiFi is active.", "success")
            except Exception as e:
                flash(f"Marked paid but MikroTik error: {e}", "warning")
        else:
            flash(f"{customer.name} is marked paid. No router assigned.", "info")

    return redirect(url_for("list_customers"))


# ==================== EXPORT TO EXCEL ====================
@app.route("/customers/export", methods=["GET"])
@login_required
@roles_required("admin", "super_admin")
def export_customers():
    
    search_term = request.args.get("search", "").strip()
    db = SessionLocal()
    try:
        query = db.query(Customer).options(
            joinedload(Customer.router).joinedload(Router.branch),
            joinedload(Customer.network)
        )
        if search_term:
            query = query.filter(
                (Customer.account_no.like(f"%{search_term}%")) |
                (Customer.name.like(f"%{search_term}%")) |
                (Customer.ip_address.like(f"%{search_term}%"))
            )
        customers = query.all()
        wb = Workbook()
        ws = wb.active
        ws.title = "Customers"

        headers = [
            "Account No", "Name", "Phone", "FAT/ID", "Location", "IP Address", "Branch",
            "Billing Amount", "Cable No", "Loop No", "Power Level", "Final Coordinates",
            "Coordinates", "Date Registered", "Password", "Status"
        ]
        ws.append(headers)

        for c in customers:
            ws.append([
                c.account_no, c.name, c.phone, c.fat_id, c.location, c.ip_address,
                c.router.branch.name if c.router and c.router.branch else "",
                c.billing_amount, c.network.cable_no if c.network else "",
                c.network.loop_no if c.network else "", c.network.power_level if c.network else "",
                c.network.final_coordinates if c.network else "",
                c.network.coordinates if c.network else "",
                c.start_date.strftime("%Y-%m-%d %H:%M:%S") if c.start_date else "",
                c.mikrotik_password or "", c.status
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
    finally:
        db.close()

    return send_file(
        output,
        as_attachment=True,
        download_name="customers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


    )

#-------export branch------------
@app.route("/branch/<int:branch_id>/customers/export")
@login_required
@roles_required("admin", "super_admin")
def export_customers_by_branch(branch_id):
    with get_db() as db:
        branch = db.query(Branch).filter_by(id=branch_id).first()
        if not branch:
            flash("Branch not found", "danger")
            return redirect(url_for("list_branches"))

        customers = (
            db.query(Customer)
            .join(Customer.router)
            .filter(Router.branch_id == branch_id)
            .options(
                joinedload(Customer.network),
                joinedload(Customer.router).joinedload(Router.branch)
            )
            .all()
        )

        wb = Workbook()
        ws = wb.active
        ws.title = f"{branch.name} Customers"

        headers = [
            "Account No", "Name", "Phone", "Email", "Location",
            "IP Address", "Branch", "Billing Amount",
            "Cable No", "Loop No", "Power Level",
            "Final Coordinates", "Coordinates",
            "Date Registered", "Status"
        ]
        ws.append(headers)

        for c in customers:
            ws.append([
                c.account_no,
                c.name,
                c.phone,
                c.fat_id,
                c.location,
                c.ip_address,
                branch.name,
                c.billing_amount,
                c.network.cable_no if c.network else "",
                c.network.loop_no if c.network else "",
                c.network.power_level if c.network else "",
                c.network.final_coordinates if c.network else "",
                c.network.coordinates if c.network else "",
                c.start_date.strftime("%Y-%m-%d %H:%M:%S") if c.start_date else "",
                c.status
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"{branch.name}_customers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/toggle_suspend/<int:customer_id>")
@login_required
@roles_required("admin", "super_admin")
def toggle_suspend(customer_id):
    with get_db() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()

        if customer:
            router = customer.router
            if customer.manually_suspended:
                # Unsuspend manually
                customer.manually_suspended = False
                customer.status = "active"
                if router:
                    unblock_ip(customer.ip_address, router)  # ✅ Use helper
                flash(f"{customer.name} has been unsuspended manually.", "success")
            else:
                # Suspend manually
                customer.manually_suspended = True
                customer.status = "manually_suspended"
                if router:
                    block_ip(customer.ip_address, router)  # ✅ Use helper
                flash(f"{customer.name} has been manually suspended.", "warning")

            db.commit()

    return redirect(url_for('manual_suspension'))


@app.route("/toggle_hold/<int:customer_id>")
@login_required
@roles_required("admin", "super_admin")
def toggle_hold(customer_id):
    with get_db() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()

        if customer:
            router = customer.router
            if customer.hold_status:
                # Unhold (activate)
                customer.hold_status = False
                customer.status = "active"
                customer.activated_on = datetime.utcnow()
                if router:
                    unblock_ip(customer.ip_address, router)
                flash(f"{customer.name} has been unheld and activated.", "success")
            else:
                # Put on hold
                customer.hold_status = True
                customer.status = "on_hold"
                if router:
                    block_ip(customer.ip_address, router)
                flash(f"{customer.name} has been put on hold.", "warning")

            db.commit()

    return redirect(url_for('manual_suspension'))

# Hold customer with selected date
@app.route('/hold_customer/<int:customer_id>', methods=['POST'])
@login_required
@roles_required("admin", "super_admin")
def hold_customer(customer_id):
    hold_until_str = request.form.get('hold_until')
    
    with get_db() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if customer and hold_until_str:
            hold_until = datetime.strptime(hold_until_str, "%Y-%m-%d")
            customer.hold_status = True
            customer.hold_until = hold_until
            customer.status = "on_hold"
            router = customer.router
            if router:
                block_ip(customer.ip_address, router)
            db.commit()
            flash(f"{customer.name} has been put on hold until {hold_until.strftime('%Y-%m-%d')}.", "warning")

    return redirect(url_for('manual_hold'))


# Unhold customer
@app.route('/unhold_customer/<int:customer_id>')
@login_required
@roles_required("admin", "super_admin")
def unhold_customer(customer_id):
    with get_db() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if customer:
            customer.hold_status = False
            customer.hold_until = None
            if not customer.activated_on:
                customer.activated_on = datetime.utcnow()
            customer.status = "active"
            router = customer.router
            if router:
                unblock_ip(customer.ip_address, router)
            db.commit()
            flash(f"{customer.name} has been reactivated successfully.", "success")

    return redirect(url_for('manual_hold'))


@app.route('/manual_manage_customers')
@login_required
@roles_required("admin", "super_admin")
def manual_manage_customers():

    with get_db() as db:
        customers = db.query(Customer).all()
    return render_template('admin/manual_hold.html', customers=customers, datetime=datetime)

@app.route("/grace_customers")
@login_required
@roles_required("admin", "super_admin")
def grace_customers():
    return redirect(url_for("list_customers", status="grace"))

def daily_status_check(db=None):
    """Check all customers and update WiFi status automatically (efficient)."""
    today = datetime.utcnow().date()
    close_session = False

    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        customers = db.query(Customer).options(joinedload(Customer.router)).all()

        for customer in customers:
            router = customer.router
            old_status = customer.status

            # ✅ Do NOT override manual states
            if old_status in ["manually_suspended", "on_hold"]:
                continue

            start_date = customer.start_date.date() if customer.start_date else today
            days_used = (today - start_date).days + 1

            # ================= NEW STATUS LOGIC =================
            if days_used <= 30:
                new_status = "active"

            elif 31 <= days_used <= 33:
                # user must click grace every day
                new_status = "grace" if customer.grace_pass_date == today else "suspended"

            else:
                new_status = "suspended"

            # ✅ Step 6B: clear grace click when active again
            if new_status == "active":
                customer.grace_pass_date = None

            # ================= APPLY STATUS =================
            customer.status = new_status

            # ✅ MikroTik only if status changed
            if router and customer.ip_address and new_status != old_status:
                try:
                    if new_status == "suspended":
                        block_ip(customer.ip_address, router)
                        print(f"🔒 Scheduler blocked {customer.ip_address} on {router.ip_address}")
                    else:
                        unblock_ip(customer.ip_address, router)
                        print(f"✅ Scheduler unblocked {customer.ip_address} on {router.ip_address}")
                except Exception as e:
                    print(f"⚠️ Scheduler MikroTik error for {customer.ip_address}: {e}")

        db.commit()

    finally:
        if close_session:
            db.close()

# ==================== SCHEDULER SETUP ====================
# # For testing: run every 5 minutes
scheduler.add_job(
    id="daily_status_check_test",
    func=daily_status_check,
    trigger="interval",
    minutes=2,
    replace_existing=True
 )

# For production: uncomment this line to run once daily at midnight UTC
# scheduler.add_job(
#     id="daily_status_check_daily",
#     func=daily_status_check,
#     trigger="cron",
#     hour=0,
#     minute=0,
#     replace_existing=True
# )


# ==================== RUN APP ====================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)