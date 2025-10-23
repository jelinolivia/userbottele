import asyncio
import json
import os
import random
import requests
from telethon import TelegramClient, events
from telethon.errors import (SessionPasswordNeededError, PhoneCodeInvalidError, 
                              AuthKeyUnregisteredError, FloodWaitError, 
                              InviteHashExpiredError, UserAlreadyParticipantError)
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from datetime import datetime
import time
import re

CONFIG_FILE = 'userbot_config.json'
API_ID = None
API_HASH = None

class GameFiConversationEngine:
    """Engine percakapan natural seperti manusia asli"""
    
    # Data real GameFi 2025
    REAL_DATA = {
        "games": ["Axie Infinity", "Illuvium", "Big Time", "Off The Grid", "Pixels",
                  "Heroes of Mavia", "Gods Unchained", "Star Atlas", "Gala Games", 
                  "Artyfact", "Guild of Guardians", "Splinterlands"],
        "chains": ["Ronin", "Polygon", "Immutable X", "Immutable zkEVM", "Arbitrum Nova",
                   "Solana", "BNB Chain", "Sui", "Beam", "Flow"],
        "tokens": ["AXS", "RON", "IMX", "ILV", "BIGTIME", "SAND", "MANA", "GALA",
                   "PIXEL", "MAVIA", "GODS", "ATLAS", "BEAM"],
    }
    
    # Starter topics yang varied
    STARTER_TOPICS = [
        "gue lagi research {game} nih, ada yang main juga?",
        "floor price {token} pump {percent}% guys",
        "baru denger {game} partnership sama {brand}",
        "gas fee {chain} murah banget sekarang",
        "{game} update kemarin gimana reviewnya?",
        "ada yang ikutan tournament {game} minggu ini?",
        "ROI {game} masih worth ga ya di 2025?",
        "whales lagi accumulate {token} kayaknya",
        "gue baru flip NFT profit lumayan tadi",
        "{chain} integrate {game} baru aja diannounce",
        "market lagi sideways ya, strategy kalian gimana?",
        "ada news terbaru soal {game}?",
        "grinding {game} masih profitable ga?",
        "tokenomics {token} sustainable menurut kalian?",
        "meta {game} berubah sejak patch terakhir",
    ]
    
    # Off-topic casual (10% chance)
    OFF_TOPICS = [
        "btw ada yang nonton event gaming kemarin?",
        "wkwk lag parah internet gue tadi",
        "udah makan siang belom guys?",
        "capek juga grinding seharian",
        "ada rekomendasi game baru ga?",
        "market crypto lagi gimana nih?",
        "weekend rencana main apa?",
        "gue butuh break dulu kayaknya haha",
        "ada yang tau group discord bagus?",
        "lagi males login game hari ini",
    ]
    
    @staticmethod
    def fill_template(text):
        """Fill dengan data random"""
        replacements = {
            "{game}": random.choice(GameFiConversationEngine.REAL_DATA["games"]),
            "{chain}": random.choice(GameFiConversationEngine.REAL_DATA["chains"]),
            "{token}": random.choice(GameFiConversationEngine.REAL_DATA["tokens"]),
            "{percent}": random.randint(10, 60),
            "{brand}": random.choice(["Ubisoft", "Epic Games", "Samsung", "Sony", "Nvidia"]),
        }
        
        for key, val in replacements.items():
            text = text.replace(key, str(val))
        return text
    
    @staticmethod
    def get_starter():
        """Get starter message"""
        # 10% chance off-topic
        if random.random() < 0.1:
            return random.choice(GameFiConversationEngine.OFF_TOPICS)
        
        topic = random.choice(GameFiConversationEngine.STARTER_TOPICS)
        return GameFiConversationEngine.fill_template(topic)
    
    @staticmethod
    def build_context(history, max_msgs=8):
        """Build context dari history terbaru"""
        recent = history[-max_msgs:] if len(history) > max_msgs else history
        
        context = "PERCAKAPAN TERAKHIR:\n"
        for msg in recent:
            context += f"{msg['name']}: {msg['text']}\n"
        
        return context
    
    @staticmethod
    def create_prompt(context, responder_name, is_reply, target_msg=None):
        """Create AI prompt yang lebih flexible"""
        
        base = f"""Kamu adalah {responder_name}, sedang chat di grup GameFi Telegram.

ATURAN PENTING:
- Bahasa Indonesia casual natural (typo ok, singkatan ok, gaul ok)
- Topik: GameFi 2025 (Axie, Illuvium, Ronin, tokens, NFT trading, P2E)
- JANGAN kaku, JANGAN formal, chat seperti teman biasa
- JANGAN selalu pakai nama orang (kadang pakai, kadang enggak)
- JANGAN ulang kata/frasa yang udah disebut orang lain
- 1-2 kalimat aja (max 100 karakter)
- Emoji: jarang aja, jangan lebay
- Kadang bercanda, kadang serius, kadang nanya, varied!

{context}

"""
        
        if is_reply and target_msg:
            base += f"\nKAMU MAU REPLY: {target_msg['name']}: {target_msg['text']}\n"
            base += "Reply dengan natural (bisa setuju, nanya detail, kasih info tambahan, atau beda pendapat)\n"
        else:
            base += "Kamu mau nambahin topik atau kasih info baru yang nyambung.\n"
        
        base += "\nRESPON SEKARANG (chat natural aja, jangan kaku):"
        
        return base


class GroupManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.groups = []
        self.load_groups()
    
    def load_groups(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.groups = data.get('groups', [])
            except:
                self.groups = []
    
    def save_groups(self):
        try:
            data = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
            data['groups'] = self.groups
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"✗ Error saving: {e}")
    
    def add_group(self, link, name=None):
        if any(g['link'] == link for g in self.groups):
            return False
        self.groups.append({
            'link': link,
            'name': name or link,
            'added_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        self.save_groups()
        return True
    
    def remove_group(self, idx):
        if 0 <= idx < len(self.groups):
            removed = self.groups.pop(idx)
            self.save_groups()
            return removed
        return None
    
    def get_groups(self):
        return self.groups
    
    async def auto_join_groups(self, client, name):
        joined, already, failed = [], [], []
        
        for group in self.groups:
            try:
                link = group['link'].strip()
                
                if 'joinchat/' in link or '+' in link:
                    hash_match = re.search(r'joinchat/([a-zA-Z0-9_-]+)', link) or re.search(r'\+([a-zA-Z0-9_-]+)', link)
                    if hash_match:
                        try:
                            await client(ImportChatInviteRequest(hash_match.group(1)))
                            joined.append(group['name'])
                            await asyncio.sleep(random.uniform(2, 4))
                        except UserAlreadyParticipantError:
                            already.append(group['name'])
                        except InviteHashExpiredError:
                            failed.append(f"{group['name']} (expired)")
                else:
                    username = link.replace('@', '').replace('https://t.me/', '')
                    try:
                        await client(JoinChannelRequest(username))
                        joined.append(group['name'])
                        await asyncio.sleep(random.uniform(2, 4))
                    except UserAlreadyParticipantError:
                        already.append(group['name'])
                
            except FloodWaitError as e:
                print(f"⏳ FloodWait {e.seconds}s...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                failed.append(f"{group['name']}")
        
        return {'joined': joined, 'already_in': already, 'failed': failed}


class UserbotManager:
    def __init__(self):
        self.userbots = []
        self.clients = {}  # {user_id: {'client': ..., 'name': ..., 'username': ...}}
        self.running = False
        self.conversation_history = []
        self.used_topics = set()  # Track topics yang udah dibahas
        self.session_id = f"gf_{int(time.time())}_{random.randint(1000,9999)}"
        self.engine = GameFiConversationEngine()
        self.group_manager = GroupManager(CONFIG_FILE)
        
        # Listener untuk detect external messages
        self.external_messages = []
        self.last_external_check = time.time()
    
    def get_display_name(self, user):
        """Ambil nama display yang proper"""
        if user.last_name:
            return f"{user.first_name} {user.last_name}"
        elif user.first_name:
            return user.first_name
        elif user.username:
            return user.username
        else:
            return f"User{user.id}"
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.userbots = data.get('userbots', [])
                    print(f"✓ Load {len(self.userbots)} userbot")
            except Exception as e:
                print(f"✗ Error: {e}")
                self.userbots = []
        else:
            self.userbots = []
    
    def save_config(self):
        try:
            data = {'userbots': self.userbots}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    existing = json.load(f)
                    if 'groups' in existing:
                        data['groups'] = existing['groups']
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"✗ Error: {e}")
    
    def remove_invalid_userbot(self, phone):
        self.userbots = [u for u in self.userbots if u['phone'] != phone]
        self.save_config()
    
    async def add_userbot(self):
        print("\n=== TAMBAH USERBOT ===")
        
        if not API_ID or not API_HASH:
            print("✗ API_ID dan API_HASH belum diset!")
            return
        
        phone = input("Nomor (contoh: +6281234567890): ").strip()
        
        if any(u['phone'] == phone for u in self.userbots):
            print("✗ Nomor sudah terdaftar!")
            return
        
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.send_code_request(phone)
                code = input("Kode verifikasi: ").strip()
                
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input("Password 2FA: ").strip()
                    await client.sign_in(password=password)
            
            me = await client.get_me()
            session_string = client.session.save()
            
            self.userbots.append({
                'phone': phone,
                'session': session_string,
                'name': me.first_name,
                'username': me.username or "no_username",
                'user_id': me.id
            })
            self.save_config()
            
            display = self.get_display_name(me)
            print(f"✓ Berhasil: {display} (@{me.username})")
            
            await client.disconnect()
            
        except Exception as e:
            print(f"✗ Error: {e}")
    
    async def call_ai(self, prompt):
        """Call AI dengan retry dan validasi"""
        try:
            url = f"https://api.ryzumi.vip/api/ai/deepseek"
            params = {
                'text': prompt,
                'prompt': 'Respond naturally in Indonesian casual language about GameFi topics',
                'session': self.session_id
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', data.get('response', ''))
                
                # Validasi response
                if result and 15 < len(result) < 150:
                    return result.strip()
            
        except Exception as e:
            pass
        
        return None
    
    def get_fallback(self):
        """Fallback response yang varied"""
        fallbacks = [
            "iya juga sih",
            "oh gitu ya",
            "hmm menarik",
            "bener juga",
            "wah ga tau gue",
            "nice info",
            "lumayan ya",
            "gue setuju",
            "sama dong",
            "wait serius?",
            "interesting",
            "makes sense",
        ]
        return random.choice(fallbacks)
    
    async def send_typing(self, client, chat, msg, reply_to=None):
        """Send dengan typing realistic"""
        try:
            words = len(msg.split())
            typing_time = min(words * 0.3 * random.uniform(0.7, 1.3), 4)
            
            async with client.action(chat, 'typing'):
                await asyncio.sleep(typing_time)
            
            sent_msg = await client.send_message(chat, msg, reply_to=reply_to)
            return sent_msg
            
        except Exception as e:
            print(f"✗ Send error: {e}")
            return None
    
    async def check_external_messages(self, chat_id):
        """Cek apakah ada pesan dari user lain (non-bot)"""
        # Implementasi sederhana: ambil message terakhir
        try:
            # Pilih random bot untuk cek
            bot_id = random.choice(list(self.clients.keys()))
            client = self.clients[bot_id]['client']
            
            messages = await client.get_messages(chat_id, limit=5)
            
            external = []
            for msg in messages:
                # Cek jika bukan dari bot kita dan dalam 60 detik terakhir
                if msg.sender_id not in self.clients and msg.text:
                    msg_time = msg.date.timestamp()
                    if time.time() - msg_time < 60:
                        external.append({
                            'sender_id': msg.sender_id,
                            'sender_name': msg.sender.first_name if msg.sender else "User",
                            'text': msg.text,
                            'msg_obj': msg
                        })
            
            return external
            
        except Exception as e:
            return []
    
    async def generate_conversation(self, chat_id):
        """Generate percakapan yang PERFECT NATURAL"""
        
        bot_ids = list(self.clients.keys())
        
        if len(bot_ids) < 2:
            print("✗ Minimal 2 bot")
            return
        
        print(f"\n{'='*60}")
        print(f"🎬 SESI BARU - NATURAL CONVERSATION")
        print(f"{'='*60}\n")
        
        # STARTER
        starter_id = random.choice(bot_ids)
        starter_client = self.clients[starter_id]['client']
        starter_name = self.clients[starter_id]['name']
        
        starter_msg = self.engine.get_starter()
        
        print(f"💬 {starter_name}: {starter_msg}")
        
        sent = await self.send_typing(starter_client, chat_id, starter_msg)
        
        self.conversation_history.append({
            'user_id': starter_id,
            'name': starter_name,
            'text': starter_msg,
            'msg_obj': sent
        })
        
        # Track topik
        for word in starter_msg.lower().split():
            if len(word) > 4:
                self.used_topics.add(word)
        
        await asyncio.sleep(random.uniform(2, 5))
        
        # CONVERSATION LOOP
        num_msgs = random.randint(15, 25)  # Lebih panjang
        prev_id = starter_id
        consecutive_same = 0  # Track berapa kali bot sama
        
        for i in range(num_msgs):
            
            # CEK EXTERNAL MESSAGE setiap 3-5 message
            if i % random.randint(3, 5) == 0:
                external = await self.check_external_messages(chat_id)
                if external:
                    # Ada user lain chat! Respond ke mereka
                    ext_msg = external[0]
                    
                    # Pilih bot untuk respond
                    responder_id = random.choice([bid for bid in bot_ids if bid != prev_id])
                    responder_client = self.clients[responder_id]['client']
                    responder_name = self.clients[responder_id]['name']
                    
                    # Build context untuk respond external
                    context = self.engine.build_context(self.conversation_history)
                    context += f"\n{ext_msg['sender_name']}: {ext_msg['text']}\n"
                    
                    prompt = f"""Kamu {responder_name} di grup GameFi.

{context}

Ada user lain ({ext_msg['sender_name']}) baru chat: "{ext_msg['text']}"

TUGAS: Respond ke {ext_msg['sender_name']} dengan natural (bisa jawab pertanyaan, kasih info, atau nanya balik).
Bahasa Indonesia casual, 1-2 kalimat, max 100 karakter.

RESPOND:"""
                    
                    ai_response = await self.call_ai(prompt)
                    response_text = ai_response if ai_response else f"oh {ext_msg['text']} menarik juga"
                    
                    print(f"📤 {responder_name} ↩️ {ext_msg['sender_name']}: {response_text}")
                    
                    sent = await self.send_typing(responder_client, chat_id, response_text, reply_to=ext_msg['msg_obj'])
                    
                    self.conversation_history.append({
                        'user_id': responder_id,
                        'name': responder_name,
                        'text': response_text,
                        'msg_obj': sent
                    })
                    
                    prev_id = responder_id
                    await asyncio.sleep(random.uniform(1, 3))
                    continue
            
            # PILIH RESPONDER (ANTI SELF-REPLY)
            available = [bid for bid in bot_ids if bid != prev_id]
            
            # Kalau udah 2x berturut-turut sama, FORCE ganti
            if consecutive_same >= 2:
                available = [bid for bid in bot_ids if bid != prev_id]
            
            if not available:
                available = bot_ids
            
            responder_id = random.choice(available)
            
            if responder_id == prev_id:
                consecutive_same += 1
            else:
                consecutive_same = 0
            
            responder_client = self.clients[responder_id]['client']
            responder_name = self.clients[responder_id]['name']
            
            # DECISION: Reply atau standalone
            # 60% reply, 30% standalone, 10% off-topic
            rand = random.random()
            
            if rand < 0.1:  # OFF-TOPIC
                off_msg = random.choice(self.engine.OFF_TOPICS)
                response_text = off_msg
                reply_to = None
                print(f"📤 {responder_name}: {response_text}")
                
            elif rand < 0.7:  # REPLY
                # Pilih target yang BUKAN diri sendiri
                available_history = [h for h in self.conversation_history[-5:] if h['user_id'] != responder_id]
                
                if not available_history:
                    # Ga ada yang bisa direply, standalone
                    context = self.engine.build_context(self.conversation_history)
                    prompt = self.engine.create_prompt(context, responder_name, False)
                    
                    ai_response = await self.call_ai(prompt)
                    response_text = ai_response if ai_response else self.get_fallback()
                    reply_to = None
                    
                else:
                    target = random.choice(available_history)
                    
                    context = self.engine.build_context(self.conversation_history)
                    prompt = self.engine.create_prompt(context, responder_name, True, target)
                    
                    ai_response = await self.call_ai(prompt)
                    response_text = ai_response if ai_response else self.get_fallback()
                    reply_to = target['msg_obj']
                    
                    print(f"📤 {responder_name} ↩️ {target['name']}: {response_text}")
                
            else:  # STANDALONE
                context = self.engine.build_context(self.conversation_history)
                prompt = self.engine.create_prompt(context, responder_name, False)
                
                ai_response = await self.call_ai(prompt)
                response_text = ai_response if ai_response else self.get_fallback()
                reply_to = None
                print(f"📤 {responder_name}: {response_text}")
            
            # SEND MESSAGE
            sent = await self.send_typing(responder_client, chat_id, response_text, reply_to=reply_to)
            
            self.conversation_history.append({
                'user_id': responder_id,
                'name': responder_name,
                'text': response_text,
                'msg_obj': sent
            })
            
            prev_id = responder_id
            
            # NATURAL DELAY (REALISTIC)
            # Instant: 15%, Quick: 50%, Normal: 30%, Slow: 5%
            delay_type = random.choices(
                ['instant', 'quick', 'normal', 'slow'],
                weights=[0.15, 0.50, 0.30, 0.05]
            )[0]
            
            delays = {
                'instant': (0.5, 2),
                'quick': (2, 5),
                'normal': (5, 10),
                'slow': (10, 15)
            }
            
            delay = random.uniform(*delays[delay_type])
            await asyncio.sleep(delay)
        
        print(f"\n{'='*60}")
        print(f"✅ Selesai: {num_msgs} pesan")
        print(f"{'='*60}\n")
    
    async def run_continuous(self, chat_id):
        """Run terus menerus"""
        
        count = 0
        
        try:
            while self.running:
                count += 1
                
                print(f"\n🔥 SESI #{count}")
                
                await self.generate_conversation(chat_id)
                
                # Break time lebih pendek (max 5 menit)
                break_patterns = {
                    'short': (30, 60),      # 30s - 1m
                    'medium': (60, 120),    # 1m - 2m
                    'long': (120, 300),     # 2m - 5m
                }
                
                pattern = random.choices(
                    list(break_patterns.keys()),
                    weights=[0.40, 0.45, 0.15]
                )[0]
                
                break_time = random.uniform(*break_patterns[pattern])
                
                print(f"⏸️  Break {int(break_time)}s ({int(break_time/60)}m {int(break_time%60)}s)\n")
                
                await asyncio.sleep(break_time)
                
                # Reset session kadang
                if random.random() < 0.2:
                    self.session_id = f"gf_{int(time.time())}_{random.randint(1000,9999)}"
                    print(f"🔄 Session reset\n")
                
                # Trim history
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                # Clear used topics
                if len(self.used_topics) > 50:
                    self.used_topics.clear()
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Stop")
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
    
    async def start_all(self):
        """Start semua bot"""
        if len(self.userbots) < 2:
            print("✗ Minimal 2 bot!")
            return
        
        groups = self.group_manager.get_groups()
        if not groups:
            print("✗ Belum ada grup!")
            return
        
        print(f"\n{'='*60}")
        print("📋 GRUP TERSEDIA")
        print(f"{'='*60}")
        for idx, g in enumerate(groups, 1):
            print(f"{idx}. {g['name']}")
        
        choice = input("\nPilih (0 untuk manual): ").strip()
        
        try:
            num = int(choice)
            if num == 0:
                chat = input("Username/ID grup: ").strip()
            elif 1 <= num <= len(groups):
                chat = groups[num-1]['link']
            else:
                print("✗ Invalid!")
                return
        except:
            print("✗ Input angka!")
            return
        
        print(f"\n{'='*60}")
        print("🔌 CONNECTING...")
        print(f"{'='*60}")
        
        for idx, bot in enumerate(self.userbots, 1):
            try:
                print(f"\n[{idx}/{len(self.userbots)}] {bot['phone']}...")
                
                client = TelegramClient(StringSession(bot['session']), API_ID, API_HASH)
                await client.connect()
                
                if await client.is_user_authorized():
                    me = await client.get_me()
                    name = self.get_display_name(me)
                    
                    self.clients[me.id] = {
                        'client': client,
                        'name': name,
                        'username': me.username or "no_username"
                    }
                    
                    print(f"✓ {name} (@{me.username})")
                    
                    result = await self.group_manager.auto_join_groups(client, name)
                    if result['joined']:
                        print(f"  ✓ Joined: {', '.join(result['joined'])}")
                    if result['already_in']:
                        print(f"  ℹ️  Already: {', '.join(result['already_in'])}")
                    
                else:
                    print(f"✗ Not authorized")
                    self.remove_invalid_userbot(bot['phone'])
                
            except AuthKeyUnregisteredError:
                print(f"✗ Invalid session")
                self.remove_invalid_userbot(bot['phone'])
            except Exception as e:
                print(f"✗ Error: {e}")
        
        if len(self.clients) < 2:
            print("\n✗ Kurang bot!")
            return
        
        print(f"\n{'='*60}")
        print(f"✅ {len(self.clients)} BOT READY")
        print(f"{'='*60}")
        for uid, data in self.clients.items():
            print(f"   • {data['name']}")
        
        self.running = True
        
        print(f"\n🎯 Target: {chat}")
        print("🤖 Mode: Perfect Natural Conversation")
        print("✅ NO self-reply, NO repetition, NO kaku")
        print("✅ Respond to external users")
        print("✅ AI-powered varied responses")
        print("🚀 Starting...\n")
        
        try:
            await self.run_continuous(chat)
        finally:
            await self.stop_all()
    
    async def stop_all(self):
        """Stop semua"""
        print("\n🔌 Disconnecting...")
        
        for uid, data in self.clients.items():
            try:
                await data['client'].disconnect()
                print(f"✓ {data['name']} disconnected")
            except Exception as e:
                print(f"✗ Error: {e}")
        
        self.clients.clear()
        self.running = False
        print("✅ All disconnected\n")
    
    def show_userbots(self):
        """Tampilkan daftar userbot"""
        if not self.userbots:
            print("\n📋 Belum ada userbot")
            return
        
        print(f"\n{'='*60}")
        print("📋 DAFTAR USERBOT")
        print(f"{'='*60}")
        
        for idx, bot in enumerate(self.userbots, 1):
            print(f"{idx}. {bot['name']} (@{bot['username']})")
            print(f"   📞 {bot['phone']}")
            if 'user_id' in bot:
                print(f"   🆔 {bot['user_id']}")
            print()
    
    async def delete_userbot(self):
        """Hapus userbot"""
        self.show_userbots()
        
        if not self.userbots:
            return
        
        try:
            choice = int(input("Pilih nomor yang mau dihapus: "))
            
            if 1 <= choice <= len(self.userbots):
                bot = self.userbots[choice - 1]
                confirm = input(f"Yakin hapus {bot['name']}? (y/n): ").lower()
                
                if confirm == 'y':
                    self.userbots.pop(choice - 1)
                    self.save_config()
                    print(f"✓ {bot['name']} dihapus")
            else:
                print("✗ Invalid")
        except ValueError:
            print("✗ Input angka")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    def manage_groups_menu(self):
        """Menu kelola grup"""
        while True:
            groups = self.group_manager.get_groups()
            
            print(f"\n{'='*60}")
            print("📋 KELOLA GRUP")
            print(f"{'='*60}")
            print(f"Total: {len(groups)}\n")
            print("1. ➕ Tambah Grup")
            print("2. 📜 Lihat Grup")
            print("3. 🗑️  Hapus Grup")
            print("4. 🔙 Kembali")
            print(f"{'='*60}")
            
            choice = input("Pilih: ").strip()
            
            if choice == '1':
                self.add_group()
            elif choice == '2':
                self.show_groups()
            elif choice == '3':
                self.delete_group()
            elif choice == '4':
                break
            else:
                print("✗ Invalid!")
    
    def add_group(self):
        """Tambah grup"""
        print("\n=== TAMBAH GRUP ===")
        print("Format:")
        print("  - @username")
        print("  - https://t.me/joinchat/xxxxx")
        print("  - https://t.me/+xxxxx")
        print("  - -1001234567890\n")
        
        link = input("Link/username: ").strip()
        
        if not link:
            print("✗ Kosong!")
            return
        
        name = input("Nama (Enter skip): ").strip()
        
        if self.group_manager.add_group(link, name):
            print(f"✓ Berhasil!")
        else:
            print("✗ Gagal")
    
    def show_groups(self):
        """Tampilkan grup"""
        groups = self.group_manager.get_groups()
        
        if not groups:
            print("\n📋 Belum ada grup")
            return
        
        print(f"\n{'='*60}")
        print("📋 DAFTAR GRUP")
        print(f"{'='*60}")
        
        for idx, g in enumerate(groups, 1):
            print(f"\n{idx}. {g['name']}")
            print(f"   Link: {g['link']}")
            print(f"   Added: {g['added_at']}")
    
    def delete_group(self):
        """Hapus grup"""
        self.show_groups()
        
        groups = self.group_manager.get_groups()
        if not groups:
            return
        
        try:
            choice = int(input("\nPilih nomor: "))
            
            if 1 <= choice <= len(groups):
                g = self.group_manager.remove_group(choice - 1)
                if g:
                    print(f"✓ '{g['name']}' dihapus")
            else:
                print("✗ Invalid")
        except ValueError:
            print("✗ Input angka")
        except Exception as e:
            print(f"✗ Error: {e}")


async def main():
    """Main function"""
    global API_ID, API_HASH
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎮 GAMEFI USERBOT - PERFECT NATURAL 2025 🎮          ║
║                                                           ║
║         ✅ NO Self-Reply (100% Fixed)                    ║
║         ✅ NO Repetition (Smart Tracking)                ║
║         ✅ NO Kaku (AI-Powered Natural)                  ║
║         ✅ Respond to External Users                     ║
║         ✅ Off-Topic Occasionally                        ║
║         ✅ Real Names from Telegram                      ║
║         ✅ Varied Delay (0.5s - 15s max)                 ║
║         ✅ Short Break (30s - 5m max)                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    # Check API
    API_ID = os.getenv('API_ID')
    API_HASH = os.getenv('API_HASH')
    
    if not API_ID or not API_HASH:
        print("⚠️  API_ID dan API_HASH belum diset!")
        print("\n📝 Cara mendapatkan:")
        print("   1. https://my.telegram.org")
        print("   2. Login dengan nomor Telegram")
        print("   3. API Development Tools")
        print("   4. Buat aplikasi baru\n")
        
        API_ID = input("API_ID: ").strip()
        API_HASH = input("API_HASH: ").strip()
        
        if not API_ID or not API_HASH:
            print("✗ Wajib diisi!")
            return
        
        with open('.env', 'w') as f:
            f.write(f"API_ID={API_ID}\n")
            f.write(f"API_HASH={API_HASH}\n")
        
        print("✓ Saved to .env\n")
    
    try:
        API_ID = int(API_ID)
    except ValueError:
        print("✗ API_ID harus angka!")
        return
    
    manager = UserbotManager()
    manager.load_config()
    
    while True:
        print(f"\n{'='*60}")
        print("📋 MENU UTAMA")
        print(f"{'='*60}")
        print("1. 🤖 Tambah Userbot")
        print("2. 📜 Lihat Userbot")
        print("3. 🗑️  Hapus Userbot")
        print("4. 📂 Kelola Grup")
        print("5. 🚀 Start Bot (Perfect Natural)")
        print("6. ❌ Exit")
        print(f"{'='*60}")
        
        choice = input("Pilih: ").strip()
        
        if choice == '1':
            await manager.add_userbot()
        elif choice == '2':
            manager.show_userbots()
        elif choice == '3':
            await manager.delete_userbot()
        elif choice == '4':
            manager.manage_groups_menu()
        elif choice == '5':
            await manager.start_all()
        elif choice == '6':
            print("\n👋 Thank you!")
            print("💡 Pastikan stop bot sebelum exit\n")
            break
        else:
            print("✗ Invalid!")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
