def get_price_filters(client, active_symbol):
    exchange_info = client.exchange_info()
    for symbol in exchange_info['symbols']:
        if symbol['symbol'] == active_symbol:
            for filter in symbol['filters']:
                if filter['filterType'] == 'PRICE_FILTER':
                    return float(filter['tickSize'])

def get_notional_min(client, active_symbol):
    exchange_info = client.exchange_info()
    for symbol in exchange_info['symbols']:
        if symbol['symbol'] == active_symbol:
            for filter in symbol['filters']:
                if filter['filterType'] == 'MIN_NOTIONAL':
                    return float(filter['minNotional'])

def get_lot_size(client, active_symbol):
    exchange_info = client.exchange_info()
    for symbol in exchange_info['symbols']:
        if symbol['symbol'] == active_symbol:
            for filter in symbol['filters']:
                if filter['filterType'] == 'LOT_SIZE':
                    return float(filter['minQty']), float(filter['stepSize'])

def format_quantity(quantity):
    return f"{quantity:.8f}".rstrip('0').rstrip('.')

def adjust_price(price, increment):
    return round(price // increment * increment, 8)

def convert_to_quantity(investment, price, step_size):
    quantity = investment / price
    quantity = (quantity // step_size) * step_size
    return quantity, format_quantity(quantity)