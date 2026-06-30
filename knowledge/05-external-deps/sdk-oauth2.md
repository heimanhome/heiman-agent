# OAuth2 认证依赖

## L1：它是什么

Heiman Agent 使用 OAuth2 协议与海曼云平台进行认证。OAuth2 是一种授权框架，允许应用程序在不获取用户凭证的情况下访问受保护的资源。

**认证流程**

1. 用户通过浏览器访问海曼 OAuth2 授权页面
2. 用户登录并授权 Heiman Agent 访问其设备数据
3. 海曼云重定向到回调 URL，携带授权码
4. Heiman Agent 使用授权码换取 access_token 和 refresh_token
5. 使用 access_token 访问海曼云 API
6. access_token 过期时，使用 refresh_token 刷新

**OAuth2 端点**

| 端点 | URL | 用途 |
|------|-----|------|
| 授权端点 | `https://spfile.heiman.cn/applogin/sso.html` | 用户授权 |
| 令牌端点 | `https://spapi.heiman.cn/api-auth/token` | 获取/刷新令牌 |
| 重定向 URI | `http://127.0.0.1:1912` | 回调地址 |

---

## L2：我们怎么用

### 配置

OAuth2 配置在 `.env` 文件中：

```env
CLIENT_ID=Wn1Y0y14x232MQdJ
CLIENT_SECRET=0i0JzQmKdCNGEnmW1Ga8Gk3WtBrTCWAw
API_URL=https://spapi.heiman.cn
AUTHORIZE_URL=https://spfile.heiman.cn/applogin/sso.html
REDIRECT_URI=http://127.0.0.1:1912
```

### 认证路由

认证路由定义在 `router/auth_router.py`：

- `GET /api/auth/login`：生成授权 URL
- `GET /api/auth/heiman_redirect`：处理授权回调
- `GET /api/auth/token`：获取当前令牌
- `POST /api/auth/refresh`：刷新令牌

### 令牌管理

令牌存储在 SQLite 数据库的 `tokens` 表中，包含：

- `access_token`：访问令牌，有效期 1 小时
- `refresh_token`：刷新令牌，用于获取新的 access_token
- `expires_at`：令牌过期时间
- `created_at`：创建时间

### 集成约束

- **client_id/client_secret**：必须从海曼云平台获取，未配置时无法进行 OAuth2 认证
- **redirect_uri**：必须与海曼云平台配置的回调地址一致，否则授权会失败
- **令牌过期**：access_token 有效期为 1 小时，过期后需要使用 refresh_token 刷新
- **网络依赖**：令牌获取和刷新需要网络连接，网络断开时认证会失败

### 出问题找谁

OAuth2 认证由海曼云平台提供，遇到认证问题（授权失败、令牌过期、回调异常）需检查：

1. `CLIENT_ID` 和 `CLIENT_SECRET` 是否正确
2. `REDIRECT_URI` 是否与海曼云平台配置一致
3. 网络连接是否正常
4. 查看日志获取详细错误信息