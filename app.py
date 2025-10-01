# ==================== STANDARD LIBRARY ====================
import threading
import time
import random
import io
from datetime import datetime, timedelta

# ==================== FLASK ====================
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file

# ==================== MIKROTIK HELPER ====================
from mikrotik_helper import block_ip, unblock_ip, generate_password

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

# ==================== HELPERS ====================
def generate_account_no():
    """Generate a unique account number."""
    return f"CUST{random.randint(10000, 99999)}"

# ==================== LOGIN / LOGOUT ====================
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(username=username).first()

            if username == "admin" and password == "admin123":
                session.update({"user_id": "super_admin", "username": "admin", "role": "super_admin"})
                flash("Welcome Super Admin", "success")
                return redirect(url_for("admin_dashboard"))

            if user and check_password_hash(user.password, password):
                if user.role != "super_admin" and not user.is_active:
                    flash("Your account is pending approval. Please contact the admin.", "warning")
                    return redirect(url_for("login"))

                if user.role not in ["admin", "super_admin"]:
                    flash("Access denied. You are not an admin.", "danger")
                    return redirect(url_for("login"))

                session.update({"user_id": user.id, "username": user.username, "role": user.role})
                flash("Welcome", "success")
                return redirect(url_for("admin_dashboard"))

            flash("Invalid username or password", "danger")
        finally:
            db.close()
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

# ==================== USER MANAGEMENT ====================
@app.route("/manage_users")
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
def pending_users():
    if session.get("role") != "super_admin":
        flash("Access denied. Only super admin can view pending users.", "danger")
        return redirect(url_for("admin_dashboard"))
    db = SessionLocal()
    try:
        users = db.query(User).filter_by(is_active=False, role="admin").all()
    finally:
        db.close()
    return render_template("admin/pending_users.html", users=users)

@app.route("/delete_user/<int:user_id>", methods=["POST"])
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
def toggle_user(user_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
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
def add_branch():
    db = SessionLocal()
    if request.method == "POST":
        name = request.form.get("name").strip()
        if db.query(Branch).filter_by(name=name).first():
            flash("Branch already exists!", "danger")
            return redirect(url_for("add_branch"))
        db.add(Branch(name=name))
        db.commit()
        flash("Branch added successfully!", "success")
        return redirect(url_for("add_branch"))
    return render_template("admin/add_branch.html")

@app.route("/add_router", methods=["GET", "POST"])
def add_router():
    db = SessionLocal()
    branches = db.query(Branch).all()
    if request.method == "POST":
        ip_address = request.form.get("ip_address")
        description = request.form.get("description")
        branch_id = request.form.get("branch_id")
        if db.query(Router).filter_by(ip_address=ip_address).first():
            flash("Router IP already exists!", "danger")
            return redirect(url_for("add_router"))
        db.add(Router(ip_address=ip_address, description=description, branch_id=branch_id))
        db.commit()
        flash("Router added successfully!", "success")
        return redirect(url_for("add_router"))
    return render_template("admin/add_router.html", branches=branches)

# ==================== ADMIN DASHBOARD ====================
@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
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

# ==================== CUSTOMER MANAGEMENT ====================
@app.route("/add_customer", methods=["GET", "POST"])
def add_customer():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        branches = db.query(Branch).all()
        if request.method == "POST":
            account_no = request.form.get("account_no") or generate_account_no()
            customer = Customer(
                account_no=account_no,
                name=request.form.get("name"),
                phone=request.form.get("phone"),
                email=request.form.get("email"),
                location=request.form.get("location"),
                ip_address=request.form.get("ip_address"),
                billing_amount=float(request.form.get("billing_amount")),
                router_id=request.form.get("router_id"),
                start_date=request.form.get("start_date") or datetime.utcnow(),
                contract_date=request.form.get("contract_date") or None,
                mikrotik_password=generate_password()
            )
            db.add(customer)
            db.commit()
            if any([request.form.get(f) for f in ["cable_no", "final_coordinates", "loop_no", "power_level", "coordinates"]]):
                network = CustomerNetwork(
                    customer_id=customer.id,
                    cable_no=request.form.get("cable_no"),
                    final_coordinates=request.form.get("final_coordinates"),
                    loop_no=request.form.get("loop_no"),
                    power_level=request.form.get("power_level"),
                    coordinates=request.form.get("coordinates")
                )
                db.add(network)
                db.commit()
            flash("Customer added successfully!", "success")
            return redirect(url_for("list_customers"))
    finally:
        db.close()
    return render_template("admin/add_new_customer.html", routers=routers, branches=branches)

# ==================== LIST / EDIT / DELETE CUSTOMERS ====================
@app.route("/customers")
def list_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        page = int(request.args.get("page", 1))
        per_page = 5
        search_term = request.args.get("search", "").strip()
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
    finally:
        db.close()
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
def edit_customer(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        customer = db.query(Customer).options(
            joinedload(Customer.router).joinedload(Router.branch),
            joinedload(Customer.network)
        ).filter(Customer.id == customer_id).first()
        if not customer:
            flash("Customer not found", "danger")
            return redirect(url_for("list_customers"))
        branches = db.query(Branch).all()
        routers = db.query(Router).all()
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
            customer.router_id = request.form.get("router_id")
            if customer.network:
                network = customer.network
            else:
                network = CustomerNetwork(customer_id=customer.id)
                customer.network = network
            network.cable_no = request.form.get("cable_no")
            network.final_coordinates = request.form.get("final_coordinates")
            network.loop_no = request.form.get("loop_no")
            network.power_level = request.form.get("power_level")
            network.coordinates = request.form.get("coordinates")
            db.add(customer)
            db.commit()
            flash("Customer updated successfully!", "success")
            return redirect(url_for("list_customers"))
    finally:
        db.close()
    return render_template(
        "admin/edit_customer.html",
        customer=customer,
        branches=branches,
        routers=routers,
        network=customer.network
    )

@app.route("/delete_customer/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if customer:
            db.delete(customer)
            db.commit()
            flash("Customer deleted successfully!", "success")
        else:
            flash("Customer not found", "danger")
    finally:
        db.close()
    return redirect(url_for("list_customers"))

# ==================== GRACE / WIFI ACCESS ====================
@app.route("/grace_popup/<ip_address>", methods=["GET", "POST"])
def grace_popup(ip_address):
    with SessionLocal() as db:
        customer = db.query(Customer).filter_by(ip_address=ip_address).first()
        if not customer:
            return "Customer not found", 404
        if customer.popup_shown:
            return redirect(url_for("wifi_access", ip_address=ip_address))
        if request.method == "POST":
            selected_days = request.form.get("grace_days")
            try:
                selected_days = int(selected_days) if selected_days else 1
                if selected_days not in [1, 2, 3, 4, 5]:
                    flash("Select 1–5 days only", "danger")
                    return redirect(url_for("grace_popup", ip_address=ip_address))
                customer.grace_days = selected_days
                customer.popup_shown = True
                customer.status = "grace"
                db.commit()
                unblock_ip(customer.ip_address)
                flash(f"Grace period of {selected_days} day(s) activated.", "success")
                return redirect(url_for("wifi_access", ip_address=ip_address))
            except Exception as e:
                db.rollback()
                flash(f"Error: {e}", "danger")
                return redirect(url_for("grace_popup", ip_address=ip_address))
        return render_template("customer/grace_popup.html", customer=customer)

@app.route("/wifi_access/<ip_address>")
def wifi_access(ip_address):
    with SessionLocal() as db:
        customer = db.query(Customer).filter_by(ip_address=ip_address).first()
        if not customer:
            return "Customer not found", 404

        # Normalize all to date objects
        today = datetime.utcnow().date()
        start_date = customer.start_date.date() if customer.start_date else today
        subscription_end = start_date + timedelta(days=30)
        grace_end = subscription_end + timedelta(days=customer.grace_days or 0)
        days_left = (subscription_end - today).days

        status = short_message = detailed_message = None

        # ==================== ACTIVE ====================
        if today <= subscription_end:
            customer.status = "active"
            status = "active"
            short_message = f"Your WiFi is active until {subscription_end}."

            if 1 <= days_left <= 4 and not customer.pre_expiry_popup_shown:
                detailed_message = (
                    f"Hi {customer.name}, your subscription expires on <strong>{subscription_end}</strong> "
                    f"({days_left} day(s) left).<br>"
                    "Pay via Paybill <strong>4002057</strong><br>"
                    f"Account No: <strong>{customer.account_no}</strong><br>"
                    "If already paid, forward Mpesa SMS to <strong>+254 790 924185</strong>."
                )
                customer.pre_expiry_popup_shown = True

            try:
                unblock_ip(customer.ip_address)
            except Exception as e:
                print(f"IP unblock error: {e}")

        # ==================== GRACE ====================
        elif subscription_end < today <= grace_end:
            customer.status = "grace"
            status = "grace"
            short_message = f"Your subscription expired on {subscription_end}. You are in grace until {grace_end}."

            if not customer.popup_shown and not request.args.get("paid"):
                return redirect(url_for("grace_popup", ip_address=ip_address))

            days_remaining = (grace_end - today).days
            detailed_message = (
                f"Hi {customer.name}, your subscription expired on <strong>{subscription_end}</strong>.<br>"
                f"You have <strong>{days_remaining} day(s)</strong> left in your grace period (ends on {grace_end}).<br>"
                "Please pay to avoid suspension."
            )
            try:
                unblock_ip(customer.ip_address)
            except Exception as e:
                print(f"IP unblock error during grace: {e}")

        # ==================== SUSPENDED ====================
        else:
            customer.status = "suspended"
            status = "suspended"
            short_message = (
                f"Your WiFi was suspended. Subscription expired on {subscription_end} "
                f"and grace ended on {grace_end}."
            )
            detailed_message = (
                f"Hi {customer.name}, your account is suspended.<br>"
                f"Subscription expired on <strong>{subscription_end}</strong> "
                f"and grace ended on <strong>{grace_end}</strong>.<br><br>"
                "Pay via Paybill <strong>4002057</strong><br>"
                f"Account No: <strong>{customer.account_no}</strong><br>"
                "Forward Mpesa SMS to <strong>+254 790 924185</strong> after payment."
            )
            try:
                block_ip(customer.ip_address)
            except Exception as e:
                print(f"IP block error: {e}")

        db.commit()

        return render_template(
            "customer/wifi_home.html",
            customer=customer,
            status=status,
            short_message=short_message,
            detailed_message=detailed_message,
        )

# ==================== GRACE / SUSPENDED CUSTOMERS ====================
@app.route("/grace_customers")
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
def mark_paid(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    with SessionLocal() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            flash("Customer not found.", "danger")
            return redirect(url_for("grace_customers"))

        # Reset subscription
        customer.start_date = datetime.utcnow()
        customer.grace_days = 0
        customer.status = "active"
        customer.popup_shown = False
        customer.pre_expiry_popup_shown = False
        db.commit()

        try:
            unblock_ip(customer.ip_address)
            flash(f"{customer.name} is marked paid and WiFi is active.", "success")
        except Exception as e:
            flash(f"Marked paid but MikroTik error: {e}", "warning")
    return redirect(url_for("grace_customers"))

# ==================== EXPORT TO EXCEL ====================
@app.route("/customers/export", methods=["GET"])
def export_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))

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

# ==================== DAILY STATUS CHECK ====================
def daily_status_check(db=None):
    today = datetime.utcnow().date()
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True
    try:
        customers = db.query(Customer).all()
        for customer in customers:
            start_date = customer.start_date.date() if customer.start_date else today
            subscription_end = start_date + timedelta(days=31)
            grace_end = subscription_end + timedelta(days=customer.grace_days or 0)
            days_left = (subscription_end - today).days
            old_status = customer.status

            # ==================== ACTIVE ====================
            if today <= subscription_end:
                customer.status = "active"
                if old_status != "active":
                    try:
                        unblock_ip(customer.ip_address)
                        print(f"✅ Unblocked {customer.name} ({customer.ip_address})")
                    except Exception as e:
                        print(f"❌ Error unblocking {customer.ip_address}: {e}")

            # ==================== GRACE ====================
            elif subscription_end < today <= grace_end:
                customer.status = "grace"

            # ==================== SUSPENDED ====================
            else:
                customer.status = "suspended"
                customer.popup_shown = True
                if old_status != "suspended":
                    try:
                        block_ip(customer.ip_address)
                        print(f"🔒 Blocked {customer.name} ({customer.ip_address})")
                    except Exception as e:
                        print(f"❌ Error blocking {customer.ip_address}: {e}")

            # Pre-expiry popup logic
            customer.pre_expiry_popup_shown = not (1 <= days_left <= 4)

        db.commit()
    finally:
        if close_session:
            db.close()


def run_scheduler():
    while True:
        daily_status_check()
        time.sleep(24 * 60 * 60)

threading.Thread(target=run_scheduler, daemon=True).start()

# ==================== RUN APP ====================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

