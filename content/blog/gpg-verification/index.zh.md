---
title: 验证开源软件包：从校验和到 GPG 签名
date: 2026-07-17T10:45:00-04:00
description: 用校验和、GPG 签名和可信的密钥指纹，验证开源软件包的完整性与来源。
authors: [donny]
categories: [安全]
tags: [GPG, Security, DevOps]
images: [gpg-verification.jpg]
translation_notice: en
---

从开源项目下载二进制文件或源码压缩包时，常见的做法是“检查哈希”。这能确认文件没有在传输途中损坏，却不能证明文件确实出自合法的维护者。

对于关注安全的用户和开发者，验证应当是一条完整的流程：从**完整性**（文件是否发生变化？）走向**真实性**（是谁签署了这个文件？）。

## 基础：用校验和验证完整性

校验和（哈希）是第一道防线，可以检测意外损坏或简单的篡改。

### 常用命令

不同操作系统使用不同的工具来计算下载文件的哈希。

**Linux（GNU Coreutils）：**

```bash
sha256sum package.tar.gz
```

**macOS：**

```bash
shasum -a 256 package.tar.gz
```

### 局限

如果攻击者入侵了下载服务器，就可以同时替换二进制文件和 `sha256sum.txt`。两者的哈希仍然匹配，但你验证的已经是恶意文件。这就是需要密码学签名的原因。

---

## 关键：用 GPG 验证真实性

GPG 签名能证明某个私钥的持有者签署了文件。即使服务器被入侵，没有私钥的攻击者也无法伪造签名。

### 逐步验证

#### A. 获取公钥

验证签名需要维护者的公钥。**注意：** 从提供二进制文件的同一台服务器下载公钥存在风险。更稳妥的方式是通过独立的可信渠道获取密钥文件，然后导入。

```bash
# Import from a key file (recommended)
gpg --import developer_key.asc

# Import from a keyserver (fallback)
gpg --keyserver hkps://keys.openpgp.org --recv-keys <KEY_ID>
```

#### B. 验证签名

软件包通常附有独立签名文件，例如 ASCII 文本格式的 `package.tar.gz.asc`，或二进制格式的 `package.tar.gz.sig`。

```bash
# GPG often finds the data file automatically when names follow the convention
gpg --verify package.tar.gz.asc

# Otherwise, specify both files
gpg --verify package.tar.gz.asc package.tar.gz
```

### 如何解读结果

你可能看到这样的输出：

```text
gpg: Good signature from "Developer Name <email@example.com>"
gpg: WARNING: This key is not certified with a trusted signature!
```

**关键提醒：**
“Good signature”只说明签名来自与你导入的公钥相对应的私钥。如果你导入的是一把冒充开发者的恶意密钥，签名仍然会显示为“Good”。

**只有通过独立渠道核对了密钥指纹，“Good signature”才足以作为判断依据。** 下一节介绍这个步骤。

---

## 信任缺口：确认密钥

PGP 最困难的部分是“带外验证”：通过独立渠道确认密钥。要真正建立信任，就应核对密钥指纹。

1. 在项目官网或开发者可信的个人资料页找到指纹。
2. 将它与导入的密钥进行比较：

```bash
gpg --fingerprint <KEY_ID>
```

如果指纹一致，就能确认拿到的是对应的公钥。

---

## 实际示例

### 示例一：LibreWolf（bsys6）

LibreWolf 提供带有具体版本号的二进制包，例如 `librewolf-152.0.6-1-linux-x86_64-package.tar.xz`。

**操作流程：**

1. 下载二进制包和对应的签名文件。
2. 从 LibreWolf 官方安全渠道获取公钥。
3. 执行验证：

```bash
# 1. Check the hash first (integrity)
sha256sum librewolf-152.0.6-1-linux-x86_64-package.tar.xz
# Compare with the per-file SHA256 table on repo.librewolf.net

# 2. Import the developer's key
gpg --keyserver hkps://keys.openpgp.org --recv-keys <LibreWolf_Dev_Key_ID>

# 3. Verify authenticity; LibreWolf uses binary .sig signatures
gpg --verify librewolf-152.0.6-1-linux-x86_64-package.tar.xz.sig librewolf-152.0.6-1-linux-x86_64-package.tar.xz
```

### 示例二：Restic

Restic 为发布版本提供签名，帮助确认备份工具本身没有被篡改。

**操作流程：**

1. 下载二进制文件（例如 `restic_0.19.1_linux_amd64.bz2`）、`SHA256SUMS` 和 `SHA256SUMS.asc`。
2. 导入 Restic 维护者的公钥，Key ID 为 `91A6868BD3F7A907`。
3. 执行验证：

```bash
# 1. Verify that fd0 signed the checksum file (authenticity)
gpg --verify SHA256SUMS.asc SHA256SUMS

# 2. Compare the binary's hash with the signed checksum (integrity)
sha256sum restic_0.19.1_linux_amd64.bz2
# Compare with the hash listed in SHA256SUMS
```

Restic 也会签署 Git 标签，可以直接验证标签签名：

```bash
# Verify the annotated tag object's signature
git tag -v v0.19.1
```

*注：签名有效时，GPG 会显示“Good signature from fd0 (Alexander Neumann)”。务必与 Restic 官方文档核对 Key ID（`91A6868BD3F7A907`），避免使用冒充的密钥进行验证。*

---

## 开发者速查表

| 目标 | 命令 | 说明 |
| --- | --- | --- |
| **检查 SHA256** | `sha256sum <file>` | macOS 使用 `shasum -a 256` |
| **导入密钥** | `gpg --import <file>` 或 `gpg --recv-keys <ID>` | 可使用 `hkps://keys.openpgp.org` |
| **验证签名** | `gpg --verify <sig> [file]` | `.asc` 为文本格式，`.sig` 为二进制格式 |
| **检查指纹** | `gpg --fingerprint <ID>` | 与官方来源核对 |
| **导出公钥** | `gpg --export -a <ID>` | 用于分享自己的公钥 |
