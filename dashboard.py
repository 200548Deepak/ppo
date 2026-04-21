import os
from decimal import Decimal
from flask import Flask, jsonify, render_template

from ppo import fetch_orders, calculate_profit, DB_PATH

app = Flask(__name__)

def convert_decimals(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(v) for v in obj]
    return obj

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        orders = fetch_orders(DB_PATH)
        daily_summary, buy_breakdown, unmatched_sells = calculate_profit(orders)
        
        # We only need daily_summary for the dashboard currently
        # Convert Decimal values to float for JSON serialization
        serializable_summary = convert_decimals(daily_summary)
        return jsonify(serializable_summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000, debug=True)
