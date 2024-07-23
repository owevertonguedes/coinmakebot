import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("EVOLUTION_API_KEY")

def alert(action, amount, active, price, profit=None, profit_percentage=None,sell_orders_realized=None):
    
    if not api_key:
        print("Erro: API Key não encontrada")
        return

    url = "https://api.flowads.io/message/sendText/weverton"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "apikey": api_key
    }

    amount = float(amount)
    price = float(price)

    message = f"Hey, foi feita uma {action} de {active}.\nPreço: {price:.8f}. Valor: {amount * price:.8f} USD"

    if profit is not None:
        profit = float(profit)
        profit_percentage = float(profit_percentage)
        sell_orders_realized = float(sell_orders_realized)

        message += f"\nLucro: {profit:.2f}\nPorcentagem de Lucro: {profit_percentage:.2f}%\nOrdens de venda realizadas com sucesso: {sell_orders_realized}"

    body = {
        "number": "5582987163633",
        "textMessage": {
            "text": message
        },
        "options": {
            "delay": 0
        }
    }

 

    try:
        response = requests.post(url, headers=headers, json=body)
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)
        return response.status_code, response.text
    except requests.exceptions.RequestException as e:
        print("Erro ao enviar requisição:", e)
        return None, str(e)