#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, time, json, subprocess, requests, urllib.parse
from seleniumbase import SB

# ===================== 环境变量配置 =====================
EMAIL        = os.environ.get("KATABUMP_EMAIL") or ""
PASSWORD     = os.environ.get("KATABUMP_PASSWORD") or ""
DISCORD_TOKEN= os.environ.get("DISCORD_TOKEN") or ""          # Discord Token（备用登录）
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""

BASE_URL = "https://dashboard.katabump.com"

# 解析 Discord Token（支持逗号分隔，取最后一个）
DC_TOKEN = ""
if DISCORD_TOKEN:
    _parts = DISCORD_TOKEN.split(",", 1)
    DC_TOKEN = _parts[-1].strip()

_LOGIN_METHOD = "邮箱密码"   # 记录实际登录方式，用于通知

# ===================== Telegram 通知模块（支持截图） =====================
def _send_tg_message(text: str):
    """发送纯文本通知（内部函数）"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"⚠️ Telegram 文本通知异常: {e}")

def send_tg_alert(status_icon: str, status_text: str, extra: str = "",
                  photo_path: str = None):
    """
    统一通知入口：
    - 必发送文本通知（包含状态、账户、登录方式等）
    - 若提供 photo_path（截图文件路径），则额外发送带标题的图片
    """
    # 构造文本消息
    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    if '@' in EMAIL:
        name, domain = EMAIL.split('@', 1)
        masked = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked = EMAIL[:2] + '****'

    text = (
        f"🇫🇷 katabump 续期通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 续期账户: {masked}\n"
        f"🔐 登录方式: {_LOGIN_METHOD}\n"
        f"⏱️ 续期时间: {current_time_str}"
    )
    if extra:
        text += f"\n📝 {extra}"

    # 先发送纯文本（无论有无截图）
    _send_tg_message(text)

    # 如果有截图，发送图片（附带简短说明）
    if photo_path and os.path.exists(photo_path):
        print(f"📸 正在通过 Telegram 发送截图: {photo_path}")
        try:
            with open(photo_path, "rb") as img:
                requests.post(
                    f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto",
                    data={"chat_id": TG_CHAT_ID, "caption": f"{status_icon} {status_text}"},
                    files={"photo": img},
                    timeout=20
                )
            print("✅ 截图已发送")
        except Exception as e:
            print(f"⚠️ 截图发送异常: {e}")

# ===================== Discord OAuth 备用登录（简化无 state） =====================
DISCORD_CLIENT_ID   = "1127907091324080218"                # Katabump 的 Discord 应用 ID
OAUTH_REDIRECT_URI  = "https://dashboard.katabump.com/auth/discord"
OAUTH_SCOPE         = "email identify guilds.join"
DISCORD_API         = "https://discord.com/api/v9/oauth2/authorize"
DISCORD_UA          = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

def discord_authorize(state: str = "") -> str:
    """用 DC_TOKEN 完成 Discord 侧授权，返回回调 URL（state 可空）"""
    query = urllib.parse.urlencode({
        "client_id":     DISCORD_CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  OAUTH_REDIRECT_URI,
        "scope":         OAUTH_SCOPE,
        "state":         state,
    })
    authorize_url = f"{DISCORD_API}?{query}"

    headers = {
        "accept":           "*/*",
        "authorization":    DC_TOKEN,
        "content-type":     "application/json",
        "origin":           "https://discord.com",
        "referer":          f"https://discord.com/oauth2/authorize?{urllib.parse.urlencode({'client_id': DISCORD_CLIENT_ID, 'redirect_uri': OAUTH_REDIRECT_URI, 'response_type': 'code', 'scope': OAUTH_SCOPE, 'state': state})}",
        "user-agent":       DISCORD_UA,
        "x-discord-locale": "zh-CN",
    }

    body = json.dumps({
        "permissions": "0",
        "authorize": True,
        "integration_type": 0,
        "location_context": {
            "guild_id": "10000",
            "channel_id": "10000",
            "channel_type": 10000,
        },
    })

    try:
        resp = requests.post(authorize_url, headers=headers, data=body, timeout=20)
        if resp.status_code != 200:
            print(f"❌ Discord 授权失败: {resp.status_code} - {resp.text[:200]}")
            return ""
        location = resp.json().get("location", "")
        if not location:
            print("❌ 响应中无 location 字段")
            return ""
        print("✅ 获取回调 URL（已脱敏）")
        return location
    except Exception as e:
        print(f"❌ Discord 授权异常: {e}")
        return ""

def do_discord_login(sb) -> bool:
    """通过 Discord Token 完成 Katabump 登录（无 state 模式）"""
    global _LOGIN_METHOD
    _LOGIN_METHOD = "Discord Token"
    print("\n🔑 尝试 Discord 登录（无 state）...")

    callback_url = discord_authorize(state="")
    if not callback_url:
        return False

    print("↩️ 打开回调链接...")
    sb.uc_open_with_reconnect(callback_url, reconnect_time=4)
    time.sleep(3)

    # 等待跳转到 dashboard
    for _ in range(30):
        url = sb.get_current_url()
        title = sb.get_title() or ""
        if url.startswith(BASE_URL + "/dashboard") or "Dashboard | KataBump" in title:
            print(f"✅ Discord 登录成功！当前页面：{url}")
            return True
        time.sleep(0.5)

    print(f"❌ 登录超时，最终 URL：{url}")
    sb.save_screenshot("discord_timeout.png")
    send_tg_alert("❌", "Discord 登录失败", "超时或跳转异常", "discord_timeout.png")
    return False

# ===================== 原 Katabump 邮箱登录 + 续期 =====================
# 以下 JavaScript 片段保持不变（展开 Turnstile、检测等）
_EXPAND_JS = """
(function() {
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    if (!ts) return 'no-turnstile';
    var el = ts;
    for (var i = 0; i < 20; i++) {
        el = el.parentElement;
        if (!el) break;
        var s = window.getComputedStyle(el);
        if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden')
            el.style.overflow = 'visible';
        el.style.minWidth = 'max-content';
    }
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    return 'done';
})()
"""

_EXISTS_JS = """
(function(){
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

_WININFO_JS = """
(function(){
    return {
        sx: window.screenX || 0,
        sy: window.screenY || 0,
        oh: window.outerHeight,
        ih: window.innerHeight
    };
})()
"""

_ALTCHA_EXPAND_JS = """
(function() {
    var modal = document.querySelector('div.modal.show') || document;
    var iframes = modal.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            iframes[i].style.width  = '300px';
            iframes[i].style.height = '150px';
            iframes[i].style.minWidth  = '300px';
            iframes[i].style.minHeight = '150px';
            iframes[i].style.visibility = 'visible';
            iframes[i].style.opacity = '1';
            var el = iframes[i];
            for (var j = 0; j < 10; j++) {
                el = el.parentElement;
                if (!el) break;
                el.style.overflow = 'visible';
            }
            var r2 = iframes[i].getBoundingClientRect();
            return { cx: Math.round(r2.x + 30), cy: Math.round(r2.y + r2.height / 2) };
        }
    }
    return null;
})()
"""

_ALTCHA_SOLVED_JS = """
(function(){
    var modal = document.querySelector('div.modal.show') || document;
    var inputs = modal.querySelectorAll('input[type="hidden"]');
    for (var i = 0; i < inputs.length; i++) {
        var n = (inputs[i].name || '').toLowerCase();
        if ((n.includes('altcha') || n.includes('captcha')) &&
            inputs[i].value && inputs[i].value.length > 20) return true;
    }
    var cbs = modal.querySelectorAll('input[type="checkbox"]');
    for (var j = 0; j < cbs.length; j++) {
        if (cbs[j].disabled) return true;
    }
    var w = modal.querySelector('[data-state="verified"],.altcha--verified,.altcha-verified');
    if (w) return true;
    return false;
})()
"""

def js_fill_input(sb, selector: str, text: str):
    safe = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (setter) setter.call(el, "{safe}");
        else el.value = "{safe}";
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)

def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]], timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except:
            pass
    try:
        subprocess.run(["xdotool", "getactivewindow", "windowactivate"], timeout=3, stderr=subprocess.DEVNULL)
    except:
        pass

def _xdotool_click(x: int, y: int):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)], timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, stderr=subprocess.DEVNULL)
    except:
        os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")

def handle_turnstile(sb) -> bool:
    print("🔍 处理 Cloudflare Turnstile 验证...")
    time.sleep(2)
    if sb.execute_script(_SOLVED_JS):
        print("✅ 已静默通过")
        return True
    for _ in range(3):
        try: sb.execute_script(_EXPAND_JS)
        except: pass
        time.sleep(0.5)
    for attempt in range(6):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 通过（第 {attempt} 次尝试）")
            return True
        print(f"🖱️ 第 {attempt + 1} 次调用 uc_gui_click_captcha...")
        try:
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f"⚠️ 调用异常: {e}")
        for _ in range(16):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 通过（第 {attempt + 1} 次尝试）")
                return True
        print(f"⚠️ 第 {attempt + 1} 次未通过")
    print("❌ Turnstile 6 次均失败")
    return False

def login(sb) -> bool:
    global _LOGIN_METHOD
    _LOGIN_METHOD = "邮箱密码"
    print(f"🌐 打开登录页面: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(6)

    print("⏳ 等待 Cloudflare 验证通过...")
    for i in range(30):
        if 'input[name="email"]' in (sb.get_page_source() or "").lower():
            print(f"✅ Cloudflare 验证通过（{i+1}s）")
            break
        time.sleep(1)

    try:
        sb.wait_for_element('input[name="email"]', timeout=15)
    except:
        try:
            sb.wait_for_element('input[name="Email"]', timeout=5)
        except:
            print("❌ 登录表单加载失败")
            sb.save_screenshot("login_load_fail.png")
            send_tg_alert("❌", "登录表单加载失败", photo_path="login_load_fail.png")
            return False

    print("🍪 关闭可能的 Cookie 弹窗...")
    try:
        for btn in sb.find_elements("button"):
            if "Accept" in (btn.text or ""):
                btn.click()
                time.sleep(0.5)
                break
    except:
        pass

    js_fill_input(sb, 'input[name="email"]', EMAIL)
    time.sleep(0.3)
    js_fill_input(sb, 'input[name="password"]', PASSWORD)
    time.sleep(1)

    print("⏳ 等待 Turnstile...")
    ts_found = any(sb.execute_script(_EXISTS_JS) for _ in range(10) if not time.sleep(1))
    if ts_found and not handle_turnstile(sb):
        print("❌ 登录界面的 Turnstile 验证失败")
        sb.save_screenshot("login_turnstile_fail.png")
        send_tg_alert("❌", "Turnstile 验证失败", photo_path="login_turnstile_fail.png")
        return False

    sb.press_keys('input[name="password"]', '\n')
    print("⏳ 等待登录跳转...")
    for _ in range(12):
        time.sleep(1)
        cur_url = sb.get_current_url().split('?')[0].lower()
        title = sb.get_title() or ""
        if cur_url.startswith(f"{BASE_URL}/dashboard") or "Dashboard | KataBump" in title:
            break

    cur_url = sb.get_current_url().split('?')[0].lower()
    title = sb.get_title() or ""
    if cur_url.startswith(f"{BASE_URL}/dashboard") or "Dashboard | KataBump" in title:
        print("✅ 邮箱登录成功")
        return True
    print("❌ 邮箱登录失败")
    sb.save_screenshot("login_failed.png")
    send_tg_alert("❌", "邮箱登录失败", photo_path="login_failed.png")
    return False

def _read_alert(sb):
    try:
        return (sb.find_element("div.alert", timeout=4).text or "").strip()
    except:
        return ""

def _goto_server_detail(sb) -> bool:
    print("\n🖥️ 正在进入服务器续期页...")
    time.sleep(5)
    alert = _read_alert(sb)
    if alert and "can't renew" in alert.lower():
        print(f"ℹ️ 提示: {alert}")
        send_tg_alert("ℹ️", "未到续期时间", alert)
        return False

    selectors = ['a[href*="/servers/edit?id="]', 'td a[href*="/servers/edit"]', 'table a[href*="/servers/edit"]', 'table td a']
    see_link = None
    for sel in selectors:
        try:
            see_link = sb.find_element(sel, timeout=8)
            break
        except:
            continue
    if not see_link:
        for a in sb.find_elements("a"):
            if (a.text or "").strip().lower() == "see":
                see_link = a
                break
    if not see_link:
        print("❌ 未找到 'See' 链接")
        sb.save_screenshot("servers_page_fail.png")
        send_tg_alert("❌", "未找到 See 链接", photo_path="servers_page_fail.png")
        return False

    see_link.click()
    time.sleep(5)
    return True

def _open_renew_modal(sb) -> bool:
    print("\n🔄 查找 Renew 按钮...")
    try:
        renew_btn = sb.find_element('button[data-bs-target="#renew-modal"]', timeout=10)
    except:
        try:
            renew_btn = sb.find_element('button.btn.btn-outline-primary', timeout=5)
        except:
            print("❌ 未找到 Renew 按钮")
            sb.save_screenshot("renew_button_missing.png")
            send_tg_alert("❌", "未找到 Renew 按钮", photo_path="renew_button_missing.png")
            return False

    # 修复：不使用 arguments[0] 传递元素，直接用选择器滚动
    try:
        sb.execute_script(
            'document.querySelector(\'button[data-bs-target="#renew-modal"]\').scrollIntoView({behavior:"smooth",block:"center"});'
        )
    except:
        # 如果上面的选择器失败，尝试备用选择器
        try:
            sb.execute_script(
                'document.querySelector(\'button.btn.btn-outline-primary\').scrollIntoView({behavior:"smooth",block:"center"});'
            )
        except:
            pass  # 滚动失败不致命

    time.sleep(0.8)
    renew_btn.click()
    time.sleep(3)
    try:
        sb.find_element('div.modal.show', timeout=5)
        print("✅ Renew 模态框已弹出")
        return True
    except:
        print("⚠️ 模态框未弹出")
        sb.save_screenshot("modal_not_shown.png")
        send_tg_alert("❌", "续期弹窗未出现", photo_path="modal_not_shown.png")
        return False

def _solve_altcha(sb) -> bool:
    print("\n🔐 处理 ALTCHA...")
    time.sleep(2)
    if sb.execute_script(_ALTCHA_SOLVED_JS):
        print("✅ ALTCHA 已通过")
        return True
    coords = None
    try:
        coords = sb.execute_script(_ALTCHA_EXPAND_JS)
    except:
        pass
    for attempt in range(3):
        if sb.execute_script(_ALTCHA_SOLVED_JS):
            return True
        if coords:
            try:
                wi = sb.execute_script(_WININFO_JS)
                bar = wi["oh"] - wi["ih"]
                ax = coords["cx"] + wi["sx"]
                ay = coords["cy"] + wi["sy"] + bar
                print(f"🖱️ ALTCHA 点击 ({ax}, {ay})")
                _xdotool_click(ax, ay)
            except:
                pass
        try:
            for iframe in sb.find_elements('div.modal.show iframe'):
                iframe.click()
        except:
            pass
        sb.execute_script("""
            (function(){
                var m = document.querySelector('div.modal.show');
                if (!m) return;
                m.querySelectorAll('iframe').forEach(f => f.click());
                m.querySelectorAll('label').forEach(l => { if(/robot|captcha|verify/i.test(l.textContent)) l.click(); });
                m.querySelectorAll('input[type="checkbox"]').forEach(c => { if(!c.disabled) c.click(); });
            })()
        """)
        for _ in range(6):
            time.sleep(1)
            if sb.execute_script(_ALTCHA_SOLVED_JS):
                return True
        print(f"⚠️ 第 {attempt+1} 轮未通过")
        try:
            coords = sb.execute_script(_ALTCHA_EXPAND_JS)
        except:
            pass
    print("❌ ALTCHA 3 轮均失败")
    sb.save_screenshot("altcha_fail.png")
    send_tg_alert("❌", "ALTCHA 验证失败", photo_path="altcha_fail.png")
    return False

def _submit_renew(sb):
    print("🖱️ 点击 Renew 提交...")
    try:
        sb.find_element('div.modal.show button.btn-primary', timeout=5).click()
    except:
        sb.execute_script("""
            var m = document.querySelector('div.modal.show');
            if (m) m.querySelectorAll('button').forEach(b => { if(/renew/i.test(b.textContent)) b.click(); });
        """)
    time.sleep(3)

def _check_renew_result(sb):
    print("\n📋 检查续期结果...")
    alert = _read_alert(sb)
    if not alert:
        time.sleep(3)
        alert = _read_alert(sb)
    if alert:
        print(f"📩 页面提示: {alert}")
        low = alert.lower()
        if "can't renew" in low or "unable" in low:
            send_tg_alert("⏳", "未到续期时间", alert)
        elif any(kw in low for kw in ("renewed", "success", "extended")):
            send_tg_alert("✅", "续期成功", alert)
        else:
            send_tg_alert("ℹ️", "续期操作已执行", alert)
    else:
        sb.save_screenshot("renew_result_unknown.png")
        send_tg_alert("ℹ️", "续期操作已执行", "无明确提示", "renew_result_unknown.png")

def renew_server(sb):
    print("\n" + "#" * 25)
    print("  开始自动续期流程")
    print("#" * 25)
    if not _goto_server_detail(sb):
        return
    if not _open_renew_modal(sb):
        return
    if not _solve_altcha(sb):
        return
    _submit_renew(sb)
    _check_renew_result(sb)

# ===================== 主入口 =====================
def main():
    global _LOGIN_METHOD
    print("#" * 25)
    print("   katabump 自动登录续期（支持 Discord 备用）")
    print("#" * 25)

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        print(f"🔗 挂载代理: {proxy_str}")
        sb_kwargs["proxy"] = proxy_str
    else:
        print("🌐 直连访问")

    with SB(**sb_kwargs) as sb:
        try:
            sb.open("https://api.ip.sb/ip")
            print(f"📍 当前出口IP: {sb.get_text('body')}")
        except:
            pass

        login_ok = False

        # 1. 优先 Discord 登录（如果配置了 DISCORD_TOKEN）
        if DC_TOKEN:
            if do_discord_login(sb):
                login_ok = True
                print("✅ Discord 登录成功，跳过邮箱登录")
            else:
                print("⚠️ Discord 登录失败，回退到邮箱登录...")

        # 2. 邮箱密码登录（默认或回退）
        if not login_ok:
            _LOGIN_METHOD = "邮箱密码"
            if login(sb):
                login_ok = True
            else:
                print("\n❌ 登录失败，终止操作")
                return

        # 3. 执行续期
        renew_server(sb)

if __name__ == "__main__":
    main()
