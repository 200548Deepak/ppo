from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import sqlite3
from pathlib import Path


DB_PATH = Path(r"E:\Deepak\Work\ppo\completed_orders.db")
LOG_PATH = Path(r"E:\Deepak\Work\ppo\profit_report.log")
IST_OFFSET = timedelta(hours=5, minutes=30)
MONEY_QUANTIZER = Decimal("0.01")
QTY_QUANTIZER = Decimal("0.00000001")


@dataclass
class BuyLot:
    order_number: str
    date: str
    create_time: int
    original_amount: Decimal
    remaining_amount: Decimal
    unit_price: Decimal
    total_price: Decimal


def to_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(QTY_QUANTIZER, rounding=ROUND_HALF_UP)


def ist_date_from_create_time(create_time_ms: int) -> str:
    utc_time = datetime.fromtimestamp(create_time_ms / 1000, tz=timezone.utc)
    return (utc_time + IST_OFFSET).date().isoformat()


def fetch_orders(db_path: Path) -> list[dict[str, object]]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY createTime ASC")
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description or ()]
        return [dict(zip(column_names, row)) for row in rows]
    finally:
        conn.close()


def calculate_profit(orders: list[dict[str, object]]) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]], list[dict[str, object]]]:
    inventory: deque[BuyLot] = deque()
    daily_summary: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "buy_amount": Decimal("0"),
            "sell_amount": Decimal("0"),
            "profit": Decimal("0"),
            "buy_order_numbers": [],
            "sell_order_numbers": [],
            "closed_buy_order_numbers": [],
            "carried_forward_buy_order_numbers": [],
        }
    )
    buy_breakdown: dict[str, dict[str, object]] = {}
    unmatched_sells: list[dict[str, object]] = []

    for order in orders:
        trade_type = str(order.get("tradeType") or "").upper()
        create_time = int(order.get("createTime") or 0)
        date_str = ist_date_from_create_time(create_time)
        amount = to_decimal(order.get("amount"))
        total_price = to_decimal(order.get("totalPrice"))
        unit_price = to_decimal(order.get("unitPrice"))
        order_number = str(order.get("orderNumber") or "")

        if trade_type == "BUY":
            inventory.append(
                BuyLot(
                    order_number=order_number,
                    date=date_str,
                    create_time=create_time,
                    original_amount=amount,
                    remaining_amount=amount,
                    unit_price=unit_price,
                    total_price=total_price,
                )
            )
            daily_summary[date_str]["buy_amount"] += amount
            daily_summary[date_str]["buy_order_numbers"].append(order_number)
            buy_breakdown[order_number] = {
                "date": date_str,
                "create_time": create_time,
                "amount": amount,
                "unit_price": unit_price,
                "total_price": total_price,
                "sold_amount": Decimal("0"),
                "profit": Decimal("0"),
                "remaining_amount": amount,
                "matches": [],
            }
            continue

        if trade_type != "SELL":
            continue

        daily_summary[date_str]["sell_amount"] += amount
        daily_summary[date_str]["sell_order_numbers"].append(order_number)

        remaining_sell_amount = amount
        sell_effective_unit_price = (total_price / amount) if amount else Decimal("0")

        while remaining_sell_amount > 0 and inventory:
            buy_lot = inventory[0]
            matched_amount = min(remaining_sell_amount, buy_lot.remaining_amount)
            buy_effective_unit_price = (
                buy_lot.total_price / buy_lot.original_amount
                if buy_lot.original_amount
                else Decimal("0")
            )
            buy_cost = matched_amount * buy_effective_unit_price
            sell_revenue = matched_amount * sell_effective_unit_price
            profit = sell_revenue - buy_cost

            buy_entry = buy_breakdown[buy_lot.order_number]
            buy_entry["sold_amount"] += matched_amount
            buy_entry["profit"] += profit
            buy_entry["remaining_amount"] = buy_lot.remaining_amount - matched_amount
            buy_entry["matches"].append(
                {
                    "sell_order_number": order_number,
                    "sell_date": date_str,
                    "matched_amount": matched_amount,
                    "buy_unit_price": buy_lot.unit_price,
                    "sell_unit_price": unit_price,
                    "profit": profit,
                }
            )

            daily_summary[date_str]["profit"] += profit

            buy_lot.remaining_amount -= matched_amount
            remaining_sell_amount -= matched_amount

            if buy_lot.remaining_amount <= 0:
                if buy_lot.order_number not in daily_summary[date_str]["closed_buy_order_numbers"]:
                    daily_summary[date_str]["closed_buy_order_numbers"].append(buy_lot.order_number)
                inventory.popleft()

        if remaining_sell_amount > 0:
            unmatched_sells.append(
                {
                    "order_number": order_number,
                    "date": date_str,
                    "remaining_amount": remaining_sell_amount,
                }
            )

        for open_buy_lot in inventory:
            if open_buy_lot.order_number not in daily_summary[date_str]["carried_forward_buy_order_numbers"]:
                daily_summary[date_str]["carried_forward_buy_order_numbers"].append(open_buy_lot.order_number)

    return daily_summary, buy_breakdown, unmatched_sells


def print_report(
    daily_summary: dict[str, dict[str, object]],
    buy_breakdown: dict[str, dict[str, object]],
    unmatched_sells: list[dict[str, object]],
    log_path: Path | None = None,
) -> None:
    output_lines: list[str] = []

    def emit(line: str) -> None:
        output_lines.append(line)
        print(line)

    emit("Daily profit report")

    for date_str in sorted(daily_summary):
        summary = daily_summary[date_str]
        emit(f"\nDate: {date_str}")
        emit(f"  Buy amount: {quantize_qty(summary['buy_amount'])} USDT")
        emit(f"  Sell amount: {quantize_qty(summary['sell_amount'])} USDT")
        emit(f"  Profit: ₹{quantize_money(summary['profit'])}")

        if summary["closed_buy_order_numbers"]:
            emit("  Buy orders fully matched on this day:")
            for order_number in summary["closed_buy_order_numbers"]:
                buy_entry = buy_breakdown[order_number]
                emit(
                    f"    {order_number}: bought {quantize_qty(buy_entry['amount'])} USDT @ ₹{quantize_money(buy_entry['unit_price'])} "
                    f"(total ₹{quantize_money(buy_entry['total_price'])}), sold {quantize_qty(buy_entry['sold_amount'])} USDT, "
                    f"profit ₹{quantize_money(buy_entry['profit'])}"
                )

        if summary["carried_forward_buy_order_numbers"]:
            emit("  Buy orders carried forward to next day:")
            for order_number in summary["carried_forward_buy_order_numbers"]:
                buy_entry = buy_breakdown[order_number]
                if buy_entry["remaining_amount"] <= 0:
                    continue
                emit(
                    f"    {order_number}: remaining {quantize_qty(buy_entry['remaining_amount'])} USDT "
                    f"from original {quantize_qty(buy_entry['amount'])} USDT"
                )

        emit("  Buy order breakdown:")
        for order_number in summary["buy_order_numbers"]:
            buy_entry = buy_breakdown[order_number]
            emit(
                f"    {order_number}: bought {quantize_qty(buy_entry['amount'])} USDT @ ₹{quantize_money(buy_entry['unit_price'])} "
                f"(total ₹{quantize_money(buy_entry['total_price'])}), sold {quantize_qty(buy_entry['sold_amount'])} USDT, "
                f"remaining {quantize_qty(buy_entry['remaining_amount'])} USDT, profit ₹{quantize_money(buy_entry['profit'])}"
            )
            for match in buy_entry["matches"]:
                emit(
                    f"      matched with sell {match['sell_order_number']} on {match['sell_date']}: "
                    f"{quantize_qty(match['matched_amount'])} USDT @ buy ₹{quantize_money(match['buy_unit_price'])} "
                    f"-> sell ₹{quantize_money(match['sell_unit_price'])}, profit ₹{quantize_money(match['profit'])}"
                )

    if unmatched_sells:
        emit("\nUnmatched sell orders:")
        for item in unmatched_sells:
            emit(
                f"  {item['order_number']} on {item['date']} still has {quantize_qty(item['remaining_amount'])} USDT without buy inventory"
            )

    if log_path is not None:
        log_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def main() -> None:
    orders = fetch_orders(DB_PATH)
    daily_summary, buy_breakdown, unmatched_sells = calculate_profit(orders)
    print_report(daily_summary, buy_breakdown, unmatched_sells, log_path=LOG_PATH)
    print(f"\nReport saved to {LOG_PATH}")


if __name__ == "__main__":
    main()