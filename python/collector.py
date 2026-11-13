"""

    TODO:
    1) Добавить комментарии
    2) Добавьть логгирование
    3) Небольшой (Почти полный) рефакторинг
    4) Сделать установщик
    5) Отправка IP-Адреса, на котором установлен сборщик

"""

import json
import logging
import os
import socket
import time

import psutil
import requests


CONFIG = "config.json"


def load_config():

    if not os.path.exists(CONFIG):

        server_name = str(input("Server name (default hostname): ").strip() or socket.gethostname())
        webpanel_ip = str(input("Webpanel's IP: ").strip())
        webpanel_port = int(input("Webpanel's port: ").strip())

        config = {
            "server_name": server_name,
            "webpanel_ip": webpanel_ip,
            "webpanel_port": webpanel_port
        }

        with open(CONFIG, "w") as file:
            json.dump(config, file, indent = 4)

        return config

    with open(CONFIG, "r") as file:
        return json.load(file)


config = load_config()

API_URL = f"http://{config["webpanel_ip"]}:{config["webpanel_port"]}/metrics"


def collect_data() :

    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage('/')
    network = psutil.net_io_counters()
    uptime = time.time() - psutil.boot_time()


    def _get_network_transfer_rate(interval = 1.0):
        
        net1 = psutil.net_io_counters()
        sent1, recv1 = net1.bytes_sent, net1.bytes_recv
        time1 = time.monotonic()

        time.sleep(interval)

        net2 = psutil.net_io_counters()
        sent2, recv2 = net2.bytes_sent, net2.bytes_recv
        time2 = time.monotonic()

        elapsed = time2 - time1

        if elapsed <= 0:
            raise ValueError(f"{config["server_name"]} : ValueError -> Invalid spacing")

        sent_rate = (sent2 - sent1) / elapsed
        recv_rate = (recv2 - recv1) / elapsed

        return sent_rate, recv_rate 


    def _hz_to_ghz(hz_value):
        return hz_value / 1000


    def _format_volume(bytes):
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            
            bytes /= 1024.0
        
        return f"{bytes:.1f} TB"


    def _format_rate(bytes_per_sec):

        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            
            if bytes_per_sec < 1024.0:
                return f"{bytes_per_sec:.2f} {unit}"
            
            bytes_per_sec /= 1024.0
        
        return f"{bytes_per_sec:.2f} TB/s"


    upload, download = _get_network_transfer_rate(interval = 1.0)


    def _format_uptime(time):

        days, remainder = divmod(int(time), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []

        if days: parts.append(f"{days}d")
        if hours or days: parts.append(f"{hours}h")

        parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        return " ".join(parts)

    data = {
        "server_name" : config["server_name"],
        "cpu" : {
            "percent" : f"{psutil.cpu_percent(interval = 1):.0f}",
            "cores" : psutil.cpu_count(logical = False),
            "frequency" : f"{_hz_to_ghz(psutil.cpu_freq().current):.2f} Ghz",
            "average_load" : ", ".join(f"{x:.2f}" for x in psutil.getloadavg())
        },
        "memory" : {
            "percent" : f"{memory.percent:.0f}",
            "used" : _format_volume(memory.used),
            "total" : _format_volume(memory.total)
        },
        "swap" : {
            "percent" : f"{swap.percent:.0f}",
            "used" : _format_volume(swap.used),
            "total" : _format_volume(swap.total)
        },
        "storage" : {
            "percent" : f"{disk.percent:.0f}",
            "used" : _format_volume(disk.used),
            "total" : _format_volume(disk.total)
        },
        "network" : {
            "upload" : _format_rate(upload),
            "download" : _format_rate(download),
            "total_send" : _format_volume(network.bytes_sent),
            "total_received" : _format_volume(network.bytes_recv)
        },
        "uptime" : _format_uptime(uptime)
    }

    return data


while True:

    data = collect_data()
    
    try:
        
        response = requests.post(API_URL, json = data, timeout = 5)
        
        print(f"{data['server_name']} : Data sent to {config['webpanel_ip']}:{config['webpanel_port']} (status {response.status_code})")
    
    
    except requests.RequestException as exception:
        print(f"{data['server_name']} : Request error -> {exception}")