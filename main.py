import websocket
import traceback
import json
import pandas as pd
import os
import time
from binance.spot import Spot
from dotenv import load_dotenv
from helpers import *
from alert import *
import sys

load_dotenv()

if len(sys.argv) < 4:
    print("Uso: python3 main.py <symbol> <profit_percentage> <investment> [--testnet] [--cancel_orders]")
    sys.exit(1)

active_symbol = sys.argv[1].upper()
profit_percentage = float(sys.argv[2])
investment = float(sys.argv[3])
is_testnet = '--testnet' in sys.argv
cancel_orders = '--cancel_orders' in sys.argv

if is_testnet:
    api_key = os.getenv("TESTNET_API_KEY")
    secret_key = os.getenv("TESTNET_SECRET_KEY")
    base_url = os.getenv("TESTNET_BASE_URL")
else:
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    base_url = os.getenv("BINANCE_BASE_URL")

client = Spot(api_key, secret_key, base_url=base_url)
endpoint = 'wss://stream.binance.com:9443/ws'
our_msg = json.dumps({"method": "SUBSCRIBE", "params": [f"{active_symbol.lower()}@miniTicker"], "id": 1})

current_price = None
buy_order_price = None
buy_order_executed_price = None
sell_order_price = None
quantity = None
formatted_quantity = None

buy_order_placed = False
sell_order_placed = False
buy_order_id = None
sell_order_id = None
sell_orders_realized = 0

tick_size = get_price_filters(client, active_symbol)
notional_min = get_notional_min(client, active_symbol)
min_qty, step_size = get_lot_size(client, active_symbol)

df = pd.DataFrame()

def on_open(ws):
    print("Conexão estabelecida.")
    if cancel_orders:
        cancel_all_open_orders(active_symbol)
    check_existing_orders()
    ws.send(our_msg)

def on_close(ws, close_status_code, close_msg):
    print("Conexão fechada. Tentando reconectar em 5 segundos...")
    time.sleep(5)
    reconnect()

def on_error(ws, error):
    print(f"Ocorreu um erro: {error}. Tentando reconectar em 5 segundos...")
    tb = traceback.format_exc()
    print("Detalhes do erro:\n", tb)
    time.sleep(5)
    reconnect()

def reconnect():
    global ws
    ws = websocket.WebSocketApp(endpoint, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.run_forever()

def cancel_all_open_orders(symbol):
    try:
        result = client.cancel_open_orders(symbol=symbol)
        print(f"Todas as ordens abertas para {symbol} foram canceladas: {result}")
    except Exception as e:
        print(f"Erro ao cancelar ordens abertas: {e}")

def check_existing_orders():
    global buy_order_id, sell_order_id, buy_order_placed, sell_order_placed
    orders = client.get_open_orders(symbol=active_symbol)
    for order in orders:
        if order['side'] == 'BUY' and order['status'] == 'NEW':
            buy_order_id = order['orderId']
            buy_order_placed = True
            print(f"Ordem de compra pendente encontrada: {order}")
        elif order['side'] == 'SELL' and order['status'] == 'NEW':
            sell_order_id = order['orderId']
            sell_order_placed = True
            print(f"Ordem de venda pendente encontrada: {order}")

def on_message(ws, message):
    global df, current_price, buy_order_price, buy_order_executed_price, quantity, formatted_quantity, buy_order_placed, sell_order_placed, buy_order_id, sell_order_id, step_size, tick_size, sell_orders_realized

    out = json.loads(message)
    if 'c' in out:
        out = pd.DataFrame({'price': float(out['c'])}, index=[pd.to_datetime(out['E'], unit='ms')])
        df = pd.concat([df, out], axis=0)
        df = df.tail(5)
        current_price = df['price'].iloc[-1]
        buy_order_price = adjust_price((current_price * (1 - profit_percentage / 100)), tick_size)
        print(f"Preço atual: {current_price:.10f}")

        if buy_order_placed and buy_order_id and not sell_order_placed and not sell_order_id:
            if check_order_status("buy"):
                print("Ordem de compra executada.")
                buy_order = client.get_order(symbol=active_symbol, orderId=buy_order_id)
                buy_order_executed_price = float(buy_order['price'])
                try:
                  alert("execução de ordem de compra", buy_order['origQty'], active_symbol, buy_order['price'])
                except Exception as e:
                  print(f"Erro ao enviar alerta: {e}")
                place_sell_order()     
            return
        
        if sell_order_placed and sell_order_id and not buy_order_id:
            if check_order_status("sell"):
              print("Ordem de venda executada. Aguardando o tempo de reset (30s).")
              sell_order = client.get_order(symbol=active_symbol, orderId=sell_order_id)
              
              sell_price = float(sell_order['price'])
              quantity = float(sell_order['origQty'])
              profit = float((sell_price - buy_order_executed_price) * quantity)

              realized_profit_percentage = float(((sell_price / buy_order_executed_price) - 1) * 100)
              sell_orders_realized += 1

              try:
                  alert("execução de ordem de venda", quantity, active_symbol, sell_price, profit, realized_profit_percentage, sell_orders_realized)
              except Exception as e:
                  print(f"Erro ao enviar alerta: {e}")
              
              time.sleep(30)
              sell_order_placed = False
              buy_order_placed = False
              buy_order_id = None
              sell_order_id = None
            else:
              print("A ordem de venda foi criada com sucesso, aguardando a execução.")
              return

        if buy_order_placed or sell_order_placed:
            print("A ordem de compra já foi criada.")
            return
        if buy_order_placed and sell_order_placed:
            print("A ordem de venda já foi criada.")
            return

        quantity, formatted_quantity = convert_to_quantity(investment, buy_order_price, step_size)
        order = place_buy_order()
       
        if not order:
            print("Ordem de compra não foi criada.")
            return

def place_buy_order():
    global current_price, buy_order_price, quantity, formatted_quantity, buy_order_placed, buy_order_id, sell_order_id
    if current_price is not None:
        try:  
            order = client.new_order(
                symbol=active_symbol,
                side='BUY',
                type='LIMIT',
                timeInForce='GTC',
                quantity=formatted_quantity,
                price=f"{buy_order_price:.10f}".rstrip('0').rstrip('.')
            )
            print(f"Ordem de compra criada: {order}")
            buy_order_placed = True
            sell_order_id = False
            buy_order_id = order['orderId']
            try:
              alert("criação de ordem de compra", order['origQty'], active_symbol, order['price'])
            except Exception as e:
              print(f"Erro ao enviar alerta: {e}")
            
            return order   
        except Exception as e:
            print(f"Erro ao criar ordem de compra: {e}")
            exit()

def place_sell_order():
    global current_price, quantity, formatted_quantity, buy_order_id, sell_order_id, sell_order_placed, sell_order_price
    sell_order_price = adjust_price((current_price * (1 + profit_percentage / 100)), tick_size)

    print(f"Preço de venda: {sell_order_price:.10f}, Preço de compra: {buy_order_price:.10f}")

    try:
        order = client.new_order(
            symbol=active_symbol,
            side='SELL',
            type='LIMIT',
            timeInForce='GTC',
            quantity=formatted_quantity,
            price=f"{sell_order_price:.10f}".rstrip('0').rstrip('.')
        )
        print(f"Ordem de venda criada: {order}")
        sell_order_placed = True
        buy_order_id = None
        sell_order_id = order['orderId']
        try:
            alert("criação de ordem de venda", order['origQty'], active_symbol, order['price'])
        except Exception as e:
            print(f"Erro ao enviar alerta: {e}")
    except Exception as e:
        print(f"Erro ao criar ordem de venda: {e}")

def check_order_status(type):
    global buy_order_id, sell_order_id
    if buy_order_id and type == "buy":
        try:
            order_status = client.get_order(symbol=active_symbol, orderId=buy_order_id)
            print(f"Status da ordem de compra: {order_status['status']}")
            if order_status['status'] == 'FILLED':
                return True
        except Exception as e:
            print(f"Erro ao verificar status da ordem: {e}")
    elif sell_order_id and type == "sell":
        try:
            order_status = client.get_order(symbol=active_symbol, orderId=sell_order_id)
            print(f"Status da ordem de venda: {order_status['status']}")
            if order_status['status'] == 'FILLED':
                return True
        except Exception as e:
            print(f"Erro ao verificar status da ordem: {e}")
    return False

ws = websocket.WebSocketApp(endpoint, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
ws.run_forever()
