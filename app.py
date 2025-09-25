from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from connections import SessionLocal
from models import User, Customer, CustomerNetwork
from datetime import datetime, timedelta
import threading
import time
import random

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ==================== HELPER ====================
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
                session["user_id"] = "super_admin"
                session["username"] = "admin"
                session["role"] = "super_admin"
                flash("Welcome Super Admin", "success")
                return redirect(url_for("admin_dashboard"))

            if user and check_password_hash(user.password, password):
                if user.role != "super_admin" and not user.is_active:
                    flash("Your account is pending approval. Please contact the admin.", "warning")
                    return redirect(url_for("login"))

                if user.role not in ["admin", "super_admin"]:
                    flash("Access denied. You are not an admin.", "danger")
                    return redirect(url_for("login"))

                session["user_id"] = user.id
                session["username"] = user.username
                session["role"] = user.role
                flash("Welcome", "success")
                return redirect(url_for("admin_dashboard"))

            else:
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

@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("admin/admin_dashboard.html", username=session.get("username"))

# ==================== CUSTOMER CRUD ====================
@app.route("/customers/add", methods=["GET", "POST"])
def add_customer():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        location = request.form.get("location")
        ip_address = request.form.get("ip_address")
        billing_amount = request.form.get("billing_amount")
        account_no = request.form.get("account_no")
        cable_no = request.form.get("cable_no")
        router_no = request.form.get("router_no")
        loop_no = request.form.get("loop_no")
        power_level = request.form.get("power_level")
        signal_strength = request.form.get("signal_strength")
        coordinates = request.form.get("coordinates")

        if not name or not phone or not billing_amount or not ip_address or not account_no:
            flash("All required fields must be filled.", "warning")
            return redirect(url_for("add_customer"))

        db = SessionLocal()
        try:
            # Check if account number already exists
            existing_account = db.query(Customer).filter_by(account_no=account_no).first()
            if existing_account:
                flash(f"Account number {account_no} already exists! Choose a different one.", "danger")
                return redirect(url_for("add_customer"))

            # Check if IP address already exists
            existing_ip = db.query(Customer).filter_by(ip_address=ip_address).first()
            if existing_ip:
                flash(f"IP address {ip_address} has already been assigned to another customer!", "danger")
                return redirect(url_for("add_customer"))

            # Create new customer
            start_date = datetime.utcnow()
            new_customer = Customer(
                name=name,
                phone=phone,
                email=email,
                location=location,
                ip_address=ip_address,
                billing_amount=float(billing_amount),
                account_no=account_no,
                start_date=start_date,
                grace_days=0,
                status="active",
                popup_shown=False,
                pre_expiry_popup_shown=False
            )
            db.add(new_customer)
            db.commit()  # commit to get new_customer.id

            # Add network info
            network = CustomerNetwork(
                customer_id=new_customer.id,
                cable_no=cable_no,
                router_no=router_no,
                loop_no=loop_no,
                power_level=power_level,
                #signal_strength=signal_strength,
                coordinates=coordinates
            )
            db.add(network)
            db.commit()

            flash("Customer added successfully!", "success")
            return redirect(url_for("list_customers"))

        finally:
            db.close()

    return render_template("admin/add_new_customer.html")

from sqlalchemy.orm import joinedload  # make sure this is at the top

@app.route("/customers")
def list_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        page = int(request.args.get("page", 1))
        per_page = 5

        # Base query
        query = db.query(Customer).options(joinedload(Customer.network))

        # Search term (optional)
        search_term = request.args.get("search", "").strip()
        if search_term:
            query = query.filter(
                (Customer.account_no.ilike(f"%{search_term}%")) |
                (Customer.name.ilike(f"%{search_term}%")) |
                (Customer.ip_address.ilike(f"%{search_term}%"))
            )

        # Pagination
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
        search_term=search_term  # ✅ pass to template
    )




@app.route("/edit_customer/<int:customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    customer = db.query(Customer).filter_by(id=customer_id).first()
    network = db.query(CustomerNetwork).filter_by(customer_id=customer_id).first()
    if not customer:
        db.close()
        flash("Customer not found", "danger")
        return redirect(url_for("list_customers"))
    if request.method == "POST":
        try:
            customer.name = request.form.get("name", "").strip()
            customer.phone = request.form.get("phone", "").strip()
            customer.email = request.form.get("email", "").strip()
            customer.location = request.form.get("location", "").strip()
            customer.ip_address = request.form.get("ip_address", "").strip()
            customer.billing_amount = float(request.form.get("billing_amount", 0))
            customer.account_no = request.form.get("account_no") or customer.account_no

            if network:
                network.cable_no = request.form.get("cable_no")
                network.router_no = request.form.get("router_no")
                network.loop_no = request.form.get("loop_no")
                network.power_level = request.form.get("power_level")
                #network.signal_strength = request.form.get("signal_strength")
                network.coordinates = request.form.get("coordinates")

            db.commit()
            flash("Customer updated successfully!", "success")
            return redirect(url_for("list_customers"))
        except Exception as e:
            db.rollback()
            flash(f"Error: {str(e)}", "danger")
        finally:
            db.close()
    db.close()
    return render_template("admin/edit_customer.html", customer=customer, network=network)

@app.route("/delete_customer/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        network = db.query(CustomerNetwork).filter_by(customer_id=customer_id).first()
        if customer:
            if network:
                db.delete(network)
            db.delete(customer)
            db.commit()
            flash("Customer deleted successfully!", "success")
        else:
            flash("Customer not found", "danger")
    except Exception as e:
        db.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("list_customers"))

# ==================== GRACE / WIFI / MARK PAID ====================
@app.route("/grace_popup/<ip_address>", methods=["GET", "POST"])
def grace_popup(ip_address):
    db = SessionLocal()
    customer = db.query(Customer).filter_by(ip_address=ip_address).first()
    if not customer:
        db.close()
        return "Customer not found", 404
    if request.method == "POST":
        selected_days = int(request.form.get("grace_days", 1))
        customer.grace_days = selected_days
        customer.popup_shown = True
        db.commit()
        db.close()
        flash(f"Grace period selected: {selected_days} day(s)", "success")
        return redirect(url_for("wifi_home", ip_address=ip_address))
    db.close()
    return render_template("customer/grace_popup.html", customer=customer)

@app.route("/wifi_access/<ip_address>")
def wifi_home(ip_address):
    db = SessionLocal()
    customer = db.query(Customer).filter_by(ip_address=ip_address).first()
    if not customer:
        db.close()
        return "Customer not found", 404
    today = datetime.utcnow()
    subscription_end = customer.start_date + timedelta(days=30)
    grace_end = subscription_end + timedelta(days=customer.grace_days)

    if today <= subscription_end:
        status = "active"
    elif subscription_end < today <= grace_end:
        if not customer.popup_shown:
            db.close()
            return redirect(url_for("grace_popup", ip_address=ip_address))
        status = "grace"
    else:
        status = "suspended"
    db.close()
    return render_template("customer/wifi_home.html", customer=customer, status=status)

@app.route("/wifi_access")
def wifi_access_by_ip():
    client_ip = request.remote_addr
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter_by(ip_address=client_ip).first()
        if not customer:
            return f"No customer found for IP {client_ip}", 404
        today = datetime.utcnow()
        subscription_end = customer.start_date + timedelta(days=30)
        grace_end = subscription_end + timedelta(days=customer.grace_days)
        days_left = (subscription_end - today).days
        if 0 < days_left <= 4 and not customer.pre_expiry_popup_shown:
            customer.pre_expiry_popup_shown = True
            db.commit()
            return render_template("customer/pre_expiry_popup.html", customer=customer, days_left=days_left)
        if today <= subscription_end:
            status = "active"
        elif subscription_end < today <= grace_end:
            if not customer.popup_shown:
                return redirect(url_for("grace_popup", ip_address=customer.ip_address))
            status = "grace"
        else:
            status = "suspended"
        return render_template("customer/wifi_home.html", customer=customer, status=status)
    finally:
        db.close()

@app.route("/mark_paid/<ip_address>", methods=["POST"])
def mark_paid(ip_address):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter_by(ip_address=ip_address).first()
        if not customer:
            flash("Customer not found", "danger")
        else:
            customer.start_date = datetime.utcnow()
            customer.grace_days = 0
            customer.popup_shown = False
            customer.status = "active"
            db.commit()
            flash(f"{customer.name} marked as paid. WiFi reset.", "success")
    finally:
        db.close()
    return redirect(url_for("list_customers"))

#=====================export to excel========================
from flask import send_file, request, flash
from openpyxl import Workbook
import io
from sqlalchemy.orm import joinedload

@app.route("/customers/export", methods=["GET"])
def export_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    search_term = request.args.get("search", "").strip()

    db = SessionLocal()
    try:
        query = db.query(Customer).options(joinedload(Customer.network))

        # Apply search filter if present
        if search_term:
            query = query.filter(
                (Customer.account_no.like(f"%{search_term}%")) |
                (Customer.name.like(f"%{search_term}%")) |
                (Customer.ip_address.like(f"%{search_term}%"))
            )

        customers = query.all()

        # Create Excel workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Customers"

        # Header row
        headers = [
            "Account No", "Name", "Phone", "Email", "Location", "IP Address",
            "Billing Amount", "Cable No", "Loop No", "Power Level",
            "Coordinates", "Status", "Created At"
        ]
        ws.append(headers)

        # Data rows
        for c in customers:
            ws.append([
                c.account_no,
                c.name,
                c.phone,
                c.email,
                c.location,
                c.ip_address,
                c.billing_amount,
                c.network.cable_no if c.network else "",
                c.network.loop_no if c.network else "",
                c.network.power_level if c.network else "",
                c.network.coordinates if c.network else "",
                c.status,
                c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
            ])

        # Save workbook to in-memory file
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
def daily_status_check():
    today = datetime.utcnow()
    with SessionLocal() as db:
        customers = db.query(Customer).all()
        for customer in customers:
            subscription_end = customer.start_date + timedelta(days=30)
            grace_end = subscription_end + timedelta(days=customer.grace_days)
            days_left = (subscription_end - today).days
            if today <= subscription_end:
                customer.status = "active"
            elif subscription_end < today <= grace_end:
                customer.status = "grace"
                customer.popup_shown = False
            else:
                customer.status = "suspended"
                customer.popup_shown = True
            if days_left > 4:
                customer.pre_expiry_popup_shown = False
        db.commit()

def run_scheduler():
    while True:
        daily_status_check()
        time.sleep(86400)

threading.Thread(target=run_scheduler, daemon=True).start()

# ==================== RUN APP ====================
if __name__ == "__main__":
    app.run(debug=True)
