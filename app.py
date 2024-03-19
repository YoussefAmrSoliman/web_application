import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == "POST" or request.method == "GET":
        stocks = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])
        total = []
        total_usd = []
        for purchase in stocks:
            total.append(purchase["price"] * int(purchase["quantaty"]))
        for h in range(len(total)):
            total_usd.append(usd(total[h]))
        for purchase in stocks:
            purchase["price"] = usd(purchase["price"])
        cash = int(db.execute("SELECT cash FROM users WHERE id= ? ", session["user_id"])[0]["cash"])
        total_after = 0
        for purchase in stocks:
            total_after = total_after + (lookup(purchase["symbol"])["price"] * int(purchase["quantaty"]))
        all = usd(cash + total_after)
        cash = usd(cash)
        return render_template("index.html", stocks=stocks, all=all, cash=cash, total_usd=total_usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol") or lookup(request.form.get("symbol")) is None:
            return apology("must provide valid stock symbol", 400)
        if not request.form.get("shares") or not request.form.get("shares").isdigit() or not int(request.form.get("shares")) > 0:
            return apology("must provide positive integer", 400)
        id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id= ? ", id)[0]["cash"]
        stock = lookup(request.form.get("symbol"))
        if cash < (stock["price"] * int(request.form.get("shares"))):
            return apology("there is not enough cash", 400)
        else:
            cash_after = cash - (stock["price"] * int(request.form.get("shares")))
            stocks = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])
            f = False
            s = []
            for i in stocks:
                if i["symbol"] == request.form.get("symbol"):
                    f = True
                    s = i
            if f == False:
                db.execute("INSERT INTO purchases (symbol, price, quantaty, user_id) VALUES(?,?,?,?)",
                           request.form.get("symbol"), stock["price"], int(request.form.get("shares")), id)
            else:
                db.execute("UPDATE purchases SET quantaty = ? WHERE symbol = ?", int(
                    s["quantaty"]) + int(request.form.get("shares")), request.form.get("symbol"))
            db.execute("INSERT INTO history (symbol, price, quantaty, user_id, tran) VALUES(?,?,?,?,?)",
                       request.form.get("symbol"), stock["price"], int(request.form.get("shares")), id, "Buy")
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_after, id)
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == "POST" or request.method == "GET":
        history = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
        return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        stocks = lookup(request.form.get("symbol"))
        if not request.form.get("symbol") or not stocks:
            return apology("must provide stock symbol", 400)
        return render_template("quoted.html", stocks=stocks)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()
    users = db.execute("SELECT username FROM users")
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide unique user name", 400)
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password do not match", 400)
        for user in users:
            if request.form.get("username") == user["username"]:
                return apology("username already taken please enter different username", 400)
        db.execute("INSERT INTO users (username, hash) VALUES(?,?)",
                   request.form.get("username"), generate_password_hash(request.form.get("password")))
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])
    if request.method == "POST":
        id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id= ? ", id)[0]["cash"]
        stock = lookup(request.form.get("symbol"))

        if not stocks:
            return apology("there are no stocks")
        if not request.form.get("symbol"):
            return apology("must select symbol", 400)
        s = int(db.execute("SELECT * FROM purchases WHERE symbol = ?", request.form.get("symbol"))[0]["quantaty"])
        if not request.form.get("shares") or not request.form.get("shares").isdigit() or int(request.form.get("shares")) > s:
            return apology("must provide shares quantaty", 400)

        shares = s - int(request.form.get("shares"))
        if shares > 0:
            db.execute("UPDATE purchases SET quantaty = ? WHERE symbol = ?", shares, request.form.get("symbol"))
        else:
            db.execute("DELETE FROM purchases WHERE symbol=?", request.form.get("symbol"))
        cash_after = cash + stock["price"] * int(request.form.get("shares"))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_after, id)
        db.execute("INSERT INTO sellings (symbol, price, quantaty, user_id) VALUES(?,?,?,?)",
                   request.form.get("symbol"), stock["price"], int(request.form.get("shares")), id)
        db.execute("INSERT INTO history (symbol, price, quantaty, user_id, tran) VALUES(?,?,?,?,?)",
                   request.form.get("symbol"), stock["price"], int(request.form.get("shares")), id, "Sell")
        return redirect("/")
    else:
        return render_template("sell.html", stocks=stocks)
