# ==================== STANDARD LIBRARY ====================
import os
import io
from datetime import datetime, timedelta

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

scheduler = APScheduler()

# APScheduler config (safe defaults)
app.config["SCHEDULER_API_ENABLED"] = False
app.config["SCHEDULER_TIMEZONE"] = "UTC"

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
        total_users = db.query(Customer).count()
        active_users = db.query(Customer).filter_by(status="active").count()
        grace_users = db.query(Customer).filter_by(status="grace").count()
        suspended_users = db.query(Customer).filter_by(status="suspended").count()
        return render_template(
            "admin/admin_dashboard.html",
            username=session.get("username"),
            role=session.get("role"),
            total_users=total_users,
            active_users=active_users,
            grace_users=grace_users,
            suspended_users=suspended_users,
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

# ==================== BRANCH AND ROUTER MANAGEMENT ====================
@app.route("/add_branch", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def add_branch():
    with get_db() as db:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if db.query(Branch).filter_by(name=name).first():
                flash("Branch already exists!", "danger")
                return redirect(url_for("add_branch"))
            
            db.add(Branch(name=name))
            db.commit()
            flash("Branch added successfully!", "success")
            return redirect(url_for("add_branch"))
        
        return render_template("admin/add_branch.html")


#==================list/edit/delete branch===================
@app.route("/list_branches")
@login_required
@roles_required("admin", "super_admin")
def list_branches():
    with get_db() as db:
        branches = db.query(Branch).all()
    return render_template("admin/list_branches.html", branches=branches)

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

# ==================== CUSTOMER MANAGEMENT ====================
@app.route("/add_customer", methods=["GET", "POST"])
@login_required
@roles_required("admin", "super_admin")
def add_customer():
    with get_db() as db:
        branches = db.query(Branch).all()
        routers = []

        # ✅ Load routers for first branch by default
        if branches:
            routers = db.query(Router).filter(Router.branch_id == branches[0].id).all()

        if request.method == "POST":
            router_id = request.form.get("router_id")
            router_id = int(router_id) if router_id else None

            customer = Customer(
                account_no=request.form.get("account_no"),
                name=request.form.get("name"),
                phone=request.form.get("phone"),
                email=request.form.get("email"),
                location=request.form.get("location"),
                ip_address=request.form.get("ip_address"),
                billing_amount=request.form.get("billing_amount"),
                start_date=request.form.get("start_date"),
                contract_date=request.form.get("contract_date"),
                router_id=router_id
            )

            db.add(customer)
            db.commit()

            # Network info
            network = CustomerNetwork(
                customer_id=customer.id,
                cable_no=request.form.get("cable_no"),
                cable_type=request.form.get("cable_type"),
                splitter=request.form.get("splitter"),
                tube_no=request.form.get("tube_no"),
                core_used=request.form.get("core_used"),
                final_coordinates=request.form.get("final_coordinates"),
                loop_no=request.form.get("loop_no"),
                power_level=request.form.get("power_level"),
                coordinates=request.form.get("coordinates"),
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
@app.route("/customers")
@login_required
@roles_required("admin", "super_admin")
def list_customers():
    search_term = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 5

    with get_db() as db:
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

        total = query.count()
        customers = query.offset((page - 1) * per_page).limit(per_page).all()
        has_next = total > page * per_page

    return render_template(
        "admin/list_customer.html",
        customers=customers,
        page=page,
        per_page=per_page,
        total=total,
        has_next=has_next,
        search_term=search_term
    )


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

        # ✅ Get selected branch THROUGH router
        selected_branch_id = (
            customer.router.branch.id
            if customer.router and customer.router.branch
            else None
        )

        # ✅ Load routers ONLY for that branch
        routers = []
        if selected_branch_id:
            routers = db.query(Router).filter(
                Router.branch_id == selected_branch_id
            ).all()

        if request.method == "POST":
            customer.account_no = request.form.get("account_no")
            customer.name = request.form.get("name")
            customer.phone = request.form.get("phone")
            customer.email = request.form.get("email")
            customer.location = request.form.get("location")
            customer.ip_address = request.form.get("ip_address")
            customer.billing_amount = request.form.get("billing_amount")
            customer.start_date = request.form.get("start_date")
            customer.contract_date = request.form.get("contract_date")

            # ❌ DO NOT set customer.branch_id (it does not exist)

            # ✅ Assign router (router determines branch)
            selected_router_id = request.form.get("router_id")
            customer.router_id = int(selected_router_id) if selected_router_id else None

            # Network info
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

# ==================== GRACE / WIFI ACCESS ====================
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

@app.route("/wifi_access/<ip_address>")
def wifi_access(ip_address):
    with get_db() as db:
        customer = db.query(Customer).options(
            joinedload(Customer.router)
        ).filter_by(ip_address=ip_address).first()

        if not customer:
            return "Customer not found", 404

        today = datetime.utcnow().date()
        start_date = customer.start_date.date() if customer.start_date else today
        subscription_end = start_date + timedelta(days=30)
        grace_days = customer.grace_days or 0
        grace_end = subscription_end + timedelta(days=grace_days)
        days_used = (today - start_date).days + 1
        days_left = max((subscription_end - today).days, 0)

        status = short_message = detailed_message = None
        router = customer.router
        show_popup = False  # New: controls popup display

        # ==================== ACTIVE ====================
        if today <= subscription_end:
            customer.status = "active"
            status = "active"
            short_message = f"Your subscription runs from {start_date} to {subscription_end}."

            # ✅ Daily notifications from day 25–30
            if 25 <= days_used <= 30:
                show_popup = True
                detailed_message = (
                    f"Hi {customer.name}, your subscription will expire on "
                    f"<strong>{subscription_end}</strong> ({days_left} day(s) left). "
                    f"Please make payment to continue uninterrupted service."
                )

        # ==================== GRACE PERIOD ====================
        elif subscription_end < today <= grace_end:
            customer.status = "grace"
            status = "grace"
            short_message = f"Your subscription expired on {subscription_end}. Please pay before {grace_end}."
            if router:
                unblock_ip(customer.ip_address, router)  # Grace: unblock IP

        # ==================== SUSPENDED ====================
        else:
            customer.status = "suspended"
            status = "suspended"
            short_message = f"Your WiFi was suspended. Subscription expired on {subscription_end} and grace ended on {grace_end}."
            detailed_message = f"Hi {customer.name}, your account is suspended. Contact support for help."
            if router and router.ip_address:
                block_ip(customer.ip_address, router)  # Suspend: block IP
                print(f"🔒 {customer.name} ({customer.ip_address}) has been blocked.")

        db.commit()

        return render_template(
            "wifi_home.html",
            customer=customer,
            status=status,
            short_message=short_message,
            detailed_message=detailed_message,
            days_left=days_left if show_popup else None,
            show_popup=show_popup,  # New
            current_year=datetime.utcnow().year
        )

# ==================== GRACE / SUSPENDED CUSTOMERS ====================
@app.route("/grace_customers")
@login_required
@roles_required("admin", "super_admin")
def grace_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        grace_list = db.query(Customer).filter_by(status="grace").all()
    finally:
        db.close()
    return render_template("admin/grace_customers.html", customers=grace_list)

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
        customer = db.query(Customer).options(joinedload(Customer.router)).filter_by(id=customer_id).first()
        if not customer:
            flash("Customer not found.", "danger")
            return redirect(url_for("list_customers"))

        router = customer.router

        # Reset subscription
        customer.start_date = datetime.utcnow()
        customer.grace_days = 0
        customer.status = "active"
        customer.popup_shown = False
        customer.pre_expiry_popup_shown = False

        db.commit()

        # ✅ Unblock IP using helper
        if router:
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
            "Account No", "Name", "Phone", "Email", "Location", "IP Address", "Branch",
            "Billing Amount", "Cable No", "Loop No", "Power Level", "Final Coordinates",
            "Coordinates", "Date Registered", "Password", "Status"
        ]
        ws.append(headers)

        for c in customers:
            ws.append([
                c.account_no, c.name, c.phone, c.email, c.location, c.ip_address,
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

# ==================== APScheduler Job ====================
from datetime import datetime

def daily_status_check(db=None):
    """Check all customers and update WiFi status automatically."""
    today = datetime.utcnow().date()
    close_session = False

    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        customers = db.query(Customer).all()
        for customer in customers:
            router = customer.router
            start_date = customer.start_date.date() if customer.start_date else today
            subscription_end = start_date + timedelta(days=30)
            grace_days = customer.grace_days or 1
            grace_end = subscription_end + timedelta(days=grace_days)
            old_status = customer.status

            if today <= subscription_end:
                customer.status = "active"
                if old_status != "active" and router:
                    unblock_ip(customer.ip_address, router)
            elif subscription_end < today <= grace_end:
                customer.status = "grace"
                if router:
                    unblock_ip(customer.ip_address, router)
            else:
                customer.status = "suspended"
                if old_status != "suspended" and router:
                    block_ip(customer.ip_address, router)
        db.commit()
    finally:
        if close_session:
            db.close()

# ==================== SCHEDULER SETUP ====================
# For testing: run every 5 minutes
scheduler.add_job(
    id="daily_status_check_test",
    func=daily_status_check,
    trigger="interval",
    minutes=5,
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
 
    scheduler.start()
    print("Scheduler started successfully.")

    app.run(debug=True, host="0.0.0.0", port=5000)
