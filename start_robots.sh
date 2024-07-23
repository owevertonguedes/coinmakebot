#!/bin/bash

# Encerra todas as sesões ativas
tmux kill-server

# Inicia uma nova sessão tmux para cada par e executa o robô de trade
# Ex.: tmux new-session -d -s eth "python3 main.py ETHFDUSD 0.4 130 --testnet --cancel_orders"
tmux new-session -d -s floki "python3 main.py FLOKIFDUSD 0.4 500"
# tmux new-session -d -s sol "python3 main.py SOLFDUSD 0.3 100"
# tmux new-session -d -s pepe "python3 main.py PEPEFDUSD 0.3 100"
# tmux new-session -d -s eth "python3 main.py ETHFDUSD 0.3 100"

# Lista todas as sessões tmux ativas
tmux ls
