# Katabump Server Auto-Renewal

## 🚀 GitHub Actions 云端运行 (推荐)

🔐 Secrets 配置

| Secret 名称         | 是否必填 | 说明                                              |
|---------------------|----------|---------------------------------------------------|
| USERS_JSON      | ✅ 必填  | Katabump账号密码，json格式                             |
| PROXY_NODE      | ❌ 可选  | 代理链接（需包含协议，如：socks5://）     |
| TG_BOT_TOKEN        | ❌ 可选  | Telegram Bot Token（用于发送通知）                |
| TG_CHAT_ID          | ❌ 可选  | Telegram Chat ID（接收通知的用户或群组 ID）        |

━━━━━━━━━━━━━━━━━━━━━━

1. **Fork 本仓库** 到你的 GitHub 账号。
2. 进入你的仓库，点击 **Settings** -> **Secrets and variables** -> **Actions**。
3. 点击 **New repository secret**，添加一个名为 `USERS_JSON` 的 Secret。
4. **Value** 的格式必须是 JSON 数组（请尽量压缩为一行）：
   ```json
   [{"username": "your_email@example.com", "password": "your_password"}]
   ```
5. **(可选) 配置代理**:

  支持两种代理方式：

  **全协议代理 (推荐)**
  添加名为 `PROXY_NODE` 的 Secret，支持 vmess、vless、hy2、tuic、socks5 等所有主流协议。
  - **格式示例**:
    - vmess: `vmess://base64EncodedJSON`
    - vless: `vless://uuid@host:port?security=tls&type=ws&...#name`
    - hy2: `hy2://password@host:port?sni=xxx`
    - socks5: `socks5://user:pass@host:port`

6. **(可选) Telegram 消息推送**:
   如果你希望在续期成功、失败或跳过时收到 Telegram 通知（包含截图），请配置以下 Secret：
   - `TG_BOT_TOKEN`: 你的 Telegram Bot Token (从 @BotFather 获取)。
   - `TG_CHAT_ID`: 你的 Chat ID (用户 ID 或群组 ID)。
   > 如果未配置，脚本将跳过发送通知。

### 4. 运行结果与截图

- **运行日志**: 在 Actions 中的 `Run Renew Script` 步骤查看。
- **截图留存**: 每次运行（无论成功与否），通过 `Upload Screenshots` 步骤自动上传截图。
  - 你可以在 Workflow 运行详情页的 **Artifacts** 区域下载 `screenshots` 压缩包。
  - 每个账号对应一张截图（`username.png`），方便确认状态。

5. 保存后，进入 **Actions** 页面，启用 Workflow。它会在每隔3天运行一次 北京时间 10:00 (UTC 02:00)，可在工作流文件 [renew.yml](.github/workflows/renew.yml) 中修改运行时间
6. 你也可以手动点击 "Run workflow" 立即测试。
7. **随机延迟**: 定时任务触发时，脚本会随机延迟 0-3 小时后执行，防止被目标站识别为自动化。手动触发时不会有延迟，立即执行。

---
