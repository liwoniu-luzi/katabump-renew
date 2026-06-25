## 🚀 katabump 自动续期（GitHub Actions）

这是一个基于 GitHub Actions 的自动化脚本，用于定时登录自动续期 katabump 应用。

━━━━━━━━━━━━━━━━━━━━━━

🔐 Secrets 配置说明

| Secret 名称         | 是否必填 | 说明                                              |
|---------------------|----------|---------------------------------------------------|
| KATABUMP_EMAIL     | ✅ 必填  | katabump 登录邮箱                                    |
| KATABUMP_PASSWORD  | ✅ 必填  | katabump 登录密码                                    | 
| NODE_LINK          | ❌ 可选  | 代理链接（需包含协议，如 socks5:// vless:// hysteria2://)|
| TG_BOT_TOKEN       | ❌ 可选  | Telegram Bot Token（用于发送通知）                     |
| TG_CHAT_ID         | ❌ 可选  | Telegram Chat ID（接收通知的用户或群组 ID）              |

━━━━━━━━━━━━━━━━━━━━━━

📌 示例填写格式（复制下面内容，分开添加）：
KATABUMP_EMAIL=xxxx@gmail.com
KATABUMP_PASSWORD=xxxxx
NODE_LINK=socks5://user:pass@123.456.789:1234  
TG_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz  
TG_CHAT_ID=123456789  

━━━━━━━━━━━━━━━━━━━━━━
