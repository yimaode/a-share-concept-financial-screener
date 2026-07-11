"""akshare 行情、指数和机构持仓特征，用于 CANSLIM 的 L/I/M 维度。"""

from __future__ import annotations

from datetime import date, timedelta
import time

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False


def _as_of_date(as_of_period: str | None) -> date:
    if not as_of_period:
        return date.today()
    year, kind = int(as_of_period[:4]), as_of_period[4:]
    month_day = {"Q1": (3, 31), "H1": (6, 30), "Q3": (9, 30), "A": (12, 31)}
    if kind not in month_day:
        raise ValueError("as_of_period must use YYYYQ1, YYYYH1, YYYYQ3, or YYYYA")
    month, day = month_day[kind]
    return date(year, month, day)


def _close_values(frame) -> list[float]:
    if frame is None or frame.empty:
        return []
    close_column = next((c for c in ("收盘", "close", "收盘价", "Close") if c in frame.columns), None)
    if close_column is None:
        return []
    values: list[float] = []
    for value in frame[close_column].tolist():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric == numeric:
            values.append(numeric)
    return values


def _return(values: list[float], lookback: int = 120) -> float | None:
    if len(values) < min(lookback + 1, 30) or values[-lookback] == 0:
        return None
    return values[-1] / values[-lookback] - 1


def _retry_call(fetcher, *args, **kwargs):
    last_error = None
    for attempt in range(3):
        try:
            return fetcher(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(.5 * (attempt + 1))
    raise last_error


def _stock_history(company_code: str, start: date, end: date):
    try:
        return _retry_call(
            ak.stock_zh_a_hist, symbol=company_code, period="daily",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="qfq",
        )
    except Exception:
        symbol = ("sh" if company_code.startswith("6") else "sz") + company_code
        return _retry_call(
            ak.stock_zh_a_daily, symbol=symbol, start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"), adjust="qfq",
        )


def _index_history(start: date, end: date):
    try:
        return _retry_call(
            ak.stock_zh_index_daily_em, symbol="sh000300",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"),
        )
    except Exception:
        return _retry_call(
            ak.index_zh_a_hist, symbol="000300", period="daily",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"),
        )


def fetch_market_features(company_code: str, as_of_period: str | None = None) -> dict:
    """返回 L(相对强弱)、I(机构持仓)、M(市场方向)的 akshare 原始特征。"""
    result = {
        "company_code": company_code,
        "as_of_period": as_of_period or "latest_available",
        "source": "akshare",
        "leader_relative_strength_6m": None,
        "stock_return_6m": None,
        "index_return_6m": None,
        "institution_holder_count": None,
        "market_above_ma50": None,
        "market_above_ma200": None,
        "warnings": [],
    }
    if not HAS_AKSHARE:
        result["warnings"].append("akshare is not installed")
        return result

    end = _as_of_date(as_of_period)
    start = end - timedelta(days=420)
    stock_return = None
    index_return = None
    try:
        stock_values = _close_values(_stock_history(company_code, start, end))
        stock_return = _return(stock_values)
        result["stock_return_6m"] = stock_return
        if stock_return is None:
            result["warnings"].append("insufficient stock history for relative strength")
    except Exception as exc:
        result["warnings"].append(f"stock market data unavailable: {exc}")

    try:
        index_values = _close_values(_index_history(start, end))
        index_return = _return(index_values)
        result["index_return_6m"] = index_return
        if len(index_values) >= 200:
            ma50 = sum(index_values[-50:]) / 50
            ma200 = sum(index_values[-200:]) / 200
            result["market_above_ma50"] = index_values[-1] > ma50
            result["market_above_ma200"] = index_values[-1] > ma200
        else:
            result["warnings"].append("insufficient index history for market moving averages")
    except Exception as exc:
        result["warnings"].append(f"index market data unavailable: {exc}")

    if stock_return is not None and index_return is not None:
        result["leader_relative_strength_6m"] = stock_return - index_return

    try:
        quarter = f"{end.year}{1 if end.month <= 3 else 2 if end.month <= 6 else 3 if end.month <= 9 else 4}"
        holders = _retry_call(ak.stock_institute_hold_detail, stock=company_code, quarter=quarter)
        result["institution_holder_count"] = 0 if holders is None else int(len(holders))
    except Exception as exc:
        result["warnings"].append(f"institution data unavailable: {exc}")
    return result
