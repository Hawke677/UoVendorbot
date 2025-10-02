import requests
import time
import json
import os
from datetime import datetime
import threading

# Configurazione
BOT_TOKEN = "8145701044:AAHOvgsMRt-NKrdfF0h2uVsliXKnZpkfrtM"
CHAT_ID = 235744599
SEARCHES_FILE = "bot_searches.json"
CREDS_FILE = "bot_creds.json"

class UOVendorBot:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
        self.session = requests.Session()
        self.searches = []
        self.monitoring_threads = {}
        self.logged_in = False
        self.last_update_id = 0
        
        self.load_data()
        self.log("Bot avviato")
    
    def log(self, msg):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {msg}")
        try:
            with open("bot_log.txt", 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {msg}\n")
        except:
            pass
    
    def send_message(self, text):
        try:
            requests.post(f"{self.base_url}/sendMessage", 
                         json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
        except Exception as e:
            self.log(f"Errore invio messaggio: {e}")
    
    def load_data(self):
        try:
            if os.path.exists(SEARCHES_FILE):
                with open(SEARCHES_FILE, 'r') as f:
                    self.searches = json.load(f)
            if os.path.exists(CREDS_FILE):
                with open(CREDS_FILE, 'r') as f:
                    creds = json.load(f)
                    self.do_login(creds['email'], creds['password'])
        except Exception as e:
            self.log(f"Errore caricamento dati: {e}")
    
    def save_searches(self):
        try:
            with open(SEARCHES_FILE, 'w') as f:
                json.dump(self.searches, f, indent=2)
        except Exception as e:
            self.log(f"Errore salvataggio: {e}")
    
    def save_creds(self, email, password):
        try:
            with open(CREDS_FILE, 'w') as f:
                json.dump({"email": email, "password": password}, f)
        except Exception as e:
            self.log(f"Errore salvataggio credenziali: {e}")
    
    def do_login(self, email, password):
        try:
            resp = self.session.post("https://portal.uooutlands.com/api/user/login",
                                    json={"email": email, "password": password},
                                    headers={"Content-Type": "application/json"},
                                    timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                if 'jwt' in data:
                    self.session.headers.update({'Authorization': f'Bearer {data["jwt"]}'})
                    self.logged_in = True
                    self.save_creds(email, password)
                    self.log(f"Login effettuato: {email}")
                    return True
            return False
        except Exception as e:
            self.log(f"Errore login: {e}")
            return False
    
    def check_vendor(self, search):
        item = search['item'].lower()
        max_price = search['price']
        
        try:
            resp = self.session.post("https://portal.uooutlands.com/api/VendorSearch/Search",
                                    json={"page": 0, "pageSize": 20, "sortName": "Price", "sortAscending": True,
                                          "filterParams": {"name": item, "category": 0, "propertyFilters": []}},
                                    headers={"Content-Type": "application/json", "Accept": "application/json",
                                            "Origin": "https://portal.uooutlands.com", 
                                            "Referer": "https://portal.uooutlands.com/vendor-search"},
                                    timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                found = [i for i in items if i.get('price', 0) <= max_price]
                
                if found:
                    self.log(f"Trovati {len(found)} {item}")
                    msg = f"🎯 <b>Trovati {len(found)} {item}!</b>\n\n"
                    
                    for i in found[:5]:  # Max 5 risultati per non intasare
                        x, y = i.get('vendorLocationX', 0), i.get('vendorLocationY', 0)
                        msg += f"📦 <b>{i.get('name')}</b>\n"
                        msg += f"💰 Prezzo: {i.get('price')}gp\n"
                        msg += f"👤 Vendor: {i.get('vendorName')}\n"
                        msg += f"🏪 Shop: {i.get('shopName', '-')}\n"
                        msg += f"📍 Coords: ({x}, {y})\n\n"
                    
                    if len(found) > 5:
                        msg += f"... e altri {len(found) - 5} risultati"
                    
                    self.send_message(msg)
                else:
                    self.log(f"Nessun {item} trovato")
            elif resp.status_code in [401, 403]:
                self.log("Sessione scaduta")
                self.send_message("⚠️ Sessione scaduta! Usa /login per riautenticarti")
                search['running'] = False
        except Exception as e:
            self.log(f"Errore controllo {item}: {e}")
    
    def monitor_loop(self, search_id):
        search = self.searches[search_id]
        self.log(f"Avviato monitoraggio: {search['item']}")
        
        while search.get('running', False):
            self.check_vendor(search)
            
            interval = search.get('interval', 300)
            for _ in range(interval):
                if not search.get('running', False):
                    break
                time.sleep(1)
        
        self.log(f"Fermato monitoraggio: {search['item']}")
    
    def handle_command(self, text):
        import re
        
        # Parser migliorato per gestire virgolette
        if text.startswith('/add'):
            parts = re.findall(r'"([^"]*)"|(\S+)', text)
            parts = [p[0] if p[0] else p[1] for p in parts]
        else:
            parts = text.split()
        
        cmd = parts[0].lower()
        
        if cmd == "/start":
            msg = """🎮 <b>UO Outlands Vendor Monitor Bot</b>

Comandi disponibili:

<b>Autenticazione:</b>
/login [email] [password] - Accedi al portale

<b>Gestione ricerche:</b>
/add [oggetto] [prezzo] [intervallo] - Aggiungi ricerca
/list - Mostra ricerche attive
/start_search [id] - Avvia ricerca
/pause_search [id] - Metti in pausa
/remove [id] - Elimina ricerca
/startall - Avvia tutte
/pauseall - Pausa tutte

<b>Info:</b>
/status - Stato bot
/help - Questa guida

Esempio: /add "lyric aspect core" 25000 300"""
            self.send_message(msg)
        
        elif cmd == "/help":
            self.handle_command("/start")
        
        elif cmd == "/login":
            if len(parts) < 3:
                self.send_message("Uso: /login email password")
                return
            
            email = parts[1]
            password = parts[2]
            
            if self.do_login(email, password):
                self.send_message("✅ Login effettuato con successo!")
            else:
                self.send_message("❌ Login fallito. Controlla le credenziali.")
        
        elif cmd == "/add":
            if not self.logged_in:
                self.send_message("⚠️ Devi prima fare login con /login")
                return
            
            if len(parts) < 3:
                self.send_message("Uso: /add \"oggetto\" prezzo [intervallo]\nEsempio: /add \"lyric aspect core\" 25000 300")
                return
            
            # parts[0] = /add, parts[1] = oggetto, parts[2] = prezzo, parts[3] = intervallo
            item = parts[1]
            try:
                price = int(parts[2])
                interval = int(parts[3]) if len(parts) > 3 else 300
                
                if interval < 30 or interval > 600:
                    self.send_message("⚠️ Intervallo deve essere tra 30 e 600 secondi")
                    return
                
                search_id = len(self.searches)
                self.searches.append({
                    'id': search_id,
                    'item': item,
                    'price': price,
                    'interval': interval,
                    'running': False
                })
                
                self.save_searches()
                self.send_message(f"✅ Ricerca aggiunta!\n📦 {item}\n💰 Max: {price}gp\n⏱️ Intervallo: {interval}s\nID: {search_id}")
            except (ValueError, IndexError) as e:
                self.send_message(f"❌ Errore: {e}\nUso corretto: /add \"oggetto\" prezzo [intervallo]")
        
        elif cmd == "/list":
            if not self.searches:
                self.send_message("Nessuna ricerca attiva")
                return
            
            msg = "<b>📋 Ricerche attive:</b>\n\n"
            for s in self.searches:
                status = "▶️ In esecuzione" if s.get('running') else "⏸️ In pausa"
                msg += f"ID {s['id']}: {s['item']}\n"
                msg += f"💰 Max: {s['price']}gp\n"
                msg += f"⏱️ Intervallo: {s['interval']}s\n"
                msg += f"Status: {status}\n\n"
            
            self.send_message(msg)
        
        elif cmd == "/start_search":
            if len(parts) < 2:
                self.send_message("Uso: /start_search [id]")
                return
            
            try:
                search_id = int(parts[1])
                if search_id < 0 or search_id >= len(self.searches):
                    self.send_message("❌ ID non valido")
                    return
                
                search = self.searches[search_id]
                if search.get('running'):
                    self.send_message("⚠️ Ricerca già in esecuzione")
                    return
                
                search['running'] = True
                thread = threading.Thread(target=self.monitor_loop, args=(search_id,), daemon=True)
                self.monitoring_threads[search_id] = thread
                thread.start()
                
                self.send_message(f"▶️ Avviata ricerca: {search['item']}")
            except ValueError:
                self.send_message("❌ ID deve essere un numero")
        
        elif cmd == "/pause_search":
            if len(parts) < 2:
                self.send_message("Uso: /pause_search [id]")
                return
            
            try:
                search_id = int(parts[1])
                if search_id < 0 or search_id >= len(self.searches):
                    self.send_message("❌ ID non valido")
                    return
                
                search = self.searches[search_id]
                search['running'] = False
                self.send_message(f"⏸️ Messa in pausa: {search['item']}")
            except ValueError:
                self.send_message("❌ ID deve essere un numero")
        
        elif cmd == "/remove":
            if len(parts) < 2:
                self.send_message("Uso: /remove [id]")
                return
            
            try:
                search_id = int(parts[1])
                if search_id < 0 or search_id >= len(self.searches):
                    self.send_message("❌ ID non valido")
                    return
                
                search = self.searches[search_id]
                search['running'] = False
                removed = self.searches.pop(search_id)
                
                # Riassegna ID
                for i, s in enumerate(self.searches):
                    s['id'] = i
                
                self.save_searches()
                self.send_message(f"🗑️ Rimossa ricerca: {removed['item']}")
            except ValueError:
                self.send_message("❌ ID deve essere un numero")
        
        elif cmd == "/startall":
            count = 0
            for search in self.searches:
                if not search.get('running'):
                    search['running'] = True
                    thread = threading.Thread(target=self.monitor_loop, args=(search['id'],), daemon=True)
                    self.monitoring_threads[search['id']] = thread
                    thread.start()
                    count += 1
            
            self.send_message(f"▶️ Avviate {count} ricerche")
        
        elif cmd == "/pauseall":
            count = 0
            for search in self.searches:
                if search.get('running'):
                    search['running'] = False
                    count += 1
            
            self.send_message(f"⏸️ Messe in pausa {count} ricerche")
        
        elif cmd == "/status":
            status = "✅ Autenticato" if self.logged_in else "❌ Non autenticato"
            running = sum(1 for s in self.searches if s.get('running'))
            
            msg = f"<b>📊 Status Bot</b>\n\n"
            msg += f"Autenticazione: {status}\n"
            msg += f"Ricerche totali: {len(self.searches)}\n"
            msg += f"Ricerche attive: {running}\n"
            
            self.send_message(msg)
        
        else:
            self.send_message("❌ Comando non riconosciuto. Usa /help per la lista comandi")
    
    def get_updates(self):
        try:
            resp = requests.get(f"{self.base_url}/getUpdates", 
                               params={"offset": self.last_update_id + 1, "timeout": 30})
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok'):
                    for update in data.get('result', []):
                        self.last_update_id = update['update_id']
                        
                        if 'message' in update and 'text' in update['message']:
                            chat_id = update['message']['chat']['id']
                            if chat_id == CHAT_ID:
                                text = update['message']['text']
                                self.log(f"Comando ricevuto: {text}")
                                self.handle_command(text)
        except Exception as e:
            self.log(f"Errore get_updates: {e}")
    
    def run(self):
        self.send_message("🤖 Bot avviato e pronto!")
        self.log("Bot in ascolto...")
        
        while True:
            try:
                self.get_updates()
            except KeyboardInterrupt:
                self.log("Bot fermato")
                break
            except Exception as e:
                self.log(f"Errore nel loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    bot = UOVendorBot()
    bot.run()