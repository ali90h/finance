import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/register", methods=["GET", "POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    if request.method == "GET":
        return render_template("register.html")
    else:
        if not username:
            flash("THE USERNAME FIELD CAN NOT BE EMPTY!")
            return apology("Please, provide username", 400)

        elif not password:
            flash("THE PASSWORD FIELD CAN NOT BE EMPTY!")
            return apology("Please, provide username", 400)

        elif not confirmation:
            flash("YOU MUST REPEAT YOUR PASSWORD")
            return apology("Please, provide password", 400)

        elif password != confirmation:
            flash("PASSWORD DON'T MATCH")
            return apology("Please, provide password", 400)

        if password == confirmation:
            hash_p = generate_password_hash(password)
            check = db.execute("SELECT * FROM users WHERE username = ?", username)
            if len(check) != 0:
                flash("This username already exists")
                return apology("Please, provide username", 400)
            else:
                new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_p)
                if not new_user:
                    flash("Query Error")
                    return redirect("/register")

            login = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = login[0]["id"]
            session["username"] = username
            flash("Registered!")
            return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("You must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("You must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = request.form.get("username")

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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        quote = request.form.get("symbol")
        if not quote:
            flash("Search field cannot be empty")
            return apology("Search field cannot be empty", 400)

        search = lookup(quote)
        if not search:
            flash("Query Error")
            return apology("Search field cannot be empty", 400)

        search["price"] = usd(search["price"])

        return render_template("quoted.html", search=search)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            flash("Missing Symbol")
            return apology("Missing Symbol", 400)
        if not shares:
            flash("Missing Shares")
            return apology("Missing Shares", 400)
        if shares.isdigit() == False:
            flash("You can't purchase partial shares")
            return apology("You can't purchase partial shares", 400)
        if shares.isalpha() == True:
            flash("Letters are invalid characters for quantity")
            return apology("Letters are invalid characters for quantity", 400)

        int_shares = int(float(shares))
        if int_shares <= 0:
            flash("Invalid amount of shares")
            return apology("Invalid amount of shares", 400)
# s
        stock = lookup(symbol)
        if not stock:
            flash("Invalid Stock Symbol")
            return apology("Invalid Stock Symbol", 400)
        data = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        if not data:
            flash("Cash Query Failed")
            return apology("Cash Query Failed", 400)

        cash = data[0]["cash"]

        stock_price = round(stock["price"], 2)
        total = stock_price * int_shares

        if (int_shares * stock_price) > cash:
            flash("You don't have enough cash")
            return apology("You don't have enough cash", 400)

        buy = db.execute("INSERT INTO transactions (user_id, symbol, shares, price, total) VALUES (?, ?, ?, ?, ?)",
                         session["user_id"], symbol, shares, stock_price, total)
        if not buy:
            flash("Buy Query Error")
            return apology("Buy Query Error", 400)

        type = "BOUGHT"
        history = db.execute("INSERT INTO history (user_id, type, symbol, shares, price) VALUES (?, ?, ?, ?, ?)",
                             session["user_id"], type, symbol, shares, stock_price)
        if not history:
            flash("History Query Error")
            return apology("History Query Error", 400)

        spend_cash = db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total, session["user_id"])
        if not spend_cash:
            flash("Spending Query Error")
            return apology("Spending Query Error", 400)
        flash("Bought!")
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        symbolsform = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", session["user_id"])
        return render_template("sell.html", symbols=[row["symbol"] for row in symbolsform])
    else:
        symbol = request.form.get("symbol")
        amount = request.form.get("shares")
        transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])

        if not symbol:
            flash("Symbol field cannot be empty")
            return apology("Symbol field cannot be empty")
        if not amount:
            flash("Amount field cannot be empty")
            return apology("Amount field cannot be empty")

        stocks = {}
        for elem in transactions:
            name = elem["symbol"]
            share = elem["shares"]
            for elem in transactions:
                stocks[name] = share
# .
        if not stocks[symbol]:
            flash("Invalid symbol")
            return apology("Invalid symbol")
        if int(amount) > stocks[symbol]:
            flash("You can't sell more shares than you own!")
            return apology("You can't sell more shares than you own!")
# .
        shares = -int(amount)

        stock_price_t = lookup(symbol)
        stock_price = round(stock_price_t["price"], 2)

        # append history table, then remove quantity from transactions
        type = "SOLD"
        history = db.execute("INSERT INTO history (user_id, type, symbol, shares, price) VALUES (?, ?, ?, ?, ?)",
                             session["user_id"], type, symbol, shares, stock_price)
        if not history:
            flash("History Query Error")
            return apology("History Query Error")

        # remove from transactions
        newshares = stocks[symbol] - int(amount)
        db.execute("UPDATE transactions SET shares = ? WHERE user_id = ? AND symbol = ?", newshares, session["user_id"], symbol)
        if newshares == 0:
            db.execute("DELETE FROM transactions WHERE symbol = ?", symbol)

        # add cash
        cashdb = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cashdb[0]["cash"]
        income = int(amount) * stock_price
        new_cash = cash + income

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
        flash("SOLD!")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    historydb = db.execute(
        "SELECT id, type, symbol, shares, price, time FROM history WHERE user_id = ? ORDER BY time DESC", session["user_id"])

    values = {}
    for stock in historydb:
        key = stock['id']
        elem = stock["price"]
        for stock in historydb:
            values[key] = elem

    for elem in values:
        values[elem] = usd(values[elem])

    return render_template("history.html", history=historydb, values=values)


@app.route("/", methods=['GET', 'POST'])
@login_required
def index():

    transactions = db.execute(
        "SELECT symbol, shares, SUM(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])
    cashdb = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    if not cashdb:
        return redirect("/login")
    cash = cashdb[0]["cash"]

    prices = {}
    for stock in transactions:
        test1 = lookup(stock["symbol"])
        price = test1["price"]
        elem = stock["symbol"]
        for stock in transactions:
            prices[elem] = price

    total = {}
    for stock in transactions:
        elem = stock["symbol"]
        value = prices[elem] * stock["shares"]
        for stock in transactions:
            total[elem] = value

    names = {}
    for stock in transactions:
        elem = stock["symbol"]
        name1 = lookup(elem)
        name = name1["name"]
        for stock in transactions:
            names[elem] = name

    totalstocks = sum(total.values())

    allassets = float(cash) + totalstocks

    for elem in prices:
        prices[elem] = usd(prices[elem])

    for elem in total:
        total[elem] = usd(total[elem])

    return render_template("index.html", transactions=transactions, cash=usd(cash), prices=prices, total=total, names=names, allassets=usd(allassets), stock=usd(totalstocks))


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    cashdb = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cashdb[0]["cash"]
    if request.method == "GET":
        return render_template("addcash.html", cash=usd(cash))
    else:
        increase = request.form.get("increase")
        if not increase:
            flash("Deposit value cannot be empty")
            return redirect("/addcash")
        if int(increase) <= 0:
            flash("Value must be bigger than 0")
            return redirect("/addcash")
        new = int(increase) + int(cash)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new, session["user_id"])

        inc = int(increase)
        n = "-"
        type = "ADDED CASH"
        history = db.execute("INSERT INTO history (user_id, type, symbol, shares, price) VALUES (?, ?, ?, ?, ?)",
                             session["user_id"], type, n, n, inc)
        if not history:
            flash("History Query Error")
            return redirect("/addcash")

        flash('Money added successfully')
        return redirect("/addcash")

# ali abd
# ali
# ali
# ali
# ali
# ali
# cs50
# cs50
# cs50
# cs50
# cs50
# cs50
# cs50
# cs50
# cs50
# cs50
# cs50
