---
title: 自建 SearXNG：属于你的私有搜索引擎
date: 2026-06-11T11:50:00-04:00
description: 使用 Docker 部署 SearXNG，再通过 Tailscale 的 HTTPS 入口访问自己的搜索引擎。
authors: [donny]
images: [searxng-wordmark.svg]
categories: [自托管]
tags: [SearXNG, Docker, Tailscale, Privacy]
translation_notice: en
---

每次使用 Google 搜索，你的查询都可能被记录、用于构建画像，并关联到你在不同设备上的身份。久而久之，这些记录会勾勒出你的兴趣、健康关注、政治倾向等信息，而它们都保存在别人的服务器上。

[SearXNG](https://github.com/searxng/searxng) 是一个免费、开源的**元搜索引擎**。它不维护自己的搜索索引，而是把查询转发给多个搜索引擎（Google、Bing、DuckDuckGo、Wikipedia 等），去除跟踪信息，再把结果汇总给你。上游搜索引擎看到的是来自你服务器的请求。

自托管 SearXNG 可以带来：

- **隐私**——没有搜索画像、过滤气泡和广告。
- **控制权**——自己选择搜索引擎、结果排序方式，以及谁能访问实例。
- **结果质量**——汇总多个引擎的结果，往往比单一来源更好。
- **避免厂商锁定**——自己掌握搜索服务，不必受制于服务关闭、体验恶化或收购。

本文介绍如何用 Docker 部署 SearXNG，先验证它能正常运行，再通过 [Tailscale](https://tailscale.com/) 安全地开放访问，让自己的设备都能使用。（参考视频：[Replace Google with SearXNG - a privacy respecting, self-hosted search engine](https://www.youtube.com/watch?v=cg9d87PuanE)）

---

## 准备工作：在 Linux 上安装 Docker

首先，在 Linux 机器上安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
```

安装后，将当前用户加入 Docker 用户组，避免每次都需要输入 `sudo`：

```bash
sudo usermod -aG docker $USER
newgrp docker
```

完整的安装后配置步骤见 [Docker 官方文档](https://docs.docker.com/engine/install/linux-postinstall/)。

---

## 安装 Tailscale

要在局域网之外访问 SearXNG，请安装 [Tailscale](https://tailscale.com/)，并将机器连接到自己的 tailnet：

```bash
sudo tailscale up --ssh
```

稍后会用 `tailscale serve` 为 SearXNG 提供 HTTPS 访问。先让搜索服务运行起来。

---

## 使用 Docker 部署 SearXNG

参考 [SearXNG 官方 Docker 安装指南](https://docs.searxng.org/admin/installation-docker.html#installation-container)。

### 1. 创建环境

```bash
mkdir -p ./searxng/core-config/
cd ./searxng/

curl -fsSL \
    -O https://raw.githubusercontent.com/searxng/searxng/master/container/docker-compose.yml \
    -O https://raw.githubusercontent.com/searxng/searxng/master/container/.env.example
```

### 2. 配置环境

复制并编辑 `.env` 文件：

```bash
cp -i .env.example .env
nano .env
```

至少需要设置用于 cookie 签名的密钥。用下面的命令生成：

```bash
openssl rand -hex 32
```

将输出粘贴到 `.env` 中：

```text
SEARXNG_SECRET="<paste the hex string here>"
```

### 3. 启动服务

```bash
docker compose up -d
```

### 4. 验证服务正常运行

继续之前，先检查 SearXNG 是否真的运行起来了。打开浏览器，通过服务器的 Tailscale 域名和 8080 端口访问 HTTP 服务：

```text
http://my-server.tailabcd1234.ts.net:8080
```

应该能看到 SearXNG 搜索页面。尝试搜索一次，确认能够返回结果。

如果有问题，检查容器日志：

```bash
docker compose logs -f
```

常见问题：

- **端口冲突**——如果 8080 已被占用，修改 `docker-compose.yml` 中的端口映射，例如改为 `8081:8080`。
- **容器无法启动**——运行 `docker compose ps` 查看容器状态，用 `docker compose logs` 查看报错。
- **没有搜索结果**——部分引擎可能暂时屏蔽了请求，可以在 `core-config/settings.yml` 中启用或禁用相应引擎。

停止服务：

```bash
docker compose down
```

---

## 通过 Tailscale 提供访问

确认 SearXNG 正常运行后，就可以在 tailnet 中通过 HTTPS 访问它。无需开放公网端口，Tailscale 会处理 TLS 和访问控制。

```bash
sudo tailscale serve --bg 8080
```

它会创建类似这样的 HTTPS 地址：

```text
https://my-server.tailabcd1234.ts.net
```

其中：

- `my-server` 是这台机器的 Tailscale **机器名**，可以在运行 `tailscale up` 时设置，或稍后在 [Tailscale 管理控制台](https://login.tailscale.com/admin/machines)修改。
- `tailabcd1234.ts.net` 是你账户专属的 **tailnet MagicDNS 域名**。

机器名和 tailnet 域名都可以随时在 Tailscale 管理控制台中修改。

接下来，让 `.env` 中的 `SEARXNG_BASE_URL` 与该地址一致：

```text
SEARXNG_BASE_URL="https://my-server.tailabcd1234.ts.net"
```

重启 SearXNG，使修改生效：

```bash
docker compose down && docker compose up -d
```

在 tailnet 中的任意设备上访问这个 `https://` 地址，确认可以使用。

---

## 自定义 SearXNG 设置

编辑 `core-config/settings.yml`，按需调整配置。[官方设置文档](https://docs.searxng.org/admin/settings/index.html)介绍了全部选项，以下几项尤其值得了解：

- **`engines`**——启用、禁用搜索引擎，或调整其顺序，例如 Google、Bing、DuckDuckGo 等。
- **`server.limiter`**——通过限流防止实例被滥用，分享给他人使用时尤其有用。
- **`server.image_proxy`**——通过服务器代理图片结果，避免上游 CDN 直接看到你的 IP。
- **`ui.theme`**——选择主题，例如 `simple`、`ocavue` 等。
- **`search.default_lang`**——设置搜索结果的默认语言。

修改后重启：

```bash
docker compose restart
```

---

## 将 SearXNG 设为 Chrome 默认搜索引擎

实例运行后，就可以将它设为 Chrome 的默认搜索引擎。具体步骤见[这篇指南](https://blog.ktz.me/replacing-google-with-searxng-as-the-default-in-chrome/)。

---

## 回顾

| 步骤 | 作用 |
| --- | --- |
| 安装 Docker | 为 SearXNG 提供容器运行环境 |
| 安装 Tailscale | 建立安全网络，无需开放公网端口 |
| 部署 SearXNG | 用 Docker Compose 运行私有元搜索引擎 |
| 验证服务 | 开放访问前先确认服务正常 |
| Tailscale serve | 在 tailnet 中提供 HTTPS 入口 |
| 自定义设置 | 调整引擎、限流、主题与语言 |
| 配置浏览器 | 将 SearXNG 设为默认搜索引擎 |

至此，你就拥有了由自己掌控的私有搜索引擎，不必再把每次查询都直接交给 Google。

## 延伸探索

- **[SearXNG on GitHub](https://github.com/searxng/searxng)**——源码、问题反馈与贡献入口。
- **[Local Deep Research](https://github.com/LearningCircuit/local-deep-research)**——开源研究工具，底层使用 SearXNG 检索并综合网络信息。
