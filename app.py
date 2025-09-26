# ==================== STANDARD LIBRARY ====================
import threading
import time
import random
import io
from datetime import datetime, timedelta

# ==================== FLASK ====================
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file
)

# ==================== THIRD-PARTY ====================
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from sqlalchemy.orm import joinedload

# ==================== LOCAL MODULES ====================
from connections import SessionLocal
from models import User, Customer, CustomerNetwork

# ==================== FLASK APP ====================
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

        return render_template("admin/admin_dashboard.html",
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
        coordinates = request.form.get("coordinates")

        if not name or not phone or not billing_amount or not ip_address or not account_no:
            flash("All required fields must be filled.", "warning")
            return redirect(url_for("add_customer"))

        db = SessionLocal()
        try:
            existing_account = db.query(Customer).filter_by(account_no=account_no).first()
            if existing_account:
                flash(f"Account number {account_no} already exists! Choose a different one.", "danger")
                return redirect(url_for("add_customer"))

            existing_ip = db.query(Customer).filter_by(ip_address=ip_address).first()
            if existing_ip:
                flash(f"IP address {ip_address} has already been assigned to another customer!", "danger")
                return redirect(url_for("add_customer"))

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
            db.commit()

            network = CustomerNetwork(
                customer_id=new_customer.id,
                cable_no=cable_no,
                router_no=router_no,
                loop_no=loop_no,
                power_level=power_level,
                coordinates=coordinates
            )
            db.add(network)
            db.commit()

            flash("Customer added successfully!", "success")
            return redirect(url_for("list_customers"))
        finally:
            db.close()

    return render_template("admin/add_new_customer.html")

# ==================== LIST / EDIT / DELETE CUSTOMERS ====================
@app.route("/customers")
def list_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        page = int(request.args.get("page", 1))
        per_page = 5
        query = db.query(Customer).options(joinedload(Customer.network))
        search_term = request.args.get("search", "").strip()
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

    # 🚫 Prevent user from re-using the grace popup
    if customer.popup_shown:
        db.close()
        flash("Grace period has already been selected.", "warning")
        return redirect(url_for("wifi_access", ip_address=ip_address))

    if request.method == "POST":
        try:
            selected_days = int(request.form.get("grace_days", 1))
            # ✅ Enforce allowed grace days (optional but recommended)
            if selected_days not in [1, 2, 3,4,5]:
                flash("Invalid grace period selected.", "danger")
                return redirect(url_for("grace_popup", ip_address=ip_address))

            customer.grace_days = selected_days
            customer.popup_shown = True
            db.commit()
            flash(f"Grace period selected: {selected_days} day(s)", "success")
            return redirect(url_for("wifi_access", ip_address=ip_address))
        except Exception as e:
            db.rollback()
            flash(f"Error: {str(e)}", "danger")
        finally:
            db.close()
    else:
        db.close()
        return render_template("customer/grace_popup.html", customer=customer)


@app.route("/wifi_access/<ip_address>")
def wifi_access(ip_address):
    db = SessionLocal()
    customer = db.query(Customer).filter_by(ip_address=ip_address).first()
    if not customer:
        db.close()
        return "Customer not found", 404

    today = datetime.utcnow()
    subscription_end = customer.start_date + timedelta(days=30)
    grace_end = subscription_end + timedelta(days=customer.grace_days)
    days_left = (subscription_end - today).days

    status = None
    short_message = None
    detailed_message = None

    if today <= subscription_end:
        status = "active"
        short_message = "Your WiFi subscription is active."

        # Show warning if nearing expiry (2–4 days left)
        if 1 <= days_left <= 4 and not customer.pre_expiry_popup_shown:
            detailed_message = (
                f"Hi {customer.name},<br>"
                f"Your account is going to be due in {days_left} day{'s' if days_left > 1 else ''}.<br>"
                "You can make payment via paybill <strong>4002057</strong><br>"
                f"and account No <strong>{customer.account_no}</strong>.<br>"
                "If already paid, kindly forward Mpesa SMS to <strong>+254 790 924185</strong>."
            )
            customer.pre_expiry_popup_shown = True
            db.commit()

    elif subscription_end < today <= grace_end:
        status = "grace"
        short_message = "Your subscription has expired. Please select a grace period below."

        # Redirect if grace popup not yet shown
        if not customer.popup_shown:
            db.close()
            return redirect(url_for("grace_popup", ip_address=ip_address))

        days_remaining = (grace_end - today).days
        detailed_message = (
            f"Hi {customer.name}, you're currently in the <strong>grace period</strong>.<br>"
            f"{days_remaining} day{'s' if days_remaining != 1 else ''} remaining before suspension.<br>"
            "Please pay as soon as possible to avoid disconnection."
        )

    else:
        status = "suspended"
        short_message = "Your WiFi is suspended. Please contact admin to reset your subscription."
        detailed_message = (
            f"Hi {customer.name}, your account has been <strong>suspended</strong> due to non-payment.<br>"
            "To restore service, pay via paybill <strong>4002057</strong><br>"
            f"Account No: <strong>{customer.account_no}</strong><br>"
            "Then forward Mpesa SMS to <strong>+254 790 924185</strong>."
        )

    db.close()
    return render_template(
        "customer/wifi_home.html",
        customer=customer,
        status=status,
        short_message=short_message,
        detailed_message=detailed_message,
    )



#==================== GRACE AND SUSPENDED CUSTOMER =====================
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

@app.route("/mark_paid/<int:customer_id>", methods=["POST"])
def mark_paid(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    with SessionLocal() as db:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            flash("Customer not found.", "danger")
        else:
            customer.start_date = datetime.utcnow()  
            customer.grace_days = 0
            customer.status = "active"
            customer.popup_shown = False
            customer.pre_expiry_popup_shown = False
            db.commit()
            flash(f"{customer.name} has been marked as paid. Subscription reset.", "success")

    return redirect(url_for("grace_customers"))

# ==================== EXPORT TO EXCEL ====================
@app.route("/customers/export", methods=["GET"])
def export_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    search_term = request.args.get("search", "").strip()
    db = SessionLocal()
    try:
        query = db.query(Customer).options(joinedload(Customer.network))
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
            "Account No", "Name", "Phone", "Email", "Location", "IP Address",
            "Billing Amount", "Cable No", "Loop No", "Power Level",
            "Coordinates", "Status", "Created At"
        ]
        ws.append(headers)
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
from apscheduler.schedulers.background import BackgroundScheduler

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
            else:
                customer.status = "suspended"
                customer.popup_shown = True  

            # Pre-expiry popup logic
            if 1 <= days_left <= 4:
                customer.pre_expiry_popup_shown = False
            else:
                customer.pre_expiry_popup_shown = True

        db.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(daily_status_check, 'cron', hour=0, minute=0)
scheduler.start()


@app.route("/terms")
def terms():
    return render_template("terms.html")  # or return "Terms page"


# ==================== RUN APP ====================
if __name__ == "__main__":
    app.run(debug=True)
