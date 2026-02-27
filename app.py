from flask import Flask, render_template, request, redirect, session
import pandas as pd
import xgboost as xgb

app = Flask(__name__)
app.secret_key = "supersecretkey"

# =============================
# Load Trained Model
# =============================
model = xgb.XGBClassifier()
model.load_model("fraud_model.json")

transaction_history = []

# =============================
# Feature Engineering
# =============================
def prepare_features(data):
    df = pd.DataFrame([data])

    df['origBalanceDiff'] = df['oldbalanceOrg'] - df['newbalanceOrig']
    df['destBalanceDiff'] = df['newbalanceDest'] - df['oldbalanceDest']
    df['isOrigZero'] = (df['oldbalanceOrg'] == 0).astype(int)
    df['isDestZero'] = (df['oldbalanceDest'] == 0).astype(int)
    df['amountToBalanceRatio'] = df['amount'] / (df['oldbalanceOrg'] + 1)

    df = pd.get_dummies(df, columns=['type'], dtype=int)

    expected_cols = model.get_booster().feature_names
    for col in expected_cols:
        if col not in df.columns:
            df[col] = 0

    return df[expected_cols]


# =============================
# Login Page
# =============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "1234":
            session["user"] = username
            return redirect("/dashboard")

    return render_template("index.html")


# =============================
# Dashboard
# =============================
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():

    if "user" not in session:
        return redirect("/")

    probability = None
    expected_loss = None
    result = None
    currency = "INR"

    if request.method == "POST":

        currency = request.form.get("currency", "INR")
        amount = float(request.form.get("amount"))
        oldbalanceOrg = float(request.form.get("oldbalanceOrg"))
        newbalanceOrig = float(request.form.get("newbalanceOrig"))
        oldbalanceDest = float(request.form.get("oldbalanceDest"))
        newbalanceDest = float(request.form.get("newbalanceDest"))
        txn_type = request.form.get("type")

        input_data = {
            "step": 1,
            "amount": amount,
            "oldbalanceOrg": oldbalanceOrg,
            "newbalanceOrig": newbalanceOrig,
            "oldbalanceDest": oldbalanceDest,
            "newbalanceDest": newbalanceDest,
            "type": txn_type
        }

        features = prepare_features(input_data)

        prob = model.predict_proba(features)[0][1]
        probability = round(prob * 100, 2)
        expected_loss = round(amount * prob, 2)

        if probability >= 70:
            result = "High Risk"
        elif probability >= 40:
            result = "Medium Risk"
        else:
            result = "Safe"

        transaction_history.append({
            "amount": amount,
            "probability": probability,
            "result": result
        })

    total_txn = len(transaction_history)
    high_risk = sum(1 for t in transaction_history if t["result"] == "High Risk")

    fraud_rate = round((high_risk / total_txn) * 100, 2) if total_txn > 0 else 0

    currency = request.form.get("currency", "INR")

    return render_template(
    "dashboard.html",
    probability=probability,
    expected_loss=expected_loss,
    result=result,
    currency=currency
)



if __name__ == "__main__":
    app.run(debug=True)
