from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from connections import SessionLocal
from models import User, Customer
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.secret_key = "supersecretkey"

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

            # ✅ Special case: Super Admin (hardcoded)
            if username == "admin" and password == "admin123":
                session["user_id"] = "super_admin"
                session["username"] = "admin"
                session["role"] = "super_admin"
                flash("Welcome Super Admin", "success")
                return redirect(url_for("admin_dashboard"))

            # ✅ Normal DB users
            if user and check_password_hash(user.password, password):
                # 🚨 If not super_admin and account inactive
                if user.role != "super_admin" and not user.is_active:
                    flash("Your account is pending approval. Please contact the admin.", "warning")
                    return redirect(url_for("login"))

                # 🚨 Only admins or super_admin allowed
                if user.role not in ["admin", "super_admin"]:
                    flash("Access denied. You are not an admin.", "danger")
                    return redirect(url_for("login"))

                # ✅ Allow login
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


# ==================== USER MANAGEMENT (ADMIN) ====================

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

#pend user
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

#delete user
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



#toggle user active/inactive
@app.route("/toggle_user/<int:user_id>", methods=["POST"])
def toggle_user(user_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.is_active = 1 if user.is_active == 0 else 0
            db.commit()
            flash(f"User '{user.username}' status updated.", "success")
        else:
            flash("User not found.", "danger")
    finally:
        db.close()

    return redirect(url_for("manage_users"))

#registrtion route
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
            # check if username exists
            existing = db.query(User).filter_by(username=username).first()
            if existing:
                flash("Username already taken", "danger")
                return redirect(url_for("register"))

            # create inactive admin
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


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

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

        if not name or not phone or not billing_amount or not ip_address:
            flash("All required fields must be filled.", "warning")
            return redirect(url_for("add_customer"))

        db = SessionLocal()
        try:
            start_date = datetime.utcnow()
            new_customer = Customer(
                name=name,
                phone=phone,
                email=email,
                location=request.form.get("location"),
                ip_address=ip_address,
               
                billing_amount=float(billing_amount),
                start_date=start_date,
                end_date=start_date + timedelta(days=30),
                grace_days=0,
                status="active",
                popup_shown=0
            )
            db.add(new_customer)
            db.commit()
            flash("Customer added successfully!", "success")
            return redirect(url_for("list_customers"))
        finally:
            db.close()

    return render_template("admin/add_new_customer.html")

@app.route("/customers")
def list_customers():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = SessionLocal()
    page = int(request.args.get("page", 1))
    per_page = 5
    query = db.query(Customer)
    total = query.count()
    customers = query.offset((page - 1) * per_page).limit(per_page).all()
    has_next = total > page * per_page
    db.close()
    return render_template("admin/list_customer.html", customers=customers, page=page, has_next=has_next)

@app.route("/edit_customer/<int:customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = SessionLocal()
    customer = db.query(Customer).filter_by(id=customer_id).first()
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
            db.commit()
            flash("Customer updated successfully!", "success")
            return redirect(url_for("list_customers"))
        except Exception as e:
            db.rollback()
            flash(f"Error: {str(e)}", "danger")
        finally:
            db.close()

    db.close()
    return render_template("admin/edit_customer.html", customer=customer)

@app.route("/delete_customer/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            flash("Customer not found", "danger")
        else:
            db.delete(customer)
            db.commit()
            flash("Customer deleted successfully!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("list_customers"))

# ==================== GRACE PERIOD / POPUP ====================
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
        customer.popup_shown = 1
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
        # Grace period: only show popup if not already shown
        if customer.popup_shown == 0:
            db.close()
            return redirect(url_for("grace_popup", ip_address=ip_address))
        status = "grace"
    else:
        # Suspended immediately after grace
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

        if today <= subscription_end:
            status = "active"
        elif subscription_end < today <= grace_end:
            if customer.popup_shown == 0:
                return redirect(url_for("grace_popup", ip_address=customer.ip_address))
            status = "grace"
        else:
            status = "suspended"

        return render_template("customer/wifi_home.html", customer=customer, status=status)
    finally:
        db.close()




# ==================== MARK SUBSCRIPTION AS PAID ====================
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
            customer.popup_shown = 0
            customer.status = "active"
            db.commit()
            flash(f"{customer.name} marked as paid. WiFi reset.", "success")
    finally:
        db.close()

    return redirect(url_for("list_customers"))

def daily_status_check():
    db = SessionLocal()
    try:
        today = datetime.utcnow()
        customers = db.query(Customer).all()
        for customer in customers:
            subscription_end = customer.start_date + timedelta(days=30)
            grace_end = subscription_end + timedelta(days=customer.grace_days)

            if today <= subscription_end:
                customer.status = "active"
                customer.popup_shown = 0
            elif subscription_end < today <= grace_end:
                customer.status = "grace"
            else:
                customer.status = "suspended"
                customer.popup_shown = 1
        db.commit()
    finally:
        db.close()

def run_scheduler():
    while True:
        try:
            daily_status_check()
        except Exception as e:
            print(f"[Scheduler Error] {e}")
        time.sleep(30)


# ==================== RUN DAILY CHECK THREAD ====================
def run_scheduler():
    while True:
        daily_status_check()
       
        time.sleep(30) 

threading.Thread(target=run_scheduler, daemon=True).start()

# ==================== RUN APP ====================
if __name__ == "__main__":
    app.run(debug=True)
